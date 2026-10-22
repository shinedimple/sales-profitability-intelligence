# Phase 3 — SQL Results Snapshot
_Raw query outputs (first rows). Facts only: interpretation follows in later phases._

Validation: 42 / 42 checks passed.

## Q01 — Headline KPIs
_1 rows_
| total_sales | total_profit | total_units | orders | customers | valid_customers | avg_order_value | profit_margin |
|---|---|---|---|---|---|---|---|
| 2,296,919.49 | 286,409.08 | 37871 | 5009 | 793 | 792 | 458.56 | 0.1247 |

## Q02 — Sales and profit by year
_4 rows_
| order_year | sales | profit | profit_margin | orders | avg_order_value | sales_growth_yoy | profit_growth_yoy | orders_growth_yoy |
|---|---|---|---|---|---|---|---|---|
| 2023 | 483,966.13 | 49,556.03 | 0.1024 | 969 | 499.45 |  |  |  |
| 2024 | 470,532.51 | 61,618.60 | 0.1310 | 1038 | 453.31 | -0.0278 | 0.2434 | 0.0712 |
| 2025 | 609,205.60 | 81,795.17 | 0.1343 | 1315 | 463.27 | 0.2947 | 0.3274 | 0.2669 |
| 2026 | 733,215.26 | 93,439.27 | 0.1274 | 1687 | 434.63 | 0.2036 | 0.1424 | 0.2829 |

## Q03 — Sales and profit by month
_48 rows, first 12 shown_
| order_year_month | sales | profit | profit_margin | sales_same_month_py | sales_growth_vs_py | profit_change_vs_py |
|---|---|---|---|---|---|---|
| 2023-01 | 14,236.90 | 2,450.19 | 0.1721 |  |  |  |
| 2023-02 | 4,519.89 | 862.31 | 0.1908 |  |  |  |
| 2023-03 | 55,691.01 | 498.73 | 0.0090 |  |  |  |
| 2023-04 | 28,013.97 | 3,500.89 | 0.1250 |  |  |  |
| 2023-05 | 23,648.29 | 2,738.71 | 0.1158 |  |  |  |
| 2023-06 | 34,595.13 | 4,976.52 | 0.1439 |  |  |  |
| 2023-07 | 33,946.39 | -841.48 | -0.0248 |  |  |  |
| 2023-08 | 27,909.47 | 5,318.10 | 0.1905 |  |  |  |
| 2023-09 | 81,777.35 | 8,328.10 | 0.1018 |  |  |  |
| 2023-10 | 31,453.39 | 3,448.26 | 0.1096 |  |  |  |
| 2023-11 | 78,628.72 | 9,292.13 | 0.1182 |  |  |  |
| 2023-12 | 69,545.62 | 8,983.57 | 0.1292 |  |  |  |

## Q04 — Seasonality: share of annual sales by calendar month
_12 rows_
| order_month | order_month_name | avg_share_of_year_sales | min_share_of_year_sales | max_share_of_year_sales | avg_share_of_year_profit | profit_margin_all_years |
|---|---|---|---|---|---|---|
| 1 | Jan | 0.0396 | 0.0294 | 0.0600 | 0.0268 | 0.0962 |
| 2 | Feb | 0.0250 | 0.0093 | 0.0377 | 0.0354 | 0.1723 |
| 3 | Mar | 0.0906 | 0.0803 | 0.1151 | 0.0925 | 0.1395 |
| 4 | Apr | 0.0610 | 0.0498 | 0.0727 | 0.0462 | 0.0844 |
| 5 | May | 0.0667 | 0.0489 | 0.0935 | 0.0762 | 0.1446 |
| 6 | Jun | 0.0657 | 0.0527 | 0.0723 | 0.0752 | 0.1394 |
| 7 | Jul | 0.0644 | 0.0611 | 0.0701 | 0.0412 | 0.0939 |
| 8 | Aug | 0.0683 | 0.0511 | 0.0861 | 0.0791 | 0.1369 |
| 9 | Sep | 0.1366 | 0.1198 | 0.1690 | 0.1332 | 0.1198 |
| 10 | Oct | 0.0839 | 0.0650 | 0.1061 | 0.1033 | 0.1587 |
| 11 | Nov | 0.1540 | 0.1304 | 0.1625 | 0.1357 | 0.1006 |
| 12 | Dec | 0.1441 | 0.1143 | 0.1592 | 0.1552 | 0.1333 |

