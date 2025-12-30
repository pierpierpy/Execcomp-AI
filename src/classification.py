import base64
from pathlib import Path
from typing import Optional
from openai import AsyncOpenAI
import json
import textwrap

from .prompts import CLASSIFICATION_PROMPT
from .schemas import TableType, TableClassification


def load_image_b64(img_path: Path) -> Optional[str]:
    """Load image as base64 string."""
    if img_path.exists():
        with open(img_path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return None


# 5. Funzione di classificazione (aggiornata)
async def classify_table(table: dict, images_base_dir: Path, client: AsyncOpenAI, model: str) -> TableClassification:
    """Classify a single table using VLM with image."""
    
    caption = table.get('table_caption', [''])[0] if table.get('table_caption') else ''
    footnotes = ' '.join(table.get('table_footnote', []))
    body = table.get('table_body', '')[:2000]
    
    prompt = CLASSIFICATION_PROMPT.format(
        caption=caption,
        footnotes=footnotes,
        table_body=body
    )
    
    content = [{"type": "text", "text": prompt}]
    
    # Solo se img_path esiste e non è vuoto
    img_path_str = table.get('img_path', '')
    if img_path_str:
        img_path = images_base_dir / img_path_str
        if img_path.exists() and img_path.is_file():
            img_b64 = load_image_b64(img_path)
            if img_b64:
                content.append({
                    "type": "image_url", 
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
    
    r = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=2000,
        temperature=0.0,
        extra_body={"guided_json": TableClassification.model_json_schema()}
    )
    
    return TableClassification.model_validate_json(r.choices[0].message.content)


def load_doc_metadata(doc_source: str, base_path: Path) -> Optional[dict]:
    """Carica i metadati dal JSON salvato nella cartella output."""
    metadata_path = base_path / f"output/{doc_source}/metadata.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            return json.load(f)
    return None


async def find_summary_compensation_in_doc(
    doc_source: str,
    all_tables: list,
    client: AsyncOpenAI,
    model: str,
    base_path: Path,
    display_func=None,
    plt_module=None,
    pil_image_class=None
):
    """
    Cerca summary compensation tables in un singolo documento.
    
    Returns:
        Tuple of (found, all_classifications) where:
        - found: list of summary_compensation tables
        - all_classifications: dict mapping (page_idx, bbox) -> classification for ALL tables
    """
    
    # Filtra tabelle di questo documento
    doc_tables = [t for t in all_tables if t.get('source_doc') == doc_source]
    print(f"Document: {doc_source}")
    print(f"Tables in document: {len(doc_tables)}")
    
    # Carica metadati dal JSON
    metadata = load_doc_metadata(doc_source, base_path)
    if metadata:
        link = metadata.get('htm_filing_link')
        if link == 'NULL':
            link = metadata.get('filing_html_index')
        print(f"SEC Link: {link}\n")
    else:
        print("Metadata not found\n")
    
    found = []
    all_classifications = {}  # Store ALL classifications
    
    for i, t in enumerate(doc_tables):
        # MinerU crea output/doc_source/doc_source/vlm/
        images_dir = base_path / f"output/{doc_source}/{doc_source}/vlm/"
        img_path = images_dir / t.get('img_path', '')
        
        # Classify
        try:
            result = await classify_table(t, images_dir, client, model)
        except Exception as e:
            print(f"Error on table {i}: {e}")
            continue
        
        # Store classification for ALL tables (not just summary_compensation)
        key = (t.get('page_idx'), tuple(t.get('bbox', [])))
        all_classifications[key] = result.model_dump()
        
        print(f"--- Table {i} (page {t.get('page_idx')}) ---")
        print(f"Type: {result.table_type.value} ({result.confidence:.2f})")
        print(f"is_header_only: {result.is_header_only} | has_header: {result.has_header}")
        
        # Formatta reason con word wrap
        print("Reason:")
        for line in textwrap.wrap(result.reason, width=80):
            print(f"  {line}")
        
        # Mostra immagine per tutte le tabelle
        if img_path.exists() and img_path.is_file():
            if display_func and plt_module and pil_image_class:
                img = pil_image_class.open(img_path)
                fig, ax = plt_module.subplots(figsize=(12, 8))
                ax.imshow(img)
                ax.axis('off')
                plt_module.tight_layout(pad=0)
                display_func(fig)
                plt_module.close(fig)
        else:
            print(f"Image not found: {img_path}")
        
        # Salva solo summary_compensation in found
        if result.table_type == TableType.SUMMARY_COMPENSATION:
            found.append({'index': i, 'table': t, 'classification': result.model_dump()})
        
        print()
    
    print(f"Found {len(found)} Summary Compensation Tables")
    return found, all_classifications
