# Multi-Club Positive Response Review Summary

Source: existing review packs under `data/processed/experimental/<club_id>/review_pack/`.

No data fetch, match-centre refresh, or backfill was run for this summary. The duplicate candidate files are capped at 200 rows by the review-pack builder, so any club showing 200 candidates should be treated as "at cap" rather than "exactly 200 total duplicates".

## Decision Table

| club_id | aggregate status | app smoke | duplicate risk | grade-label risk | recommended next step |
| --- | --- | --- | --- | --- | --- |
| `reynella` | Refreshed, aggregate-only | Passed | High, 200 capped candidates and 48 masked-name rows | High, 116 labels with sponsor, junior, T20, and association variants | Review duplicate players first, then team/grades before match-centre |
| `ashwood` | Refreshed, aggregate-only | Passed | High, 200 capped candidates and 36 masked-name rows | High, 152 labels with legacy ESCA, LOC, 1s/2s/3s, junior, and women variants | Review team/grades first, then duplicate players |
| `glen-waverley-hawks` | Refreshed, aggregate-only | Passed | High, 200 capped candidates and 16 masked-name rows | High, 120 labels including historical grade names and obvious label typos | Review team/grades first, then duplicate players |
| `plenty` | Refreshed, aggregate-only | Passed | High, 200 capped candidates and 20 masked-name rows | Medium-high, 104 labels with many junior age-group variants | Review duplicate players first, then team/grades |
| `georges-river-district` | Refreshed, aggregate-only | Passed | Highest, 200 capped candidates across 3300 player identities | Medium, 43 labels but spans grade, masters, classics, vintage, and regional cricket | Needs manual confirmation and duplicate review before match-centre |
| `southside-east-caulfield` | Refreshed, aggregate-only | Passed | Medium-high, 200 capped candidates but smallest player pool and 4 masked-name rows | Low-medium, 20 labels | Safest candidate after a light duplicate and grade-label pass |

## Reynella

- Seasons found: 20.
- Latest season: Summer 2025/26.
- Player count in review pack: 2150 player identity rows.
- Team/grade labels needing review: 116 unique labels. Review sponsor and competition-heavy labels such as `ONeills Sports Division 1 Group 1`, `ONeills Sports Division 2 T20 Finals`, `Kookaburra Sports A1 Premier Grade`, `B Grade - John Adams Shield`, junior `Under 13/15/17` labels, and multiple `A3`/`B1`/`B2` variants.
- Top 10 run scorers: Richard Gabb 6454; Jordan Wright 5641; Paul Radbourne 5071; Brett Julian 4156; Matt Hehner 3983; Marcus Williams 3884; Andrew Semple 3828; Matthew Aston 3803; Nathan Turner 3528; John Hopkins 3400.
- Top 10 wicket takers: Cameron Pannach 476; Daniel Rabbett 323; Matt Hehner 280; Damien Pimlott 253; Jonathon Hague 234; Jamie Caddy 213; Sam Tugwell 208; Michael Cload 176; Adam Ellis 171; Mark Walters 167.
- Top 10 catches: Richard Gabb 209; Scott Trenorden 108; Matthew Aston 106; Jordan Wright 103; Brett Julian 100; Matt Hehner 90; Paul Radbourne 81; Nathan Turner 73; Andrew Semple 71; Joshua Niederer 68.
- Likely duplicate player candidates: 200 capped candidates. Examples are same-normalised-name pairs such as Aadi Vaghela, Aarav A Patel, Aarav Gupta, Aarhan Ehtiram Siddique, Aaron Maddigan, Aaron Nowell, Aaron Robertson, and Aaron Tsokanos.
- Weird player names or casing issues: 48 masked `********` rows with blank normalised names. No all-caps or all-lowercase pattern was detected in the review sample.
- Empty or suspicious files: aggregate-only placeholder files are header-only for `all_seasons_matches.csv`, `all_seasons_scorecard_batting.csv`, `all_seasons_scorecard_bowling.csv`, and `all_seasons_scorecard_fielding.csv`. This is expected before scorecard or match-centre work.
- Aggregate-only app looked safe: yes. Hall of Fame, Season Overview, Milestone, and Player Profile smoke-passed with clean empty states where scorecard-derived data is absent.
- Recommendation: review duplicate players first, then clean team/grade display labels before approving match-centre/backfill.

## Ashwood

- Seasons found: 68.
- Latest season: Summer 2025/26.
- Player count in review pack: 2402 player identity rows.
- Team/grade labels needing review: 152 unique labels, the highest label count in this set. Review legacy ESCA labels, turf/matting variants, `1s`/`2s`/`3s` display variants, LOC shield names, junior age labels, and women's competition labels.
- Top 10 run scorers: Mark Edmonds 6716; Anthony Edmonds 5231; Musashi Fujihara 4592; Daniel Curnow 4588; Trevor Shepherd 3541; Paul Morrey 3151; Darren Sheean 3034; Dale Wilkinson 2755; James Morrey 2402; Dananj Wijayasingha 2346.
- Top 10 wicket takers: Timothy Pape 244; Matthew Clayton 227; Cameron Flint 222; O Effendi 207; Thomas Kinnane 206; Daniel Curnow 169; Darren Sheean 156; Shane Dissanayake 141; Dale Wilkinson 131; Jack Von Fersen 130.
- Top 10 catches: James Morrey 119; Jason Read 104; Anthony Edmonds 101; Mark Edmonds 101; Trevor Shepherd 90; Dale Healy 88; Adam Rolfe 87; Daniel Curnow 74; Ari Morton 68; Jonathan Cook 67.
- Likely duplicate player candidates: 200 capped candidates. Examples are same-normalised-name pairs such as A Bohnenkamp, A Gould, A Marshall, A Mudiyanselage Abesekara, A Nicholson, A Phelan, A Prabari, and A Pustola.
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
- Weird player names or casing issues: 4 masked `********` rows with blank normalised names. No all-caps or all-lowercase pattern was detected in the review sample.
- Empty or suspicious files: aggregate-only placeholder files are header-only for matches and scorecard batting/bowling/fielding. This is expected before scorecard or match-centre work.
- Aggregate-only app looked safe: yes. Main pages smoke-passed and the data shape is the simplest among the six clubs.
- Recommendation: safest club to continue after a light duplicate-player pass and quick team/grade confirmation.

## Recommended Manual Review Order

1. Georges River District: highest identity risk and largest player pool; confirm naming context and review duplicate candidates first.
2. Ashwood: highest grade-label count; review grade mappings before match-centre.
3. Glen Waverley Hawks: review historical labels and typo-like grade values before match-centre.
4. Reynella: review duplicate players first, then sponsor/junior/T20 grade labels.
5. Plenty: review masked duplicate candidates and junior age-grade labels.
6. Southside East Caulfield: likely safest next match-centre candidate after light review.

## Clubs That Look Safest For Match-Centre Next

Southside East Caulfield looks safest because it has the smallest player identity pool, fewest grade labels, and only 4 masked-name rows. Plenty is the next most manageable after duplicate review. Glen Waverley Hawks is already an existing pilot folder, but the grade-label cleanup should happen before expanding match-centre coverage.
