#!/usr/bin/env python3
"""
Upload Executive Compensation dataset to HuggingFace Hub.

Usage:
    python to_hf.py                          # Save locally only
    python to_hf.py --push                   # Save locally and push to HF Hub
    python to_hf.py --push --repo USER/REPO  # Push to custom repo
"""

import argparse
import json
from pathlib import Path

from datasets import Dataset, Image as HFImage
from huggingface_hub import HfApi


# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_PATH = Path(__file__).parent.resolve()
OUTPUT_PATH = BASE_PATH / "output"
HF_LOCAL_PATH = BASE_PATH / "hf/execcomp-ai-sample"
DEFAULT_REPO = "pierjoe/execcomp-ai-sample"


def build_dataset(output_path: Path) -> list[dict]:
    """Build dataset records from extraction results."""
    records = []

    for doc_dir in output_path.iterdir():
        if not doc_dir.is_dir():
            continue
        
        extraction_file = doc_dir / "extraction_results.json"
        classification_file = doc_dir / "classification_results.json"
        metadata_file = doc_dir / "metadata.json"
        
        # Carica metadata
        if not metadata_file.exists():
            continue
        with open(metadata_file) as f:
            meta = json.load(f)
        
        # Escludi fondi (no SIC)
        if meta.get("sic") == "NULL" or meta.get("sic") is None:
            continue
        
        # Se non ha extraction results, skip
        if not extraction_file.exists() or not classification_file.exists():
            continue
        
        with open(extraction_file) as f:
            extraction = json.load(f)
        with open(classification_file) as f:
            classification = json.load(f)
        
        # Base record con metadati
        base_record = {
            "cik": meta.get("cik"),
            "company": meta.get("company"),
            "year": meta.get("year"),
            "filing_date": meta.get("filing_date"),
            "sic": meta.get("sic"),
            "state_of_inc": meta.get("state_of_inc"),
            "filing_html_index": meta.get("filing_html_index"),
            "accession_number": meta.get("accession_number"),
        }
        
        # Per ogni tabella trovata
        for i, table_info in enumerate(classification.get("tables", [])):
            record = base_record.copy()
            
            # Immagine
            img_path = table_info.get("table", {}).get("img_path", "")
            images_dir = doc_dir / doc_dir.name / "vlm"
            full_img_path = images_dir / img_path
            
            if full_img_path.exists():
                record["table_image"] = str(full_img_path)
            else:
                record["table_image"] = None
            
            # HTML body
            record["table_body"] = table_info.get("table", {}).get("table_body", "")
            
            # Executives (dalla extraction corrispondente)
            if i < len(extraction.get("data", [])):
                execs = extraction["data"][i].get("executives", [])
                record["executives"] = json.dumps(execs)
            else:
                record["executives"] = json.dumps([])
            
            records.append(record)

    return records


def main():
    parser = argparse.ArgumentParser(description="Upload dataset to HuggingFace Hub")
    parser.add_argument("--push", action="store_true", help="Push to HuggingFace Hub")
    parser.add_argument("--repo", type=str, default=DEFAULT_REPO, help=f"HF repo name (default: {DEFAULT_REPO})")
    args = parser.parse_args()

    print("="*60)
    print("BUILDING HUGGINGFACE DATASET")
    print("="*60)

    # Build records
    print("\n[1/3] Collecting records from output...")
    records = build_dataset(OUTPUT_PATH)
    print(f"✓ Found {len(records)} records")

    if not records:
        print("✗ No records found. Run the pipeline first.")
        return

    # Create HF dataset
    print("\n[2/3] Creating HuggingFace dataset...")
    hf_dataset = Dataset.from_list(records)
    hf_dataset = hf_dataset.cast_column("table_image", HFImage())
    print(f"✓ Dataset created: {hf_dataset}")

    # Save locally
    print(f"\n[3/3] Saving to {HF_LOCAL_PATH}...")
    HF_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    hf_dataset.save_to_disk(str(HF_LOCAL_PATH))
    print(f"✓ Saved locally")

    # Push to Hub
    if args.push:
        print(f"\n[PUSH] Uploading to {args.repo}...")
        hf_dataset.push_to_hub(args.repo)
        print(f"✓ Pushed to https://huggingface.co/datasets/{args.repo}")

    print("\n" + "="*60)
    print("COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
