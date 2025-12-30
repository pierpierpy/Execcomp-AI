"""Visualization utilities for extracted table results."""

from pathlib import Path
from typing import Any, Optional
from IPython.display import display, HTML, Markdown
import json


def display_extraction_result(
    extracted_item: Any,
    found_table: dict,
    metadata: dict,
    base_path: Path,
    pil_image_class: Any = None
) -> None:
    """
    Display a single extraction result with image, JSON, and links.
    
    Args:
        extracted_item: The extracted SummaryCompensationTable (Pydantic model or dict)
        found_table: The found table dict with classification info
        metadata: Document metadata with filing URLs
        base_path: Base path for resolving image paths
        pil_image_class: PIL.Image class for displaying images
    """
    source_doc = found_table['table']['source_doc']
    
    # Build SEC filing links
    filing_index = metadata.get('filing_html_index', '')
    filing_htm = metadata.get('filing_htm', '')
    filing_txt = metadata.get('filing_txt', '')
    
    # Header with document info
    header_html = f"""
    <div style="background: #f0f4f8; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
        <h3 style="margin: 0 0 10px 0;">📄 {metadata.get('company_name', source_doc)}</h3>
        <p style="margin: 5px 0; color: #666;">
            <strong>CIK:</strong> {metadata.get('cik', 'N/A')} | 
            <strong>Year:</strong> {metadata.get('year', 'N/A')} |
            <strong>SIC:</strong> {metadata.get('sic', 'N/A')}
        </p>
        <p style="margin: 5px 0;">
            <a href="{filing_index}" target="_blank">📋 Filing Index</a> | 
            <a href="{filing_htm}" target="_blank">🌐 HTM</a> | 
            <a href="{filing_txt}" target="_blank">📝 TXT</a>
        </p>
    </div>
    """
    display(HTML(header_html))
    
    # Display table image
    img_path = found_table['table'].get('img_path', '')
    if img_path and pil_image_class:
        # MinerU nested structure: output/doc/doc/vlm/
        full_img_path = base_path / "output" / source_doc / source_doc / "vlm" / img_path
        
        if full_img_path.exists():
            is_merged = found_table.get('merged', False)
            merge_label = " (📎 Merged)" if is_merged else ""
            
            display(HTML(f"<h4>🖼️ Table Image{merge_label}</h4>"))
            img = pil_image_class.open(full_img_path)
            
            # Resize if too large
            max_width = 1000
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)))
            
            display(img)
        else:
            display(HTML(f"<p style='color: orange;'>⚠️ Image not found: {full_img_path}</p>"))
    
    # Classification info
    classification = found_table.get('classification', {})
    if classification:
        conf = classification.get('confidence', 'N/A')
        reason = classification.get('reason', 'N/A')
        display(HTML(f"""
        <div style="background: #e8f5e9; padding: 10px; border-radius: 5px; margin: 10px 0;">
            <strong>✅ Classification:</strong> {classification.get('table_type', 'N/A')} 
            (confidence: {conf}) <br/>
            <em>{reason}</em>
        </div>
        """))
    
    # Extracted JSON
    display(HTML("<h4>📊 Extracted Data</h4>"))
    
    if hasattr(extracted_item, 'model_dump'):
        data = extracted_item.model_dump()
    elif isinstance(extracted_item, dict):
        data = extracted_item
    else:
        data = {"raw": str(extracted_item)}
    
    # Pretty JSON display
    json_html = f"""
    <pre style="background: #1e1e1e; color: #d4d4d4; padding: 15px; 
                border-radius: 5px; overflow-x: auto; font-size: 12px;">
{json.dumps(data, indent=2, ensure_ascii=False)}
    </pre>
    """
    display(HTML(json_html))


def display_all_results(
    extracted_list: list,
    found_tables: list,
    metadata: dict,
    base_path: Path,
    pil_image_class: Any = None
) -> None:
    """
    Display all extraction results for a document.
    
    Args:
        extracted_list: List of extracted SummaryCompensationTable items
        found_tables: List of found table dicts
        metadata: Document metadata
        base_path: Base path for resolving paths
        pil_image_class: PIL.Image class
    """
    display(HTML(f"<h2>📑 Extraction Results ({len(extracted_list)} tables)</h2>"))
    display(HTML("<hr/>"))
    
    for i, (extracted, found) in enumerate(zip(extracted_list, found_tables)):
        display(HTML(f"<h3>Table {i + 1} / {len(extracted_list)}</h3>"))
        display_extraction_result(
            extracted_item=extracted,
            found_table=found,
            metadata=metadata,
            base_path=base_path,
            pil_image_class=pil_image_class
        )
        display(HTML("<hr style='border: 2px dashed #ccc; margin: 20px 0;'/>"))


def display_table_preview(
    table: dict,
    base_path: Path,
    pil_image_class: Any = None,
    show_html: bool = False
) -> None:
    """
    Quick preview of a single table (image + optional HTML).
    
    Args:
        table: Table dict from all_tables
        base_path: Base path
        pil_image_class: PIL.Image class
        show_html: Whether to show the HTML table body
    """
    source_doc = table.get('source_doc', '')
    img_path = table.get('img_path', '')
    page_idx = table.get('page_idx', 'N/A')
    
    display(HTML(f"""
    <div style="background: #fff3e0; padding: 10px; border-radius: 5px;">
        <strong>📄 {source_doc}</strong> | Page: {page_idx}
    </div>
    """))
    
    if img_path and pil_image_class:
        full_path = base_path / "output" / source_doc / source_doc / "vlm" / img_path
        if full_path.exists():
            img = pil_image_class.open(full_path)
            max_width = 800
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)))
            display(img)
    
    if show_html:
        table_body = table.get('table_body', '')
        if table_body:
            display(HTML("<h5>HTML Preview:</h5>"))
            display(HTML(f"<div style='max-height: 300px; overflow: auto;'>{table_body}</div>"))
