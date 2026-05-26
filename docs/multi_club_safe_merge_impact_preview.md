# Multi-Club Safe Merge Impact Preview

This preview uses the existing generated review packs only. No duplicate merges have been applied, no `manual_player_merges.csv` files have been edited, and no match-centre/backfill data is included. FVCC is not part of this preview.

The current safe candidate files are aggregate-only: `matches_seen_count` is `0` in the generated rows because verified match IDs are not present in these packs. The tables therefore use a `match-row proxy`, calculated from the available batting/bowling/fielding row counts, to rank likely impact without fabricating match-level evidence.

Suspicious flags are review cautions only. They do not remove a row from the safe candidate CSV. I flagged groups with more than 3 profiles, very high combined stats (3000+ runs, 150+ wickets, 80+ catches, or 40+ match-row proxy), initial-like name tokens, first/middle-token variation, common surnames (`Singh`, `Patel`, `Sharma`, `Thomas`, `Khan`, `Kumar`), and adjacent-season handoffs when another identity-risk signal is present.

## Apply Order Recommendation

Safest club to apply first: **Southside East Caulfield**.
Highest-risk club: **Georges River District** based on suspicious group volume and candidate complexity.

| Rank | Club | Safe groups | Raw profiles affected | Suspicious safe groups | Manual duplicate groups | Recommended action |
|---:|---|---:|---:|---:|---:|---|
| 1 | Southside East Caulfield | 26 | 52 | 8 | 14 | Apply safe merges after spot-checking suspicious rows |
| 2 | Glen Waverley Hawks | 54 | 108 | 9 | 17 | Apply safe merges after spot-checking suspicious rows |
| 3 | Ashwood | 95 | 191 | 11 | 12 | Review suspicious rows before applying |
| 4 | Plenty | 84 | 171 | 13 | 11 | Review suspicious rows before applying |
| 5 | Reynella | 111 | 225 | 14 | 12 | Review suspicious rows before applying |
| 6 | Georges River District | 74 | 149 | 15 | 11 | Review suspicious rows before applying |

Recommended order: Southside East Caulfield -> Glen Waverley Hawks -> Ashwood -> Plenty -> Reynella -> Georges River District.

## Apply-Mode Design Only

Apply mode has not been implemented in this step. If approved later, the low-risk design is:

- Command: `scripts/build_club_review_pack.py --club <club_id> --apply-safe-auto-merges`.
- Output target: only `clubs/<club_id>/manual_player_merges.csv`.
- FVCC guard: never touches FVCC unless `--club fvcc` is explicitly provided.
- Suspicious guard: skips suspicious safe groups unless `--include-suspicious` is explicitly passed.
- Duplicate guard: does not add rows already present in the club mapping file.
- Transparency: prints every exact row it adds.
- Safety preflight: requires a clean working tree before writing mappings.

## Reynella

- Safe auto-merge groups: 111
- Raw profiles affected: 225
- Suspicious safe groups: 14
- Manual duplicate review groups: 12

Punctuation-only examples: none found in the current safe file.

Exact case-insensitive examples: Adam Ellis (Adam Ellis); Aidan Richardson (Aidan Richardson); Aidan Secomb (Aidan Secomb); Aiden Shaw (Aiden Shaw); Alannah Rochow (Alannah Rochow)

Blocked due to season overlap: Brett Julian (3 profiles; overlap Summer 2022/23); Colin Rowston (2 profiles; overlap Summer 2014/15 | Summer 2015/16 | Summer 2016/17 | Summer 2017/18 | Summer 2018/19); Daivik Kumar (2 profiles; overlap Summer 2022/23); Ethan Sheppard (2 profiles; overlap Summer 2022/23); Luke Hardy (2 profiles; overlap Summer 2022/23)

Safe groups that still look suspicious: Richard Gabb [high stats, adjacent handoff caution]; Paul Radbourne [high stats, adjacent handoff caution]; Shaun Newell [high stats, adjacent handoff caution]; Adam Ellis [high stats, adjacent handoff caution]; Jonathon Hague [high stats, adjacent handoff caution]; Mark Nankervis [high stats, adjacent handoff caution]; Damien Pimlott [high stats, adjacent handoff caution]; Mark Walters [high stats, adjacent handoff caution]

Top 20 safe groups by combined runs/wickets/match-row proxy:

| Proposed canonical | Raw names | Seasons per raw profile | R/W/C | Match-row proxy | Reason/confidence | Suspicious flags |
|---|---|---|---:|---:|---|---|
| Richard Gabb | Richard Gabb | Richard Gabb: 12 seasons: S2007/08 to S2021/22<br>Richard Gabb: S2022/23, S2023/24, S2024/25 | 7829/5/251 | 42 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Paul Radbourne | Paul Radbourne | Paul Radbourne: 15 seasons: S2007/08 to S2021/22<br>Paul Radbourne: 4 seasons: S2022/23 to S2025/26 | 5910/160/95 | 42 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Andrew Semple | Andrew Semple | Andrew Semple: S2023/24<br>Andrew Semple: 12 seasons: S2007/08 to S2021/22 | 3959/6/71 | 18 | exact case-insensitive name match; no season overlap; high | high stats |
| Shaun Newell | Shaun Newell | Shaun Newell: 11 seasons: S2008/09 to S2019/20<br>Shaun Newell: S2020/21, S2021/22<br>Shaun Newell: S2022/23 | 3506/0/64 | 42 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Josh Rudd | Josh Rudd | Josh Rudd: S2025/26<br>Josh Rudd: 9 seasons: S2008/09 to S2021/22 | 3253/36/34 | 34 | exact case-insensitive name match; no season overlap; high | high stats |
| Adam Ellis | Adam Ellis | Adam Ellis: 4 seasons: S2022/23 to S2025/26<br>Adam Ellis: 13 seasons: S2008/09 to S2021/22 | 3209/208/47 | 42 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Jonathon Hague | Jonathon Hague | Jonathon Hague: 14 seasons: S2009/10 to S2023/24<br>Jonathon Hague: S2024/25 | 3142/249/73 | 53 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Wayne Copley | Wayne Copley | Wayne Copley: 4 seasons: S2022/23 to S2025/26<br>Wayne Copley: 14 seasons: S2008/09 to S2021/22 | 2855/48/46 | 32 | exact case-insensitive name match; no season overlap; high | none |
| Mark Nankervis | Mark Nankervis | Mark Nankervis: 10 seasons: S2012/13 to S2021/22<br>Mark Nankervis: S2022/23 | 2802/171/44 | 37 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Jo Cooke | Jo Cooke | Jo Cooke: 4 seasons: S2018/19 to S2021/22<br>Jo Cooke: 4 seasons: S2022/23 to S2025/26 | 2769/101/27 | 10 | exact case-insensitive name match; no season overlap; high | none |
| Damien Pimlott | Damien Pimlott | Damien Pimlott: S2022/23, S2023/24, S2024/25<br>Damien Pimlott: 15 seasons: S2007/08 to S2021/22 | 2651/290/52 | 39 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Jason Jennings | Jason Jennings | Jason Jennings: 4 seasons: S2007/08 to S2021/22<br>Jason Jennings: 4 seasons: S2022/23 to S2025/26 | 2077/10/28 | 19 | exact case-insensitive name match; no season overlap; high | none |
| Josh Burrows | Josh Burrows | Josh Burrows: 4 seasons: S2022/23 to S2025/26<br>Josh Burrows: 6 seasons: S2016/17 to S2021/22 | 1972/120/62 | 33 | exact case-insensitive name match; no season overlap; high | none |
| Mark Walters | Mark Walters | Mark Walters: 12 seasons: S2008/09 to S2021/22<br>Mark Walters: S2022/23 | 1570/167/34 | 31 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Ashley Mack | Ashley Mack | Ashley Mack: 13 seasons: S2007/08 to S2020/21<br>Ashley Mack: S2023/24 | 1567/0/28 | 28 | exact case-insensitive name match; no season overlap; high | none |
| Jayden Simons | Jayden Simons | Jayden Simons: S2019/20, S2020/21, S2021/22<br>Jayden Simons: 4 seasons: S2022/23 to S2025/26 | 1512/9/38 | 11 | exact case-insensitive name match; no season overlap; high | none |
| Jake Shaw | Jake Shaw | Jake Shaw: 10 seasons: S2012/13 to S2021/22<br>Jake Shaw: S2022/23, S2023/24 | 1433/144/36 | 31 | exact case-insensitive name match; no season overlap; high | none |
| Brock Carlisle | Brock Carlisle | Brock Carlisle: S2020/21, S2021/22<br>Brock Carlisle: 4 seasons: S2022/23 to S2025/26 | 1412/17/48 | 14 | exact case-insensitive name match; no season overlap; high | none |
| Mitchell Trenorden | Mitchell Trenorden | Mitchell Trenorden: 4 seasons: S2022/23 to S2025/26<br>Mitchell Trenorden: 4 seasons: S2017/18 to S2021/22 | 1208/41/23 | 12 | exact case-insensitive name match; no season overlap; high | none |
| Tanner Kenny | Tanner Kenny | Tanner Kenny: 6 seasons: S2015/16 to S2021/22<br>Tanner Kenny: S2023/24 | 1125/33/10 | 8 | exact case-insensitive name match; no season overlap; high | none |

## Ashwood

- Safe auto-merge groups: 95
- Raw profiles affected: 191
- Suspicious safe groups: 11
- Manual duplicate review groups: 12

Punctuation-only examples: Jordan D'Silva (Jordan D'Silva, Jordan Dsilva)

Exact case-insensitive examples: Aadithya Pai (Aadithya Pai); Aaryan Panchal (Aaryan Panchal); Aidan Morton (Aidan Morton); Aiden Smith (Aiden Smith); Alex Hamlyn (Alex Hamlyn)

Blocked due to season overlap: Daksh Sharma (2 profiles; overlap Summer 2023/24); Dale Healy (2 profiles; overlap Summer 2019/20 | Summer 2020/21 | Summer 2021/22); Jasmeet Singh (2 profiles; overlap Summer 2021/22); Lachlan Smith (3 profiles; overlap Summer 2019/20); Manoj Sharma (2 profiles; overlap Summer 2019/20)

Safe groups that still look suspicious: Anthony Edmonds [high stats, adjacent handoff caution]; Jarrod Dennis [high stats, adjacent handoff caution]; Ari Morton [high stats, adjacent handoff caution]; Timothy Pape [high stats, adjacent handoff caution]; Yuvraj Singh [common surname, adjacent handoff caution]; Jordan D'Silva [initial-like token, first/middle variation]; Partha Patel [common surname, adjacent handoff caution]; Zara Sharma [common surname, adjacent handoff caution]