## Q05 — Sales and profit by category
_3 rows_
| category | sales | profit | profit_margin | units | share_of_sales | share_of_profit | sales_rank | profit_rank |
|---|---|---|---|---|---|---|---|---|
| Technology | 836,154.03 | 145,454.95 | 0.1740 | 6939 | 0.3640 | 0.5079 | 1 | 1 |
| Furniture | 741,718.42 | 18,463.33 | 0.0249 | 8026 | 0.3229 | 0.0645 | 2 | 3 |
| Office Supplies | 719,047.03 | 122,490.80 | 0.1704 | 22906 | 0.3130 | 0.4277 | 3 | 2 |

## Q06 — Sales and profit by sub-category
_17 rows, first 12 shown_
| category | sub_category | sales | profit | profit_margin | loss_amount | lines | share_of_sales | share_of_profit | sales_rank | profit_rank |
|---|---|---|---|---|---|---|---|---|---|---|
| Technology | Copiers | 149,528.03 | 55,617.82 | 0.3720 | 0.0000 | 68 | 0.0651 | 0.1942 | 8 | 1 |
| Technology | Phones | 330,007.05 | 44,515.73 | 0.1349 | -7,530.62 | 889 | 0.1437 | 0.1554 | 1 | 2 |
| Technology | Accessories | 167,380.32 | 41,936.64 | 0.2505 | -930.63 | 775 | 0.0729 | 0.1464 | 7 | 3 |
| Office Supplies | Paper | 78,479.21 | 34,053.57 | 0.4339 | 0.0000 | 1370 | 0.0342 | 0.1189 | 12 | 4 |
| Office Supplies | Binders | 203,412.73 | 30,221.76 | 0.1486 | -38,510.50 | 1523 | 0.0886 | 0.1055 | 5 | 5 |
| Furniture | Chairs | 328,167.73 | 26,602.23 | 0.0811 | -9,868.78 | 616 | 0.1429 | 0.0929 | 2 | 6 |
| Office Supplies | Storage | 223,843.61 | 21,278.83 | 0.0951 | -6,426.30 | 846 | 0.0975 | 0.0743 | 3 | 7 |
| Office Supplies | Appliances | 107,532.16 | 18,138.01 | 0.1687 | -8,629.64 | 466 | 0.0468 | 0.0633 | 10 | 8 |
| Furniture | Furnishings | 91,705.16 | 13,059.14 | 0.1424 | -6,490.91 | 957 | 0.0399 | 0.0456 | 11 | 9 |
| Office Supplies | Envelopes | 16,476.40 | 6,964.18 | 0.4227 | 0.0000 | 254 | 0.0072 | 0.0243 | 15 | 10 |
| Office Supplies | Art | 27,118.79 | 6,527.79 | 0.2407 | 0.0000 | 796 | 0.0118 | 0.0228 | 14 | 11 |
| Office Supplies | Labels | 12,486.31 | 5,546.25 | 0.4442 | 0.0000 | 364 | 0.0054 | 0.0194 | 16 | 12 |

## Q07 — Sales and profit by region
_4 rows_
| region | regional_manager | sales | profit | profit_margin | effective_discount_rate | orders | avg_order_value | share_of_sales | share_of_profit |
|---|---|---|---|---|---|---|---|---|---|
| West | Sadie Pawthorne | 725,457.82 | 108,418.45 | 0.1494 | 0.1555 | 1611 | 450.32 | 0.3158 | 0.3785 |
| East | Chuck Magee | 678,499.87 | 91,534.84 | 0.1349 | 0.1946 | 1401 | 484.30 | 0.2954 | 0.3196 |
| South | Fred Suzuki | 391,721.91 | 46,749.43 | 0.1193 | 0.2128 | 822 | 476.55 | 0.1705 | 0.1632 |
| Central | Roxanne Rodriguez | 501,239.89 | 39,706.36 | 0.0792 | 0.2456 | 1175 | 426.59 | 0.2182 | 0.1386 |

