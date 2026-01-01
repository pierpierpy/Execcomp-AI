#!/usr/bin/env python3
"""
Upload Executive Compensation dataset to HuggingFace Hub.

Usage:
    python scripts/to_hf.py         # Save locally only
    python scripts/to_hf.py --push  # Save locally and push to HF Hub
"""

import argparse
import json
from pathlib import Path
from collections import Counter

from datasets import Dataset, Image as HFImage
from huggingface_hub import HfApi


# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_PATH = Path(__file__).parent.parent.resolve()  # Go up from scripts/ to project root
OUTPUT_PATH = BASE_PATH / "output"
DOCS_PATH = BASE_PATH / "docs"
HF_LOCAL_PATH = BASE_PATH / "hf/execcomp-ai-sample"
HF_REPO = "pierjoe/execcomp-ai-sample"


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

    # Show duplicates analysis
    keys = [(r["cik"], r["year"]) for r in records]
    counts = Counter(keys)
    duplicates = {k: v for k, v in counts.items() if v > 1}
    
    print(f"\n📊 Dataset Statistics:")
    print(f"   Total records: {len(records)}")
    print(f"   Unique (cik, year): {len(counts)}")
    print(f"   With duplicates: {len(duplicates)}")
    
    if duplicates:
        print(f"\n⚠️  Duplicates (same cik+year, multiple tables):")
        for (cik, year), count in sorted(duplicates.items(), key=lambda x: -x[1]):
            company = next((r["company"] for r in records if r["cik"] == cik and r["year"] == year), "Unknown")
            print(f"   CIK {cik}, Year {year}: {count} tables - {company}")

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
        print(f"\n[PUSH] Uploading to {HF_REPO}...")
        hf_dataset.push_to_hub(HF_REPO)
        print(f"✓ Dataset pushed")
        
        # Upload docs (images + README)
        api = HfApi()
        
        # Upload README
        readme_path = DOCS_PATH / "HF_README.md"
        if readme_path.exists():
            print(f"   Uploading README.md...")
            api.upload_file(
                path_or_fileobj=str(readme_path),
                path_in_repo="README.md",
                repo_id=HF_REPO,
                repo_type="dataset"
            )
        
        # Upload doc images
        for img_file in DOCS_PATH.glob("*.png"):
            print(f"   Uploading {img_file.name}...")
            api.upload_file(
                path_or_fileobj=str(img_file),
                path_in_repo=f"docs/{img_file.name}",
                repo_id=HF_REPO,
                repo_type="dataset"
            )
        
        print(f"✓ Pushed to https://huggingface.co/datasets/{HF_REPO}")

    print("\n" + "="*60)
    print("COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
