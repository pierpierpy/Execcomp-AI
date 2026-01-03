#!/usr/bin/env python3
"""
Fix Pending Documents

Finds documents that are "pending" (non-fund without completed extraction)
and re-processes them.

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

# Add src to path for tracker
sys.path.insert(0, str(BASE_PATH))
from src.tracking import Tracker


def find_pending_docs(tracker: Tracker):
    """Find all pending documents and categorize them using the tracker."""
    no_pdf = []
    no_mineru = []
    not_classified = []
    
    # Get all non-fund documents that aren't complete
    for doc_id, doc_info in tracker.data["documents"].items():
        # Skip funds
        if doc_info.get("sic") in ("NULL", None):
            continue
        
        # Skip if complete
        status = doc_info.get("status")
        if status in ("complete", "no_sct"):
            continue
        
        phases = doc_info.get("phases", {})
        pdf_path = PDF_PATH / f"{doc_id}.pdf"
        
        if not pdf_path.exists():
            no_pdf.append(doc_id)
        elif "mineru_done" not in phases:
            no_mineru.append(doc_id)
        else:
            # Has MinerU but not classified/extracted
            # Count tables from content_list
            content_files = list((OUTPUT_PATH / doc_id).rglob("*_content_list.json"))
            n_tables = 0
            if content_files:
                with open(content_files[0]) as f:
                    data = json.load(f)
                n_tables = len([item for item in data if item.get('type') == 'table'])
            not_classified.append((doc_id, n_tables))
    
    return no_pdf, no_mineru, not_classified


def main():
    fix_mode = "--fix" in sys.argv
    
    print("=" * 60)
    print("PENDING DOCUMENTS ANALYSIS")
    print("=" * 60)
    
    # Initialize tracker
    tracker = Tracker(BASE_PATH)
    tracker.print_stats()
    
    no_pdf, no_mineru, not_classified = find_pending_docs(tracker)
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
    
    # Rebuild tracker after deletion
    print("\n🔄 Rebuilding tracker...")
    tracker.rebuild_from_files()
    
    print("\n🚀 Running pipeline with --continue...")
    print("=" * 60)
    
    # Run pipeline in continue mode
    subprocess.run([sys.executable, str(BASE_PATH / "scripts" / "pipeline.py"), "--continue"])


if __name__ == "__main__":
    main()