## Q08 — Sales and profit by state
_49 rows, first 12 shown_
| state_province | region | sales | profit | profit_margin | effective_discount_rate | orders | volume_flag | sales_rank | profit_rank | cumulative_share_of_sales |
|---|---|---|---|---|---|---|---|---|---|---|
| California | West | 457,687.63 | 76,381.39 | 0.1669 | 0.1320 | 1021 | OK | 1 | 1 | 0.1993 |
| New York | East | 310,876.27 | 74,038.55 | 0.2382 | 0.0946 | 562 | OK | 2 | 2 | 0.3346 |
| Texas | Central | 170,188.05 | -25,729.36 | -0.1512 | 0.3906 | 487 | OK | 3 | 49 | 0.4087 |
| Washington | West | 138,641.27 | 33,402.65 | 0.2409 | 0.0823 | 256 | OK | 4 | 3 | 0.4691 |
| Pennsylvania | East | 116,511.91 | -15,559.96 | -0.1335 | 0.3783 | 288 | OK | 5 | 47 | 0.5198 |
| Florida | South | 89,473.71 | -3,399.30 | -0.0380 | 0.3658 | 200 | OK | 6 | 41 | 0.5587 |
| Illinois | Central | 80,166.10 | -12,607.89 | -0.1573 | 0.3992 | 276 | OK | 7 | 46 | 0.5936 |
| Ohio | East | 77,976.76 | -16,959.32 | -0.2175 | 0.4201 | 236 | OK | 8 | 48 | 0.6276 |
| Michigan | Central | 76,269.61 | 24,463.19 | 0.3207 | 0.0111 | 117 | OK | 9 | 4 | 0.6608 |
| Virginia | South | 70,636.72 | 18,597.95 | 0.2633 | 0.0000 | 115 | OK | 10 | 5 | 0.6915 |
| North Carolina | South | 55,603.16 | -7,490.91 | -0.1347 | 0.3706 | 136 | OK | 11 | 45 | 0.7158 |
| Indiana | Central | 53,555.36 | 18,382.94 | 0.3433 | 0.0000 | 73 | OK | 12 | 6 | 0.7391 |

## Q09 — Sales and profit by customer segment
_3 rows_
| segment | sales | profit | profit_margin | orders | valid_customers | avg_order_value | orders_per_customer | sales_per_customer | profit_per_customer | share_of_sales | share_of_profit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Consumer | 1,161,401.34 | 134,119.21 | 0.1155 | 2586 | 409 | 449.11 | 6.3200 | 2,839.61 | 327.92 | 0.5056 | 0.4683 |
| Corporate | 706,146.37 | 91,979.13 | 0.1303 | 1514 | 236 | 466.41 | 6.4200 | 2,992.15 | 389.74 | 0.3074 | 0.3211 |
| Home Office | 429,371.78 | 60,310.74 | 0.1405 | 909 | 147 | 472.36 | 6.1200 | 2,889.44 | 403.39 | 0.1869 | 0.2106 |