Top 20 safe groups by combined runs/wickets/match-row proxy:

| Proposed canonical | Raw names | Seasons per raw profile | R/W/C | Match-row proxy | Reason/confidence | Suspicious flags |
|---|---|---|---:|---:|---|---|
| Anthony Edmonds | Anthony Edmonds | Anthony Edmonds: 19 seasons: S2001/02 to S2022/23<br>Anthony Edmonds: S2023/24, S2024/25, S2025/26 | 6441/6/120 | 35 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Jarrod Dennis | Jarrod Dennis | Jarrod Dennis: S2023/24, S2024/25, S2025/26<br>Jarrod Dennis: 5 seasons: S2018/19 to S2022/23 | 3521/26/46 | 20 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Brendan Jones | Brendan Jones | Brendan Jones: 8 seasons: S2015/16 to S2022/23<br>Brendan Jones: S2023/24, S2024/25, S2025/26 | 2961/88/24 | 30 | exact case-insensitive name match; no season overlap; high | none |
| Hugo Fitton | Hugo Fitton | Hugo Fitton: S2023/24, S2024/25<br>Hugo Fitton: S2025/26<br>Hugo Fitton: 5 seasons: S2018/19 to S2022/23 | 2870/101/29 | 25 | exact case-insensitive name match; no season overlap; high | adjacent handoff caution |
| Anthony Papalia | Anthony Papalia | Anthony Papalia: S2023/24<br>Anthony Papalia: 10 seasons: S2013/14 to S2022/23 | 2423/40/35 | 25 | exact case-insensitive name match; no season overlap; high | none |
| Jack Von Fersen | Jack Von Fersen | Jack Von Fersen: 9 seasons: S2014/15 to S2022/23<br>Jack Von Fersen: S2023/24 | 2281/130/56 | 28 | exact case-insensitive name match; no season overlap; high | none |
| Ari Morton | Ari Morton | Ari Morton: S2023/24, S2024/25, S2025/26<br>Ari Morton: 5 seasons: S2018/19 to S2022/23 | 2144/53/101 | 10 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Oscar Sarafian | Oscar Sarafian | Oscar Sarafian: S2023/24, S2024/25, S2025/26<br>Oscar Sarafian: S2021/22, S2022/23 | 2131/77/36 | 17 | exact case-insensitive name match; no season overlap; high | none |
| James Dunn | James Dunn | James Dunn: S2023/24<br>James Dunn: 12 seasons: S2008/09 to S2020/21 | 2052/135/45 | 21 | exact case-insensitive name match; no season overlap; high | none |
| William Croxford | William Croxford | William Croxford: 7 seasons: S2016/17 to S2022/23<br>William Croxford: S2023/24 | 1810/37/48 | 23 | exact case-insensitive name match; no season overlap; high | none |
| Jack Moore | Jack Moore | Jack Moore: S2018/19, S2019/20, S2020/21<br>Jack Moore: S2023/24, S2024/25, S2025/26 | 1751/17/16 | 13 | exact case-insensitive name match; no season overlap; high | none |
| Timothy Pape | Timothy Pape | Timothy Pape: S2023/24, S2024/25, S2025/26<br>Timothy Pape: 17 seasons: S2006/07 to S2022/23 | 1631/288/78 | 35 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Angus Haworth | Angus Haworth | Angus Haworth: S2020/21, S2021/22, S2022/23<br>Angus Haworth: S2023/24, S2024/25, S2025/26 | 1626/62/31 | 16 | exact case-insensitive name match; no season overlap; high | none |
| Nigel Arulanandam | Nigel Arulanandam | Nigel Arulanandam: 5 seasons: S2018/19 to S2022/23<br>Nigel Arulanandam: S2024/25 | 1517/5/24 | 7 | exact case-insensitive name match; no season overlap; high | none |
| Harein Malawwethantri | Harein Malawwethantri | Harein Malawwethantri: S2023/24, S2024/25, S2025/26<br>Harein Malawwethantri: 5 seasons: S2018/19 to S2022/23 | 1328/71/19 | 13 | exact case-insensitive name match; no season overlap; high | none |
| Pascal Traczewski | Pascal Traczewski | Pascal Traczewski: S2023/24, S2024/25, S2025/26<br>Pascal Traczewski: S2021/22, S2022/23 | 1304/31/16 | 13 | exact case-insensitive name match; no season overlap; high | none |
| Cohen Billing | Cohen Billing | Cohen Billing: 4 seasons: S2019/20 to S2022/23<br>Cohen Billing: S2023/24, S2024/25, S2025/26 | 1032/77/33 | 10 | exact case-insensitive name match; no season overlap; high | none |
| Charlie Hawtin | Charlie Hawtin | Charlie Hawtin: S2023/24, S2024/25, S2025/26<br>Charlie Hawtin: 7 seasons: S2016/17 to S2022/23 | 916/145/23 | 27 | exact case-insensitive name match; no season overlap; high | none |
| Thomas Lee | Thomas Lee | Thomas Lee: S2023/24<br>Thomas Lee: 5 seasons: S2011/12 to S2022/23 | 886/16/22 | 17 | exact case-insensitive name match; no season overlap; high | none |
| Dansiam Rainsford | Dansiam Rainsford | Dansiam Rainsford: S2023/24, S2024/25, S2025/26<br>Dansiam Rainsford: 6 seasons: S2017/18 to S2022/23 | 880/34/34 | 17 | exact case-insensitive name match; no season overlap; high | none |

