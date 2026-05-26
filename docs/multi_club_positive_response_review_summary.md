# Multi-Club Positive Response Review Summary

Source: existing review packs under `data/processed/experimental/<club_id>/review_pack/`.

No data fetch, match-centre refresh, or backfill was run for this summary. The duplicate candidate files are capped at 200 rows by the review-pack builder, so any club showing 200 candidates should be treated as "at cap" rather than "exactly 200 total duplicates". The safe auto-merge counts are review-only proposals: no `manual_player_merges.csv` files have been edited.

## Post Match-Centre Backfill Update

The six pilot clubs have now completed the controlled match-centre/backfill run and deploy-safe rebuild. The detailed run summary is in `docs/multi_club_match_centre_backfill_summary.md`.

| club_id | completed scorecards | ball-by-ball matches | ball events | app smoke | current recommendation |
| --- | ---: | ---: | ---: | --- | --- |
| `southside-east-caulfield` | 893 | 195 | 74,758 | Passed | Safest client-preview candidate after a final grade-label pass |
| `glen-waverley-hawks` | 3,475 | 698 | 241,113 | Passed | Review historical team/grade labels and duplicate candidates |
| `ashwood` | 5,248 | 920 | 303,650 | Passed | Review team/grade mappings before client preview |
| `plenty` | 3,214 | 503 | 200,539 | Passed | Review duplicate candidates and junior/team-grade labels |
| `reynella` | 3,110 | 572 | 244,422 | Passed | Review safe duplicate groups and sponsor/junior/T20 labels |
| `georges-river-district` | 2,604 | 295 | 155,573 | Passed | Highest manual-review risk; confirm identities and naming before preview |

Review packs were regenerated after backfill and remain ignored under `data/processed/experimental/<club_id>/review_pack/`. Raw/full match-centre files remain ignored and uncommitted. Southside East Caulfield is the only pilot club with approved safe duplicate merges applied; the other pilot clubs still use review-only duplicate proposals.

## Decision Table

| club_id | aggregate status | app smoke | duplicate risk | grade-label risk | recommended next step |
| --- | --- | --- | --- | --- | --- |
| `reynella` | Refreshed, aggregate-only | Passed | High, 111 safe review-only groups and 12 manual groups | High, 116 labels with sponsor, junior, T20, and association variants | Review safe merges, then blocked overlaps and team/grades |
| `ashwood` | Refreshed, aggregate-only | Passed | High, 95 safe review-only groups and 12 manual groups | High, 152 labels with legacy ESCA, LOC, 1s/2s/3s, junior, and women variants | Review team/grades first, then safe/blocked duplicate groups |
| `glen-waverley-hawks` | Refreshed, aggregate-only | Passed | High, 54 safe review-only groups and 17 manual groups | High, 120 labels including historical grade names and obvious label typos | Review team/grades first, then safe/blocked duplicate groups |
| `plenty` | Refreshed, aggregate-only | Passed | High, 84 safe review-only groups and 11 manual groups | Medium-high, 104 labels with many junior age-group variants | Review safe duplicate groups, then junior/team-grade labels |
| `georges-river-district` | Refreshed, aggregate-only | Passed | Highest, 74 safe review-only groups and 11 manual groups across 3300 player identities | Medium, 43 labels but spans grade, masters, classics, vintage, and regional cricket | Needs manual confirmation and duplicate review before match-centre |
| `southside-east-caulfield` | Refreshed, aggregate-only | Passed | Medium-high, 26 safe review-only groups and 14 manual groups | Low-medium, 20 labels | Safest candidate after reviewing safe/blocked duplicate groups |

## Reynella