## Q10 — Top 10 products by sales
_10 rows_
| sales_rank | product_label | category | sub_category | sales | profit | profit_margin | units | orders |
|---|---|---|---|---|---|---|---|---|
| 1 | Canon imageCLASS 2200 Advanced Copier [TEC-CO-10004722] | Technology | Copiers | 61,599.82 | 25,199.93 | 0.4091 | 20 | 5 |
| 2 | Fellowes PB500 Electric Punch Plastic Comb Binding Machine with Manual Bind [OFF-BI-10003527] | Office Supplies | Binders | 27,453.38 | 7,753.04 | 0.2824 | 31 | 10 |
| 3 | Cisco TelePresence System EX90 Videoconferencing Unit [TEC-MA-10002412] | Technology | Machines | 22,638.48 | -1,811.08 | -0.0800 | 6 | 1 |
| 4 | HON 5400 Series Task Chairs for Big and Tall [FUR-CH-10002024] | Furniture | Chairs | 21,870.58 | 0.0000 | 0.0000 | 39 | 8 |
| 5 | GBC DocuBind TL300 Electric Binding System [OFF-BI-10001359] | Office Supplies | Binders | 19,823.48 | 2,233.51 | 0.1127 | 37 | 11 |
| 6 | GBC Ibimaster 500 Manual ProClick Binding System [OFF-BI-10000545] | Office Supplies | Binders | 19,024.50 | 760.98 | 0.0400 | 48 | 9 |
| 7 | Hewlett Packard LaserJet 3310 Copier [TEC-CO-10001449] | Technology | Copiers | 18,839.69 | 6,983.88 | 0.3707 | 38 | 8 |
| 8 | HP Designjet T520 Inkjet Large Format Printer - 24" Color [TEC-MA-10001127] | Technology | Machines | 18,374.90 | 4,094.98 | 0.2229 | 12 | 3 |
| 9 | GBC DocuBind P400 Electric Binding System [OFF-BI-10004995] | Office Supplies | Binders | 17,965.07 | -1,878.17 | -0.1045 | 27 | 6 |
| 10 | High Speed Automatic Electric Letter Opener [OFF-SU-10000151] | Office Supplies | Supplies | 17,030.31 | -262.00 | -0.0154 | 11 | 3 |

## Q11 — Top 10 products by profit
_10 rows_
| profit_rank | product_label | category | sub_category | sales | profit | profit_margin | units | orders |
|---|---|---|---|---|---|---|---|---|
| 1 | Canon imageCLASS 2200 Advanced Copier [TEC-CO-10004722] | Technology | Copiers | 61,599.82 | 25,199.93 | 0.4091 | 20 | 5 |
| 2 | Fellowes PB500 Electric Punch Plastic Comb Binding Machine with Manual Bind [OFF-BI-10003527] | Office Supplies | Binders | 27,453.38 | 7,753.04 | 0.2824 | 31 | 10 |
| 3 | Hewlett Packard LaserJet 3310 Copier [TEC-CO-10001449] | Technology | Copiers | 18,839.69 | 6,983.88 | 0.3707 | 38 | 8 |
| 4 | Canon PC1060 Personal Laser Copier [TEC-CO-10003763] | Technology | Copiers | 11,619.83 | 4,570.93 | 0.3934 | 19 | 4 |
| 5 | HP Designjet T520 Inkjet Large Format Printer - 24" Color [TEC-MA-10001127] | Technology | Machines | 18,374.90 | 4,094.98 | 0.2229 | 12 | 3 |
| 6 | Ativa V4110MDD Micro-Cut Shredder [TEC-MA-10003979] | Technology | Machines | 7,699.89 | 3,772.95 | 0.4900 | 11 | 2 |
| 7 | 3D Systems Cube Printer, 2nd Generation, Magenta [TEC-MA-10001047] | Technology | Machines | 14,299.89 | 3,717.97 | 0.2600 | 11 | 2 |
| 8 | Plantronics Savi W720 Multi-Device Wireless Headset System [TEC-AC-10002049] | Technology | Accessories | 9,367.29 | 3,696.28 | 0.3946 | 24 | 7 |
| 9 | Ibico EPK-21 Electric Binding System [OFF-BI-10001120] | Office Supplies | Binders | 15,875.92 | 3,345.28 | 0.2107 | 13 | 3 |
| 10 | Zebra ZM400 Thermal Label Printer [TEC-MA-10000045] | Technology | Machines | 6,965.70 | 3,343.54 | 0.4800 | 6 | 2 |

