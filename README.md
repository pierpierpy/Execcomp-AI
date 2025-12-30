# Execcomp-AI

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

Open `pipeline.ipynb` and run cells in order:

1. **Cell 2** - Load SEC filings from `data/DEF14A_all.jsonl` (on Hugging Face `pierjoe/SEC-DEF14A-2005-2022`)
2. **Cell 3** - Convert to PDF + extract tables with MinerU
3. **Cell 4** - Count documents with/without tables
4. **Cell 10** - Run classification + extraction on all documents

The pipeline will:
- Skip **funds** (SIC = NULL) - they don't have exec compensation
- Skip **already processed** documents (checks for `extraction_results.json`)
- **Classify** each table using VLM (summary_compensation, director_compensation, etc.)
- **Merge** tables split across pages (detects header-only tables)
- **Extract** structured JSON from Summary Compensation Tables
- **Save** results to `output/{doc_id}/`

## Example

**Input:** [GTT Communications DEF 14A 2018](https://www.sec.gov/Archives/edgar/data/1315255/0001398344-18-006199-index.html)

**Extracted Table:**

![Sample Table](docs/image.jpg)

**Output JSON:**
```json
{
    "name": "Luca Mignini",
    "title": "Former Executive Vice President - Strategic Initiatives",
    "fiscal_year": 2018,
    "salary": 747433,
    "bonus": 50000,
    "stock_awards": 1731729,
    "option_awards": 363899,
    "non_equity_incentive": 0,
    "change_in_pension": 0,
    "other_compensation": 228655,
    "total": 3121716
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


## 🚧 Work in Progress

The pipeline is currently running on the largest possible set of SEC filings. In the meantime, you can explore some initial samples here:

👉 **[pierjoe/execcomp-ai-sample](https://huggingface.co/datasets/pierjoe/execcomp-ai-sample)**

> ⚠️ **Note:** These are early samples and may contain errors due to bugs that are being fixed. The final dataset will be more accurate.