- Seasons found: 20.
- Latest season: Summer 2025/26.
- Player count in review pack: 2150 player identity rows.
- Team/grade labels needing review: 116 unique labels. Review sponsor and competition-heavy labels such as `ONeills Sports Division 1 Group 1`, `ONeills Sports Division 2 T20 Finals`, `Kookaburra Sports A1 Premier Grade`, `B Grade - John Adams Shield`, junior `Under 13/15/17` labels, and multiple `A3`/`B1`/`B2` variants.
- Top 10 run scorers: Richard Gabb 6454; Jordan Wright 5641; Paul Radbourne 5071; Brett Julian 4156; Matt Hehner 3983; Marcus Williams 3884; Andrew Semple 3828; Matthew Aston 3803; Nathan Turner 3528; John Hopkins 3400.
- Top 10 wicket takers: Cameron Pannach 476; Daniel Rabbett 323; Matt Hehner 280; Damien Pimlott 253; Jonathon Hague 234; Jamie Caddy 213; Sam Tugwell 208; Michael Cload 176; Adam Ellis 171; Mark Walters 167.
- Top 10 catches: Richard Gabb 209; Scott Trenorden 108; Matthew Aston 106; Jordan Wright 103; Brett Julian 100; Matt Hehner 90; Paul Radbourne 81; Nathan Turner 73; Andrew Semple 71; Joshua Niederer 68.
- Likely duplicate player candidates: 200 capped candidates. Examples are same-normalised-name pairs such as Aadi Vaghela, Aarav A Patel, Aarav Gupta, Aarhan Ehtiram Siddique, Aaron Maddigan, Aaron Nowell, Aaron Robertson, and Aaron Tsokanos.
- Strict safe auto-merge review: 111 safe groups / 225 profile rows. Examples: Adam Ellis split between 2008/09-2021/22 and 2022/23-2025/26; Aidan Richardson split between 2015/16-2021/22 and 2022/23-2024/25; Aidan Secomb split between 2016/17-2021/22 and 2022/23.
- Blocked duplicate review: 12 manual groups / 27 profile rows; 9 groups are blocked by season overlap. Examples: Brett Julian overlaps in Summer 2022/23; Colin Rowston overlaps across 2014/15-2018/19; Daivik Kumar overlaps in Summer 2022/23.
- Weird player names or casing issues: 48 masked `********` rows with blank normalised names. No all-caps or all-lowercase pattern was detected in the review sample.
- Empty or suspicious files: aggregate-only placeholder files are header-only for `all_seasons_matches.csv`, `all_seasons_scorecard_batting.csv`, `all_seasons_scorecard_bowling.csv`, and `all_seasons_scorecard_fielding.csv`. This is expected before scorecard or match-centre work.
- Aggregate-only app looked safe: yes. Hall of Fame, Season Overview, Milestone, and Player Profile smoke-passed with clean empty states where scorecard-derived data is absent.
- Recommendation: review safe auto-merge proposals first, then blocked same-season overlap groups, then clean team/grade display labels before approving match-centre/backfill.

## Ashwood

- Seasons found: 68.
- Latest season: Summer 2025/26.
- Player count in review pack: 2402 player identity rows.
- Team/grade labels needing review: 152 unique labels, the highest label count in this set. Review legacy ESCA labels, turf/matting variants, `1s`/`2s`/`3s` display variants, LOC shield names, junior age labels, and women's competition labels.
- Top 10 run scorers: Mark Edmonds 6716; Anthony Edmonds 5231; Musashi Fujihara 4592; Daniel Curnow 4588; Trevor Shepherd 3541; Paul Morrey 3151; Darren Sheean 3034; Dale Wilkinson 2755; James Morrey 2402; Dananj Wijayasingha 2346.
- Top 10 wicket takers: Timothy Pape 244; Matthew Clayton 227; Cameron Flint 222; O Effendi 207; Thomas Kinnane 206; Daniel Curnow 169; Darren Sheean 156; Shane Dissanayake 141; Dale Wilkinson 131; Jack Von Fersen 130.
- Top 10 catches: James Morrey 119; Jason Read 104; Anthony Edmonds 101; Mark Edmonds 101; Trevor Shepherd 90; Dale Healy 88; Adam Rolfe 87; Daniel Curnow 74; Ari Morton 68; Jonathan Cook 67.
- Likely duplicate player candidates: 200 capped candidates. Examples are same-normalised-name pairs such as A Bohnenkamp, A Gould, A Marshall, A Mudiyanselage Abesekara, A Nicholson, A Phelan, A Prabari, and A Pustola.
- Strict safe auto-merge review: 95 safe groups / 191 profile rows. Examples: Aadithya Pai split between 2020/21 and 2021/22-2022/23; Aaryan Panchal split between 2021/22-2022/23 and 2023/24-2025/26; Aidan Morton split between 2021/22-2022/23 and 2023/24-2025/26.
- Blocked duplicate review: 12 manual groups / 25 profile rows; 5 groups are blocked by season overlap. Examples: Daksh Sharma overlaps in Summer 2023/24; Dale Healy overlaps across 2019/20-2021/22; Jasmeet Singh overlaps in Summer 2021/22.
- Weird player names or casing issues: 36 masked `********` rows with blank normalised names. No all-caps or all-lowercase pattern was detected in the review sample.
- Empty or suspicious files: aggregate-only placeholder files are header-only for matches and scorecard batting/bowling/fielding. This is expected before scorecard or match-centre work.
- Aggregate-only app looked safe: yes. The four main pages smoke-passed with no FVCC leakage, traceback, `NaN`, `None`, or internal IDs.
- Recommendation: review team/grade mappings first because label complexity is the main risk, then review duplicate players before match-centre.

