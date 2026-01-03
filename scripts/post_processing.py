#!/usr/bin/env python3
"""
Post-Processing: Add SCT probability scores and generate analysis.

Uses a fine-tuned binary classifier (Qwen3-VL-4B) to score each table image,
adding a 'sct_probability' column that helps filter false positives.

Also generates dataset statistics, charts, and threshold analysis.

Usage:
    python scripts/post_processing.py             # Build dataset locally
    python scripts/post_processing.py --push      # Build and push to HF
    python scripts/post_processing.py --push-only # Push existing dataset (no rebuild)
"""

import json
import sys
from pathlib import Path
from collections import Counter

from datasets import Dataset, Image as HFImage
from huggingface_hub import HfApi
from tqdm.auto import tqdm

# =============================================================================
# CONFIGURATION (edit these values directly)
# =============================================================================

BASE_PATH = Path(__file__).parent.parent.resolve()
OUTPUT_PATH = BASE_PATH / "output"
DOCS_PATH = BASE_PATH / "docs"
HF_LOCAL_PATH = BASE_PATH / "hf/execcomp-ai-postprocessed"
HF_REPO = "pierjoe/execcomp-ai-sample"

# Classifier settings
# Local path or HuggingFace repo ID. If local doesn't exist, downloads from HF.
# Set to None to use default (tries local first, then HuggingFace)
# CLASSIFIER_MODEL_PATH = None  # or "pierjoe/Qwen3-VL-4B-SCT-Classifier" or local path
CLASSIFIER_MODEL_PATH = "hf/models/exp3-weighted-loss-qwen3-bigger_dataset/full"
CLASSIFIER_BATCH_SIZE = 8
CLASSIFIER_DEVICE = "cuda:0"

# Filtering (set to None to keep all records)
SCT_PROBABILITY_THRESHOLD = None  # e.g., 0.5 to filter low-confidence

# Analysis settings
RUN_ANALYSIS = True
RUN_THRESHOLD_ANALYSIS = True

# Add src to path
sys.path.insert(0, str(BASE_PATH))


def push_only():
    """Push existing local dataset to HuggingFace without rebuilding."""
    from datasets import load_from_disk
    
    print("=" * 60)
    print("PUSH-ONLY MODE")
    print("=" * 60)
    
    if not HF_LOCAL_PATH.exists():
        print(f"✗ Local dataset not found at {HF_LOCAL_PATH}")
        print("  Run without --push-only first to build the dataset.")
        return
    
    # Load existing dataset
    print(f"\nLoading dataset from {HF_LOCAL_PATH}...")
    hf_dataset = load_from_disk(str(HF_LOCAL_PATH))
    print(f"✓ Dataset: {hf_dataset}")
    
    # Push to Hub
    print(f"\nPushing dataset to {HF_REPO}...")
    hf_dataset.push_to_hub(HF_REPO)
    print(f"✓ Dataset pushed")
    
    # Upload docs
    api = HfApi()
    
    readme_path = DOCS_PATH / "HF_README.md"
    if readme_path.exists():
        print(f"   Uploading README.md...")
        api.upload_file(
            path_or_fileobj=str(readme_path),
            path_in_repo="README.md",
            repo_id=HF_REPO,
            repo_type="dataset"
        )
    
    for img_file in DOCS_PATH.glob("*.png"):
        print(f"   Uploading {img_file.name}...")
        api.upload_file(
            path_or_fileobj=str(img_file),
            path_in_repo=f"docs/{img_file.name}",
            repo_id=HF_REPO,
            repo_type="dataset"
        )
    
    print(f"\n✓ Pushed to https://huggingface.co/datasets/{HF_REPO}")
    print("=" * 60)