## Glen Waverley Hawks

- Safe auto-merge groups: 54
- Raw profiles affected: 108
- Suspicious safe groups: 9
- Manual duplicate review groups: 17

Punctuation-only examples: none found in the current safe file.

Exact case-insensitive examples: Aaditya Sharma (Aaditya Sharma); Aansh Pandya (Aansh Pandya); Ahilan Sivakumaran (Ahilan Sivakumaran); Ahmed Virk (Ahmed Virk); Andrew Robjant (Andrew Robjant)

Blocked due to season overlap: Ashton Scott (2 profiles; overlap Summer 2016/17 | Summer 2017/18); Krish Agrawal (3 profiles; overlap Summer 2019/20); Martin Fleming (2 profiles; overlap Summer 1999/00 | Summer 2000/01 | Summer 2001/02 | Summer 2002/03 | Summer 2003/04 | Summer 2006/07); N Cameron (2 profiles; overlap Summer 1996/97 | Summer 1997/98); Neeraj Kochhar (2 profiles; overlap Summer 2022/23)

Safe groups that still look suspicious: Liam O'Rourke [high stats, initial-like token, adjacent handoff caution]; Greg Mccormick [high stats, adjacent handoff caution]; Paul Young [high stats, adjacent handoff caution]; Nathan Bungey [high stats, adjacent handoff caution]; Mitchell Kohne [high stats, adjacent handoff caution]; Reece Anderson [high stats, adjacent handoff caution]; Darsh Singh [common surname, adjacent handoff caution]; Aaditya Sharma [common surname, adjacent handoff caution]

Top 20 safe groups by combined runs/wickets/match-row proxy:

| Proposed canonical | Raw names | Seasons per raw profile | R/W/C | Match-row proxy | Reason/confidence | Suspicious flags |
|---|---|---|---:|---:|---|---|
| Greg Mccormick | Greg Mccormick | Greg Mccormick: 27 seasons: S1996/97 to S2022/23<br>Greg Mccormick: S2023/24 | 6278/230/87 | 41 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Paul Young | Paul Young | Paul Young: 7 seasons: S2016/17 to S2022/23<br>Paul Young: S2023/24, S2024/25, S2025/26 | 4282/7/44 | 29 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Ahilan Sivakumaran | Ahilan Sivakumaran | Ahilan Sivakumaran: 9 seasons: S2016/17 to S2025/26<br>Ahilan Sivakumaran: S2019/20 | 3185/43/83 | 19 | exact case-insensitive name match; no season overlap; high | high stats |
| Nathan Bungey | Nathan Bungey | Nathan Bungey: 28 seasons: S1995/96 to S2022/23<br>Nathan Bungey: S2023/24, S2024/25, S2025/26 | 3017/386/108 | 51 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Darren Dineshkumar | Darren Dineshkumar | Darren Dineshkumar: 6 seasons: S2017/18 to S2022/23<br>Darren Dineshkumar: S2023/24, S2024/25, S2025/26 | 2714/52/33 | 18 | exact case-insensitive name match; no season overlap; high | none |
| Mitchell Kohne | Mitchell Kohne | Mitchell Kohne: S2023/24, S2024/25<br>Mitchell Kohne: 9 seasons: S2014/15 to S2022/23 | 2404/159/49 | 31 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Kiruba Sathiyaseelan | Kiruba Sathiyaseelan | Kiruba Sathiyaseelan: 9 seasons: S2004/05 to S2022/23<br>Kiruba Sathiyaseelan: S2023/24 | 2341/42/30 | 18 | exact case-insensitive name match; no season overlap; high | none |
| James Stevenson | James Stevenson | James Stevenson: 9 seasons: S1999/00 to S2016/17<br>James Stevenson: S2024/25 | 1989/53/26 | 12 | exact case-insensitive name match; no season overlap; high | none |
| Mahir Qureshi | Mahir Qureshi | Mahir Qureshi: S2023/24, S2024/25<br>Mahir Qureshi: 8 seasons: S2004/05 to S2022/23 | 1868/70/26 | 18 | exact case-insensitive name match; no season overlap; high | none |
| Liam O'Rourke | Liam O'Rourke | Liam O'Rourke: 8 seasons: S2015/16 to S2022/23<br>Liam O'Rourke: S2023/24, S2024/25, S2025/26 | 1618/46/116 | 28 | exact case-insensitive name match; no season overlap; high | high stats, initial-like token, adjacent handoff caution |
| Noel Blacker | Noel Blacker | Noel Blacker: 5 seasons: S2018/19 to S2022/23<br>Noel Blacker: S2023/24, S2024/25, S2025/26 | 1596/16/13 | 15 | exact case-insensitive name match; no season overlap; high | none |
| Sachith Prasad | Sachith Prasad | Sachith Prasad: S2023/24, S2024/25<br>Sachith Prasad: 14 seasons: S2006/07 to S2022/23 | 1593/81/47 | 30 | exact case-insensitive name match; no season overlap; high | none |
| Liam Powell | Liam Powell | Liam Powell: S2024/25<br>Liam Powell: 9 seasons: S2011/12 to S2019/20 | 1564/33/68 | 17 | exact case-insensitive name match; no season overlap; high | none |
| Anthony Stiles | Anthony Stiles | Anthony Stiles: S2023/24, S2024/25, S2025/26<br>Anthony Stiles: S2020/21, S2021/22, S2022/23 | 1462/0/36 | 10 | exact case-insensitive name match; no season overlap; high | none |
| Reece Anderson | Reece Anderson | Reece Anderson: S2023/24, S2024/25, S2025/26<br>Reece Anderson: 8 seasons: S2015/16 to S2022/23 | 1408/151/42 | 30 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Max Taborsky | Max Taborsky | Max Taborsky: S2023/24, S2025/26<br>Max Taborsky: 8 seasons: S2015/16 to S2022/23 | 1093/62/67 | 19 | exact case-insensitive name match; no season overlap; high | none |
| Harindra Mendu | Harindra Mendu | Harindra Mendu: 6 seasons: S2017/18 to S2022/23<br>Harindra Mendu: S2023/24, S2024/25 | 977/64/19 | 19 | exact case-insensitive name match; no season overlap; high | none |
| Aansh Pandya | Aansh Pandya | Aansh Pandya: S2023/24, S2024/25, S2025/26<br>Aansh Pandya: 5 seasons: S2018/19 to S2022/23 | 950/31/25 | 9 | exact case-insensitive name match; no season overlap; high | none |
| Austin Swamy | Austin Swamy | Austin Swamy: S2024/25<br>Austin Swamy: 9 seasons: S2012/13 to S2022/23 | 900/73/32 | 18 | exact case-insensitive name match; no season overlap; high | none |
| Sankar Melethat | Sankar Melethat | Sankar Melethat: S2025/26<br>Sankar Melethat: 6 seasons: S2012/13 to S2017/18 | 885/14/11 | 7 | exact case-insensitive name match; no season overlap; high | none |

