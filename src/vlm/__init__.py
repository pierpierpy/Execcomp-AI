# VLM module - Classification, extraction, prompts and schemas

from .schemas import (
    TableType,
    TableClassification,
    Executive,
    SummaryCompensationTable
)
from .prompts import (
    CLASSIFICATION_PROMPT,
    EXTRACTION_PROMPT,
    EXTRACTION_PROMPT_WITH_IMAGE
)
from .classification import find_summary_compensation_in_doc, classify_table
from .extraction import (
    extract_summary_compensation_table,
    extract_all_summary_compensation
)
from .classifier import SCTClassifier