## Glen Waverley Hawks

- Seasons found: 36.
- Latest season: Summer 2026/27.
- Player count in review pack: 2576 player identity rows.
- Team/grade labels needing review: 120 unique labels. Review historical labels such as `Under 14 A Grade 77/78 to 2000`, repeated grade variants, shield names, and obvious spelling/label issues such as `Anklbytrs`.
- Top 10 run scorers: Glen Mahoney 7734; Sunny Somaia 7544; Stuart Wynd 6993; Greg Mccormick 6202; Apurwa Sarve 6038; Chris Briginshaw 5995; Brooke Calder 5956; Grant Haye 5692; Jarrod Greaves 5196; Luke Galle 4025.
- Top 10 wicket takers: Matthew Briginshaw 414; Nathan Bungey 363; Luke Galle 334; Arun Chelvan 330; Stuart Wynd 312; Chris Perkins 303; Patrick Eldridge 259; Shane Vanin 256; Ivan Greaves 235; Michael Armstrong 232.
- Top 10 catches: Chris George 215; Brett Powell 183; Glen Mahoney 180; Cameron Hocart 139; Glen Powell 117; Michael Brennan 117; James Anderson 114; Nathan Bungey 104; Grant Haye 99; Chris Briginshaw 95.
- Likely duplicate player candidates: 200 capped candidates. Examples are same-normalised-name pairs such as A Aruna, A Blake, A Bourrilhan, A Chester, A Clarke, A Dekel, A Harrold, and A Henly.
- Strict safe auto-merge review: 54 safe groups / 108 profile rows. Examples: Aaditya Sharma split between 2022/23 and 2023/24-2025/26; Aansh Pandya split between 2018/19-2022/23 and 2023/24-2025/26; Ahilan Sivakumaran split with a standalone 2019/20 profile.
- Blocked duplicate review: 17 manual groups / 36 profile rows; 15 groups are blocked by season overlap. Examples: Ashton Scott overlaps in 2016/17-2017/18; Krish Agrawal overlaps in 2019/20; Martin Fleming overlaps across several historical seasons.
- Weird player names or casing issues: 16 masked `********` rows with blank normalised names. No all-caps or all-lowercase pattern was detected in the review sample.
- Empty or suspicious files: aggregate-only placeholder files are header-only for matches and scorecard batting/bowling/fielding. This is expected before scorecard or match-centre work.
- Aggregate-only app looked safe: yes. This existing pilot folder smoke-passed after being updated to the current structure.
- Recommendation: review team/grades first because of historical labels and visible typo-like values, then review duplicate players.

## Plenty

