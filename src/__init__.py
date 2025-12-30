# SEC DEF 14A Table Extraction Pipeline

# VLM - Classification, extraction, schemas
from .vlm import (
    TableType,
    TableClassification,
    Executive,
    SummaryCompensationTable,
    find_summary_compensation_in_doc,
    extract_summary_compensation_table,
    extract_all_summary_compensation,
)

# Processing - PDF conversion, MinerU, table extraction
from .processing import (
    get_doc_id,
    convert_docs_to_pdf,
    process_pdfs_with_mineru,
    extract_tables_from_output,
    merge_consecutive_tables,
)

# IO - Results and visualization
from .io import (
    save_classification_results,
    save_extraction_results,
    display_extraction_result,
    display_all_results,
    display_table_preview,
)