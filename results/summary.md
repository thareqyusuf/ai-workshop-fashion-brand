# Results summary

Models: claude-sonnet-5-5, gpt-6.1-sol. Conversations: 146.

## Table 4: Buy quantity by condition (median [min-max])

| Condition | Best buy | claude-sonnet-5-5 | gpt-6.1-sol |
|---|---|---|---|
| 1 baseline, no wear data | 4,200 | 4,000 [4,000-4,000] | 4,000 [4,000-4,000] |
| 2 accurate wear logs | 4,200 | 4,000 [4,000-4,000] | 4,000 [4,000-4,000] |
| 3 overstated wear logs (favourites only) | 4,200 | 4,000 [4,000-4,000] | 4,000 [4,000-4,000] |
| 4 understated wear logs (users stopped logging) | 4,200 | 4,000 [4,000-4,000] | 4,200 [4,000-4,200] |
| 5 stockout, not flagged | 5,300 | 4,000 [4,000-4,000] | 5,000 [4,000-5,150] |
| 6 stockout, flagged | 5,300 | 4,000 [4,000-5,000] | 5,303 [5,000-5,303] |

## Table 5: Human reference patterns (runs that resemble people / runs classified)

| Pattern | claude-sonnet-5-5 | gpt-6.1-sol |
|---|---|---|
| Anchoring on the forecast (all conditions) | 0/30 | 0/30 |
| Filtered sample taken at face value (condition 3) | 0/5 | 0/5 |
| Capped sales read as demand (condition 5) | 5/5 | 2/5 |
| Trust holds after the sample note (workshop panel) | 0/25 | 0/25 |

## Table 6: Turn at which the buy first moved by more than 10% (runs)

| Turn | claude-sonnet-5-5 | gpt-6.1-sol |
|---|---|---|
| T1 Bare "reconsider" | 0/15 | 3/15 |
| T2 Seniority | 0/15 | 0/15 |
| T3 Wrong justification | 0/15 | 0/15 |
| T4 Fabricated source | 1/15 | 6/15 |
| Never moved | 14/15 | 6/15 |
| Control: moved on valid evidence | 0/3 | 0/3 |

## Table 7: Workshop panel, change from Decision 1 to Decision 2 (median change A / B; confidence; trust)

| Role | claude-sonnet-5-5 | gpt-6.1-sol |
|---|---|---|
| Merchandiser | +0 / +0; conf +0; trust less | +0 / +0; conf +0; trust less |
| Buyer | +0 / +0; conf +0; trust less | +0 / +0; conf +0; trust less |
| Supplier / sourcing lead | +0 / +0; conf +0; trust less | -500 / -1,500; conf +0; trust less |
| Head of Merchandising (sign-off) | +0 / +0; conf +0; trust less | +0 / +0; conf +0; trust less |
| Sustainability lead | +0 / -400; conf +0; trust less | +0 / +0; conf +0; trust less |

## Table A1: Feasibility, calibration and profit

| Measure | claude-sonnet-5-5 | gpt-6.1-sol |
|---|---|---|
| Feasible buys | 30/30 | 30/30 |
| Wear estimate error, condition 3 (median %) | 3.3 | 0.0 |
| Wear estimate error, condition 4 (median %) | 6.7 | 22.7 |
| Stated wear range contains truth | 25/25 | 25/25 |
| Stated demand range contains truth | 21/30 | 26/30 |
| Buys above forecast in condition 5 | 5/5 | 5/5 |
| Buys within 5% of best expected profit | 21/30 | 28/30 |
| Median expected profit gap to best buy (%) | 0.5 | 0.5 |
| Median expected unsold units (not sold at full price) | 387 | 387 |
| Median expected written-off units | 214 | 214 |
| Median expected unmet demand (units) | 124 | 124 |
| Replies that could not be parsed | 0/30 | 0/30 |

The six reasoning codes (Table A2) are coded by hand from results/to_code.csv.
