"""Save classification and extraction results to JSON files."""

import json
from pathlib import Path
from datetime import datetime
from typing import Any


def json_serial(obj: Any) -> str:
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def save_classification_results(
    found_tables: list[dict],
    output_path: Path,
    metadata: dict = None
) -> Path:
    """
    Save classification results to JSON.
    
    Args:
        found_tables: List of classified tables with their metadata
        output_path: Directory where to save the results
        metadata: Optional additional metadata to include
        
    Returns:
        Path to the saved JSON file
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_tables_found": len(found_tables),
        "metadata": metadata or {},
        "tables": found_tables
    }
    
    save_path = output_path / "classification_results.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=json_serial)
    
    print(f"💾 Classification results saved to: {save_path}")
    return save_path


def save_extraction_results(
    extracted_data: list[dict],
    output_path: Path,
    metadata: dict = None
) -> Path:
    """
    Save extraction results to JSON.
    
    Args:
        extracted_data: List of extracted SummaryCompensationTable data
        output_path: Directory where to save the results
        metadata: Optional additional metadata to include
        
    Returns:
        Path to the saved JSON file
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Convert Pydantic models to dicts if needed
    serializable_data = []
    for item in extracted_data:
        if hasattr(item, 'model_dump'):
            serializable_data.append(item.model_dump())
        elif isinstance(item, dict):
            serializable_data.append(item)
        else:
            serializable_data.append(str(item))
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_extracted": len(serializable_data),
        "metadata": metadata or {},
        "data": serializable_data
    }
    
    save_path = output_path / "extraction_results.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=json_serial)
    
    print(f"💾 Extraction results saved to: {save_path}")
    return save_path
