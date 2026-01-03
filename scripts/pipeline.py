#!/usr/bin/env python3
"""
Executive Compensation Extraction Pipeline

Usage:
    python scripts/pipeline.py          # Show status only
    python scripts/pipeline.py 100       # Process up to 100 documents total
"""

import asyncio
import json
import random
import sys
from pathlib import Path

# =============================================================================
# CONFIGURATION (edit these values directly)
# =============================================================================

SEED = 42424242
VLM_BASE_URL = "http://localhost:8000/v1"
VLM_MODEL = "Qwen/Qwen3-VL-32B-Instruct"

MINERU_MAX_CONCURRENT = 8
DOC_MAX_CONCURRENT = 16

# Set to True to process pending documents instead of adding new ones
CONTINUE_MODE = False

# Filter by years (empty list = all years)
# Examples: [2020, 2021, 2022] or range(2015, 2023)
YEARS_FILTER = [2020]  # e.g., [2020, 2021] or list(range(2005, 2010))

# =============================================================================
# PATHS
# =============================================================================

BASE_PATH = Path(__file__).parent.parent.resolve()
PDF_PATH = BASE_PATH / "pdfs"
OUTPUT_PATH = BASE_PATH / "output"
DATA_PATH = BASE_PATH / "data/DEF14A_all.jsonl"
HF_DATASET = "pierjoe/SEC-DEF14A-2005-2022"

# =============================================================================
# MAIN PIPELINE
# =============================================================================