## Q12 — Bottom 10 products by profit
_10 rows_
| loss_rank | product_label | category | sub_category | sales | profit | profit_margin | effective_discount_rate | lines | loss_lines |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Cubify CubeX 3D Printer Double Head Print [TEC-MA-10000418] | Technology | Machines | 11,099.96 | -8,879.97 | -0.8000 | 0.5889 | 3 | 2 |
| 2 | Lexmark MX611dhe Monochrome Laser Printer [TEC-MA-10000822] | Technology | Machines | 16,829.90 | -4,589.97 | -0.2727 | 0.4500 | 4 | 3 |
| 3 | Cubify CubeX 3D Printer Triple Head Print [TEC-MA-10004125] | Technology | Machines | 7,999.98 | -3,839.99 | -0.4800 | 0.5000 | 1 | 1 |
| 4 | Chromcraft Bull-Nose Wood Oval Conference Tables & Bases [FUR-TA-10000198] | Furniture | Tables | 9,917.64 | -2,876.12 | -0.2900 | 0.3333 | 5 | 4 |
| 5 | Bush Advantage Collection Racetrack Conference Table [FUR-TA-10001889] | Furniture | Tables | 9,544.73 | -1,934.40 | -0.2027 | 0.3182 | 7 | 6 |
| 6 | GBC DocuBind P400 Electric Binding System [OFF-BI-10004995] | Office Supplies | Binders | 17,965.07 | -1,878.17 | -0.1045 | 0.5111 | 6 | 3 |
| 7 | Cisco TelePresence System EX90 Videoconferencing Unit [TEC-MA-10002412] | Technology | Machines | 22,638.48 | -1,811.08 | -0.0800 | 0.5000 | 1 | 1 |
| 8 | Martin Yale Chadless Opener Electric Letter Opener [OFF-SU-10002881] | Office Supplies | Supplies | 16,656.20 | -1,299.18 | -0.0780 | 0.0909 | 6 | 3 |
| 9 | Balt Solid Wood Round Tables [FUR-TA-10001950] | Furniture | Tables | 6,518.75 | -1,201.06 | -0.1842 | 0.2316 | 4 | 2 |
| 10 | BoxOffice By Design Rectangular and Half-Moon Meeting Room Tables [FUR-TA-10004289] | Furniture | Tables | 1,706.25 | -1,148.44 | -0.6731 | 0.4800 | 3 | 3 |

## Q13 — High-sales but low-profit products
_196 rows, first 12 shown_
| product_label | category | sub_category | sales | profit | profit_margin | company_margin | effective_discount_rate | issue_type |
|---|---|---|---|---|---|---|---|---|
| Cubify CubeX 3D Printer Double Head Print [TEC-MA-10000418] | Technology | Machines | 11,099.96 | -8,879.97 | -0.8000 | 0.1247 | 0.5889 | Loss-making |
| Lexmark MX611dhe Monochrome Laser Printer [TEC-MA-10000822] | Technology | Machines | 16,829.90 | -4,589.97 | -0.2727 | 0.1247 | 0.4500 | Loss-making |
| Cubify CubeX 3D Printer Triple Head Print [TEC-MA-10004125] | Technology | Machines | 7,999.98 | -3,839.99 | -0.4800 | 0.1247 | 0.5000 | Loss-making |
| Chromcraft Bull-Nose Wood Oval Conference Tables & Bases [FUR-TA-10000198] | Furniture | Tables | 9,917.64 | -2,876.12 | -0.2900 | 0.1247 | 0.3333 | Loss-making |
| Bush Advantage Collection Racetrack Conference Table [FUR-TA-10001889] | Furniture | Tables | 9,544.73 | -1,934.40 | -0.2027 | 0.1247 | 0.3182 | Loss-making |
| GBC DocuBind P400 Electric Binding System [OFF-BI-10004995] | Office Supplies | Binders | 17,965.07 | -1,878.17 | -0.1045 | 0.1247 | 0.5111 | Loss-making |
| Cisco TelePresence System EX90 Videoconferencing Unit [TEC-MA-10002412] | Technology | Machines | 22,638.48 | -1,811.08 | -0.0800 | 0.1247 | 0.5000 | Loss-making |
| Martin Yale Chadless Opener Electric Letter Opener [OFF-SU-10002881] | Office Supplies | Supplies | 16,656.20 | -1,299.18 | -0.0780 | 0.1247 | 0.0909 | Loss-making |
| Balt Solid Wood Round Tables [FUR-TA-10001950] | Furniture | Tables | 6,518.75 | -1,201.06 | -0.1842 | 0.1247 | 0.2316 | Loss-making |
| BoxOffice By Design Rectangular and Half-Moon Meeting Room Tables [FUR-TA-10004289] | Furniture | Tables | 1,706.25 | -1,148.44 | -0.6731 | 0.1247 | 0.4800 | Loss-making |
| Riverside Furniture Oval Coffee Table, Oval End Table, End Table with Drawer [FUR-TA-10004154] | Furniture | Tables | 4,446.18 | -1,147.40 | -0.2581 | 0.1247 | 0.3800 | Loss-making |
| Hon 2090 “Pillow Soft” Series Mid Back Swivel/Tilt Chairs [FUR-CH-10003312] | Furniture | Chairs | 5,282.42 | -989.05 | -0.1872 | 0.1247 | 0.2167 | Loss-making |

