"""Visualization utilities for extracted table results."""

from pathlib import Path
from typing import Any, Optional
from IPython.display import display, HTML, Markdown
import json

# ============== CONFIGURATION ==============
DISPLAY_MAX_WIDTH = 1000
PREVIEW_MAX_WIDTH = 800


def display_extraction_result(
    extracted_item: Any,
    found_table: dict,
    metadata: dict,
    base_path: Path,
    pil_image_class: Any = None
) -> None:
    """
    Display a single extraction result with image, JSON, and links.
    """
    source_doc = found_table['table']['source_doc']
    
    # Links
    filing_index = metadata.get('filing_html_index', '')
    filing_htm = metadata.get('filing_htm', '')
    filing_txt = metadata.get('filing_txt', '')
    
    links_html = f"""
    <p><a href="{filing_index}" target="_blank">📋 Index</a> | 
    <a href="{filing_htm}" target="_blank">🌐 HTM</a> | 
    <a href="{filing_txt}" target="_blank">📝 TXT</a></p>
    """
    display(HTML(links_html))
    
    # Image
    img_path = found_table['table'].get('img_path', '')
    if img_path and pil_image_class:
        full_img_path = base_path / "output" / source_doc / source_doc / "vlm" / img_path
        if full_img_path.exists():
            img = pil_image_class.open(full_img_path)
            if img.width > DISPLAY_MAX_WIDTH:
                ratio = DISPLAY_MAX_WIDTH / img.width
                img = img.resize((DISPLAY_MAX_WIDTH, int(img.height * ratio)))
            display(img)
    
    # JSON
    if hasattr(extracted_item, 'model_dump'):
        data = extracted_item.model_dump()
    elif isinstance(extracted_item, dict):
        data = extracted_item
    else:
        data = {"raw": str(extracted_item)}
    
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
    """Display all extraction results."""
    for i, (extracted, found) in enumerate(zip(extracted_list, found_tables)):
        display(HTML(f"<h3>Table {i + 1}</h3>"))
        display_extraction_result(
            extracted_item=extracted,
            found_table=found,
            metadata=metadata,
            base_path=base_path,
            pil_image_class=pil_image_class
        )
        display(HTML("<hr/>"))


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
            if img.width > PREVIEW_MAX_WIDTH:
                ratio = PREVIEW_MAX_WIDTH / img.width
                img = img.resize((PREVIEW_MAX_WIDTH, int(img.height * ratio)))
            display(img)
    
    if show_html:
        table_body = table.get('table_body', '')
        if table_body:
            display(HTML("<h5>HTML Preview:</h5>"))
            display(HTML(f"<div style='max-height: 300px; overflow: auto;'>{table_body}</div>"))
