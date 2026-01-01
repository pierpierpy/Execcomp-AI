#!/usr/bin/env python3
"""
Generate analysis statistics and charts as images.

This script generates all stats tables and charts as PNG images in docs/
so they can be embedded in README files and auto-updated.

Usage:
    python scripts/do_analysis.py
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_PATH = Path(__file__).parent.parent.resolve()
OUTPUT_PATH = BASE_PATH / "output"
DOCS_PATH = BASE_PATH / "docs"
DOCS_PATH.mkdir(exist_ok=True)

# Style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.size'] = 11
plt.rcParams['figure.facecolor'] = 'white'


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_table_image(data: list[list], headers: list[str], title: str, filename: str, 
                       col_widths: list[float] = None, highlight_last: bool = False):
    """Create a table as a PNG image."""
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
    plt.savefig(DOCS_PATH / filename, dpi=150, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    print(f"  ✓ {filename}")


# =============================================================================
# MAIN ANALYSIS
# =============================================================================

def main():
    print("=" * 60)
    print("GENERATING ANALYSIS IMAGES")
    print(f"Output: {DOCS_PATH}")
    print("=" * 60)
    
    # =========================================================================
    # 1. Collect Pipeline Statistics
    # =========================================================================
    print("\n[1/4] Collecting pipeline statistics...")
    
    total_docs = 0
    funds = 0
    with_sct = 0
    no_sct = 0
    total_tables = 0
    
    for d in OUTPUT_PATH.iterdir():
        if not d.is_dir():
            continue
        total_docs += 1
        
        meta_path = d / "metadata.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            if meta.get("sic") in ("NULL", None):
                funds += 1
                continue
        
        if (d / "extraction_results.json").exists():
            with_sct += 1
            class_path = d / "classification_results.json"
            if class_path.exists():
                with open(class_path) as f:
                    classification = json.load(f)
                total_tables += len(classification.get("tables", []))
        elif (d / "no_sct_found.json").exists():
            no_sct += 1
    
    non_funds = total_docs - funds
    multi_table = total_tables - with_sct
    
    print(f"  Total docs: {total_docs:,}, With SCT: {with_sct:,}, Tables: {total_tables:,}")
    
    # =========================================================================
    # 2. Load Executive Data from HuggingFace or build locally
    # =========================================================================
    print("\n[2/4] Loading executive compensation data...")
    
    exec_records = []
    table_records = []
    
    for doc_dir in OUTPUT_PATH.iterdir():
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
                    exec_data["filing_year"] = meta.get("year")
                    exec_data["sic"] = meta.get("sic")
                    exec_records.append(exec_data)
    
    df = pd.DataFrame(table_records)
    exec_df = pd.DataFrame(exec_records)
    
    # Convert compensation columns to numeric
    comp_cols = ['salary', 'bonus', 'stock_awards', 'option_awards', 
                 'non_equity_incentive', 'change_in_pension', 'other_compensation', 'total']
    for col in comp_cols:
        if col in exec_df.columns:
            exec_df[col] = pd.to_numeric(exec_df[col], errors='coerce')
    
    print(f"  Executive records: {len(exec_df):,}")
    print(f"  Unique companies: {df['cik'].nunique():,}")
    
    # =========================================================================
    # 3. Generate Table Images
    # =========================================================================
    print("\n[3/4] Generating table images...")
    
    # --- Pipeline Stats Table ---
    today = datetime.now().strftime("%B %d, %Y")
    create_table_image(
        data=[
            ["Documents processed", f"{total_docs:,}"],
            ["Funds (skipped)", f"{funds:,} ({funds/total_docs*100:.1f}%)"],
            ["With SCT", f"{with_sct:,}"],
            ["No SCT", f"{no_sct:,}"],
            ["Tables extracted", f"{total_tables:,}"],
            ["Multi-table docs", f"{multi_table:,}"],
        ],
        headers=["Metric", "Value"],
        title=f"Pipeline Statistics (updated {today})",
        filename="stats_pipeline.png",
        col_widths=[0.5, 0.3],
        highlight_last=True
    )
    
    # --- Compensation Stats Table ---
    create_table_image(
        data=[
            ["Executive records", f"{len(exec_df):,}"],
            ["Unique companies", f"{df['cik'].nunique():,}"],
            ["Year range", f"{df['year'].min()} - {df['year'].max()}"],
            ["Mean total comp", f"${exec_df['total'].mean()/1e6:.2f}M"],
            ["Median total comp", f"${exec_df['total'].median()/1e6:.2f}M"],
            ["Max total comp", f"${exec_df['total'].max()/1e6:.1f}M"],
            ["Mean salary", f"${exec_df['salary'].mean()/1e3:.0f}K"],
        ],
        headers=["Metric", "Value"],
        title=f"Compensation Statistics (updated {today})",
        filename="stats_compensation.png",
        col_widths=[0.5, 0.3]
    )
    
    # --- Top 10 Table ---
    top_execs = exec_df.nlargest(10, 'total')[['name', 'company', 'filing_year', 'total']].copy()
    top_data = []
    for _, row in top_execs.iterrows():
        top_data.append([
            row['name'][:30],  # Truncate long names
            row['company'][:25],
            str(int(row['filing_year'])),
            f"${row['total']/1e6:.1f}M"
        ])
    
    create_table_image(
        data=top_data,
        headers=["Executive", "Company", "Year", "Total"],
        title=f"🏆 Top 10 Highest Paid (updated {today})",
        filename="stats_top10.png",
        col_widths=[0.35, 0.35, 0.1, 0.2]
    )
    
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
    
    create_table_image(
        data=breakdown_data,
        headers=["Component", "Mean", "Median", "Max"],
        title=f"Compensation Breakdown (updated {today})",
        filename="stats_breakdown.png",
        col_widths=[0.35, 0.2, 0.2, 0.2],
        highlight_last=True
    )
    
    # =========================================================================
    # 4. Generate Charts
    # =========================================================================
    print("\n[4/4] Generating charts...")
    
    # --- Pie Chart: Document Breakdown ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    labels1 = ['Funds\n(no exec comp)', 'With SCT', 'No SCT']
    sizes1 = [funds, with_sct, no_sct]
    colors1 = ['#95a5a6', '#27ae60', '#e74c3c']
    axes[0].pie(sizes1, labels=labels1, autopct='%1.1f%%', colors=colors1, startangle=90)
    axes[0].set_title(f'Document Breakdown (n={total_docs:,})', fontsize=14, fontweight='bold')
    
    labels2 = ['Single table', 'Multiple tables']
    single_docs = with_sct - multi_table
    sizes2 = [single_docs, multi_table]
    colors2 = ['#3498db', '#9b59b6']
    axes[1].pie(sizes2, labels=labels2, autopct='%1.1f%%', colors=colors2, startangle=90)
    axes[1].set_title(f'Documents with SCT (n={with_sct:,})', fontsize=14, fontweight='bold')
    
    plt.suptitle(f'Updated: {today}', fontsize=10, color='gray')
    plt.tight_layout()
    plt.savefig(DOCS_PATH / 'chart_pipeline.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✓ chart_pipeline.png")
    
    # --- Bar Chart: Tables by Year ---
    if len(df) > 0:
        year_counts = df['year'].value_counts().sort_index()
        
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
        plt.savefig(DOCS_PATH / 'chart_by_year.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("  ✓ chart_by_year.png")
    
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
        plt.savefig(DOCS_PATH / 'chart_distribution.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("  ✓ chart_distribution.png")
    
    # --- Line Chart: Trends Over Time ---
    if len(exec_df) > 0:
        yearly_comp = exec_df.groupby('filing_year')['total'].agg(['mean', 'median']).reset_index()
        
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(yearly_comp['filing_year'], yearly_comp['mean'] / 1e6, 
                marker='o', linewidth=2, label='Mean', color='#3498db')
        ax.plot(yearly_comp['filing_year'], yearly_comp['median'] / 1e6, 
                marker='s', linewidth=2, label='Median', color='#e74c3c')
        
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Total Compensation ($ millions)', fontsize=12)
        ax.set_title(f'Executive Compensation Trends Over Time (updated {today})', fontsize=14, fontweight='bold')
        ax.legend()
        ax.set_xticks(yearly_comp['filing_year'])
        ax.set_xticklabels(yearly_comp['filing_year'].astype(int), rotation=45)
        
        plt.tight_layout()
        plt.savefig(DOCS_PATH / 'chart_trends.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("  ✓ chart_trends.png")
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"\nGenerated images in {DOCS_PATH}:")
    for f in sorted(DOCS_PATH.glob("*.png")):
        print(f"  - {f.name}")
    
    print(f"\nTo update READMEs, run:")
    print(f"  git add docs/*.png && git commit -m 'Update stats' && git push")
    print(f"  python scripts/to_hf.py --push")


if __name__ == "__main__":
    main()
