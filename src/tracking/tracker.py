"""
Pipeline Tracker - Central tracking system for document processing status.

Usage:
    from src.tracking import Tracker
    
    tracker = Tracker()
    tracker.set_phase("doc_id", "mineru_done")
    tracker.get_pending("classified")  # docs with mineru but no classification
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


class Tracker:
    def __init__(self, base_path: Path = None):
        if base_path is None:
            base_path = Path(__file__).parent.parent.parent.resolve()
        self.base_path = base_path
        self.tracker_file = base_path / "pipeline_tracker.json"
        self.output_path = base_path / "output"
        self._data = None
    
    @property
    def data(self) -> dict:
        if self._data is None:
            self.load()
        return self._data
    
    def load(self):
        """Load tracker from file."""
        if self.tracker_file.exists():
            with open(self.tracker_file) as f:
                self._data = json.load(f)
        else:
            self._data = {"last_updated": None, "documents": {}}
    
    def save(self):
        """Save tracker to file."""
        self._data["last_updated"] = datetime.now().isoformat()
        with open(self.tracker_file, "w") as f:
            json.dump(self._data, f, indent=2)
    
    # -------------------------------------------------------------------------
    # Document operations
    # -------------------------------------------------------------------------
    
    def add_document(self, doc_id: str, metadata: dict):
        """Add a new document to the tracker."""
        if doc_id in self.data["documents"]:
            return  # Already exists
        
        self.data["documents"][doc_id] = {
            "cik": metadata.get("cik"),
            "company_name": metadata.get("company_name"),
            "year": metadata.get("year"),
            "accession_number": metadata.get("accession_number"),
            "sic": metadata.get("sic"),
            "phases": {},
            "status": "pending",
            "sct_tables": []
        }
    
    def get_document(self, doc_id: str) -> Optional[dict]:
        """Get document info."""
        return self.data["documents"].get(doc_id)
    
    def set_phase(self, doc_id: str, phase: str, timestamp: str = None):
        """Mark a phase as complete for a document."""
        if doc_id not in self.data["documents"]:
            return
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        self.data["documents"][doc_id]["phases"][phase] = timestamp
    
    def has_phase(self, doc_id: str, phase: str) -> bool:
        """Check if document has completed a phase."""
        doc = self.data["documents"].get(doc_id)
        if not doc:
            return False
        return phase in doc.get("phases", {})
    
    def set_status(self, doc_id: str, status: str):
        """Set final status: 'complete', 'no_sct', 'fund', 'pending'."""
        if doc_id in self.data["documents"]:
            self.data["documents"][doc_id]["status"] = status
    
    def set_sct_tables(self, doc_id: str, table_paths: List[str]):
        """Set the SCT table image paths."""
        if doc_id in self.data["documents"]:
            self.data["documents"][doc_id]["sct_tables"] = table_paths
    
    # -------------------------------------------------------------------------
    # Query operations
    # -------------------------------------------------------------------------
    
    def get_by_status(self, status: str) -> List[str]:
        """Get all doc_ids with a specific status."""
        return [
            doc_id for doc_id, doc in self.data["documents"].items()
            if doc.get("status") == status
        ]
    
    def get_pending(self, phase: str) -> List[str]:
        """Get docs that need a specific phase (previous phase done, this one not)."""
        phase_order = ["pdf_created", "mineru_done", "classified", "extracted"]
        
        if phase not in phase_order:
            return []
        
        phase_idx = phase_order.index(phase)
        prev_phase = phase_order[phase_idx - 1] if phase_idx > 0 else None
        
        pending = []
        for doc_id, doc in self.data["documents"].items():
            phases = doc.get("phases", {})
            
            # Skip funds for phases after pdf_created
            if phase != "pdf_created" and doc.get("sic") in ("NULL", None):
                continue
            
            # Check if previous phase done (or no previous phase)
            if prev_phase and prev_phase not in phases:
                continue
            
            # Check if this phase not done
            if phase not in phases:
                pending.append(doc_id)
        
        return pending
    
    def get_all_doc_ids(self) -> List[str]:
        """Get all tracked doc_ids."""
        return list(self.data["documents"].keys())
    
    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------
    
    def stats(self) -> dict:
        """Get summary statistics."""
        docs = self.data["documents"]
        
        status_counts = {"complete": 0, "no_sct": 0, "fund": 0, "pending": 0}
        phase_counts = {"pdf_created": 0, "mineru_done": 0, "classified": 0, "extracted": 0}
        
        for doc in docs.values():
            status = doc.get("status", "pending")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            for phase in doc.get("phases", {}):
                phase_counts[phase] = phase_counts.get(phase, 0) + 1
        
        return {
            "total": len(docs),
            "by_status": status_counts,
            "by_phase": phase_counts
        }
    
    def print_stats(self):
        """Print a nice summary."""
        s = self.stats()
        print()
        print("=" * 50)
        print("PIPELINE TRACKER STATUS")
        print("=" * 50)
        print(f"Total documents: {s['total']:,}")
        print()
        print("By status:")
        print(f"  Complete (with SCT): {s['by_status'].get('complete', 0):,}")
        print(f"  No SCT found:        {s['by_status'].get('no_sct', 0):,}")
        print(f"  Funds (skipped):     {s['by_status'].get('fund', 0):,}")
        print(f"  Pending:             {s['by_status'].get('pending', 0):,}")
        print()
        print("By phase completed:")
        print(f"  [1] PDF created:     {s['by_phase'].get('pdf_created', 0):,}")
        print(f"  [2] MinerU done:     {s['by_phase'].get('mineru_done', 0):,}")
        print(f"  [3] VLM processed:   {s['by_phase'].get('extracted', 0):,}")
        print(f"      → Found SCT:     {s['by_status'].get('complete', 0):,}")
        print(f"      → No SCT:        {s['by_status'].get('no_sct', 0):,}")
        print("=" * 50)
    
    # -------------------------------------------------------------------------
    # Rebuild from files
    # -------------------------------------------------------------------------
    
    def rebuild_from_files(self):
        """Rebuild tracker by scanning existing output folders."""
        print("Rebuilding tracker from files...")
        
        self._data = {"last_updated": None, "documents": {}}
        
        folders = [d for d in self.output_path.iterdir() if d.is_dir()]
        
        for folder in folders:
            doc_id = folder.name
            
            # Load metadata
            meta_path = folder / "metadata.json"
            if not meta_path.exists():
                continue
            
            with open(meta_path) as f:
                meta = json.load(f)
            
            # Determine phases
            phases = {}
            phases["pdf_created"] = meta.get("created_at", datetime.now().isoformat())
            
            # Check MinerU
            if list(folder.rglob("*_content_list.json")):
                phases["mineru_done"] = datetime.now().isoformat()
            
            # Check classification
            class_path = folder / "classification_results.json"
            if class_path.exists():
                phases["classified"] = datetime.now().isoformat()
            
            # Check extraction
            extract_path = folder / "extraction_results.json"
            no_sct_path = folder / "no_sct_found.json"
            
            if extract_path.exists() or no_sct_path.exists():
                phases["extracted"] = datetime.now().isoformat()
            
            # Determine status
            sic = meta.get("sic")
            if sic in ("NULL", None):
                status = "fund"
            elif extract_path.exists():
                status = "complete"
            elif no_sct_path.exists():
                status = "no_sct"
            else:
                status = "pending"
            
            # Get SCT tables
            sct_tables = []
            if class_path.exists():
                with open(class_path) as f:
                    class_data = json.load(f)
                sct_tables = [t.get("image_path", "") for t in class_data.get("tables", [])]
            
            # Add to tracker
            self._data["documents"][doc_id] = {
                "cik": meta.get("cik"),
                "company_name": meta.get("company_name"),
                "year": meta.get("year"),
                "accession_number": meta.get("accession_number"),
                "sic": sic,
                "phases": phases,
                "status": status,
                "sct_tables": sct_tables
            }
        
        self.save()
        print(f"✓ Rebuilt tracker with {len(self._data['documents'])} documents")