async def main():
    # Imports
    sys.path.insert(0, str(BASE_PATH))
    from datasets import load_dataset
    from openai import AsyncOpenAI
    from tqdm import tqdm
    from src import (
        get_doc_id,
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
        Tracker,
    )
    
    # Initialize tracker
    tracker = Tracker(BASE_PATH)
    
    # Parse command line
    # No args and no year filter = just show stats
    if len(sys.argv) == 1 and not YEARS_FILTER:
        tracker.print_stats()
        return
    
    target_size = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        target_size = int(sys.argv[1])
    
    # Create directories
    PDF_PATH.mkdir(exist_ok=True)
    OUTPUT_PATH.mkdir(exist_ok=True)
    
    print("="*60)
    print("EXECUTIVE COMPENSATION EXTRACTION PIPELINE")
    print("="*60)
    
    # Show current status
    tracker.print_stats()
    
    # Load dataset
    print("\n[1/6] Loading dataset...")
    if DATA_PATH.exists():
        dataset = load_dataset("json", data_files=str(DATA_PATH))
        all_docs = dataset["train"]
        print(f"✓ Loaded from local file")
    else:
        all_docs = load_dataset(HF_DATASET, split="train")
        print(f"✓ Loaded from HuggingFace")
    
    # Build doc_id -> doc mapping
    doc_id_to_doc = {get_doc_id(doc): doc for doc in all_docs}
    
    # Filter by years if specified
    if YEARS_FILTER:
        years_set = set(YEARS_FILTER)
        before_filter = len(doc_id_to_doc)
        doc_id_to_doc = {k: v for k, v in doc_id_to_doc.items() if v.get('year') in years_set}
        print(f"\n[YEAR FILTER] {before_filter:,} → {len(doc_id_to_doc):,} documents (years: {sorted(years_set)})")
    
    # Determine what to process
    tracked_ids = set(tracker.get_all_doc_ids())
    
    if CONTINUE_MODE:
        # Continue: process pending documents (need MinerU or need classification)
        pending_mineru = set(tracker.get_pending("mineru_done"))
        pending_classify = set(tracker.get_pending("classified"))
        doc_ids_to_process = list(pending_mineru | pending_classify)
        print(f"\n[CONTINUE MODE] Processing {len(doc_ids_to_process)} pending documents")
    elif YEARS_FILTER and not target_size:
        # Year filter without target: process ALL documents from those years
        all_doc_ids = list(doc_id_to_doc.keys())
        untracked = [d for d in all_doc_ids if d not in tracked_ids]
        doc_ids_to_process = untracked
        print(f"\n[YEAR MODE] Processing all {len(doc_ids_to_process)} untracked documents from {sorted(set(YEARS_FILTER))}")
    elif target_size:
        # Target size: keep all tracked + add new ones to reach target
        if target_size <= len(tracked_ids):
            print(f"\n✓ Already have {len(tracked_ids)} documents, target is {target_size}")
            doc_ids_to_process = []
        else:
            # Add new documents
            new_needed = target_size - len(tracked_ids)
            all_doc_ids = list(doc_id_to_doc.keys())
            untracked = [d for d in all_doc_ids if d not in tracked_ids]
            random.seed(SEED)
            random.shuffle(untracked)
            new_doc_ids = untracked[:new_needed]
            doc_ids_to_process = new_doc_ids
            print(f"\n[NEW DOCS] Adding {len(new_doc_ids)} new documents (target: {target_size})")
    else:
        doc_ids_to_process = []
    
    if not doc_ids_to_process:
        print("\nNothing to process.")
        return
    
    # Get docs to process
    docs_to_process = [doc_id_to_doc[d] for d in doc_ids_to_process if d in doc_id_to_doc]
    
    # Initialize VLM client
    client = AsyncOpenAI(base_url=VLM_BASE_URL, api_key="dummy")
    
    # =========================================================================
    # PHASE 1: Convert HTML to PDF
    # =========================================================================
    print("\n[2/6] Converting HTML to PDF...")
    convert_docs_to_pdf(docs_to_process, base_path=BASE_PATH)
    
    # Update tracker for new documents
    for doc in docs_to_process:
        doc_id = get_doc_id(doc)
        output_dir = OUTPUT_PATH / doc_id
        meta_path = output_dir / "metadata.json"
        pdf_path = PDF_PATH / f"{doc_id}.pdf"
        
        # If PDF exists but output folder doesn't, recreate it
        if pdf_path.exists() and not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
            # Create metadata
            text_fields = {'text'}
            metadata = {k: v for k, v in doc.items() if k not in text_fields}
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2)
        
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            tracker.add_document(doc_id, meta)
            tracker.set_phase(doc_id, "pdf_created")
            # Mark funds immediately
            if meta.get("sic") in ("NULL", None):
                tracker.set_status(doc_id, "fund")
    tracker.save()
    
    # =========================================================================
    # PHASE 2: MinerU Processing
    # =========================================================================
    print("\n[3/6] Processing PDFs with MinerU...")
    
    # Get docs that need MinerU (non-funds without mineru_done)
    funds_skipped = []
    need_mineru = []
    for d in doc_ids_to_process:
        doc = tracker.get_document(d)
        if not doc:
            continue
        if tracker.has_phase(d, "mineru_done"):
            continue
        if doc.get("sic") in ("NULL", None):
            funds_skipped.append(d)
        else:
            need_mineru.append(d)
    
    if funds_skipped:
        print(f"  Skipping {len(funds_skipped)} funds (no executive compensation)")
    
    if need_mineru:
        failed, success = process_pdfs_with_mineru(
            base_path=BASE_PATH, 
            max_concurrent=MINERU_MAX_CONCURRENT, 
            doc_ids=need_mineru
        )
        
        # Update tracker
        for doc_id in success:
            tracker.set_phase(doc_id, "mineru_done")
        tracker.save()
        print(f"✓ MinerU: {len(success)} successful, {len(failed)} failed")
    else:
        print("✓ No documents need MinerU processing")
    
    # =========================================================================
    # PHASE 3: Fix orphan images
    # =========================================================================
    print("\n[4/6] Fixing orphan images...")
    fix_stats = fix_all_orphan_images(OUTPUT_PATH)
    print(f"✓ Fixed {fix_stats['total_fixed']} tables in {fix_stats['docs_fixed']} documents")
    
    # =========================================================================
    # PHASE 4: Extract tables
    # =========================================================================
    print("\n[5/6] Extracting tables from MinerU output...")
    all_tables, extraction_stats = extract_tables_from_output(
        output_path=OUTPUT_PATH, 
        save_path=str(BASE_PATH / "all_tables.json")
    )
    print(f"✓ Extracted {len(all_tables)} tables from {len(extraction_stats['with_tables'])} documents")
    
    # =========================================================================
    # PHASE 5: Classification + Extraction
    # =========================================================================
    print("\n[6/6] Classifying tables and extracting compensation data...")
    
    # Get docs that need classification (have MinerU, not fund, not done)
    need_classify = []
    for doc_id in doc_ids_to_process:
        doc_info = tracker.get_document(doc_id)
        if not doc_info:
            continue
        if doc_info.get("sic") in ("NULL", None):
            continue  # Fund
        if not tracker.has_phase(doc_id, "mineru_done"):
            continue  # No MinerU yet
        if tracker.has_phase(doc_id, "extracted"):
            continue  # Already done
        need_classify.append(doc_id)
    
    # Also include docs with tables from extraction_stats
    doc_sources_with_tables = set(t.get('source_doc') for t in all_tables)
    need_classify = [d for d in need_classify if d in doc_sources_with_tables]
    
    print(f"Documents to classify: {len(need_classify)}")
    
    stats = {"processed": 0, "no_sct": 0, "errors": 0}
    stats_lock = asyncio.Lock()
    doc_semaphore = asyncio.Semaphore(DOC_MAX_CONCURRENT)
    
    async def process_document(doc_id: str):
        """Process a single document: classify tables, merge, extract data."""
        meta_path = OUTPUT_PATH / doc_id / "metadata.json"
        if not meta_path.exists():
            return
        with open(meta_path) as f:
            meta = json.load(f)
        
        async with doc_semaphore:
            try:
                # Classify tables
                found, all_classifications = await find_summary_compensation_in_doc(
                    doc_source=doc_id,
                    all_tables=all_tables,
                    client=client,
                    model=VLM_MODEL,
                    base_path=BASE_PATH,
                    debug=False
                )
                
                if not found:
                    save_no_sct_results(OUTPUT_PATH / doc_id, metadata=meta)
                    tracker.set_phase(doc_id, "extracted")
                    tracker.set_status(doc_id, "no_sct")
                    async with stats_lock:
                        stats["no_sct"] += 1
                    return
                
                # Merge consecutive tables
                images_base_dir = OUTPUT_PATH / doc_id / doc_id / "vlm"
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
                save_classification_results(found, OUTPUT_PATH / doc_id, metadata=meta)
                save_extraction_results(extracted, OUTPUT_PATH / doc_id, metadata=meta)
                
                # Update tracker
                sct_paths = []
                for f in found:
                    # Try different possible locations for image path
                    if "image_path" in f:
                        sct_paths.append(f["image_path"])
                    elif "table" in f and "img_path" in f["table"]:
                        sct_paths.append(f["table"]["img_path"])
                    elif "img_path" in f:
                        sct_paths.append(f["img_path"])
                
                tracker.set_phase(doc_id, "classified")
                tracker.set_phase(doc_id, "extracted")
                tracker.set_status(doc_id, "complete")
                tracker.set_sct_tables(doc_id, sct_paths)
                
                async with stats_lock:
                    stats["processed"] += 1
                
            except Exception as e:
                async with stats_lock:
                    stats["errors"] += 1
                tqdm.write(f"✗ Error {doc_id}: {e}")
    
    # Process documents
    if need_classify:
        tasks = [process_document(doc_id) for doc_id in need_classify]
        for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Processing"):
            await coro
        tracker.save()
    
    # Also mark docs with no tables as no_sct
    for doc_id in doc_ids_to_process:
        doc_info = tracker.get_document(doc_id)
        if not doc_info:
            continue
        if doc_info.get("sic") in ("NULL", None):
            continue  # Fund
        if tracker.has_phase(doc_id, "extracted"):
            continue  # Already done
        if tracker.has_phase(doc_id, "mineru_done") and doc_id not in doc_sources_with_tables:
            # Has MinerU but no tables extracted
            meta_path = OUTPUT_PATH / doc_id / "metadata.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    meta = json.load(f)
                save_no_sct_results(OUTPUT_PATH / doc_id, metadata=meta)
                tracker.set_phase(doc_id, "extracted")
                tracker.set_status(doc_id, "no_sct")
    tracker.save()
    
    # =========================================================================
    # FINAL STATUS
    # =========================================================================
    print("\n" + "="*60)
    print("PIPELINE COMPLETE")
    print("="*60)
    print(f"This run: {stats['processed']} with SCT, {stats['no_sct']} no SCT, {stats['errors']} errors")
    print()
    tracker.print_stats()


if __name__ == "__main__":
    asyncio.run(main())
