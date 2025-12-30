# Logica per estrarre tabelle da MinerU output e trasformarle in JSON strutturato

from typing import Optional, Tuple, List, Dict
from pathlib import Path
import json
from PIL import Image


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


def merge_consecutive_tables(found: list[dict], images_base_dir: Path, all_tables: list[dict], all_classifications: dict, debug: bool = False) -> list[dict]:
    """
    Merge tables split across pages using header detection.
    
    Two merge cases:
    1. is_header_only=True: Table has only header, merge with subsequent tables without header
    2. has_header=True (with data): Table has header + data, merge with subsequent tables without header
    
    In both cases, merge continues until we find a table with has_header=True (new table starts)
    
    Args:
        found: List of classified summary_compensation tables
        images_base_dir: Path to images directory
        all_tables: ALL tables from the document (to find adjacent non-classified tables)
        all_classifications: Dict mapping (page_idx, bbox) -> classification for ALL tables
        debug: If True, print detailed merge information
    
    Returns:
        List with merged tables where applicable
    """
    if len(found) == 0:
        return found
    
    # Get source doc from first found table
    source_doc = found[0]['table']['source_doc']
    
    # Get all tables from this document, sorted by page and vertical position
    doc_tables = sorted(
        [t for t in all_tables if t.get('source_doc') == source_doc],
        key=lambda x: (x.get('page_idx', 0), x.get('bbox', [0, 0, 0, 0])[1])
    )
    
    merged_results = []
    processed_indices = set()
    
    for f_idx, f in enumerate(found):
        if f_idx in processed_indices:
            continue
        
        classification = f.get('classification', {})
        is_header_only = classification.get('is_header_only', False)
        has_header = classification.get('has_header', True)
        
        # Check if this table can start a merge:
        # Case 1: is_header_only=True (only header, no data)
        # Case 2: has_header=True (has header with data)
        should_try_merge = is_header_only or has_header
        
        if not should_try_merge:
            # No header, keep as-is
            merged_results.append(f)
            continue
        
        # This table has a header - look for data tables to merge
        header_table = f['table']
        header_page = header_table.get('page_idx', 0)
        header_bbox = header_table.get('bbox', [0, 0, 0, 0])
        header_bottom = header_bbox[3]  # y2 coordinate (bottom of header)
        
        # Find the index of this table in all doc_tables
        header_idx_in_doc = None
        for i, dt in enumerate(doc_tables):
            if (dt.get('page_idx') == header_page and 
                dt.get('bbox') == header_bbox):
                header_idx_in_doc = i
                break
        
        if header_idx_in_doc is None:
            merged_results.append(f)
            continue
        
        # Collect tables to merge
        tables_to_merge = [header_table]
        last_merged_page = header_page
        last_merged_bottom = header_bottom
        
        if debug:
            merge_type = "is_header_only=True" if is_header_only else "has_header=True"
            print(f"\n🔍 Starting merge from table {f['index']} (page {header_page}, {merge_type})")
        
        # Track if we actually merged anything
        merged_any = False
        
        # Look at subsequent tables in doc_tables
        for next_idx in range(header_idx_in_doc + 1, len(doc_tables)):
            next_table = doc_tables[next_idx]
            next_page = next_table.get('page_idx', 0)
            next_bbox = next_table.get('bbox', [0, 0, 0, 0])
            next_top = next_bbox[1]  # y1 coordinate (top of next table)
            
            # Calculate vertical distance
            if next_page == last_merged_page:
                # Same page: distance from bottom of last to top of next
                distance = next_top - last_merged_bottom
            elif next_page == last_merged_page + 1 and next_top < 150:
                # Next page, table at top: consider it close
                distance = 0
            else:
                # Too far (different page, not at top)
                if debug:
                    print(f"   ❌ Table on page {next_page} too far (not adjacent page or not at top)")
                break
            
            # Check distance threshold first
            DISTANCE_THRESHOLD = 200
            if distance > DISTANCE_THRESHOLD:
                if debug:
                    print(f"   ❌ Distance {distance:.0f}px > {DISTANCE_THRESHOLD}px threshold")
                break
            
            # Look up classification from all_classifications
            next_key = (next_page, tuple(next_bbox))
            next_classification = all_classifications.get(next_key, {})
            has_header = next_classification.get('has_header', True)  # Default True = stop
            
            if debug:
                print(f"   📋 Next table page {next_page}, distance={distance:.0f}px, has_header={has_header}")
            
            # If this table has a header, it's a new table - stop merging
            if has_header:
                if debug:
                    print(f"   ⛔ Stopping: next table has header (new table starts)")
                break
            
            # Add this table to merge list
            tables_to_merge.append(next_table)
            last_merged_page = next_page
            last_merged_bottom = next_bbox[3]
            if debug:
                print(f"   ✅ Added to merge (has_header=False)")
        
        # Now merge all collected tables
        if len(tables_to_merge) == 1:
            # Only header, nothing to merge
            if debug:
                print(f"   ℹ️ No tables to merge, keeping as-is")
            merged_results.append(f)
        else:
            # Merge images and HTML
            merged_images = []
            merged_html_parts = []
            
            for t in tables_to_merge:
                img_path = images_base_dir / t.get('img_path', '')
                if img_path.exists():
                    merged_images.append(Image.open(img_path))
                
                html = t.get('table_body', '')
                # Remove table tags for concatenation
                html = html.replace('<table>', '').replace('</table>', '')
                merged_html_parts.append(html)
            
            # Combine images vertically
            if merged_images:
                max_width = max(img.width for img in merged_images)
                total_height = sum(img.height for img in merged_images)
                combined_img = Image.new('RGB', (max_width, total_height), 'white')
                
                y_offset = 0
                for img in merged_images:
                    combined_img.paste(img, (0, y_offset))
                    y_offset += img.height
                
                # Save merged image
                merged_name = f"merged_{f['index']}.jpg"
                combined_img.save(images_base_dir / merged_name)
            else:
                merged_name = header_table.get('img_path', '')
            
            # Combine HTML
            merged_html = '<table>' + ''.join(merged_html_parts) + '</table>'
            
            # Create merged entry
            merged_entry = f.copy()
            merged_entry['table'] = header_table.copy()
            merged_entry['table']['img_path'] = merged_name
            merged_entry['table']['table_body'] = merged_html
            merged_entry['merged'] = True
            merged_entry['merged_count'] = len(tables_to_merge)
            
            merged_results.append(merged_entry)
            
            pages_merged = sorted(set(t.get('page_idx', 0) for t in tables_to_merge))
            if debug:
                print(f"📎 Merged {len(tables_to_merge)} tables (pages {pages_merged})")
    
    return merged_results