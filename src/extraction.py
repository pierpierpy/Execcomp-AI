# Estrazione strutturata di dati da tabelle Summary Compensation

import base64
from pathlib import Path
from typing import Optional, List
from openai import AsyncOpenAI

from .prompts import EXTRACTION_PROMPT, EXTRACTION_PROMPT_WITH_IMAGE
from .schemas import Executive, SummaryCompensationTable


def load_image_b64(img_path: Path) -> Optional[str]:
    """Load image as base64 string."""
    if img_path.exists():
        with open(img_path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return None


async def extract_summary_compensation_table(
    table: dict,
    images_base_dir: Path,
    client: AsyncOpenAI,
    model: str,
    company: str = "",
    cik: str = "",
    filing_year: str = "",
    fiscal_year_end: str = "",
    is_merged: bool = False
) -> SummaryCompensationTable:
    """Estrae dati strutturati da una Summary Compensation Table."""
    
    caption = table.get('table_caption', [''])[0] if table.get('table_caption') else ''
    table_body = table.get('table_body', '')  # Full HTML, no truncation
    
    # Use different prompt for merged tables (with image)
    prompt_template = EXTRACTION_PROMPT_WITH_IMAGE if is_merged else EXTRACTION_PROMPT
    prompt = prompt_template.format(
        company=company or "Unknown",
        cik=cik or "Unknown",
        filing_year=filing_year or "Unknown",
        fiscal_year_end=fiscal_year_end or "Unknown",
        table_body=table_body
    )
    
    content = [{"type": "text", "text": prompt}]
    
    # Add image for merged tables (HTML may be incomplete)
    if is_merged:
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
    
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=8000,  # Increased for large tables
        temperature=0.0,
        extra_body={"guided_json": SummaryCompensationTable.model_json_schema()}
    )
    
    return SummaryCompensationTable.model_validate_json(response.choices[0].message.content)




async def extract_all_summary_compensation(
    found_tables: list,
    all_tables: list,
    client: AsyncOpenAI,
    model: str,
    base_path: Path,
    metadata: dict = None
) -> List[SummaryCompensationTable]:
    """
    Estrae dati strutturati da tutte le Summary Compensation Tables trovate.
    
    Args:
        found_tables: Lista di dict con 'index', 'table', 'result' da find_summary_compensation_in_doc
        all_tables: Lista completa delle tabelle
        client: Client AsyncOpenAI
        model: Nome del modello VLM
        base_path: Path base del progetto
        metadata: Metadata del documento (company, cik, etc.)
    
    Returns:
        Lista di SummaryCompensationTable estratte
    """
    
    results = []
    
    company = metadata.get('company', '') if metadata else ''
    cik = str(metadata.get('cik', '')) if metadata else ''
    filing_year = str(metadata.get('year', '')) if metadata else ''
    fiscal_year_end = metadata.get('fiscal_year_end', '') if metadata else ''
    
    for item in found_tables:
        table = item['table']
        doc_source = table.get('source_doc', '')
        images_dir = base_path / f"output/{doc_source}/{doc_source}/vlm/"
        is_merged = item.get('merged', False)
        
        try:
            extracted = await extract_summary_compensation_table(
                table=table,
                images_base_dir=images_dir,
                client=client,
                model=model,
                company=company,
                cik=cik,
                filing_year=filing_year,
                fiscal_year_end=fiscal_year_end,
                is_merged=is_merged
            )
            results.append(extracted)
            merged_tag = " [MERGED]" if is_merged else ""
            print(f"✓ Extracted table {item['index']}{merged_tag}: {len(extracted.executives)} executives")
        except Exception as e:
            print(f"✗ Error extracting table {item['index']}: {e}")
    
    return results
