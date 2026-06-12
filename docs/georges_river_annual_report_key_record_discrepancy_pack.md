# GRDCC Annual Report Key Record Discrepancy Pack

## Purpose
This is a read-only discrepancy pack comparing the 2024-25 Annual Report against PlayCricket, Historical Excel, and final app-facing source logic.

## Final Source Logic Used
- Historical Excel through Summer 1971/72.
- PlayCricket from Summer 1972/73 onward.
- Sources are never summed for the same player-season.

## Executive Summary
- Total discrepancy/review rows: **182**
- Top scorer rows: **75**
- Top wicket-taker rows: **30**
- 500-run season rows: **60**
- 50-wicket season rows: **17**
- Private-preview blockers: **0**
- Authoritative-record blockers: **135**

## Top Scorer / Most Runs
Harry Milburn is the key career discrepancy: Annual Report **10,788**, clean alias-aware Excel **10,035**, PlayCricket **891**, and current final logic **8,865**. The gap is explained by unresolved `H Milburn` aliases, a quarantined Summer 1970/71 row, and likely pre-1948/49 missing coverage. Resolve the proven aliases and 1970/71 evidence before claiming authoritative career alignment.

## Top Wicket-Taker / Most Wickets
Gordon Leslie is the key career discrepancy: Annual Report **707**, clean alias-aware Excel **327**, PlayCricket **0**, and current final logic **242**. The raw workbook reconstructs 707 exactly. The current gap comes from unresolved `G Leslie` aliases and a shifted-column ingestion issue affecting 1954/55-1964/65.

## 500 Runs in a Season
The underlying validation contains **52 exact matches**, **15 report-row reviews**, and **5 material report/source mismatches**. The focused pack also includes source-only threshold rows requiring scope review.

Material mismatches:
- C. Warren Summer 1949/50: Annual Report 618 vs final logic 615.
- Harry Milburn Summer 1962/63: Annual Report 573 vs final logic 575.
- Jason Lill Summer 2009/10: Annual Report 540 vs final logic 544.
- Christopher McArthur Summer 2016/17: Annual Report 530 vs final logic 625.
- Christopher McArthur Summer 2023/24: Annual Report 583 vs final logic 605.

## 50 Wickets in a Season
The underlying validation contains **14 exact matches** and **10 historical report rows missing from or requiring review against the current final source data**. The focused pack contains **17** review/discrepancy rows after including source-only threshold candidates. Likely causes include historical name variants, missing coverage, and the shifted-column Excel bowling parsing issue.

## Preview Readiness
These discrepancies do not block a caveated private preview because no high-severity odd source record remains app-facing. They do block an authoritative claim that all career and historical threshold records fully align with the Annual Report.

Selected all-time career records now have a separate approved Annual Report featured-record override layer. Harry Milburn's 10,788 runs and Gordon Leslie's 707 wickets are displayed as official Annual Report totals without altering source rows or season-level calculations.

## Recommended Next Actions
1. Resolve Gordon Leslie's shifted-column Excel ingestion issue.
2. Resolve Harry Milburn aliases and the quarantined Summer 1970/71 row.
3. Re-run Annual Report key-record validation.
4. Only then claim authoritative career/all-time record alignment.