## Q14 — Sub-category portfolio quadrant (revenue vs margin)
_17 rows, first 12 shown_
| category | sub_category | sales | profit | profit_margin | portfolio_quadrant | median_sales_threshold | margin_threshold |
|---|---|---|---|---|---|---|---|
| Furniture | Chairs | 328,167.73 | 26,602.23 | 0.0811 | Margin leak: high sales, low margin | 114,880.00 | 0.1247 |
| Office Supplies | Storage | 223,843.61 | 21,278.83 | 0.0951 | Margin leak: high sales, low margin | 114,880.00 | 0.1247 |
| Furniture | Tables | 206,965.53 | -17,725.48 | -0.0856 | Margin leak: high sales, low margin | 114,880.00 | 0.1247 |
| Technology | Machines | 189,238.63 | 3,384.76 | 0.0179 | Margin leak: high sales, low margin | 114,880.00 | 0.1247 |
| Furniture | Bookcases | 114,880.00 | -3,472.56 | -0.0302 | Margin leak: high sales, low margin | 114,880.00 | 0.1247 |
| Office Supplies | Appliances | 107,532.16 | 18,138.01 | 0.1687 | Niche earner: low sales, high margin | 114,880.00 | 0.1247 |
| Furniture | Furnishings | 91,705.16 | 13,059.14 | 0.1424 | Niche earner: low sales, high margin | 114,880.00 | 0.1247 |
| Office Supplies | Paper | 78,479.21 | 34,053.57 | 0.4339 | Niche earner: low sales, high margin | 114,880.00 | 0.1247 |
| Office Supplies | Art | 27,118.79 | 6,527.79 | 0.2407 | Niche earner: low sales, high margin | 114,880.00 | 0.1247 |
| Office Supplies | Envelopes | 16,476.40 | 6,964.18 | 0.4227 | Niche earner: low sales, high margin | 114,880.00 | 0.1247 |
| Office Supplies | Labels | 12,486.31 | 5,546.25 | 0.4442 | Niche earner: low sales, high margin | 114,880.00 | 0.1247 |
| Office Supplies | Fasteners | 3,024.28 | 949.52 | 0.3140 | Niche earner: low sales, high margin | 114,880.00 | 0.1247 |

## Q15 — Profitability by discount band
_5 rows_
| discount_band | lines | share_of_lines | sales | share_of_sales | profit | profit_margin | loss_line_share | discount_amount |
|---|---|---|---|---|---|---|---|---|
| No discount | 4798 | 0.4801 | 1,087,908.47 | 0.4736 | 320,987.60 | 0.2951 | 0.0000 | 0.0000 |
| 1-20% | 3803 | 0.3806 | 846,522.24 | 0.3685 | 100,785.47 | 0.1191 | 0.1375 | 202,052.90 |
| 21-40% | 459 | 0.0459 | 233,856.53 | 0.1018 | -35,805.41 | -0.1531 | 0.9020 | 128,551.71 |
| 41-60% | 215 | 0.0215 | 71,048.21 | 0.0309 | -28,944.19 | -0.4074 | 1.0000 | 73,373.30 |
| 61-80% | 718 | 0.0719 | 57,584.04 | 0.0251 | -70,614.40 | -1.2263 | 1.0000 | 162,635.68 |

