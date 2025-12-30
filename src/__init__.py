# SEC DEF 14A Table Extraction Pipeline

from .schemas import (
    TableType,
    TableClassification,
    Executive,
    SummaryCompensationTable
)
from .pdf_conversion import get_doc_id, convert_docs_to_pdf
from .mineru_processing import process_pdfs_with_mineru
from .table_extraction import extract_tables_from_output
from .classification import find_summary_compensation_in_doc
from .extraction import (
    extract_summary_compensation_table,
    extract_all_summary_compensation
)