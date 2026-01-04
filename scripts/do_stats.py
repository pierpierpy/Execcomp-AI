#!/usr/bin/env python3
"""
Regenerate statistics images from processed documents.

Usage:
    python scripts/regenerate_stats.py
"""

from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis import generate_stats_images
from src.tracking import Tracker


def main():
    project_root = Path(__file__).parent.parent
    tracker = Tracker(project_root)
    
    output_path = project_root / "output"
    docs_path = project_root / "docs"
    
    print("Regenerating statistics...")
    result = generate_stats_images(output_path, docs_path, tracker)
    print(f"Generated {len(result)} images in {docs_path}")
    
    for img in result:
        print(f"  - {img.name}")


if __name__ == "__main__":
    main()