- Seasons found: 28.
- Latest season: Summer 2025/26.
- Player count in review pack: 1920 player identity rows.
- Team/grade labels needing review: 104 unique labels. Review junior age-group labels such as `U10`, `U12`, `U14`, `U16`, `Under 12`, and `Under 14`; shield labels such as `Barclay Shield`; and senior shield names such as `C Grade - Les Horne Shield` and `E Grade - Les Kemp Shield`.
- Top 10 run scorers: Mitch Johnson 6494; Gordon Zull 5616; Scott Keane 4261; Jayden Bedford 3942; Graeme Pavey 3106; Liam Banthorpe 2975; Tom Weir 2971; Matt Deligiorgis 2905; Nicholas Curtin 2763; Darren Connelley 2733.
- Top 10 wicket takers: Paul Hubber 338; Shane Cullen 293; Mark Turnbull 258; Daniel Cocking 236; Dayne Smith 163; Christopher Barclay 157; Mitch Johnson 151; Dwayne Fowles 149; Andrew Villani 138; Luke Rosbrook 137.
- Top 10 catches: Matt Deligiorgis 133; Scott Keane 133; Ralf Koegler 92; Chris Alexopoulos 90; Mark Johnson 87; Gordon Zull 74; Jack Sacchetta 64; Owen Pisani 62; Mitch Johnson 58; Jayden Bedford 53.
- Likely duplicate player candidates: 200 capped candidates. Examples include masked-name rows and same-normalised-name pairs such as Aaditya Srivastava, Aaron Cooray, Aaron Lowe, Aaron Walton, Aaryan Chopra, and `******** French`.
- Strict safe auto-merge review: 84 safe groups / 171 profile rows. Examples: Aaryan Chopra split between 2022/23 and 2023/24; Aayaan Aswal split around 2020/21; Abhayveer Uppal split between 2018/19-2022/23 and 2025/26.
- Blocked duplicate review: 11 manual groups / 23 profile rows; 9 groups are blocked by season overlap. Examples: Angus Regan overlaps in 2021/22-2022/23; Brent Redmond overlaps in 2003/04; Cameron Fitzgerald overlaps in 2021/22.
- Weird player names or casing issues: 20 masked rows, including `********` and `******** French`; 16 rows have blank normalised names. No all-caps or all-lowercase pattern was detected in the review sample.
- Empty or suspicious files: aggregate-only placeholder files are header-only for matches and scorecard batting/bowling/fielding. This is expected before scorecard or match-centre work.
- Aggregate-only app looked safe: yes. Main pages smoke-passed with club-specific data and clean empty states.
- Recommendation: review duplicate players first because masked names appear in duplicate candidates, then review junior/team-grade labels before match-centre.

## Georges River District

- Seasons found: 71.
- Latest season: Summer 2025/26.
- Player count in review pack: 3300 player identity rows, the largest player identity set in this review.
- Team/grade labels needing review: 43 unique labels. The label count is manageable, but the data spans first to fifth grade, Frank Gray Shield, Metropolitan competitions, masters, classics, vintage, O60/O65 regional competitions, and community cup formats.
- Top 10 run scorers: Kevin Croom 8606; Trevor Davies 8532; Gavin Scott 6918; Ryan Croom 6118; Peter Remfrey 5449; Sean Mantle 5308; Bruce Whitehouse 5079; Alex Economou 4812; Christopher Mcarthur 4776; Andrew Mcguiness 4600.
- Top 10 wicket takers: Paul Thomas 608; Dave Jiffkins 495; Daniel Yates 491; Gavin Scott 439; Jeff Woods 379; Trevor Davies 367; Phil Gibson 357; Benjamin Vella 310; Ben Saunders 263; Harjit Singh 263.
- Top 10 catches: Meville Fernando 311; Ryan Croom 221; Benjamin Churcher 154; Gavin Scott 143; Bruce Whitehouse 130; Peter Remfrey 124; Alex Economou 112; Andrew Mcguiness 107; Curtis Cheney 103; Jason Lill 101.
- Likely duplicate player candidates: 200 capped candidates. Examples are same-normalised-name pairs such as A Harrison, A Hartley, A Murphy, A O'Connor, A Young, Aadil Shariff, Aamir Chaudhry, and Aaron Greening.
- Strict safe auto-merge review: 74 safe groups / 149 profile rows. Examples: Adam Scott split between 2015/16-2018/19 and 2024/25-2025/26; Aidan Wood split between 2021/22 and 2022/23; Alan Wright split between 2018/19-2021/22 and 2023/24.
- Blocked duplicate review: 11 manual groups / 24 profile rows; 6 groups are blocked by season overlap. Examples: Peter Francis overlaps in 2012/13; Peter Thomas overlaps in 2016/17; Peter Trajkovski overlaps in 1983/84.
- Weird player names or casing issues: 36 masked `********` rows with blank normalised names. No all-caps or all-lowercase pattern was detected in the review sample.
- Empty or suspicious files: aggregate-only placeholder files are header-only for matches and scorecard batting/bowling/fielding. This is expected before scorecard or match-centre work.
- Aggregate-only app looked safe: yes. Main app smoke passed. The official PlayCricket identity is Georges River Cricket Club while the onboarding target uses Georges River District, so keep this naming note visible during review.
- Recommendation: needs manual confirmation and duplicate review before match-centre. This is the highest-risk club because of the largest player identity pool, long history, and capped duplicate list.

