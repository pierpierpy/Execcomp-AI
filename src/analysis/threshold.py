"""
Threshold analysis for SCT probability optimization.

Finds the optimal threshold that maximizes single-SCT documents
while maintaining good dataset coverage.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


@dataclass
class ThresholdAnalysisResult:
    """Result of threshold analysis."""
    threshold: float
    total_records: int
    total_docs: int
    single_sct: int
    multi_sct: int
    single_pct: float
    
    def __str__(self) -> str:
        return (
            f"Threshold {self.threshold:.2f}: "
            f"{self.single_sct}/{self.total_docs} single-SCT ({self.single_pct:.1f}%)"
        )


def analyze_thresholds(
    records: list[dict],
    thresholds: list[float] | None = None
) -> list[ThresholdAnalysisResult]:
    """
    Analyze different thresholds and their effect on duplicates.
    
    Args:
        records: List of records with 'sct_probability', 'cik', 'year' fields
        thresholds: List of thresholds to test (default: 0.0 to 1.0 by 0.05)
    
    Returns:
        List of ThresholdAnalysisResult for each threshold
    """
    if thresholds is None:
        thresholds = list(np.arange(0.0, 1.01, 0.05))
    
    results = []
    
    for thresh in thresholds:
        # Filter by threshold
        filtered = [r for r in records if r["sct_probability"] >= thresh]
        
        # Count documents with exactly 1 SCT
        doc_counts = Counter((r["cik"], r["year"]) for r in filtered)
        
        total_docs = len(doc_counts)
        single_sct = sum(1 for count in doc_counts.values() if count == 1)
        multi_sct = sum(1 for count in doc_counts.values() if count > 1)
        total_records = len(filtered)
        
        results.append(ThresholdAnalysisResult(
            threshold=thresh,
            total_records=total_records,
            total_docs=total_docs,
            single_sct=single_sct,
            multi_sct=multi_sct,
            single_pct=single_sct / total_docs * 100 if total_docs > 0 else 0
        ))
    
    return results


def find_optimal_threshold(
    results: list[ThresholdAnalysisResult],
    min_coverage: float = 0.5
) -> ThresholdAnalysisResult:
    """
    Find threshold that maximizes single-SCT documents while keeping coverage.
    
    Args:
        results: List of ThresholdAnalysisResult
        min_coverage: Minimum fraction of documents to retain (default: 0.5)
    
    Returns:
        Optimal ThresholdAnalysisResult
    """
    max_docs = max(r.total_docs for r in results)
    min_docs_threshold = max_docs * min_coverage
    
    valid_results = [r for r in results if r.total_docs >= min_docs_threshold]
    
    if not valid_results:
        return results[0]
    
    # Find the one with highest single_pct
    best = max(valid_results, key=lambda r: r.single_pct)
    return best


def print_threshold_analysis(
    results: list[ThresholdAnalysisResult],
    optimal: ThresholdAnalysisResult
) -> str:
    """
    Format threshold analysis as a string report.
    
    Args:
        results: List of analysis results
        optimal: The optimal result
    
    Returns:
        Formatted report string
    """
    lines = []
    lines.append("=" * 80)
    lines.append("THRESHOLD ANALYSIS")
    lines.append("=" * 80)
    
    lines.append(f"\n{'Threshold':<12} {'Records':<10} {'Docs':<10} {'Single SCT':<12} {'Multi SCT':<12} {'Single %':<10}")
    lines.append("-" * 80)
    
    for r in results:
        marker = " ◄ OPTIMAL" if r.threshold == optimal.threshold else ""
        lines.append(
            f"{r.threshold:<12.2f} {r.total_records:<10} {r.total_docs:<10} "
            f"{r.single_sct:<12} {r.multi_sct:<12} {r.single_pct:<10.1f}{marker}"
        )
    
    lines.append("\n" + "=" * 80)
    lines.append(f"OPTIMAL THRESHOLD: {optimal.threshold:.2f}")
    lines.append("=" * 80)
    lines.append(f"  Records: {optimal.total_records:,}")
    lines.append(f"  Documents: {optimal.total_docs:,}")
    lines.append(f"  Single-SCT docs: {optimal.single_sct:,} ({optimal.single_pct:.1f}%)")
    lines.append(f"  Multi-SCT docs: {optimal.multi_sct:,}")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def plot_threshold_analysis(
    results: list[ThresholdAnalysisResult],
    optimal: ThresholdAnalysisResult,
    output_path: Path
) -> Path:
    """
    Generate threshold analysis plot.
    
    Args:
        results: List of analysis results
        optimal: The optimal result
        output_path: Directory to save plot
    
    Returns:
        Path to saved plot
    """
    thresholds = [r.threshold for r in results]
    single_pct = [r.single_pct for r in results]
    total_docs = [r.total_docs for r in results]
    total_records = [r.total_records for r in results]
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Plot 1: Single-SCT percentage vs threshold
    ax1 = axes[0]
    ax1.plot(thresholds, single_pct, 'b-o', linewidth=2, markersize=4)
    ax1.axvline(optimal.threshold, color='red', linestyle='--', 
                label=f'Optimal: {optimal.threshold:.2f}')
    ax1.set_xlabel('Threshold', fontsize=12)
    ax1.set_ylabel('Single-SCT Documents (%)', fontsize=12)
    ax1.set_title('Single-SCT Document Rate by Threshold', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 105)
    
    # Plot 2: Coverage (documents retained)
    ax2 = axes[1]
    ax2.plot(thresholds, total_docs, 'g-o', linewidth=2, markersize=4, label='Documents')
    ax2.plot(thresholds, total_records, 'b-s', linewidth=2, markersize=4, label='Records')
    ax2.axvline(optimal.threshold, color='red', linestyle='--', 
                label=f'Optimal: {optimal.threshold:.2f}')
    ax2.set_xlabel('Threshold', fontsize=12)
    ax2.set_ylabel('Count', fontsize=12)
    ax2.set_title('Dataset Size by Threshold', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, 1)
    
    plt.tight_layout()
    
    output_file = output_path / 'analysis_threshold.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    return output_file


def get_multi_sct_examples(
    records: list[dict],
    threshold: float,
    n: int = 5
) -> list[dict]:
    """
    Get examples of documents with multiple SCTs at given threshold.
    
    Args:
        records: List of records
        threshold: Probability threshold
        n: Number of examples to return
    
    Returns:
        List of example documents with their records
    """
    filtered = [r for r in records if r["sct_probability"] >= threshold]
    
    # Group by document
    doc_records = defaultdict(list)
    for r in filtered:
        key = (r["cik"], r["year"], r.get("company", ""))
        doc_records[key].append(r)
    
    # Find multi-SCT documents
    multi = [(k, v) for k, v in doc_records.items() if len(v) > 1]
    multi.sort(key=lambda x: -len(x[1]))  # Sort by count descending
    
    examples = []
    for (cik, year, company), recs in multi[:n]:
        examples.append({
            "cik": cik,
            "year": year,
            "company": company,
            "num_tables": len(recs),
            "probabilities": sorted([r["sct_probability"] for r in recs], reverse=True)
        })
    
    return examples
