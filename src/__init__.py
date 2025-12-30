# SEC DEF 14A Table Extraction Pipeline

from .schemas import (
    TableType,
    TableClassification,
    Executive,
    SummaryCompensationTable
)
from .pdf_conversion import get_doc_id, convert_docs_to_pdf
from .mineru_processing import process_pdfs_with_mineru
from .table_extraction import extract_tables_from_output, merge_consecutive_tables
from .classification import find_summary_compensation_in_doc
from .extraction import (
    extract_summary_compensation_table,
    extract_all_summary_compensation
)
from .results import (
    save_classification_results,
    save_extraction_results
)
from .visualization import (
    display_extraction_result,
    display_all_results,
    display_table_preview
)