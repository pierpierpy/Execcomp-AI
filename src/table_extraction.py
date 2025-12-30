# Logica per estrarre tabelle da MinerU output e trasformarle in JSON strutturato

from typing import Optional, Tuple, List, Dict
from pathlib import Path
import json


def extract_tables_from_output(output_path: Path = Path("output"), save_path: str = "all_tables.json") -> Tuple[List[Dict], Dict]:
    """Extract all tables from MinerU output.
    
    Returns:
        Tuple of (all_tables, stats) where stats contains processing details
    """
    all_tables = []
    
    stats = {
        'total_dirs': 0,
        'processed': [],      # Docs with content_list.json
        'no_mineru_output': [],  # Docs without content_list.json (MinerU didn't run/failed)
        'no_tables': [],      # Docs processed by MinerU but with 0 tables
        'with_tables': [],    # Docs with at least 1 table
    }

    all_dirs = [d for d in output_path.iterdir() if d.is_dir()]
    stats['total_dirs'] = len(all_dirs)
    
    for output_dir in all_dirs:
        content_files = list(output_dir.rglob("*_content_list.json"))
        
        if not content_files:
            stats['no_mineru_output'].append(output_dir.name)
            continue
        
        stats['processed'].append(output_dir.name)
        
        with open(content_files[0]) as f:
            data = json.load(f)
        
        tables = [item for item in data if item.get('type') == 'table']
        
        if len(tables) == 0:
            stats['no_tables'].append(output_dir.name)
        else:
            stats['with_tables'].append(output_dir.name)
        
        for t in tables:
            t['source_doc'] = output_dir.name
            all_tables.append(t)

    # Print summary
    print(f"=== Extraction Summary ===")
    print(f"Total output directories: {stats['total_dirs']}")
    print(f"  - MinerU processed: {len(stats['processed'])}")
    print(f"  - MinerU NOT processed (no content_list.json): {len(stats['no_mineru_output'])}")
    print(f"")
    print(f"Of processed documents:")
    print(f"  - With tables: {len(stats['with_tables'])}")
    print(f"  - Without tables: {len(stats['no_tables'])}")
    print(f"")
    print(f"Total tables extracted: {len(all_tables)}")
    
    if stats['no_mineru_output']:
        print(f"\n⚠️  Documents NOT processed by MinerU:")
        for doc in sorted(stats['no_mineru_output']):
            print(f"    - {doc}")
    
    if stats['no_tables']:
        print(f"\n📄 Documents with 0 tables:")
        for doc in sorted(stats['no_tables']):
            print(f"    - {doc}")

    # Save all tables
    with open(save_path, "w") as f:
        json.dump(all_tables, f, indent=2)
    
    return all_tables, stats