## Plenty

- Safe auto-merge groups: 84
- Raw profiles affected: 171
- Suspicious safe groups: 13
- Manual duplicate review groups: 11

Punctuation-only examples: Hamish O'Halloran (Hamish O'Halloran, Hamish Ohalloran)

Exact case-insensitive examples: Aaryan Chopra (Aaryan Chopra); Aayaan Aswal (Aayaan Aswal); Abhayveer Uppal (Abhayveer Uppal); Andrew Frederiksen (Andrew Frederiksen); Andrew King (Andrew King)

Blocked due to season overlap: Angus Regan (3 profiles; overlap Summer 2021/22 | Summer 2022/23); Brent Redmond (2 profiles; overlap Summer 2003/04); Cameron Fitzgerald (2 profiles; overlap Summer 2021/22); Dean Barnett (2 profiles; overlap Summer 2022/23); John Sacchetta (2 profiles; overlap Summer 2011/12)

Safe groups that still look suspicious: Mitch Johnson [high stats, adjacent handoff caution]; Gordon Zull [high stats, adjacent handoff caution]; Matt Deligiorgis [high stats, adjacent handoff caution]; Tom Weir [high stats, adjacent handoff caution]; Nicholas Curtin [high stats, adjacent handoff caution]; Owen Pisani [high stats, adjacent handoff caution]; Shane Cullen [high stats, adjacent handoff caution]; Hamish O'Halloran [initial-like token, first/middle variation]

Top 20 safe groups by combined runs/wickets/match-row proxy:

| Proposed canonical | Raw names | Seasons per raw profile | R/W/C | Match-row proxy | Reason/confidence | Suspicious flags |
|---|---|---|---:|---:|---|---|
| Mitch Johnson | Mitch Johnson | Mitch Johnson: S2023/24, S2024/25<br>Mitch Johnson: 18 seasons: S2002/03 to S2022/23 | 7061/176/68 | 39 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Gordon Zull | Gordon Zull | Gordon Zull: 18 seasons: S2002/03 to S2022/23<br>Gordon Zull: S2023/24, S2024/25, S2025/26 | 6946/99/90 | 42 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Scott Keane | Scott Keane | Scott Keane: S2023/24, S2024/25, S2025/26<br>Scott Keane: 18 seasons: S2002/03 to S2021/22 | 4471/0/139 | 41 | exact case-insensitive name match; no season overlap; high | high stats |
| Matt Deligiorgis | Matt Deligiorgis | Matt Deligiorgis: 20 seasons: S2002/03 to S2022/23<br>Matt Deligiorgis: S2023/24, S2024/25, S2025/26 | 3607/47/139 | 33 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Tom Weir | Tom Weir | Tom Weir: S2023/24, S2024/25, S2025/26<br>Tom Weir: 8 seasons: S2015/16 to S2022/23 | 3580/25/49 | 17 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Graeme Pavey | Graeme Pavey | Graeme Pavey: 15 seasons: S2002/03 to S2021/22<br>Graeme Pavey: S2024/25, S2025/26 | 3407/42/42 | 28 | exact case-insensitive name match; no season overlap; high | high stats |
| Nicholas Curtin | Nicholas Curtin | Nicholas Curtin: 10 seasons: S2003/04 to S2022/23<br>Nicholas Curtin: S2023/24, S2024/25 | 3324/2/24 | 18 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| James King | James King | James King: S2023/24, S2024/25<br>James King: 12 seasons: S2011/12 to S2022/23 | 2468/90/42 | 30 | exact case-insensitive name match; no season overlap; high | none |
| David Love | David Love | David Love: S2024/25<br>David Love: 11 seasons: S2002/03 to S2014/15 | 2404/44/50 | 20 | exact case-insensitive name match; no season overlap; high | none |
| Ethan Weir | Ethan Weir | Ethan Weir: S2023/24, S2024/25, S2025/26<br>Ethan Weir: 8 seasons: S2015/16 to S2022/23 | 2053/122/40 | 31 | exact case-insensitive name match; no season overlap; high | none |
| Paul Alexopoulos | Paul Alexopoulos | Paul Alexopoulos: 5 seasons: S2018/19 to S2022/23<br>Paul Alexopoulos: S2023/24, S2024/25, S2025/26 | 1688/22/34 | 14 | exact case-insensitive name match; no season overlap; high | none |
| Owen Pisani | Owen Pisani | Owen Pisani: 9 seasons: S2014/15 to S2022/23<br>Owen Pisani: S2023/24, S2024/25 | 1632/50/88 | 23 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Kai Axton | Kai Axton | Kai Axton: S2023/24, S2024/25, S2025/26<br>Kai Axton: 6 seasons: S2017/18 to S2022/23 | 1592/73/52 | 18 | exact case-insensitive name match; no season overlap; high | none |
| Jesse King | Jesse King | Jesse King: S2024/25<br>Jesse King: 8 seasons: S2009/10 to S2020/21 | 1530/77/34 | 17 | exact case-insensitive name match; no season overlap; high | none |
| Shane Cullen | Shane Cullen | Shane Cullen: 17 seasons: S2002/03 to S2022/23<br>Shane Cullen: S2023/24, S2024/25, S2025/26 | 1397/357/22 | 38 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Ashley Coles | Ashley Coles | Ashley Coles: 5 seasons: S2017/18 to S2022/23<br>Ashley Coles: S2023/24 | 1387/77/8 | 11 | exact case-insensitive name match; no season overlap; high | none |
| Liam Mallia | Liam Mallia | Liam Mallia: 7 seasons: S2014/15 to S2021/22<br>Liam Mallia: S2025/26 | 1327/7/14 | 15 | exact case-insensitive name match; no season overlap; high | none |
| Jack Burge | Jack Burge | Jack Burge: 13 seasons: S2010/11 to S2022/23<br>Jack Burge: S2023/24 | 1323/95/44 | 37 | exact case-insensitive name match; no season overlap; high | none |
| Matthew Tino | Matthew Tino | Matthew Tino: S2023/24, S2024/25<br>Matthew Tino: 9 seasons: S2014/15 to S2022/23 | 1316/42/18 | 21 | exact case-insensitive name match; no season overlap; high | none |
| Cillian Wenholz | Cillian Wenholz | Cillian Wenholz: S2023/24, S2024/25, S2025/26<br>Cillian Wenholz: 4 seasons: S2019/20 to S2022/23 | 1100/20/11 | 7 | exact case-insensitive name match; no season overlap; high | none |

## Georges River District

- Safe auto-merge groups: 74
- Raw profiles affected: 149
- Suspicious safe groups: 15
- Manual duplicate review groups: 11

Punctuation-only examples: Barry O'Rourke (Barry O'Rourke, Barry Orourke)

Exact case-insensitive examples: Adam Scott (Adam Scott); Aidan Wood (Aidan Wood); Alan Wright (Alan Wright); Alex Economou (Alex Economou); Alexander Ristevski (Alexander Ristevski)

Blocked due to season overlap: Peter Francis (2 profiles; overlap Summer 2012/13); Peter Thomas (4 profiles; overlap Summer 2016/17); Peter Trajkovski (2 profiles; overlap Summer 1983/84); Ranganatha Rangappa (2 profiles; overlap Summer 2021/22); Robert Stares (2 profiles; overlap Summer 2022/23)

Safe groups that still look suspicious: Paul Thomas [high stats, common surname, adjacent handoff caution]; Kevin Croom [high stats, adjacent handoff caution]; Peter Remfrey [high stats, adjacent handoff caution]; Sean Mantle [high stats, adjacent handoff caution]; Alex Economou [high stats, adjacent handoff caution]; Dave Jiffkins [high stats, adjacent handoff caution]; Riley Orr [high stats, adjacent handoff caution]; Robert Henriques [high stats, adjacent handoff caution]

Top 20 safe groups by combined runs/wickets/match-row proxy:

| Proposed canonical | Raw names | Seasons per raw profile | R/W/C | Match-row proxy | Reason/confidence | Suspicious flags |
|---|---|---|---:|---:|---|---|
| Kevin Croom | Kevin Croom | Kevin Croom: 37 seasons: S1983/84 to S2021/22<br>Kevin Croom: 4 seasons: S2022/23 to S2025/26 | 8782/5/101 | 70 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Peter Remfrey | Peter Remfrey | Peter Remfrey: 31 seasons: S1980/81 to S2021/22<br>Peter Remfrey: 4 seasons: S2022/23 to S2025/26 | 5777/19/133 | 64 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Sean Mantle | Sean Mantle | Sean Mantle: 18 seasons: S2004/05 to S2021/22<br>Sean Mantle: S2022/23, S2023/24 | 5316/19/81 | 46 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Alex Economou | Alex Economou | Alex Economou: 4 seasons: S2022/23 to S2025/26<br>Alex Economou: 17 seasons: S1996/97 to S2021/22 | 5190/4/123 | 29 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Dave Jiffkins | Dave Jiffkins | Dave Jiffkins: S2022/23, S2023/24, S2025/26<br>Dave Jiffkins: 26 seasons: S1994/95 to S2021/22 | 4683/518/100 | 49 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Martin Cole | Martin Cole | Martin Cole: 24 seasons: S1980/81 to S2020/21<br>Martin Cole: 4 seasons: S2022/23 to S2025/26 | 3560/58/39 | 49 | exact case-insensitive name match; no season overlap; high | high stats |
| Shane Pargeter | Shane Pargeter | Shane Pargeter: 10 seasons: S2011/12 to S2021/22<br>Shane Pargeter: S2023/24, S2025/26 | 3534/118/71 | 12 | exact case-insensitive name match; no season overlap; high | high stats |
| Paul Thomas | Paul Thomas | Paul Thomas: 4 seasons: S2022/23 to S2025/26<br>Paul Thomas: 50 seasons: S1968/69 to S2021/22 | 3379/620/94 | 93 | exact case-insensitive name match; no season overlap; high | high stats, common surname, adjacent handoff caution |
| Curtis Cheney | Curtis Cheney | Curtis Cheney: S2022/23, S2023/24, S2024/25<br>Curtis Cheney: 8 seasons: S2010/11 to S2020/21 | 3210/2/127 | 26 | exact case-insensitive name match; no season overlap; high | high stats |
| Riley Orr | Riley Orr | Riley Orr: 11 seasons: S2009/10 to S2021/22<br>Riley Orr: 4 seasons: S2022/23 to S2025/26 | 2536/226/93 | 37 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Lindsay Le Bas | Lindsay Le Bas | Lindsay Le Bas: 15 seasons: S1988/89 to S2021/22<br>Lindsay Le Bas: 4 seasons: S2022/23 to S2025/26 | 2421/110/61 | 34 | exact case-insensitive name match; no season overlap; high | none |
| Robert Henriques | Robert Henriques | Robert Henriques: S2022/23, S2023/24<br>Robert Henriques: 9 seasons: S2013/14 to S2021/22 | 2392/154/63 | 24 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Chris Benjamin | Chris Benjamin | Chris Benjamin: 10 seasons: S1989/90 to S2021/22<br>Chris Benjamin: S2022/23 | 2212/9/22 | 13 | exact case-insensitive name match; no season overlap; high | none |
| Ali Ali | Ali Ali | Ali Ali: 4 seasons: S2022/23 to S2025/26<br>Ali Ali: 19 seasons: S2002/03 to S2021/22 | 2200/331/91 | 68 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Fabian Heaton | Fabian Heaton | Fabian Heaton: 4 seasons: S2022/23 to S2025/26<br>Fabian Heaton: 9 seasons: S2013/14 to S2021/22 | 2001/12/60 | 20 | exact case-insensitive name match; no season overlap; high | none |
| George Hodgson | George Hodgson | George Hodgson: 5 seasons: S2016/17 to S2020/21<br>George Hodgson: S2014/15, S2015/16, S2021/22<br>George Hodgson: 4 seasons: S2022/23 to S2025/26 | 1537/43/19 | 24 | exact case-insensitive name match; no season overlap; high | none |
| Glenn Ross | Glenn Ross | Glenn Ross: 7 seasons: S1990/91 to S2002/03<br>Glenn Ross: S2022/23, S2023/24 | 1524/1/30 | 13 | exact case-insensitive name match; no season overlap; high | none |
| Neil Karpin | Neil Karpin | Neil Karpin: 9 seasons: S2013/14 to S2021/22<br>Neil Karpin: S2022/23, S2023/24, S2025/26 | 1506/39/10 | 19 | exact case-insensitive name match; no season overlap; high | none |
| Daniel Milliken | Daniel Milliken | Daniel Milliken: 4 seasons: S2018/19 to S2021/22<br>Daniel Milliken: 4 seasons: S2022/23 to S2025/26 | 1486/3/26 | 18 | exact case-insensitive name match; no season overlap; high | none |
| Brendan Dodd | Brendan Dodd | Brendan Dodd: S2024/25<br>Brendan Dodd: 6 seasons: S2009/10 to S2017/18 | 1180/3/46 | 17 | exact case-insensitive name match; no season overlap; high | none |

## Southside East Caulfield

- Safe auto-merge groups: 26
- Raw profiles affected: 52
- Suspicious safe groups: 8
- Manual duplicate review groups: 14

Punctuation-only examples: none found in the current safe file.

Exact case-insensitive examples: Arpan Desai (Arpan Desai); Deepak Gopalaraju (Deepak Gopalaraju); Denis Shaw (Denis Shaw); Falgun Patel (Falgun Patel); Francis Bernard (Francis Bernard)

Blocked due to season overlap: Ankit Patel (2 profiles; overlap Summer 2018/19); Ankur Sharma (2 profiles; overlap Summer 2012/13 | Summer 2013/14); Bhumil Patel (2 profiles; overlap Summer 2019/20); Chirag Patel (2 profiles; overlap Summer 2018/19 | Summer 2019/20 | Summer 2020/21); Chirag Shah (2 profiles; overlap Summer 2016/17 | Summer 2017/18)

Safe groups that still look suspicious: Kartar Singh [high stats, common surname, adjacent handoff caution]; Francis Bernard [high stats, adjacent handoff caution]; Denis Shaw [high stats, adjacent handoff caution]; Falgun Patel [common surname, adjacent handoff caution]; Puneet Bhardwaj [high stats]; Rajiv Chandla [high stats]; Nirlep Patel [common surname]; Vinay Kumar [common surname]