def build_records_with_probability(output_path: Path, classifier) -> list[dict]:
    """
    Build dataset records with SCT probability scores.
    
    Args:
        output_path: Path to output directory
        classifier: SCTClassifier instance
        
    Returns:
        List of records with sct_probability field
    """
    records = []
    image_paths = []  # Collect for batch classification
    record_indices = []  # Track which record each image belongs to

    # First pass: collect all records and image paths
    print("\n[1/2] Collecting records...")
    for doc_dir in tqdm(list(output_path.iterdir()), desc="Scanning"):
        if not doc_dir.is_dir():
            continue
        
        extraction_file = doc_dir / "extraction_results.json"
        classification_file = doc_dir / "classification_results.json"
        metadata_file = doc_dir / "metadata.json"
        
        if not metadata_file.exists():
            continue
        with open(metadata_file) as f:
            meta = json.load(f)
        
        # Skip funds
        if meta.get("sic") == "NULL" or meta.get("sic") is None:
            continue
        
        if not extraction_file.exists() or not classification_file.exists():
            continue
        
        with open(extraction_file) as f:
            extraction = json.load(f)
        with open(classification_file) as f:
            classification = json.load(f)
        
        # Base record
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
        
        # For each table
        for i, table_info in enumerate(classification.get("tables", [])):
            record = base_record.copy()
            
            # Image path
            img_path = table_info.get("table", {}).get("img_path", "")
            images_dir = doc_dir / doc_dir.name / "vlm"
            full_img_path = images_dir / img_path
            
            if full_img_path.exists():
                record["table_image"] = str(full_img_path)
                image_paths.append(full_img_path)
                record_indices.append(len(records))
            else:
                record["table_image"] = None
            
            # HTML body
            record["table_body"] = table_info.get("table", {}).get("table_body", "")
            
            # Executives
            if i < len(extraction.get("data", [])):
                execs = extraction["data"][i].get("executives", [])
                record["executives"] = json.dumps(execs)
            else:
                record["executives"] = json.dumps([])
            
            # Placeholder for probability (will fill in batch)
            record["sct_probability"] = None
            
            records.append(record)
    
    print(f"✓ Found {len(records)} records, {len(image_paths)} with images")
    
    # Second pass: batch classify all images
    print("\n[2/2] Classifying images...")
    if image_paths:
        probabilities = classifier.classify_batch(
            image_paths, 
            batch_size=CLASSIFIER_BATCH_SIZE,
            show_progress=True
        )
        
        # Assign probabilities to records
        for idx, prob in zip(record_indices, probabilities):
            records[idx]["sct_probability"] = round(prob, 4)
    
    # Records without images get probability 0
    for record in records:
        if record["sct_probability"] is None:
            record["sct_probability"] = 0.0
    
    return records


def print_stats(records: list[dict]):
    """Print dataset statistics."""
    print("\n" + "=" * 60)
    print("DATASET STATISTICS")
    print("=" * 60)
    
    total = len(records)
    with_image = sum(1 for r in records if r["table_image"])
    
    # Probability distribution
    probs = [r["sct_probability"] for r in records]
    high_conf = sum(1 for p in probs if p >= 0.7)
    medium_conf = sum(1 for p in probs if 0.3 <= p < 0.7)
    low_conf = sum(1 for p in probs if p < 0.3)
    
    print(f"\nTotal records: {total:,}")
    print(f"With images: {with_image:,}")
    print(f"\nSCT Probability Distribution:")
    print(f"  High (≥0.7):    {high_conf:,} ({high_conf/total*100:.1f}%)")
    print(f"  Medium (0.3-0.7): {medium_conf:,} ({medium_conf/total*100:.1f}%)")
    print(f"  Low (<0.3):     {low_conf:,} ({low_conf/total*100:.1f}%)")
    
    # Duplicates analysis
    keys = [(r["cik"], r["year"]) for r in records]
    counts = Counter(keys)
    duplicates = {k: v for k, v in counts.items() if v > 1}
    
    print(f"\nUnique (cik, year): {len(counts):,}")
    print(f"With multiple tables: {len(duplicates):,}")
    
    if duplicates:
        # Check if classifier helps disambiguate
        could_filter = 0
        for (cik, year), count in duplicates.items():
            doc_records = [r for r in records if r["cik"] == cik and r["year"] == year]
            high_prob = [r for r in doc_records if r["sct_probability"] >= 0.7]
            if len(high_prob) == 1:
                could_filter += 1
        
        print(f"  → Classifier can disambiguate: {could_filter}/{len(duplicates)}")
    
    print("=" * 60)