## Southside East Caulfield

- Seasons found: 47.
- Latest season: Winter 2026.
- Player count in review pack: 926 player identity rows, the smallest player identity set in this review.
- Team/grade labels needing review: 20 unique labels. Review winter/summer scope labels and senior grade labels such as `Pullen Shield`, `Quiney Shield`, `Woolnough Shield`, `Senior T20`, `Standard One Day Grade`, and `WINTER (South Division - Saturday)`.
- Top 10 run scorers: Puneet Bhardwaj 4344; Jatin Bhatia 3908; Jatin Dave 3475; Aamir Rana 2808; Vatsan Vasu 2566; Ronak Patel 2503; Rajiv Chandla 2402; Mehul Tandel 2218; Hiren Tandel 2150; Bhaumik Jani 2041.
- Top 10 wicket takers: Puneet Bhardwaj 260; Kartar Singh 259; Christopher Jones 226; Rajiv Chandla 190; Rohit Tiwari 164; Bhaumik Jani 142; Denis Shaw 133; Vatsan Vasu 129; Mehul Tandel 125; Siddarth Amin 118.
- Top 10 catches: Hiren Tandel 97; Nathan Benson 86; Rohit Tiwari 78; Aamir Rana 60; Jatin Bhatia 58; Ronak Patel 50; Bhaumik Jani 48; Aatish Patel 42; Francis Bernard 40; Vatsan Vasu 40.
- Likely duplicate player candidates: 200 capped candidates. Examples are same-normalised-name pairs such as A Jones, Aamir Rana, Aarav Mehta, Aashay Desai, Aatish Patel, Aayush Sharma, Abdul Chaudhary, and Abhijeet Chauhan.
- Strict safe auto-merge review: 26 safe groups / 52 profile rows. Examples: Arpan Desai split between 2015/16-2022/23 and 2024/25; Deepak Gopalaraju split between 2008/09 and 2009/10; Denis Shaw split between 2006/07-2022/23 and 2023/24-2025/26.
- Blocked duplicate review: 14 manual groups / 28 profile rows; 9 groups are blocked by season overlap. Examples: Ankit Patel overlaps in 2018/19; Ankur Sharma overlaps in 2012/13-2013/14; Bhumil Patel overlaps in 2019/20.
- Weird player names or casing issues: 4 masked `********` rows with blank normalised names. No all-caps or all-lowercase pattern was detected in the review sample.
- Empty or suspicious files: aggregate-only placeholder files are header-only for matches and scorecard batting/bowling/fielding. This is expected before scorecard or match-centre work.
- Aggregate-only app looked safe: yes. Main pages smoke-passed and the data shape is the simplest among the six clubs.
- Recommendation: safest club to continue after a light duplicate-player pass and quick team/grade confirmation.

## Recommended Manual Review Order

1. Georges River District: highest identity risk and largest player pool; confirm naming context and review safe/blocked duplicate groups first.
2. Ashwood: highest grade-label count; review grade mappings and safe/blocked duplicate groups before match-centre.
3. Glen Waverley Hawks: review historical labels, typo-like grade values, and high same-season-overlap count.
4. Reynella: review the largest safe auto-merge set, then sponsor/junior/T20 grade labels.
5. Plenty: review masked duplicate candidates, safe groups, and junior age-grade labels.
6. Southside East Caulfield: likely safest next match-centre candidate after light safe/blocked duplicate review.

## Clubs That Look Safest For Match-Centre Next

Southside East Caulfield looks safest because it has the smallest player identity pool, fewest grade labels, and only 4 masked-name rows. Plenty is the next most manageable after duplicate review. Glen Waverley Hawks is already an existing pilot folder, but the grade-label cleanup should happen before expanding match-centre coverage.
