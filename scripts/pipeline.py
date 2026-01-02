#!/usr/bin/env python3
"""
Executive Compensation Extraction Pipeline

Usage:
    python scripts/pipeline.py          # Process all 150 documents
    python scripts/pipeline.py 10       # Process only 10 documents
"""

import asyncio
import json
import random
import sys
from pathlib import Path

# per vedere quali sono state mergiate

# i documenti possono essere di 3 tipi
# possono essere fondi -> non hanno SCT
# possono avere SCT
# possono non avere SCT

# =============================================================================
# CONFIGURATION - MODIFY THESE VALUES AS NEEDED
# =============================================================================

SEED = 42424242
SAMPLE_SIZE = 150  # Default, can be overridden by command line arg
DONT_SKIP = False  # If True, reprocess documents even if they have no_sct_found.json

VLM_BASE_URL = "http://localhost:8000/v1"
VLM_MODEL = "Qwen/Qwen3-VL-32B-Instruct"

MINERU_MAX_CONCURRENT = 8
DOC_MAX_CONCURRENT = 16  # Max concurrent document processing (classification + extraction)

# =============================================================================
# PATHS
# =============================================================================

BASE_PATH = Path(__file__).parent.parent.resolve()  # Go up from scripts/ to project root
PDF_PATH = BASE_PATH / "pdfs"
OUTPUT_PATH = BASE_PATH / "output"
DATA_PATH = BASE_PATH / "data/DEF14A_all.jsonl"  # Local file (optional)
HF_DATASET = "pierjoe/SEC-DEF14A-2005-2022"  # HuggingFace dataset

# =============================================================================
# MAIN PIPELINE
# =============================================================================

