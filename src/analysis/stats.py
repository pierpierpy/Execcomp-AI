"""
Statistics generation for dataset analysis.

Generates statistics tables and charts as PNG images for documentation.
"""

import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt


# Style configuration
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.size'] = 11
plt.rcParams['figure.facecolor'] = 'white'


def create_table_image(
    data: list[list],
    headers: list[str],
    title: str,
    output_path: Path,
    col_widths: list[float] = None,
    highlight_last: bool = False
) -> Path:
    """
    Create a table as a PNG image.
    
    Args:
        data: Table data as list of rows
        headers: Column headers
        title: Table title
        output_path: Full path to save image
        col_widths: Optional column widths
        highlight_last: Whether to highlight last row
    
    Returns:
        Path to saved image
    """
    fig, ax = plt.subplots(figsize=(8, max(2, len(data) * 0.5 + 1)))
    ax.axis('off')
    
    # Create table
    table = ax.table(
        cellText=data,
        colLabels=headers,
        loc='center',
        cellLoc='left',
        colColours=['#3498db'] * len(headers),
    )
    
    # Style
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    
    # Header style
    for i in range(len(headers)):
        table[(0, i)].set_text_props(color='white', fontweight='bold')
        table[(0, i)].set_facecolor('#2c3e50')
    
    # Alternating row colors
    for i in range(1, len(data) + 1):
        for j in range(len(headers)):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#ecf0f1')
            else:
                table[(i, j)].set_facecolor('white')
            
            # Highlight last row if requested
            if highlight_last and i == len(data):
                table[(i, j)].set_text_props(fontweight='bold')
                table[(i, j)].set_facecolor('#d5f5e3')
    
    # Column widths
    if col_widths:
        for i, w in enumerate(col_widths):
            for j in range(len(data) + 1):
                table[(j, i)].set_width(w)
    
    plt.title(title, fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    
    return output_path


def collect_pipeline_data(output_path: Path, tracker) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Collect pipeline statistics from tracker and output directory.
    
    Args:
        output_path: Path to output directory
        tracker: Tracker instance
    
    Returns:
        Tuple of (table_df, exec_df, pipeline_stats)
    """
    stats = tracker.stats()
    
    total_docs = stats['total']
    funds = stats['by_status'].get('fund', 0)
    with_sct = stats['by_status'].get('complete', 0)
    no_sct = stats['by_status'].get('no_sct', 0)
    
    # Count tables from complete documents
    total_tables = 0
    for doc_id in tracker.get_by_status('complete'):
        doc_info = tracker.get_document(doc_id)
        if doc_info:
            total_tables += len(doc_info.get('sct_tables', []))
    
    pipeline_stats = {
        'total_docs': total_docs,
        'funds': funds,
        'with_sct': with_sct,
        'no_sct': no_sct,
        'total_tables': total_tables,
        'multi_table': total_tables - with_sct,
        'non_funds': total_docs - funds,
    }
    
    # Collect executive data from output
    exec_records = []
    table_records = []
    
    for doc_dir in output_path.iterdir():
        if not doc_dir.is_dir():
            continue
        
        extraction_file = doc_dir / "extraction_results.json"
        classification_file = doc_dir / "classification_results.json"
        metadata_file = doc_dir / "metadata.json"
        
        if not all(f.exists() for f in [extraction_file, classification_file, metadata_file]):
            continue
        
        with open(metadata_file) as f:
            meta = json.load(f)
        
        if meta.get("sic") in ("NULL", None):
            continue
        
        with open(extraction_file) as f:
            extraction = json.load(f)
        with open(classification_file) as f:
            classification = json.load(f)
        
        for i, table_info in enumerate(classification.get("tables", [])):
            table_records.append({
                "cik": meta.get("cik"),
                "company": meta.get("company"),
                "year": meta.get("year"),
                "sic": meta.get("sic"),
            })
            
            if i < len(extraction.get("data", [])):
                for exec_data in extraction["data"][i].get("executives", []):
                    exec_data["cik"] = meta.get("cik")
                    exec_data["company"] = meta.get("company")
                    exec_data["filing_year"] = meta.get("year")  # Year of the SEC filing
                    # Use fiscal_year from executive data if available, otherwise fall back to filing year
                    # TODO: Missing fiscal_year may indicate a FALSE POSITIVE in classification.
                    #       Example: a "Director Compensation" table misclassified as SCT won't have
                    #       the typical SCT structure with fiscal_year for each executive.
                    #       HINT: These false positives likely have low sct_probability scores,
                    #       so filtering by sct_probability >= 0.7 should eliminate most of them.
                    #       Consider logging/flagging these cases for review.
                    if "fiscal_year" not in exec_data or exec_data.get("fiscal_year") is None:
                        exec_data["fiscal_year"] = meta.get("year")
                    exec_data["sic"] = meta.get("sic")
                    exec_records.append(exec_data)
    
    table_df = pd.DataFrame(table_records)
    exec_df = pd.DataFrame(exec_records)
    
    # Convert compensation columns to numeric
    comp_cols = ['salary', 'bonus', 'stock_awards', 'option_awards', 
                 'non_equity_incentive', 'change_in_pension', 'other_compensation', 'total']
    for col in comp_cols:
        if col in exec_df.columns:
            exec_df[col] = pd.to_numeric(exec_df[col], errors='coerce')
    
    return table_df, exec_df, pipeline_stats


def generate_stats_images(
    output_path: Path,
    docs_path: Path,
    tracker
) -> list[Path]:
    """
    Generate all statistics images.
    
    Args:
        output_path: Path to output directory
        docs_path: Path to docs directory for saving images
        tracker: Tracker instance
    
    Returns:
        List of paths to generated images
    """
    docs_path.mkdir(exist_ok=True)
    generated = []
    today = datetime.now().strftime("%B %d, %Y")
    
    # Collect data
    table_df, exec_df, stats = collect_pipeline_data(output_path, tracker)
    
    # --- Pipeline Stats Table ---
    generated.append(create_table_image(
        data=[
            ["Documents processed", f"{stats['total_docs']:,}"],
            ["Funds (skipped)", f"{stats['funds']:,} ({stats['funds']/stats['total_docs']*100:.1f}%)"],
            ["With SCT", f"{stats['with_sct']:,}"],
            ["No SCT", f"{stats['no_sct']:,}"],
            ["Tables extracted", f"{stats['total_tables']:,}"],
            ["Multi-table docs", f"{stats['multi_table']:,}"],
        ],
        headers=["Metric", "Value"],
        title=f"Pipeline Statistics (updated {today})",
        output_path=docs_path / "stats_pipeline.png",
        col_widths=[0.5, 0.3],
        highlight_last=True
    ))
    
    if len(exec_df) > 0:
        # --- Compensation Stats Table ---
        generated.append(create_table_image(
            data=[
                ["Executive records", f"{len(exec_df):,}"],
                ["Unique companies", f"{table_df['cik'].nunique():,}"],
                ["Year range", f"{table_df['year'].min()} - {table_df['year'].max()}"],
                ["Mean total comp", f"${exec_df['total'].mean()/1e6:.2f}M"],
                ["Median total comp", f"${exec_df['total'].median()/1e6:.2f}M"],
                ["Max total comp", f"${exec_df['total'].max()/1e6:.1f}M"],
                ["Mean salary", f"${exec_df['salary'].mean()/1e3:.0f}K"],
            ],
            headers=["Metric", "Value"],
            title=f"Compensation Statistics (updated {today})",
            output_path=docs_path / "stats_compensation.png",
            col_widths=[0.5, 0.3]
        ))
        
        # --- Top 10 Table ---
        top_execs = exec_df.nlargest(10, 'total')[['name', 'company', 'fiscal_year', 'total']].copy()
        top_data = []
        for _, row in top_execs.iterrows():
            top_data.append([
                row['name'][:30],
                row['company'][:25],
                str(int(row['fiscal_year'])),
                f"${row['total']/1e6:.1f}M"
            ])
        
        generated.append(create_table_image(
            data=top_data,
            headers=["Executive", "Company", "Year", "Total"],
            title=f"🏆 Top 10 Highest Paid (updated {today})",
            output_path=docs_path / "stats_top10.png",
            col_widths=[0.35, 0.35, 0.1, 0.2]
        ))
        
        # --- Compensation Breakdown Table ---
        breakdown_data = []
        for col in ['salary', 'bonus', 'stock_awards', 'option_awards', 
                    'non_equity_incentive', 'change_in_pension', 'other_compensation', 'total']:
            if col in exec_df.columns:
                mean_val = exec_df[col].mean()
                median_val = exec_df[col].median()
                max_val = exec_df[col].max()
                label = col.replace('_', ' ').title()
                breakdown_data.append([
                    label,
                    f"${mean_val/1e3:.0f}K" if mean_val < 1e6 else f"${mean_val/1e6:.2f}M",
                    f"${median_val/1e3:.0f}K" if median_val < 1e6 else f"${median_val/1e6:.2f}M",
                    f"${max_val/1e6:.1f}M"
                ])
        
        generated.append(create_table_image(
            data=breakdown_data,
            headers=["Component", "Mean", "Median", "Max"],
            title=f"Compensation Breakdown (updated {today})",
            output_path=docs_path / "stats_breakdown.png",
            col_widths=[0.35, 0.2, 0.2, 0.2],
            highlight_last=True
        ))
    
    # --- Charts ---
    generated.extend(_generate_charts(table_df, exec_df, stats, docs_path, today))
    
    return generated


def _generate_charts(
    table_df: pd.DataFrame,
    exec_df: pd.DataFrame,
    stats: dict,
    docs_path: Path,
    today: str
) -> list[Path]:
    """Generate chart images."""
    generated = []
    
    # --- Pie Chart: Document Breakdown ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    labels1 = ['Funds\n(no exec comp)', 'With SCT', 'No SCT']
    sizes1 = [stats['funds'], stats['with_sct'], stats['no_sct']]
    colors1 = ['#95a5a6', '#27ae60', '#e74c3c']
    axes[0].pie(sizes1, labels=labels1, autopct='%1.1f%%', colors=colors1, startangle=90)
    axes[0].set_title(f"Document Breakdown (n={stats['total_docs']:,})", fontsize=14, fontweight='bold')
    
    labels2 = ['Single table', 'Multiple tables']
    single_docs = stats['with_sct'] - stats['multi_table']
    sizes2 = [single_docs, stats['multi_table']]
    colors2 = ['#3498db', '#9b59b6']
    axes[1].pie(sizes2, labels=labels2, autopct='%1.1f%%', colors=colors2, startangle=90)
    axes[1].set_title(f"Documents with SCT (n={stats['with_sct']:,})", fontsize=14, fontweight='bold')
    
    plt.suptitle(f'Updated: {today}', fontsize=10, color='gray')
    plt.tight_layout()
    chart_path = docs_path / 'chart_pipeline.png'
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    generated.append(chart_path)
    
    # --- Bar Chart: Tables by Year ---
    if len(table_df) > 0:
        year_counts = table_df['year'].value_counts().sort_index()
        
        fig, ax = plt.subplots(figsize=(14, 5))
        bars = ax.bar(year_counts.index, year_counts.values, color='#3498db', edgecolor='white')
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Number of Tables', fontsize=12)
        ax.set_title(f'Summary Compensation Tables by Year (updated {today})', fontsize=14, fontweight='bold')
        ax.set_xticks(year_counts.index)
        ax.set_xticklabels(year_counts.index, rotation=45)
        
        for bar, val in zip(bars, year_counts.values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, 
                    str(val), ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        chart_path = docs_path / 'chart_by_year.png'
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        generated.append(chart_path)
    
    # --- Histogram: Compensation Distribution ---
    if len(exec_df) > 0:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        total_comp = exec_df['total'].dropna()
        total_comp = total_comp[total_comp > 0]
        
        axes[0].hist(total_comp / 1e6, bins=50, color='#27ae60', edgecolor='white', alpha=0.8)
        axes[0].set_xlabel('Total Compensation ($ millions)', fontsize=12)
        axes[0].set_ylabel('Number of Executives', fontsize=12)
        axes[0].set_title('Distribution of Total Compensation', fontsize=14, fontweight='bold')
        axes[0].axvline(total_comp.median() / 1e6, color='red', linestyle='--', 
                        label=f'Median: ${total_comp.median()/1e6:.1f}M')
        axes[0].legend()
        
        comp_breakdown = exec_df[['salary', 'bonus', 'stock_awards', 'option_awards', 
                                  'non_equity_incentive', 'other_compensation']].mean()
        comp_breakdown = comp_breakdown.sort_values(ascending=True)
        
        colors = plt.cm.viridis([i/len(comp_breakdown) for i in range(len(comp_breakdown))])
        axes[1].barh(range(len(comp_breakdown)), comp_breakdown.values / 1e6, color=colors)
        axes[1].set_xlabel('Average Amount ($ millions)', fontsize=12)
        axes[1].set_title('Compensation Components (Average)', fontsize=14, fontweight='bold')
        labels = [l.replace('_', ' ').title() for l in comp_breakdown.index]
        axes[1].set_yticks(range(len(comp_breakdown)))
        axes[1].set_yticklabels(labels)
        
        plt.suptitle(f'Updated: {today}', fontsize=10, color='gray')
        plt.tight_layout()
        chart_path = docs_path / 'chart_distribution.png'
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        generated.append(chart_path)
    
    # --- Line Chart: Trends Over Time ---
    if len(exec_df) > 0:
        yearly_comp = exec_df.groupby('fiscal_year')['total'].agg(['mean', 'median']).reset_index()
        
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(yearly_comp['fiscal_year'], yearly_comp['mean'] / 1e6, 
                marker='o', linewidth=2, label='Mean', color='#3498db')
        ax.plot(yearly_comp['fiscal_year'], yearly_comp['median'] / 1e6, 
                marker='s', linewidth=2, label='Median', color='#e74c3c')
        
        ax.set_xlabel('Fiscal Year', fontsize=12)
        ax.set_ylabel('Total Compensation ($ millions)', fontsize=12)
        ax.set_title(f'Executive Compensation Trends Over Time (updated {today})', fontsize=14, fontweight='bold')
        ax.legend()
        ax.set_xticks(yearly_comp['fiscal_year'])
        ax.set_xticklabels(yearly_comp['fiscal_year'].astype(int), rotation=45)
        
        plt.tight_layout()
        chart_path = docs_path / 'chart_trends.png'
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        generated.append(chart_path)
    
    return generated


def generate_probability_stats(
    records: list[dict],
    docs_path: Path
) -> list[Path]:
    """
    Generate statistics images for SCT probability distribution.
    
    Args:
        records: List of records with sct_probability field
        docs_path: Path to docs directory for saving images
    
    Returns:
        List of paths to generated images
    """
    from collections import Counter
    import numpy as np
    
    docs_path.mkdir(exist_ok=True)
    generated = []
    today = datetime.now().strftime("%B %d, %Y")
    
    total = len(records)
    probs = [r["sct_probability"] for r in records]
    
    # Calculate stats
    high_conf = sum(1 for p in probs if p >= 0.7)
    medium_conf = sum(1 for p in probs if 0.3 <= p < 0.7)
    low_conf = sum(1 for p in probs if p < 0.3)
    
    # Duplicates analysis
    keys = [(r["cik"], r["year"]) for r in records]
    counts = Counter(keys)
    unique_docs = len(counts)
    multi_table_docs = sum(1 for count in counts.values() if count > 1)
    
    # How many can be disambiguated
    could_disambiguate = 0
    for (cik, year), count in counts.items():
        if count > 1:
            doc_records = [r for r in records if r["cik"] == cik and r["year"] == year]
            high_prob = [r for r in doc_records if r["sct_probability"] >= 0.7]
            if len(high_prob) == 1:
                could_disambiguate += 1
    
    # --- Stats Table with descriptions ---
    # Build data with dynamic descriptions
    extra_tables = total - unique_docs
    disambiguate_pct = could_disambiguate/multi_table_docs*100 if multi_table_docs > 0 else 0
    remaining_duplicates = multi_table_docs - could_disambiguate
    
    table_data = [
        ["Total tables extracted", f"{total:,}", "Tables identified as potential SCT by VLM"],
        ["Unique documents", f"{unique_docs:,}", f"Unique (company, year) pairs → {extra_tables:,} extra tables"],
        ["✅ High confidence (≥0.7)", f"{high_conf:,} ({high_conf/total*100:.1f}%)", "Likely true SCT - recommended to keep"],
        ["⚠️ Medium (0.3-0.7)", f"{medium_conf:,} ({medium_conf/total*100:.1f}%)", "Uncertain - review manually if needed"],
        ["❌ Low confidence (<0.3)", f"{low_conf:,} ({low_conf/total*100:.1f}%)", "Likely false positives - filter these out"],
        ["Documents with duplicates", f"{multi_table_docs:,}", f"Have >1 table classified as SCT"],
        ["→ Can disambiguate", f"{could_disambiguate:,} ({disambiguate_pct:.1f}%)", f"Only 1 table has prob≥0.7 → {remaining_duplicates:,} remain ambiguous"],
    ]
    
    generated.append(create_table_image(
        data=table_data,
        headers=["Metric", "Value", "Description"],
        title=f"SCT Probability Statistics (updated {today})",
        output_path=docs_path / "stats_probability.png",
        col_widths=[0.3, 0.2, 0.5],
        highlight_last=True
    ))
    
    # --- Probability Distribution Chart ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Histogram
    ax1 = axes[0]
    ax1.hist(probs, bins=20, color='#3498db', edgecolor='white', alpha=0.8)
    ax1.axvline(0.7, color='green', linestyle='--', linewidth=2, label='High threshold (0.7)')
    ax1.axvline(0.3, color='orange', linestyle='--', linewidth=2, label='Low threshold (0.3)')
    ax1.set_xlabel('SCT Probability', fontsize=12)
    ax1.set_ylabel('Number of Tables', fontsize=12)
    ax1.set_title('SCT Probability Distribution', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.set_xlim(0, 1)
    
    # Pie chart
    ax2 = axes[1]
    labels = ['High (≥0.7)', 'Medium (0.3-0.7)', 'Low (<0.3)']
    sizes = [high_conf, medium_conf, low_conf]
    colors = ['#27ae60', '#f39c12', '#e74c3c']
    ax2.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
    ax2.set_title('Confidence Distribution', fontsize=14, fontweight='bold')
    
    plt.suptitle(f'Updated: {today}', fontsize=10, color='gray')
    plt.tight_layout()
    chart_path = docs_path / 'chart_probability.png'
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    generated.append(chart_path)
    
    return generated
