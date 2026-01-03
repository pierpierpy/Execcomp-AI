import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import threading

# ============== CONFIGURATION ==============
PDFS_DIR = "pdfs"
OUTPUT_DIR = "output"
MINERU_BACKEND = "vlm-http-client"
MINERU_URL = "http://localhost:30000"
MINERU_LANG = "en"  # English for SEC documents
DEFAULT_MAX_CONCURRENT = 8  # Reduced from higher values for better throughput


def is_mineru_processed(output_dir: Path) -> bool:
    """Check if MinerU has already processed this document."""
    content_files = list(output_dir.rglob("*_content_list.json"))
    return len(content_files) > 0


def process_pdf(pdf_path, output_base: Path, semaphore: threading.Semaphore):
    """Process single PDF with MinerU.
    
    Args:
        pdf_path: Path to PDF file
        output_base: Base output directory
        semaphore: Semaphore to limit concurrent requests
    
    Returns:
        tuple: (status, name, error_msg)
    """
    output_dir = output_base / pdf_path.stem
    
    if is_mineru_processed(output_dir):
        return 'skipped', pdf_path.name, None
    
    # Acquire semaphore before making request
    with semaphore:
        cmd = [
            "mineru",
            "-p", str(pdf_path),
            "-o", str(output_dir),
            "-b", MINERU_BACKEND,
            "-u", MINERU_URL,
            "-l", MINERU_LANG,  # Language for OCR
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return 'failed', pdf_path.name, result.stderr[:200] if result.stderr else "Unknown error"
        return 'success', pdf_path.name, None


def process_pdfs_with_mineru(base_path: Path = None, max_concurrent: int = DEFAULT_MAX_CONCURRENT, doc_ids: list = None):
    """Process PDFs with MinerU.
    
    Args:
        base_path: Base path for pdfs/ and output/ directories. If None, uses current dir.
        max_concurrent: Maximum number of concurrent MinerU processes
        doc_ids: List of document IDs to process. If None, processes all PDFs in pdfs/ folder.
    """
    base = Path(base_path) if base_path else Path(".")
    pdfs_dir = base / PDFS_DIR
    output_base = base / OUTPUT_DIR
    
    # Get PDF files to consider
    if doc_ids is not None:
        # Only process specific documents
        pdf_files = []
        for doc_id in doc_ids:
            pdf_path = pdfs_dir / f"{doc_id}.pdf"
            if pdf_path.exists():
                pdf_files.append(pdf_path)
        print(f"Processing {len(pdf_files)} PDFs from sample (of {len(doc_ids)} requested)")
    else:
        # Process all PDFs in folder
        pdf_files = list(pdfs_dir.glob("*.pdf"))
        print(f"Found {len(pdf_files)} PDFs total")
    
    # Check which files need processing
    to_process = []
    skipped = []
    for pdf in pdf_files:
        output_dir = output_base / pdf.stem
        if is_mineru_processed(output_dir):
            skipped.append(pdf.name)
        else:
            to_process.append(pdf)
    
    print(f"  - Already processed (skipped): {len(skipped)}")
    print(f"  - To process: {len(to_process)}")
    
    if not to_process:
        print("Nothing to process!")
        return [], []
    
    print(f"\nProcessing {len(to_process)} PDFs (max {max_concurrent} concurrent)")

    # Semaphore limits concurrent MinerU processes
    semaphore = threading.Semaphore(max_concurrent)
    
    failed = []
    success = []
    
    # Include skipped docs as success (they have content_list.json)
    for name in skipped:
        # Remove .pdf extension to get doc_id
        doc_id = name.replace('.pdf', '') if name.endswith('.pdf') else name
        success.append(doc_id)
    
    if not to_process:
        return failed, success
    
    # Use more workers than semaphore allows - they'll queue up waiting for semaphore
    with ThreadPoolExecutor(max_workers=len(to_process)) as executor:
        futures = {
            executor.submit(process_pdf, pdf, output_base, semaphore): pdf 
            for pdf in to_process
        }
        
        for future in tqdm(as_completed(futures), total=len(to_process)):
            status, name, error = future.result()
            # Remove .pdf extension to get doc_id
            doc_id = name.replace('.pdf', '') if name.endswith('.pdf') else name
            if status == 'failed':
                failed.append((doc_id, error))
            elif status == 'success':
                success.append(doc_id)
    
    print(f"\n=== Processing Complete ===")
    print(f"Success: {len(success)} (including {len(skipped)} already processed)")
    print(f"Failed: {len(failed)}")
    
    if failed:
        print(f"\n❌ Failed documents:")
        for name, error in failed:
            print(f"  - {name}")
            if error:
                print(f"    Error: {error[:100]}...")
    
    return failed, success
