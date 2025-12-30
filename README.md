# execcomp-ai

AI-powered pipeline to extract executive compensation data from SEC DEF 14A proxy statements.

## Overview

Extracts **Summary Compensation Tables** from 100K+ SEC filings (2005-present) using:
- **MinerU** for PDF table extraction (images + HTML)
- **Qwen3-VL-32B** for classification and structured extraction

```
SEC Filing → PDF → MinerU → Table Classification → JSON Extraction
```

## Quick Start

### 1. Start Servers

```bash
# GPU 0,1: Qwen3-VL for classification/extraction
CUDA_VISIBLE_DEVICES=0,1 vllm serve Qwen/Qwen3-VL-32B-Instruct \
    --tensor-parallel-size 2 --port 8000

# GPU 2,3: MinerU for PDF processing  
CUDA_VISIBLE_DEVICES=2,3 mineru-openai-server --engine vllm --port 30000 \
    --tensor-parallel-size 2
```

### 2. Run Pipeline

Open `pipeline.ipynb`:

```python
# Cell 2: Load documents from data/DEF14A_all.jsonl
# Cell 3: Convert to PDF + Extract tables with MinerU
# Cell 10: Run extraction on all documents
```

### 3. Create HuggingFace Dataset

Open `create_HF_ds.ipynb` to collect results and push to HF.

## Example

**Input:** [GTT Communications DEF 14A 2018](https://www.sec.gov/Archives/edgar/data/1315255/0001398344-18-006199-index.html)

**Extracted Table:**

![Sample Table](docs/sample_table.jpg)

**Output JSON:**
```json
{
  "company": "GTT Communications, Inc.",
  "executives": [
    {
      "name": "Richard D. Calder, Jr.",
      "title": "CEO and President",
      "fiscal_year": 2017,
      "salary": 525000,
      "bonus": 0,
      "stock_awards": 7184996,
      "total": 8242009
    }
  ]
}
```

## Key Features

| Challenge | Solution |
|-----------|----------|
| HTML + TXT formats | `pdfkit` for HTML, PIL+reportlab for TXT |
| Tables split across pages | Merge based on `is_header_only` flag + bbox proximity |
| Pre-2006 vs Post-2006 formats | Column mapping with synonyms |
| Funds (no exec comp) | Auto-skip when SIC = NULL |

## Output

Per document in `output/{doc_id}/`:
- `classification_results.json` - Tables found + type
- `extraction_results.json` - Structured compensation data

## Requirements

- Python 3.10+
- GPU with 40GB+ VRAM (or adjust tensor parallelism)
- `vllm`, `mineru`, `pdfkit`, `pillow`, `openai`

```bash
pip install -r requirements.txt
sudo apt-get install wkhtmltopdf
```
## OpenAI Compatible

The pipeline uses **OpenAI-compatible APIs** for classification and extraction. You can swap local models with cloud APIs:

```python
# Local (vLLM)
client = AsyncOpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

# OpenAI / Azure / Anthropic / any OpenAI-compatible endpoint
client = AsyncOpenAI(api_key="sk-...")
MODEL = "gpt-4o"  # or any vision model
```

Only **MinerU** requires local GPU for PDF table extraction. Everything else works with cloud APIs.