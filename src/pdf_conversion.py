from pathlib import Path
import requests
import pdfkit
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
import tempfile
import os
import json
from tqdm import tqdm
from datetime import datetime, date


def json_serial(obj):
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def html_to_pdf(url: str, output_path: str) -> bool:
    """Convert HTML to PDF."""
    try:
        headers = {"User-Agent": "Research Bot"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(response.text)
            temp_path = f.name
        
        options = {
            'disable-external-links': '',
            'no-images': '',
            'disable-javascript': '',
            'load-error-handling': 'ignore',
            'load-media-error-handling': 'ignore',
            'page-size': 'A4',
            'orientation': 'Portrait',
        }
        
        pdfkit.from_file(temp_path, output_path, options=options)
        Path(temp_path).unlink()
        return True
    except Exception as e:
        print(f"Error converting HTML: {e}")
        return False


def txt_to_pdf(url: str, output_path: str) -> bool:
    """Convert TXT to PDF via image rendering."""
    try:
        headers = {"User-Agent": "Research Bot"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        lines = response.text.split('\n')
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
        except:
            font = ImageFont.load_default()
        
        char_width = 6
        line_height = 12
        max_line_len = max(len(line) for line in lines) if lines else 80
        img_width = max(max_line_len * char_width + 40, 1200)
        lines_per_page = 80
        
        pages = [lines[i:i+lines_per_page] for i in range(0, len(lines), lines_per_page)]
        temp_images = []
        
        for page_num, page_lines in enumerate(pages):
            img_height = len(page_lines) * line_height + 40
            img = Image.new('RGB', (img_width, img_height), 'white')
            draw = ImageDraw.Draw(img)
            
            y = 20
            for line in page_lines:
                draw.text((20, y), line, font=font, fill='black')
                y += line_height
            
            temp_path = f"/tmp/page_{page_num}.png"
            img.save(temp_path)
            temp_images.append(temp_path)
        
        c = canvas.Canvas(output_path, pagesize=landscape(letter))
        page_width, page_height = landscape(letter)
        
        for img_path in temp_images:
            img = Image.open(img_path)
            img_w, img_h = img.size
            scale = min(page_width / img_w, page_height / img_h) * 0.95
            new_w, new_h = img_w * scale, img_h * scale
            x = (page_width - new_w) / 2
            y = (page_height - new_h) / 2
            c.drawImage(img_path, x, y, new_w, new_h)
            c.showPage()
        
        c.save()
        
        for img_path in temp_images:
            os.remove(img_path)
        
        return True
    except Exception as e:
        print(f"Error converting TXT: {e}")
        return False


def get_doc_id(doc) -> str:
    """Generate unique document ID from cik, year and accession_number."""
    return f"{doc['cik']}_{doc['year']}_{doc['accession_number']}"


def convert_docs_to_pdf(docs, text_fields: set = {'text'}):
    """Convert all docs to PDF and save metadata."""
    for i, doc in enumerate(tqdm(docs)):
        doc_id = get_doc_id(doc)
        pdf_path = f"pdfs/{doc_id}.pdf"
        output_dir = Path(f"output/{doc_id}")
        
        # Salva metadati (escludendo campo text)
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata = {k: v for k, v in doc.items() if k not in text_fields}
        metadata_path = output_dir / "metadata.json"
        if not metadata_path.exists():
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=json_serial)
        
        if Path(pdf_path).exists():
            continue
        
        # Try HTML first, then TXT
        if doc['htm_filing_link'] != 'NULL':
            success = html_to_pdf(doc['htm_filing_link'], pdf_path)
        else:
            success = txt_to_pdf(doc['complete_text_filing_link'], pdf_path)
        
        if not success:
            print(f"Failed: {doc['cik']} {doc['year']}")
