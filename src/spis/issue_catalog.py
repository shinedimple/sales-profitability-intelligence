"""
Issue catalog: the analyst's documented judgement for every data-quality issue.

Keeping decisions in code (not just in a notebook) makes them reviewable,
version-controlled and reproducible. The audit detects issues; this catalog
explains them; the cleaning module implements the stated approach.

decision values:
    CORRECT   - value is changed or row removed in the processed data
    FLAG      - row kept unchanged, a dq_* flag column is added
    DOCUMENT  - no row-level action; limitation recorded for later phases
"""

ISSUE_CATALOG = {
    "DQ01": {
        "title": "Near-duplicate order lines (identical except Row ID)",
        "severity": "Medium",
        "decision": "CORRECT",
        "meaning": "Two rows describe the same order, product, quantity, discount, sales and "
                   "profit. Only the technical Row ID differs, which suggests the line was "
                   "loaded twice.",
        "why": "Keeping a double-loaded line overstates sales, profit and units. A genuine split "
               "line would normally differ in quantity or value; these do not differ at all.",
        "approach": "Keep the first occurrence (lowest row_id), remove the copy, and record the "
                    "removed row_id and its sales/profit in the cleaning log.",
    },
    "DQ02": {
        "title": "Postal codes stored as numbers (leading zeros lost) and mixed types",
        "severity": "Medium",
        "decision": "CORRECT",
        "meaning": "US ZIP codes such as 05401 were stored as the number 5401. Canadian codes are "
                   "text (e.g. 'M7A'). The column therefore mixes numbers and strings.",
        "why": "A postal code is an identifier, not a quantity. Numeric storage breaks joins, "
               "map visuals and any lookup against external geography data.",
        "approach": "Convert to text. Zero-pad US codes to 5 digits. Keep Canadian codes as given "
                    "(upper-case, trimmed).",
    },
    "DQ03": {
        "title": "Customer IDs with inconsistent letter casing",
        "severity": "Low",
        "decision": "CORRECT",
        "meaning": "Some IDs use a lower-case second letter (e.g. 'Dl-13600') while the standard "
                   "format is two upper-case letters plus five digits.",
        "why": "Case differences can split one customer into two keys in SQL or Power BI joins. "
               "We verified that upper-casing creates no collision with another customer.",
        "approach": "Upper-case all customer IDs, then re-validate the ID pattern.",
    },
    "DQ04": {
        "title": "Customer names with inconsistent casing / formatting",
        "severity": "Low",
        "decision": "CORRECT",
        "meaning": "Some names have lower-case surname initials (e.g. 'Dorris liebe'). One name is "
                   "hyphenated without a space ('Corey-Lock').",
        "why": "Casing is cosmetic but appears in reports. Fixing the first letter is safe. "
               "Splitting 'Corey-Lock' would be a guess, so it is left as is.",
        "approach": "Capitalise the first letter of any word that starts lower-case. Do not "
                    "rewrite name structure.",
    },
    "DQ05": {
        "title": "Identity anomaly: one customer name under several IDs, and orders with "
                 "several customers",
        "severity": "High",
        "decision": "FLAG",
        "meaning": "A single customer name appears under five sequential IDs. Two orders, one year "
                   "apart, contain identical lines, each line under a different one of these IDs. "
                   "An order should belong to exactly one customer.",
        "why": "This pattern is typical of injected or synthetic test records. The financial value "
               "is small, but it would distort customer counts and customer-level metrics. "
               "Merging the IDs would be a guess, and deleting real transactions without "
               "business confirmation would be unsafe.",
        "approach": "Keep the rows. Set dq_is_identity_anomaly = True for every row of the affected "
                    "customer IDs and orders. Exclude these rows from customer-level analysis via "
                    "exclude_from_customer_analysis. Raise them with the business owner.",
    },
    "DQ06": {
        "title": "Placeholder / test customer name",
        "severity": "High",
        "decision": "FLAG",
        "meaning": "A customer is named like a test account (e.g. 'Sample Company A').",
        "why": "If it is test data, it should not count as a real customer. However, its "
               "transactions look like normal sales, so deleting them would change reported "
               "revenue without evidence.",
        "approach": "Keep in financial totals, flag with dq_is_placeholder_customer, exclude from "
                    "customer-level analysis, and escalate for confirmation.",
    },
    "DQ07": {
        "title": "Product ID and Product Name are not one-to-one",
        "severity": "Medium",
        "decision": "DOCUMENT",
        "meaning": "Some Product IDs are used for two different product names, and some names "
                   "appear under two IDs. Product ID is therefore not a reliable unique product "
                   "key on its own.",
        "why": "We cannot know which name is 'correct'. Overwriting either would invent data. "
               "Category and sub-category remain consistent, so higher-level analysis is "
               "unaffected.",
        "approach": "No change to values. In Phase 2, build a surrogate product_key on "
                    "(product_id, product_name) for product-level analysis.",
    },
    "DQ08": {
        "title": "Copied financial values across different products in the same order",
        "severity": "Low",
        "decision": "FLAG",
        "meaning": "Within one order, two different products carry exactly the same sales, "
                   "quantity, discount and profit, and the implied unit price does not fit one "
                   "of the products.",
        "why": "This suggests a manual copy-paste error, but the true values are unknown.",
        "approach": "Flag both rows with dq_is_value_copy_suspect. Keep the values.",
    },
    "DQ09": {
        "title": "Unstable implied list price for the same product",
        "severity": "Medium",
        "decision": "FLAG",
        "meaning": "Implied list price = sales / (quantity x (1 - discount)). For most products this "
                   "is stable. For some rows it differs by more than 50% from the product's median, "
                   "in extreme cases by more than 100x.",
        "why": "Large deviations point to pricing or entry errors, or to product-ID reuse. They "
               "matter for pricing and discount analysis, but there is no source to correct them "
               "from.",
        "approach": "Flag rows with dq_is_price_anomaly. Test the sensitivity of pricing and "
                    "discount findings with and without these rows in later phases.",
    },
    "DQ10": {
        "title": "Extreme values in sales and profit (statistical outliers)",
        "severity": "Info",
        "decision": "FLAG",
        "meaning": "Sales and profit are highly right-skewed: a minority of lines falls beyond the "
                   "3 x IQR fences yet carries roughly half of all sales and profit. The high count "
                   "itself shows a long-tailed distribution, not widespread errors.",
        "why": "These are plausible large B2B or high-value transactions, not impossible values. "
               "Removing them would delete real business, including the largest losses management "
               "needs to see.",
        "approach": "Keep all rows. Flag with dq_is_sales_outlier / dq_is_profit_outlier (3 x IQR). "
                    "Prefer medians and ratio-of-sums in analysis.",
    },
    "DQ11": {
        "title": "Postal code mapped to more than one city",
        "severity": "Low",
        "decision": "DOCUMENT",
        "meaning": "One postal code appears with two different city names in the same state.",
        "why": "This affects only map precision. City + state is used as the geographic key, so "
               "analysis is not affected. There is no authoritative reference to correct it from.",
        "approach": "No change. Use city + state_province (not postal code) as the geographic key.",
    },
    "DQ12": {
        "title": "Same city name in several states",
        "severity": "Info",
        "decision": "DOCUMENT",
        "meaning": "City names such as 'Springfield' exist in several states. This is real-world "
                   "geography, not an error.",
        "why": "Aggregating by city name alone would merge different cities.",
        "approach": "No change. Always group cities by (city, state_province).",
    },
    "DQ13": {
        "title": "Order dates extend beyond the current date (synthetic dataset)",
        "severity": "Info",
        "decision": "DOCUMENT",
        "meaning": "The data contains orders dated after today, which confirms the dataset years "
                   "are synthetic or shifted.",
        "why": "The data is internally consistent, so analysis remains valid. However, presenting "
               "it as real 2026 results would be misleading.",
        "approach": "No change. Refer to 'dataset years' and add a disclaimer in the README.",
    },
    "DQ14": {
        "title": "Returns are recorded per order, not per line",
        "severity": "Info",
        "decision": "DOCUMENT",
        "meaning": "The Returns table lists returned Order IDs only. We cannot tell which lines or "
                   "quantities were returned.",
        "why": "Line-level return analysis would over-attribute returns.",
        "approach": "Analyse returns at order level only. Join is_returned in Phase 2.",
    },
    "DQ15": {
        "title": "Lines with profit exactly zero",
        "severity": "Info",
        "decision": "DOCUMENT",
        "meaning": "Some lines break even exactly.",
        "why": "Unusual but not impossible. There is no evidence of an error.",
        "approach": "No change. Monitor in margin analysis.",
    },
    "DQ16": {
        "title": "Same product appears on several lines of one order",
        "severity": "Info",
        "decision": "DOCUMENT",
        "meaning": "An order contains the same product on two lines with different quantities.",
        "why": "Where unit prices are consistent across the lines, they look like legitimate split "
               "lines, not duplicates (true duplicates are handled by DQ01). The one inconsistent "
               "order is already flagged under DQ08.",
        "approach": "No change. Count distinct products per order when needed.",
    },
    "DQ17": {
        "title": "Losses larger than the line's sales value (margin below -100%)",
        "severity": "Info",
        "decision": "DOCUMENT",
        "meaning": "Some lines lose more money than their revenue. This occurs only at high "
                   "discount levels.",
        "why": "This is mathematically possible when deep discounts push the price far below cost. "
               "It is a business signal for Phase 3, not a data error.",
        "approach": "No change. Investigate in the discount analysis.",
    },
    "DQ18": {
        "title": "Canadian order lines that are copies of other orders' lines",
        "severity": "High",
        "decision": "FLAG",
        "meaning": "Order IDs end in a 6-digit sequence number. Many Canadian lines share the "
                   "sequence number, customer, product and exact sales value of a line in another "
                   "order: either a US order (CA copy of a US line), or another Canadian order "
                   "from a different year. US orders never repeat sequence numbers among "
                   "themselves.",
        "why": "This is strong evidence that part of the Canadian data was generated by copying "
               "existing records. Counting the copies would double-count revenue and invent "
               "Canadian demand. We cannot prove which side is the original for CA-CA pairs, "
               "so values are not deleted.",
        "approach": "Flag the non-US rows in each clone group with dq_is_clone_copy (assumption "
                    "A6: US records are the originals). Recommend reporting Canada separately "
                    "or excluding it from the core analysis.",
    },
    "DQ19": {
        "title": "Orders shipping to more than one location",
        "severity": "Low",
        "decision": "DOCUMENT",
        "meaning": "Some orders have lines shipped to different cities. This could be a genuine "
                   "split delivery.",
        "why": "Geography is attributed per line, so totals by city and state remain correct.",
        "approach": "No change. Attribute geography at line level, never order level.",
    },
}