## Q16 — Profitability by exact discount level
_12 rows_
| discount_label | discount_rate | lines | sales | profit | profit_margin | loss_line_share |
|---|---|---|---|---|---|---|
| 0% | 0.0000 | 4798 | 1,087,908.47 | 320,987.60 | 0.2951 | 0.0000 |
| 10% | 0.1000 | 94 | 54,369.35 | 9,029.18 | 0.1661 | 0.0426 |
| 15% | 0.1500 | 52 | 27,558.52 | 1,418.99 | 0.0515 | 0.3269 |
| 20% | 0.2000 | 3657 | 764,594.37 | 90,337.31 | 0.1182 | 0.1373 |
| 30% | 0.3000 | 226 | 102,945.28 | -10,357.22 | -0.1006 | 0.9159 |
| 32% | 0.3200 | 27 | 14,493.46 | -2,391.14 | -0.1650 | 1.0000 |
| 40% | 0.4000 | 206 | 116,417.78 | -23,057.05 | -0.1981 | 0.8738 |
| 45% | 0.4500 | 11 | 5,484.97 | -2,493.11 | -0.4545 | 1.0000 |
| 50% | 0.5000 | 66 | 58,918.54 | -20,506.43 | -0.3480 | 1.0000 |
| 60% | 0.6000 | 138 | 6,644.70 | -5,944.66 | -0.8946 | 1.0000 |
| 70% | 0.7000 | 418 | 40,620.28 | -40,075.36 | -0.9866 | 1.0000 |
| 80% | 0.8000 | 300 | 16,963.76 | -30,539.04 | -1.8003 | 1.0000 |

## Q17 — Discount band by category
_13 rows, first 12 shown_
| category | discount_band | lines | sales | share_of_category_sales | profit | profit_margin |
|---|---|---|---|---|---|---|
| Furniture | No discount | 836 | 256,025.27 | 0.3452 | 58,133.08 | 0.2271 |
| Furniture | 1-20% | 743 | 290,823.78 | 0.3921 | 14,795.95 | 0.0509 |
| Furniture | 21-40% | 323 | 159,296.84 | 0.2148 | -29,261.79 | -0.1837 |
| Furniture | 41-60% | 203 | 33,113.14 | 0.0446 | -21,308.97 | -0.6435 |
| Furniture | 61-80% | 15 | 2,459.38 | 0.0033 | -3,894.94 | -1.5837 |
| Office Supplies | No discount | 3129 | 442,150.00 | 0.6149 | 130,506.11 | 0.2952 |
| Office Supplies | 1-20% | 2217 | 237,373.89 | 0.3301 | 39,124.83 | 0.1648 |
| Office Supplies | 61-80% | 680 | 39,523.15 | 0.0550 | -47,140.14 | -1.1927 |
| Technology | No discount | 833 | 389,733.20 | 0.4661 | 132,348.42 | 0.3396 |
| Technology | 1-20% | 843 | 318,324.57 | 0.3807 | 46,864.69 | 0.1472 |
| Technology | 21-40% | 136 | 74,559.68 | 0.0892 | -6,543.61 | -0.0878 |
| Technology | 41-60% | 12 | 37,935.07 | 0.0454 | -7,635.23 | -0.2013 |

## Q18 — Customer profitability table
_792 rows, first 12 shown_
| profit_rank | customer_id | customer_name | segment | orders | sales | profit | profit_margin | cumulative_share_of_profit |
|---|---|---|---|---|---|---|---|---|
| 1 | TC-20980 | Tamara Chand | Corporate | 5 | 19,052.22 | 8,981.32 | 0.4714 | 0.0315 |
| 2 | RB-19360 | Raymond Buch | Consumer | 6 | 15,117.34 | 6,976.10 | 0.4615 | 0.0559 |
| 3 | SC-20095 | Sanjit Chand | Consumer | 9 | 14,142.33 | 5,757.41 | 0.4071 | 0.0761 |
| 4 | HL-15040 | Hunter Lopez | Consumer | 6 | 12,873.30 | 5,622.43 | 0.4368 | 0.0958 |
| 5 | AB-10105 | Adrian Barton | Consumer | 10 | 14,473.57 | 5,444.81 | 0.3762 | 0.1149 |
| 6 | TA-21385 | Tom Ashbrook | Home Office | 4 | 14,595.62 | 4,703.79 | 0.3223 | 0.1313 |
| 7 | CM-12385 | Christopher Martinez | Consumer | 4 | 8,954.02 | 3,899.89 | 0.4355 | 0.1450 |
| 8 | KD-16495 | Keith Dawkins | Corporate | 12 | 8,181.26 | 3,038.63 | 0.3714 | 0.1557 |
| 9 | AR-10540 | Andy Reiter | Consumer | 6 | 6,608.45 | 2,884.62 | 0.4365 | 0.1658 |
| 10 | DR-12940 | Daniel Raglin | Home Office | 8 | 8,350.87 | 2,869.08 | 0.3436 | 0.1758 |
| 11 | TB-21400 | Tom Boeckenhauer | Consumer | 7 | 9,133.99 | 2,798.37 | 0.3064 | 0.1856 |
| 12 | NM-18445 | Nathan Mautz | Home Office | 7 | 6,459.34 | 2,751.68 | 0.4260 | 0.1953 |

