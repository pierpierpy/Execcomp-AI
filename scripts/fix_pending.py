#!/usr/bin/env python3
"""
Fix Pending Documents

Finds documents that are "pending" (non-fund without extraction_results.json 
or no_sct_found.json) and re-processes them.

Usage:
    python scripts/fix_pending.py          # Show pending docs only
    python scripts/fix_pending.py --fix    # Delete and reprocess
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE_PATH = Path(__file__).parent.parent.resolve()
OUTPUT_PATH = BASE_PATH / "output"
PDF_PATH = BASE_PATH / "pdfs"


def find_pending_docs():
    """Find all pending documents and categorize them."""
    no_pdf = []
    no_mineru = []
    not_classified = []
    
    for doc_dir in OUTPUT_PATH.iterdir():
        if not doc_dir.is_dir():
            continue
        
        metadata_path = doc_dir / "metadata.json"
        if not metadata_path.exists():
            continue
        
        with open(metadata_path) as f:
            meta = json.load(f)
        
        # Skip funds
        if meta.get("sic") in ("NULL", None):
            continue
        
        # Skip if has results
        if (doc_dir / "extraction_results.json").exists():
            continue
        if (doc_dir / "no_sct_found.json").exists():
            continue
        
        # This is a pending doc - categorize it
        doc_name = doc_dir.name
        pdf_path = PDF_PATH / f"{doc_name}.pdf"
        content_files = list(doc_dir.rglob("*_content_list.json"))
        
        if not pdf_path.exists():
            no_pdf.append(doc_name)
        elif not content_files:
            no_mineru.append(doc_name)
        else:
            # Has content_list but no results - classification failed
            with open(content_files[0]) as f:
                data = json.load(f)
            tables = [item for item in data if item.get('type') == 'table']
            not_classified.append((doc_name, len(tables)))
    
    return no_pdf, no_mineru, not_classified


def main():
    fix_mode = "--fix" in sys.argv
    
    print("=" * 60)
    print("PENDING DOCUMENTS ANALYSIS")
    print("=" * 60)
    
    no_pdf, no_mineru, not_classified = find_pending_docs()
    total_pending = len(no_pdf) + len(no_mineru) + len(not_classified)
    
    if total_pending == 0:
        print("\n✓ No pending documents found!")
        return
    
    print(f"\nTotal pending: {total_pending}\n")
    
    if no_pdf:
        print(f"📭 No PDF ({len(no_pdf)}) - download failed:")
        for doc in sorted(no_pdf):
            print(f"    - {doc}")
        print()
    
    if no_mineru:
        print(f"🔧 No MinerU output ({len(no_mineru)}) - MinerU failed:")
        for doc in sorted(no_mineru):
            print(f"    - {doc}")
        print()
    
    if not_classified:
        print(f"📊 Not classified ({len(not_classified)}) - has tables but classification failed:")
        for doc, n_tables in sorted(not_classified):
            print(f"    - {doc} ({n_tables} tables)")
        print()
    
    if not fix_mode:
        print("=" * 60)
        print("Run with --fix to delete these folders and reprocess")
        print("=" * 60)
        return
    
    # Fix mode: delete folders and rerun pipeline
    print("=" * 60)
    print("FIXING PENDING DOCUMENTS")
    print("=" * 60)
    
    all_pending = no_pdf + no_mineru + [doc for doc, _ in not_classified]
    
    for doc in all_pending:
        doc_dir = OUTPUT_PATH / doc
        print(f"🗑️  Deleting {doc}")
        shutil.rmtree(doc_dir)
    
    print(f"\n✓ Deleted {len(all_pending)} folders")
    print("\n🚀 Running pipeline...")
    print("=" * 60)
    
    # Run pipeline
    subprocess.run([sys.executable, str(BASE_PATH / "scripts" / "pipeline.py")])


if __name__ == "__main__":
    main()
