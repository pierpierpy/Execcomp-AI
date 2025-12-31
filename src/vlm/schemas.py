# Pydantic schemas for SEC DEF 14A Table Extraction

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ============== Classification Schemas ==============

class TableType(str, Enum):
    """SEC DEF 14A table types for executive compensation filings."""
    
    SUMMARY_COMPENSATION = "summary_compensation"
    """The OFFICIAL Summary Compensation Table (SEC Item 402(c)).
    REQUIRED: Year column with MULTIPLE YEARS as ROW VALUES (e.g., 2020, 2021, 2022 in rows).
    REQUIRED: Executive names visible with titles (CEO, CFO, etc.).
    REQUIRED: Standard columns - Name, Year, Salary, Bonus, Stock Awards, Total.
    Shows same executives repeated across multiple fiscal years."""
    
    DIRECTOR_COMPENSATION = "director_compensation"
    """Board of Directors compensation table (SEC Item 402(k)).
    Shows fees paid to non-employee directors, NOT executive officers."""
    
    GRANTS_PLAN_BASED_AWARDS = "grants_plan_based_awards"
    """Grants of Plan-Based Awards table (SEC Item 402(d)).
    Shows individual stock/option grants with grant dates and fair values."""
    
    OUTSTANDING_EQUITY = "outstanding_equity"
    """Outstanding Equity Awards at Fiscal Year-End (SEC Item 402(f)).
    Shows unvested stock and unexercised options held at year end."""
    
    OPTION_EXERCISES = "option_exercises"
    """Option Exercises and Stock Vested table (SEC Item 402(g)).
    Shows options exercised and stock that vested during the year."""
    
    BENEFICIAL_OWNERSHIP = "beneficial_ownership"
    """Security Ownership table (SEC Item 403).
    Shows shares owned by executives, directors, and 5%+ shareholders."""
    
    TERMINATION_PAYMENTS = "termination_payments"
    """Potential Payments Upon Termination or Change in Control (SEC Item 402(j)).
    Shows hypothetical payments in termination scenarios."""
    
    PENSION_BENEFITS = "pension_benefits"
    """Pension Benefits table (SEC Item 402(h)).
    Shows pension plan values and accumulated benefits."""
    
    COMPENSATION_ANALYSIS = "compensation_analysis"
    """Supporting compensation tables that are NOT the official SCT.
    Includes: single-year summaries, percentage breakdowns, pay mix analysis,
    tables with years as COLUMN HEADERS instead of row values,
    alternative formats showing same data differently."""
    
    OTHER = "other"
    """Any table that doesn't fit the above categories.
    Includes: footnote tables, detailed breakdowns (Medical, Dental, 401k),
    tables without executive names, non-compensation tables."""


class TableClassification(BaseModel):
    table_type: TableType = Field(description="Type of table identified")
    confidence: float = Field(description="Confidence score 0-1")
    reason: str = Field(description="Brief explanation for classification")
    is_header_only: bool = Field(default=False, description="True if table contains only column headers without actual executive data rows")
    has_header: bool = Field(default=True, description="True if table contains a header row with column names (Name, Salary, Bonus, Year, etc.)")


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
