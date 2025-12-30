# Pydantic schemas for SEC DEF 14A Table Extraction

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ============== Classification Schemas ==============

class TableType(str, Enum):
    SUMMARY_COMPENSATION = "summary_compensation"
    DIRECTOR_COMPENSATION = "director_compensation"
    GRANTS_PLAN_BASED_AWARDS = "grants_plan_based_awards"
    OUTSTANDING_EQUITY = "outstanding_equity"
    OPTION_EXERCISES = "option_exercises"
    BENEFICIAL_OWNERSHIP = "beneficial_ownership"
    TERMINATION_PAYMENTS = "termination_payments"
    PENSION_BENEFITS = "pension_benefits"
    COMPENSATION_ANALYSIS = "compensation_analysis"
    OTHER = "other"


class TableClassification(BaseModel):
    table_type: TableType = Field(description="Type of table identified")
    confidence: float = Field(description="Confidence score 0-1")
    reason: str = Field(description="Brief explanation for classification")
    is_header_only: bool = Field(default=False, description="True if table contains only column headers without actual executive data rows")


# ============== Extraction Schemas ==============

class Executive(BaseModel):
    """Dati di compensazione di un singolo executive."""
    name: str = Field(description="Full name of the executive")
    title: Optional[str] = Field(default=None, description="Job title (CEO, CFO, President, etc.)")
    fiscal_year: int = Field(description="Fiscal year of compensation")
    salary: float = Field(default=0, description="Base salary in dollars")
    bonus: float = Field(default=0, description="Cash bonus in dollars")
    stock_awards: float = Field(default=0, description="Dollar value of stock awards granted")
    option_awards: float = Field(default=0, description="Dollar value of stock options granted (not share count)")
    non_equity_incentive: float = Field(default=0, description="Non-equity incentive plan compensation in dollars")
    change_in_pension: float = Field(default=0, description="Change in pension value and deferred compensation")
    other_compensation: float = Field(default=0, description="All other compensation (perks, 401k match, insurance, etc.)")
    total: Optional[float] = Field(default=None, description="Total compensation. Only populate if explicitly shown in table, otherwise leave null")

class SummaryCompensationTable(BaseModel):
    """Summary Compensation Table estratta da un filing SEC."""
    company: str = Field(description="Company name as it appears in the filing")
    cik: str = Field(description="SEC Central Index Key (CIK) identifier")
    fiscal_year_end: Optional[str] = Field(default=None, description="Fiscal year end date (e.g., '2023-12-31')")
    currency: str = Field(default="USD", description="Currency of compensation values")
    executives: List[Executive] = Field(description="List of executive compensation records")