Top 20 safe groups by combined runs/wickets/match-row proxy:

| Proposed canonical | Raw names | Seasons per raw profile | R/W/C | Match-row proxy | Reason/confidence | Suspicious flags |
|---|---|---|---:|---:|---|---|
| Puneet Bhardwaj | Puneet Bhardwaj | Puneet Bhardwaj: S2025/26<br>Puneet Bhardwaj: 16 seasons: S2007/08 to W2012 | 4785/288/25 | 26 | exact case-insensitive name match; no season overlap; high | high stats |
| Francis Bernard | Francis Bernard | Francis Bernard: S2023/24, S2024/25, S2025/26<br>Francis Bernard: 18 seasons: S2006/07 to W2012 | 2652/2/42 | 42 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Rajiv Chandla | Rajiv Chandla | Rajiv Chandla: 16 seasons: S2007/08 to S2022/23<br>Rajiv Chandla: S2024/25 | 2554/199/28 | 25 | exact case-insensitive name match; no season overlap; high | high stats |
| Hardiek Pattani | Hardiek Pattani | Hardiek Pattani: 15 seasons: S2006/07 to W2012<br>Hardiek Pattani: S2023/24, S2024/25, S2025/26 | 2037/9/32 | 29 | exact case-insensitive name match; no season overlap; high | none |
| Kartar Singh | Kartar Singh | Kartar Singh: 14 seasons: S2008/09 to W2012<br>Kartar Singh: S2025/26 | 1560/283/28 | 19 | exact case-insensitive name match; no season overlap; high | high stats, common surname, adjacent handoff caution |
| Denis Shaw | Denis Shaw | Denis Shaw: S2023/24, S2024/25, S2025/26<br>Denis Shaw: 17 seasons: S2006/07 to S2022/23 | 646/163/9 | 25 | exact case-insensitive name match; no season overlap; high | high stats, adjacent handoff caution |
| Hemant Chawda | Hemant Chawda | Hemant Chawda: S2021/22, S2022/23<br>Hemant Chawda: S2023/24, S2024/25, S2025/26 | 591/45/9 | 10 | exact case-insensitive name match; no season overlap; high | none |
| Harsh Vaja | Harsh Vaja | Harsh Vaja: 4 seasons: S2023/24 to W2026<br>Harsh Vaja: S2022/23 | 573/50/16 | 10 | exact case-insensitive name match; no season overlap; high | none |
| Nirlep Patel | Nirlep Patel | Nirlep Patel: S2024/25, S2025/26<br>Nirlep Patel: S2021/22, S2022/23 | 553/17/10 | 7 | exact case-insensitive name match; no season overlap; high | common surname |
| Karan Bedi | Karan Bedi | Karan Bedi: S2024/25, S2025/26<br>Karan Bedi: S2014/15, S2021/22 | 521/15/5 | 6 | exact case-insensitive name match; no season overlap; high | none |
| Arpan Desai | Arpan Desai | Arpan Desai: 8 seasons: S2015/16 to S2022/23<br>Arpan Desai: S2024/25 | 514/79/12 | 13 | exact case-insensitive name match; no season overlap; high | none |
| Sagar Thakkar | Sagar Thakkar | Sagar Thakkar: S2023/24, S2024/25<br>Sagar Thakkar: S2021/22, S2022/23 | 442/67/7 | 6 | exact case-insensitive name match; no season overlap; high | none |
| Shikhar Dhyani | Shikhar Dhyani | Shikhar Dhyani: S2019/20, S2020/21<br>Shikhar Dhyani: S2025/26 | 421/15/10 | 5 | exact case-insensitive name match; no season overlap; high | none |
| Jignesh Vekaria | Jignesh Vekaria | Jignesh Vekaria: S2023/24, S2024/25, S2025/26<br>Jignesh Vekaria: S2022/23 | 356/38/6 | 4 | exact case-insensitive name match; no season overlap; high | none |
| Krunal Shah | Krunal Shah | Krunal Shah: S2022/23<br>Krunal Shah: S2023/24 | 274/9/8 | 5 | exact case-insensitive name match; no season overlap; high | none |
| Viral Gandhi | Viral Gandhi | Viral Gandhi: 8 seasons: S2010/11 to W2012<br>Viral Gandhi: S2023/24 | 258/18/8 | 20 | exact case-insensitive name match; no season overlap; high | none |
| Paul Giles | Paul Giles | Paul Giles: S2023/24<br>Paul Giles: S2021/22, S2022/23 | 221/0/3 | 4 | exact case-insensitive name match; no season overlap; high | none |
| Michael Mccormack | Michael Mccormack | Michael Mccormack: 4 seasons: S2006/07 to S2009/10<br>Michael Mccormack: S2011/12 | 187/30/5 | 5 | exact case-insensitive name match; no season overlap; high | none |
| Prem Kumar Venkataramani | Prem Kumar Venkataramani | Prem Kumar Venkataramani: S2021/22, S2022/23<br>Prem Kumar Venkataramani: S2024/25, S2025/26 | 176/15/2 | 6 | exact case-insensitive name match; no season overlap; high | none |
| Falgun Patel | Falgun Patel | Falgun Patel: S2012/13, S2013/14<br>Falgun Patel: S2014/15 | 115/2/3 | 4 | exact case-insensitive name match; no season overlap; high | common surname, adjacent handoff caution |
