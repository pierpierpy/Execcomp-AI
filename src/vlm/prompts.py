# Prompts for SEC DEF 14A Table Classification and Extraction

# ============== Classification Prompt ==============

CLASSIFICATION_PROMPT = """Classify this table from an SEC DEF 14A proxy statement.

## Table Types:

1. **summary_compensation** - THE OFFICIAL "Summary Compensation Table" with these REQUIRED columns:
   - Name and Principal Position
   - Year
   - Salary (dollar amount)
   - Bonus (dollar amount)  
   - Stock Awards and/or Option Awards (dollar amounts)
   - Total (dollar amount)
   Must show MULTIPLE executives with ACTUAL DOLLAR AMOUNTS paid across MULTIPLE YEARS.
   This is THE main compensation table in the proxy, usually titled "Summary Compensation Table".

2. **compensation_analysis** - Supporting tables that show percentages, ratios, or partial compensation data. Examples:
   - "Base Salary as Percentage of Total Compensation"
   - "Bonus as Percentage of Total"
   - Pay mix charts or breakdowns
   - Single metric tables (only bonus amounts, only salary, etc.)
   These are NOT the main Summary Compensation Table.

3. **director_compensation** - Board director fees (not executives)

4. **grants_plan_based_awards** - Stock/option grants with grant dates

5. **outstanding_equity** - Unvested stock/unexercised options at year end

6. **option_exercises** - Options exercised or stock vested during year

7. **beneficial_ownership** - Shares owned by executives/directors/5%+ holders

8. **termination_payments** - Hypothetical payments upon termination/change in control

9. **pension_benefits** - Pension values, deferred compensation

10. **other** - Any other table

## Key rules for summary_compensation:
- MUST have **executive names visible** (e.g., "John Smith, CEO", "Jane Doe, CFO") - if NO NAMES are visible, it is NOT summary_compensation
- MUST have a **Year column** with fiscal years (e.g., 2019, 2020, 2021) as ROW VALUES, not as column headers
- MUST have Salary AND Total columns with dollar amounts
- MUST show multiple executives (CEO, CFO, etc.)
- Uses **AGGREGATED categories**: Salary, Bonus, Stock Awards, Option Awards, Non-Equity Incentive, All Other Compensation, Total

## Tables that are NOT summary_compensation (classify as "other"):
- Tables where **years are column headers** (e.g., columns labeled "2018", "2017") instead of row values → these are breakdown/summary tables → **other**
- Tables WITHOUT executive names visible → **other**
- Tables showing ONLY percentages or ONLY one component → compensation_analysis
- Tables with **detailed breakdowns** like Medical, Dental, Vision, Insurance, 401k, Perks → **other**
- Tables titled "Potential Payments", "Estimated Payments", "Termination" → termination_payments

## has_header detection (LOOK AT THE IMAGE ONLY):

**has_header = True**: The FIRST ROW of the table shows COLUMN LABELS like "Name", "Year", "Salary", "Bonus", "Stock Awards", "Total", etc. These are TEXT LABELS describing what each column contains.

**has_header = False**: The FIRST ROW of the table shows ACTUAL DATA - a person's name (e.g., "Gary A. Stewart", "John Smith"), years (2004, 2003), dollar amounts ($132,500, $10,000). NO column labels are visible.

ASK YOURSELF: What is in the FIRST ROW of this table?
- If FIRST ROW = column labels like "Name | Year | Salary | Bonus" → has_header = True  
- If FIRST ROW = data like "Gary A. Stewart | 2004 | $132,500" → has_header = False

DO NOT assume a header exists just because the table has columns. ONLY set has_header=True if you can literally SEE the header row with column names in the image.

## is_header_only detection:
- **is_header_only = True**: The table contains ONLY the header row with column names, with NO data rows below
- **is_header_only = False**: The table contains data rows with names and numbers

## Table to classify:

Caption: {caption}
Footnotes: {footnotes}
Content: {table_body}

Classify this table. Keep reason under 50 words."""


# ============== Extraction Prompt ==============

