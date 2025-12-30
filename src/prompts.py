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
- MUST have Salary AND Total columns with dollar amounts
- MUST show multiple executives (CEO, CFO, etc.)
- MUST show actual compensation, not percentages or hypotheticals
- Tables showing ONLY percentages or ONLY one component (just bonus, just salary) are compensation_analysis, NOT summary_compensation

## Header-only detection:
Determine if the table contains ONLY headers (column names like "Name", "Salary", "Bonus", "Year", "Stock Awards", "Total", etc.) WITHOUT actual executive compensation data rows with dollar amounts.
- If the table has column headers but NO data rows with executive names and dollar values → is_header_only = True
- If the table has actual executive names and compensation numbers → is_header_only = False

## Has header detection:
Determine if the table contains a header row (column names at the top).
- If the table starts with a row containing column names (Name, Salary, Bonus, Year, Total, etc.) → has_header = True
- If the table is a continuation of data without column names at the top → has_header = False

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