# Fix for orphan images in MinerU output
# MinerU sometimes generates images but doesn't link them in the JSON

from pathlib import Path
from typing import Dict, Tuple, List
from PIL import Image
import json
import statistics


def get_scale_factors(content: list, vlm_dir: Path) -> Tuple[float, float]:
    """
    Calculate scale factors from tables that already have img_path.
    
    MinerU uses a constant scale factor per document to convert
    bbox coordinates to image dimensions. We calculate this factor
    from already-linked tables.
    
    Returns:
        (scale_w, scale_h): Scale factors for width and height
    """
    scale_ws = []
    scale_hs = []
    
    for item in content:
        if item.get('type') == 'table' and item.get('img_path'):
            bbox = item.get('bbox', [])
            if not bbox or len(bbox) < 4:
                continue
            
            bbox_w = bbox[2] - bbox[0]
            bbox_h = bbox[3] - bbox[1]
            
            if bbox_w <= 0 or bbox_h <= 0:
                continue
            
            img_path = vlm_dir / item['img_path']
            if not img_path.exists():
                continue
            
            img = Image.open(img_path)
            img_w, img_h = img.size
            
            scale_ws.append(img_w / bbox_w)
            scale_hs.append(img_h / bbox_h)
    
    if scale_ws and scale_hs:
        return statistics.median(scale_ws), statistics.median(scale_hs)
    return 1.65, 2.34  # Default fallback (typical values)


def fix_orphan_images(doc_dir: Path, threshold: float = 50, dry_run: bool = False) -> Dict:
    """
    Find and match orphan images to tables without img_path.
    
    Algorithm:
    1. Calculate scale factors from already-linked tables
    2. For each table without img_path, calculate expected image dimensions
    3. Match with the orphan image that has closest dimensions (error < threshold)
    
    Args:
        doc_dir: Document directory (output/doc_name/)
        threshold: Maximum error in pixels to consider a valid match
        dry_run: If True, don't modify files but show what would be done
    
    Returns:
        Dict with fix statistics
    """
    content_files = list(doc_dir.rglob("*_content_list.json"))
    if not content_files:
        return {'status': 'no_content_list', 'fixed': 0}
    
    vlm_dir = content_files[0].parent
    images_dir = vlm_dir / "images"
    
    if not images_dir.exists():
        return {'status': 'no_images_dir', 'fixed': 0}
    
    with open(content_files[0]) as f:
        content = json.load(f)
    
    # Calculate scale factors
    scale_w, scale_h = get_scale_factors(content, vlm_dir)
    
    # Find tables without img_path
    tables_no_img = [(i, item) for i, item in enumerate(content) 
                     if item.get('type') == 'table' and not item.get('img_path')]
    
    if not tables_no_img:
        return {'status': 'no_tables_to_fix', 'fixed': 0}
    
    # Find orphan images
    used_images = set(Path(item.get('img_path', '')).name for item in content if item.get('img_path'))
    orphan_paths = [f for f in sorted(images_dir.glob("*.jpg")) if f.name not in used_images]
    
    if not orphan_paths:
        return {'status': 'no_orphan_images', 'fixed': 0, 'tables_no_img': len(tables_no_img)}
    
    # Pre-load orphan image sizes
    orphan_sizes = {}
    for img_path in orphan_paths:
        img = Image.open(img_path)
        orphan_sizes[img_path] = img.size
    
    # Matching
    matches = []
    used_orphans = set()
    errors = []
    
    for idx, t in tables_no_img:
        bbox = t.get('bbox', [])
        if not bbox or len(bbox) < 4:
            continue
        
        bbox_w = bbox[2] - bbox[0]
        bbox_h = bbox[3] - bbox[1]
        expected_w = bbox_w * scale_w
        expected_h = bbox_h * scale_h
        
        # Find best match not yet used
        best_match = None
        best_error = float('inf')
        
        for img_path in orphan_paths:
            if img_path in used_orphans:
                continue
            img_w, img_h = orphan_sizes[img_path]
            error = abs(img_w - expected_w) + abs(img_h - expected_h)
            
            if error < best_error:
                best_error = error
                best_match = img_path
        
        if best_match and best_error < threshold:
            matches.append({
                'table_idx': idx,
                'page': t.get('page_idx'),
                'img_path': f"images/{best_match.name}",
                'error': best_error
            })
            used_orphans.add(best_match)
            errors.append(best_error)
            
            # Apply fix
            if not dry_run:
                content[idx]['img_path'] = f"images/{best_match.name}"
    
    # Save if not dry_run
    if not dry_run and matches:
        with open(content_files[0], 'w') as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
    
    return {
        'status': 'ok',
        'tables_no_img': len(tables_no_img),
        'orphan_images': len(orphan_paths),
        'fixed': len(matches),
        'unmatched': len(tables_no_img) - len(matches),
        'avg_error': sum(errors)/len(errors) if errors else 0,
        'max_error': max(errors) if errors else 0,
        'scale_w': scale_w,
        'scale_h': scale_h
    }


def fix_all_orphan_images(output_path: Path, threshold: float = 50, dry_run: bool = False) -> Dict:
    """
    Apply orphan image fix to all documents in output directory.
    
    Args:
        output_path: Path to output directory containing doc folders
        threshold: Maximum error in pixels for matching
        dry_run: If True, simulate without modifying files
    
    Returns:
        Dict with overall statistics
    """
    stats = {
        'docs_processed': 0,
        'docs_fixed': 0,
        'total_fixed': 0,
        'total_unmatched': 0,
        'fixed_docs': [],
        'errors': []
    }
    
    for doc_dir in sorted(output_path.iterdir()):
        if not doc_dir.is_dir():
            continue
        
        result = fix_orphan_images(doc_dir, threshold=threshold, dry_run=dry_run)
        stats['docs_processed'] += 1
        
        if result.get('fixed', 0) > 0:
            stats['docs_fixed'] += 1
            stats['total_fixed'] += result['fixed']
            stats['total_unmatched'] += result.get('unmatched', 0)
            stats['fixed_docs'].append(doc_dir.name)
            if result.get('max_error', 0) > 0:
                stats['errors'].append(result['max_error'])
    
    return stats