def run_threshold_analysis(records: list[dict]):
    """Run threshold analysis and print results."""
    from src.analysis import analyze_thresholds, find_optimal_threshold
    from src.analysis.threshold import (
        print_threshold_analysis,
        plot_threshold_analysis,
        get_multi_sct_examples,
    )
    
    print("\n" + "=" * 60)
    print("RUNNING THRESHOLD ANALYSIS")
    print("=" * 60)
    
    # Analyze
    results = analyze_thresholds(records)
    optimal = find_optimal_threshold(results)
    
    # Print analysis
    report = print_threshold_analysis(results, optimal)
    print(report)
    
    # Generate plot
    plot_path = plot_threshold_analysis(results, optimal, DOCS_PATH)
    print(f"\n✓ Threshold plot saved to {plot_path}")
    
    # Show multi-SCT examples
    examples = get_multi_sct_examples(records, optimal.threshold, n=5)
    if examples:
        print(f"\n📋 Multi-SCT examples at threshold {optimal.threshold:.2f}:")
        for ex in examples:
            probs_str = ", ".join(f"{p:.3f}" for p in ex["probabilities"])
            print(f"  • {ex['company']} ({ex['cik']}, {ex['year']}): {ex['num_tables']} tables [{probs_str}]")
    else:
        print(f"\n✓ No multi-SCT documents at threshold {optimal.threshold:.2f}")
    
    return optimal


def main():
    # Quick push mode - skip all processing
    if "--push-only" in sys.argv:
        push_only()
        return
    
    push_mode = "--push" in sys.argv
    
    print("=" * 60)
    print("POST-PROCESSING: SCT PROBABILITY SCORING")
    print("=" * 60)
    
    # Run stats analysis first (generates images)
    if RUN_ANALYSIS:
        print("\n[0] Generating analysis images...")
        from src.analysis import generate_stats_images
        from src.tracking import Tracker
        
        tracker = Tracker(BASE_PATH)
        generated = generate_stats_images(OUTPUT_PATH, DOCS_PATH, tracker)
        print(f"✓ Generated {len(generated)} images")
    
    # Load classifier
    print("\nLoading SCT Classifier...")
    from src.vlm.classifier import SCTClassifier
    classifier = SCTClassifier(
        model_path=CLASSIFIER_MODEL_PATH,
        device=CLASSIFIER_DEVICE
    )
    
    # Build records with probability
    records = build_records_with_probability(OUTPUT_PATH, classifier)
    
    if not records:
        print("✗ No records found. Run the pipeline first.")
        return
    
    # Print stats
    print_stats(records)
    
    # Generate probability stats images
    print("\n[3/3] Generating probability statistics images...")
    from src.analysis import generate_probability_stats
    prob_images = generate_probability_stats(records, DOCS_PATH)
    print(f"✓ Generated {len(prob_images)} probability images")
    
    # Run threshold analysis
    optimal = None
    if RUN_THRESHOLD_ANALYSIS:
        optimal = run_threshold_analysis(records)
    
    # Filter by threshold if configured
    if SCT_PROBABILITY_THRESHOLD is not None:
        original_count = len(records)
        records = [r for r in records if r["sct_probability"] >= SCT_PROBABILITY_THRESHOLD]
        print(f"\n⚡ Filtered: {original_count} → {len(records)} (threshold={SCT_PROBABILITY_THRESHOLD})")
    
    # Create HF dataset
    print("\nCreating HuggingFace dataset...")
    hf_dataset = Dataset.from_list(records)
    hf_dataset = hf_dataset.cast_column("table_image", HFImage())
    print(f"✓ Dataset: {hf_dataset}")
    
    # Save locally (always)
    print(f"\nSaving to {HF_LOCAL_PATH}...")
    HF_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    hf_dataset.save_to_disk(str(HF_LOCAL_PATH))
    print(f"✓ Saved locally")
    
    # Push to Hub (if --push)
    if push_mode:
        print(f"\nPushing dataset to {HF_REPO}...")
        hf_dataset.push_to_hub(HF_REPO)
        print(f"✓ Dataset pushed")
        
        # Upload docs (README + images)
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
        
        # Upload doc images (stats charts)
        for img_file in DOCS_PATH.glob("*.png"):
            print(f"   Uploading {img_file.name}...")
            api.upload_file(
                path_or_fileobj=str(img_file),
                path_in_repo=f"docs/{img_file.name}",
                repo_id=HF_REPO,
                repo_type="dataset"
            )
        
        print(f"✓ Pushed to https://huggingface.co/datasets/{HF_REPO}")
    
    print("\n" + "=" * 60)
    print("COMPLETE")
    if optimal:
        print(f"Recommended threshold: {optimal.threshold:.2f} ({optimal.single_pct:.1f}% single-SCT)")
    print("=" * 60)


if __name__ == "__main__":
    main()