EXTRACTION_PROMPT = """Extract executive compensation data from this SEC DEF 14A table.

**Company:** {company} | **CIK:** {cik} | **Filing Year:** {filing_year}

**HTML TABLE:**
{table_body}

**COLUMN MAPPING (with synonyms):**

**salary** ← "Salary", "Salary($)", "Base Salary", "Annual Salary"

**bonus** ← "Bonus", "Bonus($)", "Cash Bonus", "Annual Bonus", "Bonus(a)", "Bonus ($)(a)"

**stock_awards** ← "Stock Awards", "Restricted Stock", "Restricted Stock Awards", "Restricted Stock Awards($)", "RSU Awards", "Equity Awards", "Restricted Stock Awards($)(a)"

**option_awards** ← "Option Awards", "Option Awards($)", "Stock Option Awards" (ONLY dollar value)

**non_equity_incentive** ← "Non-Equity Incentive", "Non-Equity Incentive Plan", "LTIP", "LTIP Payouts", "LTIP Payouts($)", "LTIP Payouts($)(c)", "Long-Term Incentive", "Incentive Plan Compensation"

**change_in_pension** ← "Change in Pension Value", "Pension", "Deferred Compensation Earnings"

**other_compensation** ← "All Other Compensation", "All Other Compensation($)", "All Other Compensation($)(d)" (RIGHTMOST column)

**total** ← "Total", "Total Compensation", "Total($)"

**IGNORE (share counts, NOT dollars):**
- "Securities Underlying Options", "Options(#)", "SARs(#)", "Securities Underlying Options/SARs(#)"

**CRITICAL - DO NOT MISS THESE COLUMNS:**
- "Restricted Stock Awards" contains DOLLAR values → extract to stock_awards
- "LTIP Payouts" contains DOLLAR values → extract to non_equity_incentive
- These columns are often under "Long-Term Compensation" header group

**RULES:**
1. Parse ALL columns in the HTML, including nested header groups
2. Each executive + year = one record  
3. Dollar values: remove $, commas → float
4. "-", "—", empty = 0
5. No "Total" column → total = null

Extract ALL executives and ALL years. Do NOT leave stock_awards or non_equity_incentive as 0 if values exist in the table."""


# ============== Extraction Prompt WITH IMAGE (for merged tables) ==============

EXTRACTION_PROMPT_WITH_IMAGE = """Extract executive compensation data from this SEC DEF 14A table.

**Company:** {company} | **CIK:** {cik} | **Filing Year:** {filing_year}

**HTML TABLE (may be incomplete due to page merge):**
{table_body}

**⚠️ IMPORTANT: This table was merged from multiple pages. The HTML may be INCOMPLETE or have missing columns.**
**USE THE IMAGE as the PRIMARY source of truth. Cross-reference with HTML but trust the IMAGE for actual values.**

**COLUMN MAPPING (with synonyms):**

**salary** ← "Salary", "Salary($)", "Base Salary", "Annual Salary"

**bonus** ← "Bonus", "Bonus($)", "Cash Bonus", "Annual Bonus", "Bonus(a)", "Bonus ($)(a)"

**stock_awards** ← "Stock Awards", "Restricted Stock", "Restricted Stock Awards", "Restricted Stock Awards($)", "RSU Awards", "Equity Awards", "Restricted Stock Awards($)(a)"

**option_awards** ← "Option Awards", "Option Awards($)", "Stock Option Awards" (ONLY dollar value)

**non_equity_incentive** ← "Non-Equity Incentive", "Non-Equity Incentive Plan", "LTIP", "LTIP Payouts", "LTIP Payouts($)", "LTIP Payouts($)(c)", "Long-Term Incentive", "Incentive Plan Compensation"

**change_in_pension** ← "Change in Pension Value", "Pension", "Deferred Compensation Earnings"

**other_compensation** ← "All Other Compensation", "All Other Compensation($)", "All Other Compensation($)(d)" (RIGHTMOST column before Total)

**total** ← "Total", "Total Compensation", "Total($)"

**IGNORE (share counts, NOT dollars):**
- "Securities Underlying Options", "Options(#)", "SARs(#)", "Securities Underlying Options/SARs(#)"

**CRITICAL FOR MERGED TABLES:**
1. READ THE IMAGE CAREFULLY - it contains the complete table
2. If a column is missing from HTML but visible in image, extract from image
3. "All Other Compensation" is often the LAST column before "Total" - check the image
4. Make sure you extract ALL executives shown in the image, even if HTML is truncated

**RULES:**
1. Parse the IMAGE first, then verify with HTML where available
2. Each executive + year = one record  
3. Dollar values: remove $, commas → float
4. "-", "—", empty = 0
5. No "Total" column → total = null

Extract ALL executives and ALL years from the IMAGE."""
