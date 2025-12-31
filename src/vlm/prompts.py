# Prompts for SEC DEF 14A Table Classification and Extraction

# ============== Classification Prompt ==============

CLASSIFICATION_PROMPT = """Classify this table from an SEC DEF 14A proxy statement.

## Table Types:

1. **summary_compensation** - THE OFFICIAL "Summary Compensation Table" (SEC Item 402(c)):
   - REQUIRED: **Year column with MULTIPLE YEARS as ROW VALUES** (e.g., rows showing 2020, 2021, 2022)
   - REQUIRED: Executive names visible with titles (CEO, CFO, etc.)
   - REQUIRED: Standard columns - Name, Year, Salary, Bonus, Stock Awards, Option Awards, Total
   - Shows SAME executives repeated across MULTIPLE fiscal years (one row per executive per year)
   - Usually titled "Summary Compensation Table"
   
   ⚠️ **CRITICAL DISTINCTION**: The Year must be a COLUMN with values IN THE ROWS.
   If years appear as COLUMN HEADERS (e.g., "2018 | 2017 | 2016" across the top) → NOT summary_compensation

2. **compensation_analysis** - Supporting tables that are NOT the official SCT:
   - Tables with **years as COLUMN HEADERS** instead of row values (e.g., columns labeled "2018", "2017")
   - Single-year summaries without Year column
   - Percentage breakdowns ("% of Total Compensation")
   - Alternative formats showing compensation data differently
   - Pay mix analysis tables
   - Tables comparing executives side-by-side with years as columns

3. **director_compensation** - Board director fees (not executives), SEC Item 402(k)

4. **grants_plan_based_awards** - Stock/option grants with grant dates, SEC Item 402(d)

5. **outstanding_equity** - Unvested stock/unexercised options at year end, SEC Item 402(f)

6. **option_exercises** - Options exercised or stock vested during year, SEC Item 402(g)

7. **beneficial_ownership** - Shares owned by executives/directors/5%+ holders, SEC Item 403

8. **termination_payments** - Hypothetical payments upon termination/change in control, SEC Item 402(j)

9. **pension_benefits** - Pension values, deferred compensation, SEC Item 402(h)

10. **other** - Any table that doesn't fit above categories

## KEY RULE - Year Format Detection:

**summary_compensation** (EXTRACT THIS):
```
Name          | Year | Salary   | Bonus    | Total
John Smith    | 2022 | $500,000 | $100,000 | $1,200,000
John Smith    | 2021 | $480,000 | $90,000  | $1,100,000
Jane Doe      | 2022 | $400,000 | $80,000  | $950,000
```
↑ Year is a COLUMN, values are IN THE ROWS, same exec appears multiple times

**compensation_analysis** (DO NOT EXTRACT AS SCT):
```
Name          | 2022 Salary | 2021 Salary | 2020 Salary
John Smith    | $500,000    | $480,000    | $450,000
Jane Doe      | $400,000    | $380,000    | $360,000
```
↑ Years are COLUMN HEADERS, each exec appears once

## Additional Rules:
- MUST have **executive names visible** - if NO NAMES visible → other
- Tables showing ONLY percentages → compensation_analysis
- Tables with **detailed breakdowns** (Medical, Dental, 401k, Perks) → other
- Tables titled "Potential Payments", "Termination" → termination_payments

## has_header detection (LOOK AT THE IMAGE):
- **has_header = True**: FIRST ROW shows column labels like "Name", "Year", "Salary", "Total"
- **has_header = False**: FIRST ROW shows actual data (person name, year numbers, dollar amounts)

## is_header_only detection:
- **is_header_only = True**: Table has ONLY header row, NO data rows
- **is_header_only = False**: Table has data rows with names and numbers

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