async def main():
    # Parse command line arg for sample size
    sample_size = SAMPLE_SIZE
    if len(sys.argv) > 1:
        try:
            sample_size = int(sys.argv[1])
            print(f"Using sample size from command line: {sample_size}")
        except ValueError:
            print(f"Invalid sample size '{sys.argv[1]}', using default {SAMPLE_SIZE}")
    
    # Imports
    from datasets import load_dataset
    from openai import AsyncOpenAI
    from tqdm import tqdm
    
    # Add project root to path for src imports
    sys.path.insert(0, str(BASE_PATH))
    from src import (
        convert_docs_to_pdf,
        process_pdfs_with_mineru,
        extract_tables_from_output,
        merge_consecutive_tables,
        find_summary_compensation_in_doc,
        extract_all_summary_compensation,
        save_classification_results,
        save_extraction_results,
        save_no_sct_results,
        fix_all_orphan_images,
    )
    
    # Create directories
    PDF_PATH.mkdir(exist_ok=True)
    OUTPUT_PATH.mkdir(exist_ok=True)
    
    print("="*60)
    print("EXECUTIVE COMPENSATION EXTRACTION PIPELINE")
    print("="*60)
    print(f"Base path: {BASE_PATH}")
    print(f"Sample size: {sample_size}")
    print(f"VLM: {VLM_MODEL}")
    print("="*60)
    
    # Load dataset
    print("\n[1/6] Loading dataset...")
    if DATA_PATH.exists():
        dataset = load_dataset("json", data_files=str(DATA_PATH))
        all_docs = dataset["train"]
        print(f"✓ Loaded from local file: {DATA_PATH}")
    else:
        all_docs = load_dataset(HF_DATASET, split="train")
        print(f"✓ Loaded from HuggingFace: {HF_DATASET}")
    
    random.seed(SEED)
    indices = random.sample(range(len(all_docs)), min(sample_size, len(all_docs)))
    docs = all_docs.select(indices)
    print(f"✓ Loaded {len(all_docs):,} documents, sampled {len(docs)}")
    
    # Initialize VLM client
    client = AsyncOpenAI(base_url=VLM_BASE_URL, api_key="dummy")
    
    # Step 1: Convert HTML to PDF
    print("\n[2/6] Converting HTML to PDF...")
    convert_docs_to_pdf(docs, base_path=BASE_PATH)
    
    # Step 2: Process PDFs with MinerU
    print("\n[3/6] Processing PDFs with MinerU...")
    failed, success = process_pdfs_with_mineru(base_path=BASE_PATH, max_concurrent=MINERU_MAX_CONCURRENT)
    print(f"✓ MinerU: {len(success)} successful, {len(failed)} failed")
    
    # Step 3: Fix orphan images
    print("\n[4/6] Fixing orphan images...")
    fix_stats = fix_all_orphan_images(OUTPUT_PATH)
    print(f"✓ Fixed {fix_stats['total_fixed']} tables in {fix_stats['docs_fixed']} documents")
    
    # Step 4: Extract tables
    print("\n[5/6] Extracting tables from MinerU output...")
    all_tables, extraction_stats = extract_tables_from_output(
        output_path=OUTPUT_PATH, 
        save_path=str(BASE_PATH / "all_tables.json")
    )
    print(f"✓ Extracted {len(all_tables)} tables from {len(extraction_stats['with_tables'])} documents")
    
    # Mark documents with 0 tables as no_sct_found (if non-fund and not already processed)
    for doc_name in extraction_stats.get('no_tables', []):
        doc_dir = OUTPUT_PATH / doc_name
        metadata_path = doc_dir / "metadata.json"
        if not metadata_path.exists():
            continue
        with open(metadata_path) as f:
            meta = json.load(f)
        # Skip funds
        if meta.get("sic") in ("NULL", None):
            continue
        # Skip if already has results
        if (doc_dir / "extraction_results.json").exists():
            continue
        if (doc_dir / "no_sct_found.json").exists():
            continue
        # Mark as no SCT (no tables from MinerU)
        save_no_sct_results(doc_dir, metadata=meta)
    
    # Step 5: Classify and extract compensation data
    print("\n[6/6] Classifying tables and extracting compensation data...")
    doc_sources = list(set(t.get('source_doc') for t in all_tables))
    
    stats = {"processed": 0, "skipped_fund": 0, "skipped_done": 0, "no_tables": 0, "errors": 0}
    stats_lock = asyncio.Lock()
    
    # Semaphore to limit concurrent document processing
    doc_semaphore = asyncio.Semaphore(DOC_MAX_CONCURRENT)
    
    async def process_document(source_doc: str):
        """Process a single document: classify tables, merge, extract data."""
        # Load metadata
        metadata_path = OUTPUT_PATH / source_doc / "metadata.json"
        if not metadata_path.exists():
            return
        with open(metadata_path) as f:
            meta = json.load(f)
        
        # Skip funds (no SIC code)
        if meta.get("sic") in ("NULL", None):
            async with stats_lock:
                stats["skipped_fund"] += 1
            return
        
        # Skip if already processed
        if (OUTPUT_PATH / source_doc / "extraction_results.json").exists():
            async with stats_lock:
                stats["skipped_done"] += 1
            return
        
        # Skip if already marked as no SCT (unless DONT_SKIP is True)
        if not DONT_SKIP and (OUTPUT_PATH / source_doc / "no_sct_found.json").exists():
            async with stats_lock:
                stats["skipped_done"] += 1
            return

        async with doc_semaphore:
            try:
                # Classify tables
                found, all_classifications = await find_summary_compensation_in_doc(
                    doc_source=source_doc,
                    all_tables=all_tables,
                    client=client,
                    model=VLM_MODEL,
                    base_path=BASE_PATH,
                    debug=False
                )
                
                if not found:
                    # Save marker indicating no SCT was found
                    save_no_sct_results(OUTPUT_PATH / source_doc, metadata=meta)
                    async with stats_lock:
                        stats["no_tables"] += 1
                    return
                
                images_base_dir = OUTPUT_PATH / source_doc / source_doc / "vlm"
                found = merge_consecutive_tables(found, images_base_dir, all_tables, all_classifications, debug=False)
                
                # Extract compensation data
                extracted = await extract_all_summary_compensation(
                    found_tables=found,
                    all_tables=all_tables,
                    client=client,
                    model=VLM_MODEL,
                    base_path=BASE_PATH,
                    metadata=meta
                )
                
                # Save results
                save_classification_results(found, OUTPUT_PATH / source_doc, metadata=meta)
                save_extraction_results(extracted, OUTPUT_PATH / source_doc, metadata=meta)
                async with stats_lock:
                    stats["processed"] += 1
                
            except Exception as e:
                async with stats_lock:
                    stats["errors"] += 1
                tqdm.write(f"✗ Error {source_doc}: {e}")
    
    # Process all documents concurrently with progress bar
    tasks = [process_document(doc) for doc in doc_sources]
    for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Processing"):
        await coro
    
    # Count totals in output folder
    total_docs = 0
    total_funds = 0
    total_with_sct = 0
    total_no_sct = 0
    total_tables = 0
    total_pending = 0  # Docs without results yet
    
    for d in OUTPUT_PATH.iterdir():
        if not d.is_dir():
            continue
        total_docs += 1
        
        # Check if fund
        meta_path = d / "metadata.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            if meta.get("sic") in ("NULL", None):
                total_funds += 1
                continue  # Funds don't count for SCT stats
        
        # Count SCT status (only for non-funds)
        if (d / "extraction_results.json").exists():
            total_with_sct += 1
            # Count tables in this doc
            class_path = d / "classification_results.json"
            if class_path.exists():
                with open(class_path) as f:
                    classification = json.load(f)
                total_tables += len(classification.get("tables", []))
        elif (d / "no_sct_found.json").exists():
            total_no_sct += 1
        else:
            total_pending += 1  # Has metadata but no results yet
    
    duplicates = total_tables - total_with_sct  # Docs with multiple tables
    
    # Print summary
    print("\n" + "="*60)
    print("PIPELINE COMPLETE")
    print("="*60)
    print(f"Processed:      {stats['processed']} (this run)")
    print(f"Total docs:     {total_docs} (in output)")
    print(f"  Funds:        {total_funds}")
    print(f"  Non-funds:    {total_docs - total_funds}")
    print(f"    With SCT:   {total_with_sct} ({total_tables} tables, {duplicates} extra)")
    print(f"    No SCT:     {total_no_sct}")
    if total_pending > 0:
        print(f"    Pending:    {total_pending}")
    print(f"Errors:         {stats['errors']}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