## Q19 — Customer profit by decile
_10 rows_
| profit_decile | customers | unprofitable_customers | sales | profit | share_of_profit | cumulative_share_of_profit | min_customer_profit | max_customer_profit |
|---|---|---|---|---|---|---|---|---|
| 1 | 80 | 0 | 603,295.26 | 165,235.41 | 0.5790 | 0.5790 | 1,158.71 | 8,981.32 |
| 2 | 80 | 0 | 342,408.41 | 69,003.87 | 0.2418 | 0.8207 | 682.55 | 1,155.43 |
| 3 | 79 | 0 | 253,544.34 | 43,858.80 | 0.1537 | 0.9744 | 456.86 | 682.17 |
| 4 | 79 | 0 | 190,688.09 | 30,022.18 | 0.1052 | 1.0796 | 316.52 | 455.53 |
| 5 | 79 | 0 | 166,691.78 | 21,061.81 | 0.0738 | 1.1534 | 227.44 | 315.22 |
| 6 | 79 | 0 | 148,553.18 | 15,168.77 | 0.0531 | 1.2066 | 154.06 | 226.45 |
| 7 | 79 | 0 | 105,272.21 | 9,118.32 | 0.0319 | 1.2385 | 83.9600 | 150.71 |
| 8 | 79 | 0 | 89,338.44 | 3,139.71 | 0.0110 | 1.2495 | 0.6000 | 83.2700 |
| 9 | 79 | 76 | 114,224.15 | -5,457.89 | -0.0191 | 1.2304 | -188.25 | 0.4600 |
| 10 | 79 | 79 | 278,279.04 | -65,753.64 | -0.2304 | 1.0000 | -6,626.39 | -196.12 |

## Q20 — Profitable vs unprofitable customers
_2 rows_
| customer_status | customers | share_of_customers | sales | share_of_sales | profit |
|---|---|---|---|---|---|
| Profitable | 637 | 0.8043 | 1,900,625.88 | 0.8291 | 356,609.75 |
| Unprofitable | 155 | 0.1957 | 391,669.03 | 0.1709 | -71,212.42 |

## Q21 — Repeat purchasing: customers by number of orders
_5 rows_
| order_frequency_band | customers | share_of_customers | share_of_sales | share_of_profit | profit_per_customer |
|---|---|---|---|---|---|
| 1 order | 12 | 0.0152 | 0.0023 | 0.0027 | 63.9500 |
| 2-3 orders | 87 | 0.1098 | 0.0432 | 0.0162 | 53.1100 |
| 4-6 orders | 337 | 0.4255 | 0.3533 | 0.3616 | 306.20 |
| 7-10 orders | 307 | 0.3876 | 0.4819 | 0.5012 | 465.95 |
| 11+ orders | 49 | 0.0619 | 0.1193 | 0.1183 | 689.24 |

## Q22 — Year-over-year customer retention
_3 rows_
| base_year | active_customers | retained_next_year | retention_rate |
|---|---|---|---|
| 2023 | 594 | 436 | 0.7340 |
| 2024 | 572 | 451 | 0.7885 |
| 2025 | 637 | 557 | 0.8744 |
