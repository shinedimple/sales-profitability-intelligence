/* ==========================================================================
   06_discounts.sql  -  discount vs profit (scope: core)

   Note: these queries show ASSOCIATION, not causation. Discount levels may
   differ by product mix; Q17 holds category constant as a first control,
   and Phase 4 tests drivers more rigorously.
   ========================================================================== */

-- query: Q15 | Profitability by discount band
-- covers: 26 Discount vs profit
-- question: How does profitability change as discounts get deeper?
-- logic: Group order lines by the fixed discount bands from dim_discount (defined before analysis, not tuned to results).
-- logic: Margin is ratio-of-sums per band; loss_line_share shows how often a line at that discount loses money.
-- use: Core evidence for a discount policy discussion, e.g. where margin turns negative.
SELECT
    discount_band,
    COUNT(*)                                                AS lines,
    ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (), 4)        AS share_of_lines,
    ROUND(SUM(sales), 2)                                    AS sales,
    ROUND(SUM(sales) / SUM(SUM(sales)) OVER (), 4)          AS share_of_sales,
    ROUND(SUM(profit), 2)                                   AS profit,
    ROUND(SUM(profit) / SUM(sales), 4)                      AS profit_margin,
    ROUND(AVG(is_loss_line), 4)                             AS loss_line_share,
    ROUND(SUM(discount_amount), 2)                          AS discount_amount
FROM vw_sales_line
WHERE is_core_scope = 1
GROUP BY discount_band, discount_band_sort
ORDER BY discount_band_sort;

-- query: Q16 | Profitability by exact discount level
-- covers: 26 Discount vs profit (detail)
-- question: At which exact discount level does a typical line stop being profitable?
-- logic: Same measures at each of the observed discount levels. Bands can hide a break point inside a band.
-- logic: Levels with few lines are kept but should be read with their line count.
-- use: Pinpoints the threshold for a potential discount cap; read together with the line counts.
SELECT
    discount_label,
    discount_rate,
    COUNT(*)                                    AS lines,
    ROUND(SUM(sales), 2)                        AS sales,
    ROUND(SUM(profit), 2)                       AS profit,
    ROUND(SUM(profit) / SUM(sales), 4)          AS profit_margin,
    ROUND(AVG(is_loss_line), 4)                 AS loss_line_share
FROM vw_sales_line
WHERE is_core_scope = 1
GROUP BY discount_label, discount_rate
ORDER BY discount_rate;

-- query: Q17 | Discount band by category
-- covers: 26 Discount vs profit (controlled for category)
-- question: Does the discount-profit relationship hold inside each category, or is it caused by which categories get discounted?
-- logic: Same band measures split by category, plus each band's share of the category's sales (window SUM per category).
-- logic: If margin falls with discount inside every category, product mix alone cannot explain the pattern.
-- use: Separates "discounting hurts" from "we discount the wrong categories" before any recommendation is made.
SELECT
    category,
    discount_band,
    COUNT(*)                                                                    AS lines,
    ROUND(SUM(sales), 2)                                                        AS sales,
    ROUND(SUM(sales) / SUM(SUM(sales)) OVER (PARTITION BY category), 4)         AS share_of_category_sales,
    ROUND(SUM(profit), 2)                                                       AS profit,
    ROUND(SUM(profit) / SUM(sales), 4)                                          AS profit_margin
FROM vw_sales_line
WHERE is_core_scope = 1
GROUP BY category, discount_band, discount_band_sort
ORDER BY category, discount_band_sort;
