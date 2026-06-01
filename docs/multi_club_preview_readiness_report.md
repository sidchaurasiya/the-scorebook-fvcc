# Multi-Club Preview Readiness Report

Run date: 2026-05-27

Branch: `onboarding/multi-club-positive-responses`

Baseline commit reviewed: `3acf23e Backfill pilot club match-centre data`

This report uses existing local processed/deploy-safe outputs, ignored review packs, and local app smoke checks only. No data was fetched, no match-centre/backfill scripts were rerun, and no external scorecard URLs were opened.

## Executive Summary

| club_id | readiness classification | app smoke | duplicate risk | team/grade risk | opponent/ground risk | BBB coverage | premiership status | recommended next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `southside-east-caulfield` | Go with caveats for private preview | Passed | Medium: approved safe merges applied; 14 manual groups remain | Low-medium: 20 labels | Medium: starter opponent/ground mappings | 195 matches / 74,758 balls | 5 verified Grand Final wins; captain fields blank | Private deployment test, then club data review |
| `glen-waverley-hawks` | Needs team/grade cleanup first | Passed | High: 54 safe groups, 17 manual groups | High: 120 historical/variant labels | Medium-high: starter opponent/ground mappings | 698 matches / 241,113 balls | No verified evidence; header-only exports | Clean historical grade labels, then duplicate review |
| `ashwood` | Needs team/grade cleanup first | Passed | High: 95 safe groups, 12 manual groups | Highest: 152 labels | Medium-high: starter opponent/ground mappings | 920 matches / 303,650 balls | No verified evidence; header-only exports | Clean team/grade labels before client preview |
| `plenty` | Needs duplicate review first | Passed | High: 84 safe groups, 11 manual groups | Medium-high: 104 labels | Medium-high: starter opponent/ground mappings | 503 matches / 200,539 balls | No verified evidence; header-only exports | Review duplicate candidates, then junior/grade labels |
| `reynella` | Needs duplicate review first | Passed | Highest safe-merge volume: 111 safe groups, 12 manual groups | High: 116 labels | Medium-high: starter opponent/ground mappings | 572 matches / 244,422 balls | No verified evidence; header-only exports | Review duplicate candidates, then sponsor/junior/T20 labels |
| `georges-river-district` | Needs duplicate review first | Passed | Highest identity complexity: 74 safe groups, 11 manual groups across largest player pool | Medium: 43 labels, but broad historical scope | Medium-high: starter opponent/ground mappings | 295 matches / 155,573 balls | No verified evidence; header-only exports | Manual identity and naming review before preview |

Recommended preview order:

1. `southside-east-caulfield`
2. `plenty`
3. `reynella`
4. `glen-waverley-hawks`
5. `ashwood`
6. `georges-river-district`

## Shared Checks

- Deploy-safe files are present for Hall of Fame, Season Overview, and Player Profile for all six clubs.
- Local app smoke passed for Hall of Fame, Season Overview, Season by Round, Milestone, Player Profile, Recent Form, fastest/ball-by-ball sections, Detailed Records, and scorecard-link presence.
- No FVCC text/data leak was observed in non-FVCC club smoke checks.
- No traceback, visible `NaN`, visible `None`, or visible raw GUID was observed in the smoke-checked pages.
- Scorecard links were present and shaped as PlayCricket scorecard URLs with `?tab=scorecard`; links were inspected only, not opened.
- Missing ball-by-ball coverage did not show an obvious misleading `0.0` in the checked BBB contexts. Actual scorecard zeros remain valid cricket data.
- GA4 remains club-aware by static inspection: `default_event_params()` adds `app_area=scorebook`, `club_id`, and `club_name`; events no-op when `GA4_MEASUREMENT_ID` is absent.
- Southside premiership exports now include verified local Grand Final wins. The other five pilot clubs remain header-only because no verified premiership evidence has been accepted. No captain data is fabricated.
- Review packs remain ignored under `data/processed/experimental/<club_id>/review_pack/`.

## Post-Fix Validation

Follow-up run date: 2026-05-27.

Root causes fixed:

- HOF Detailed Records Win % no longer uses an FVCC-only result-text check. Win-rate exports now classify the active club side from local match-centre rows.
- Scorecard-derived 30s now use club-local player identity mappings, so Southside's approved safe merges flow into `player_scorecard_milestones.csv`.
- Runtime theme CSS reads active club branding colours and overrides the main sidebar, tab, link/button, progress, and section accents. FVCC now uses its shirt-inspired navy, maroon, and gold config palette.

| club_id | HOF Win % status | 30s status | premiership status | link status | club colour/theme status | preview readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `southside-east-caulfield` | Fixed; Puneet Bhardwaj 88 wins from 167 result matches, 52.7%; Sajan Patel Best Win % 61.4% from 35/57 | Fixed; Puneet Bhardwaj 26 scorecard 30s | 5 verified Grand Final wins; 48 player rows; captains blank | Player/season/scorecard links pass UAT | Southside blue/red applied across HOF, Season Overview, Milestone, and Player Profile | Go with caveats for private preview |
| `glen-waverley-hawks` | Fixed; Glen Mahoney 133/228, 58.3% | Fixed; Glen Mahoney 47 | No verified rows; clean empty state | Links shaped correctly in smoke | Hawks green/gold applied | Needs team/grade cleanup first |
| `ashwood` | Fixed; Mark Edmonds 127/302, 42.1% | Fixed; Mark Edmonds 55 | No verified rows; clean empty state | Links shaped correctly in smoke | Ashwood green/gold applied | Needs team/grade cleanup first |
| `plenty` | Fixed; Mitch Johnson 136/233, 58.4% | Fixed; Mitch Johnson 43 | No verified rows; clean empty state | Links shaped correctly in smoke | Plenty green/gold applied | Needs duplicate review first |
| `reynella` | Fixed; Richard Gabb 27/41, 65.9% | Fixed; Richard Gabb 8 | No verified rows; clean empty state | Links shaped correctly in smoke | Reynella blue/gold applied | Needs duplicate review first |
| `georges-river-district` | Fixed; Kevin Croom 9/17, 52.9% | Fixed; Kevin Croom 31 | No verified rows; clean empty state | Links shaped correctly in smoke | Georges River blue/gold applied | Needs duplicate review first |

Southside polish notes:

- No Southside mapping files were changed. The visible team/grade labels are readable, and there were no obviously safe opponent/ground mappings to add from the current review pack.
- Southside still has 14 manual duplicate groups; they are blocked by same-season overlap and were not applied.
- Southside is safe for a first private preview with caveats: premiership wins are verified from local completed Grand Final rows, player premiership participation is scorecard-inferred, and captains remain blank until verified.

Expected deploy-safe file set per club:

- Hall of Fame: `fastest_batting_milestones.csv`, `player_bbb_batting_rates.csv`, `player_bowling_milestones.csv`, `player_premierships.csv`, `player_scorecard_milestones.csv`, `player_win_rates.csv`, `premiership_wins.csv`, `scorecard_record_links.csv`.
- Season Overview: `bbb_batting_rates_by_scope.csv`, `bbb_bowling_dot_rates_by_scope.csv`, `scorecard_batting_milestones_by_scope.csv`, `scorecard_bowling_milestones_by_scope.csv`, `season_by_round_scorecards.csv`.
- Player Profile: `batting_position_summary.csv`, `bowling_phase_summary.csv`, `dismissal_fingerprint_summary.csv`, `performance_breakdown_by_dimension.csv`, `recent_form_batting.csv`, `recent_form_bowling.csv`.

## Southside East Caulfield

Readiness: Go with caveats for private preview.

- Scorecards parsed: 893.
- Ball-by-ball: 195 matches, 74,758 ball events.
- Deploy-safe outputs: all expected Hall of Fame, Season Overview, and Player Profile files present.
- Review pack: `data/processed/experimental/southside-east-caulfield/review_pack/`.
- App smoke: passed. Player Profile smoke used `puneet_bhardwaj`; scorecard links were present.
- Scorecard-derived sections: Season by Round 893 rows; Recent Form 7,045 batting rows and 4,683 bowling rows; scorecard record links 11,751 rows across 728 linked matches.
- Ball-by-ball sections: fastest batting milestones 415 rows; player BBB batting rates 162 rows; bowling phase summary 418 rows.
- Premiership evidence: 5 verified completed Grand Final wins in `premiership_wins.csv`; 48 player-premiership rows inferred from winning-team scorecard participation in `player_premierships.csv`; captain fields remain blank until verified.

Top 5 run scorers:

| player | runs |
| --- | ---: |
| Puneet Bhardwaj | 4,785 |
| Jatin Bhatia | 3,908 |
| Jatin Dave | 3,475 |
| Aamir Rana | 2,808 |
| Francis Bernard | 2,652 |

Top 5 wicket takers:

| player | wickets |
| --- | ---: |
| Puneet Bhardwaj | 288 |
| Kartar Singh | 283 |
| Christopher Jones | 226 |
| Rajiv Chandla | 199 |
| Rohit Tiwari | 164 |

Top 5 catches:

| player | catches |
| --- | ---: |
| Hiren Tandel | 97 |
| Nathan Benson | 86 |
| Rohit Tiwari | 78 |
| Aamir Rana | 60 |
| Jatin Bhatia | 58 |

Risk notes:

- Duplicate risk: medium. Approved safe auto-merges have already been applied for Southside; 14 manual duplicate groups and 200 capped duplicate candidate rows remain for review.
- Team/grade label risk: low-medium. There are 20 display labels, mostly manageable senior/winter/summer labels.
- Opponent/ground naming risk: medium because opponent and ground mapping files are still starter/header-only.
- Obvious UI issues: none observed.
- Obvious data trust issues: HOF Win %, scorecard 30s, links, and Southside premiership wins are fixed. Remaining caveats are manual duplicate review, opponent/ground starter mappings, scorecard-inferred player premiership participation, and blank captain fields.

## Glen Waverley Hawks

Readiness: Needs team/grade cleanup first.

- Scorecards parsed: 3,475.
- Ball-by-ball: 698 matches, 241,113 ball events.
- Deploy-safe outputs: all expected Hall of Fame, Season Overview, and Player Profile files present.
- Review pack: `data/processed/experimental/glen-waverley-hawks/review_pack/`.
- App smoke: passed. Player Profile smoke used `raw_2a9340d0_cfdd_447e_8601_370472fd4b41`; scorecard links were present.
- Scorecard-derived sections: Season by Round 3,475 rows; Recent Form 26,423 batting rows and 20,204 bowling rows; scorecard record links 46,783 rows across 2,637 linked matches.
- Ball-by-ball sections: fastest batting milestones 784 rows; player BBB batting rates 483 rows; bowling phase summary 1,631 rows.
- Premiership evidence: none verified; premiership exports are header-only.

Top 5 run scorers:

| player | runs |
| --- | ---: |
| Glen Mahoney | 7,734 |
| Sunny Somaia | 7,544 |
| Stuart Wynd | 6,993 |
| Greg Mccormick | 6,202 |
| Apurwa Sarve | 6,038 |

Top 5 wicket takers:

| player | wickets |
| --- | ---: |
| Matthew Briginshaw | 414 |
| Nathan Bungey | 363 |
| Luke Galle | 334 |
| Arun Chelvan | 330 |
| Stuart Wynd | 312 |

Top 5 catches:

| player | catches |
| --- | ---: |
| Chris George | 215 |
| Brett Powell | 183 |
| Glen Mahoney | 180 |
| Cameron Hocart | 139 |
| Glen Powell | 117 |

Risk notes:

- Duplicate risk: high. Review pack has 54 safe auto-merge groups, 17 manual groups, and 200 capped duplicate candidate rows.
- Team/grade label risk: high. There are 120 display labels, including historical names and typo-like values.
- Opponent/ground naming risk: medium-high because mappings are still starter/header-only.
- Obvious UI issues: none observed.
- Obvious data trust issues: no validation errors, but client preview should wait until historical labels are cleaned.

## Ashwood

Readiness: Needs team/grade cleanup first.

- Scorecards parsed: 5,248.
- Ball-by-ball: 920 matches, 303,650 ball events.
- Deploy-safe outputs: all expected Hall of Fame, Season Overview, and Player Profile files present.
- Review pack: `data/processed/experimental/ashwood/review_pack/`.
- App smoke: passed. Player Profile smoke used `raw_e35db09a_37b8_4803_a73a_4d6355568bad`; scorecard links were present.
- Scorecard-derived sections: Season by Round 5,248 rows; Recent Form 25,713 batting rows and 21,457 bowling rows; scorecard record links 47,266 rows across 2,820 linked matches.
- Ball-by-ball sections: fastest batting milestones 1,019 rows; player BBB batting rates 611 rows; bowling phase summary 1,727 rows.
- Premiership evidence: none verified; premiership exports are header-only.

Top 5 run scorers:

| player | runs |
| --- | ---: |
| Mark Edmonds | 6,716 |
| Anthony Edmonds | 5,231 |
| Musashi Fujihara | 4,592 |
| Daniel Curnow | 4,588 |
| Trevor Shepherd | 3,541 |

Top 5 wicket takers:

| player | wickets |
| --- | ---: |
| Timothy Pape | 244 |
| Matthew Clayton | 227 |
| Cameron Flint | 222 |
| O Effendi | 207 |
| Thomas Kinnane | 206 |

Top 5 catches:

| player | catches |
| --- | ---: |
| James Morrey | 119 |
| Jason Read | 104 |
| Anthony Edmonds | 101 |
| Mark Edmonds | 101 |
| Trevor Shepherd | 90 |

Risk notes:

- Duplicate risk: high. Review pack has 95 safe auto-merge groups, 12 manual groups, and 200 capped duplicate candidate rows.
- Team/grade label risk: highest in the pilot set, with 152 display labels across legacy, junior, senior, and women competition variants.
- Opponent/ground naming risk: medium-high because mappings are still starter/header-only.
- Obvious UI issues: none observed. One non-blocking local pandas `DtypeWarning` appeared in the Streamlit log during smoke; no visible UI issue resulted.
- Obvious data trust issues: no validation errors, but grade label cleanup is needed before sharing.

## Plenty

Readiness: Needs duplicate review first.

- Scorecards parsed: 3,214.
- Ball-by-ball: 503 matches, 200,539 ball events.
- Deploy-safe outputs: all expected Hall of Fame, Season Overview, and Player Profile files present.
- Review pack: `data/processed/experimental/plenty/review_pack/`.
- App smoke: passed. Final Player Profile smoke used `raw_26d82da9_dc55_43c2_8d57_b103091e58fa` to verify Recent Form; scorecard links were present.
- Scorecard-derived sections: Season by Round 3,214 rows; Recent Form 21,042 batting rows and 17,312 bowling rows; scorecard record links 38,458 rows across 2,216 linked matches.
- Ball-by-ball sections: fastest batting milestones 745 rows; player BBB batting rates 360 rows; bowling phase summary 1,120 rows.
- Premiership evidence: none verified; premiership exports are header-only.

Top 5 run scorers:

| player | runs |
| --- | ---: |
| Mitch Johnson | 6,494 |
| Gordon Zull | 5,616 |
| Scott Keane | 4,261 |
| Jayden Bedford | 3,942 |
| Graeme Pavey | 3,106 |

Top 5 wicket takers:

| player | wickets |
| --- | ---: |
| Paul Hubber | 338 |
| Shane Cullen | 293 |
| Mark Turnbull | 258 |
| Daniel Cocking | 236 |
| Dayne Smith | 163 |

Top 5 catches:

| player | catches |
| --- | ---: |
| Matt Deligiorgis | 133 |
| Scott Keane | 133 |
| Ralf Koegler | 92 |
| Chris Alexopoulos | 90 |
| Mark Johnson | 87 |

Risk notes:

- Duplicate risk: high. Review pack has 84 safe auto-merge groups, 11 manual groups, and 200 capped duplicate candidate rows, including masked-name cases.
- Team/grade label risk: medium-high. There are 104 display labels with junior and shield variants.
- Opponent/ground naming risk: medium-high because mappings are still starter/header-only.
- Obvious UI issues: none observed after retry with a recent-form-covered player.
- Obvious data trust issues: no validation errors, but duplicate review should happen before preview.

## Reynella

Readiness: Needs duplicate review first.

- Scorecards parsed: 3,110.
- Ball-by-ball: 572 matches, 244,422 ball events.
- Deploy-safe outputs: all expected Hall of Fame, Season Overview, and Player Profile files present.
- Review pack: `data/processed/experimental/reynella/review_pack/`.
- App smoke: passed. Final Player Profile smoke used `raw_367c1193_9d30_481e_835c_ceffb481ce4f` to verify Recent Form; scorecard links were present.
- Scorecard-derived sections: Season by Round 3,110 rows; Recent Form 24,023 batting rows and 19,117 bowling rows; scorecard record links 43,249 rows across 2,313 linked matches.
- Ball-by-ball sections: fastest batting milestones 702 rows; player BBB batting rates 532 rows; bowling phase summary 1,818 rows.
- Premiership evidence: none verified; premiership exports are header-only.

Top 5 run scorers:

| player | runs |
| --- | ---: |
| Richard Gabb | 6,454 |
| Jordan Wright | 5,641 |
| Paul Radbourne | 5,071 |
| Brett Julian | 4,156 |
| Matt Hehner | 3,983 |

Top 5 wicket takers:

| player | wickets |
| --- | ---: |
| Cameron Pannach | 476 |
| Daniel Rabbett | 323 |
| Matt Hehner | 280 |
| Damien Pimlott | 253 |
| Jonathon Hague | 234 |

Top 5 catches:

| player | catches |
| --- | ---: |
| Richard Gabb | 209 |
| Scott Trenorden | 108 |
| Matthew Aston | 106 |
| Jordan Wright | 103 |
| Brett Julian | 100 |

Risk notes:

- Duplicate risk: high. Reynella has the highest safe auto-merge count in this set: 111 safe groups, 12 manual groups, and 200 capped duplicate candidate rows.
- Team/grade label risk: high. There are 116 display labels, including sponsor, junior, T20, and association variants.
- Opponent/ground naming risk: medium-high because mappings are still starter/header-only.
- Obvious UI issues: none observed after retry with a recent-form-covered player.
- Obvious data trust issues: no validation errors, but duplicate review is the first blocker.

## Georges River District

Readiness: Needs duplicate review first.

Official PlayCricket identity: Georges River Cricket Club.

- Scorecards parsed: 2,604.
- Ball-by-ball: 295 matches, 155,573 ball events.
- Deploy-safe outputs: all expected Hall of Fame, Season Overview, and Player Profile files present.
- Review pack: `data/processed/experimental/georges-river-district/review_pack/`.
- App smoke: passed. Final Player Profile smoke used `raw_06e9b44f_37a4_4d46_9b6a_3ea2cd1725f1` to verify Recent Form; scorecard links were present.
- Scorecard-derived sections: Season by Round 2,604 rows; Recent Form 22,761 batting rows and 14,483 bowling rows; scorecard record links 37,321 rows across 2,180 linked matches.
- Ball-by-ball sections: fastest batting milestones 555 rows; player BBB batting rates 329 rows; bowling phase summary 770 rows.
- Premiership evidence: none verified; premiership exports are header-only.

Top 5 run scorers:

| player | runs |
| --- | ---: |
| Kevin Croom | 8,606 |
| Trevor Davies | 8,532 |
| Gavin Scott | 6,918 |
| Ryan Croom | 6,118 |
| Peter Remfrey | 5,449 |

Top 5 wicket takers:

| player | wickets |
| --- | ---: |
| Paul Thomas | 608 |
| Dave Jiffkins | 495 |
| Daniel Yates | 491 |
| Gavin Scott | 439 |
| Jeff Woods | 379 |

Top 5 catches:

| player | catches |
| --- | ---: |
| Meville Fernando | 311 |
| Ryan Croom | 221 |
| Benjamin Churcher | 154 |
| Gavin Scott | 143 |
| Bruce Whitehouse | 130 |

Risk notes:

- Duplicate risk: highest identity complexity. The review pack has 74 safe auto-merge groups, 11 manual groups, and 200 capped duplicate candidate rows across the largest player pool.
- Team/grade label risk: medium by label count, with 43 display labels, but the historical scope is broad.
- Opponent/ground naming risk: medium-high because mappings are still starter/header-only.
- Obvious UI issues: none observed after retry with a recent-form-covered player.
- Obvious data trust issues: no validation errors, but naming/identity review should happen before sharing links.

## Southside Follow-Up Validation - May 27, 2026

Southside East Caulfield remains the recommended first private preview candidate.

Follow-up status: Preview-ready after final visual review.

- Premierships: 5 verified Southside Grand Final wins still render. Captain roles are now extracted from the verified winning-team scorecard payload where available: Vatsan Vasu, Aamir Rana, Pranav Sinha, and Christopher Jones. One E Grade row remains without captain evidence and is intentionally blank.
- Theming: shared sidebar/link/tab/progress styles resolve through active club variables. Southside uses its configured blue/accent palette across Hall of Fame, Season Overview, Milestone, and Player Profile; FVCC now uses its shirt-inspired navy, maroon, and gold config palette.
- Season Overview: Winter 2026 women’s rows now use fetched team ownership and show Caroline Springs Cricket Club as opponent, not Southside.
- Hall of Fame: Men/Women toggle added and verified. Women’s view shows classified women’s records and clean empty states where sections have no women’s data.
- Links: HOF player, season, and scorecard links remained valid in local smoke.
- Remaining caveats: 14 manual duplicate groups remain, opponent/ground mappings are still conservative starter mappings, and a final human mobile/narrow visual pass is still recommended.

## Fastest Innings Validation Follow-Up - May 27, 2026

Fastest Innings is now stricter across all pilot clubs and FVCC.

- Source cumulative batter-run fields are advisory only; deploy-safe fastest records use per-delivery batter-run progression unless source cumulative values validate cleanly.
- Suspicious rows are excluded or corrected before display. Missing or untrustworthy ball-by-ball coverage remains unavailable rather than guessed.
- The false-looking fastest 50 examples were corrected from existing local ball-by-ball data: Plenty Geoffrey King 52 balls, Reynella Cameron Pannach 63 balls, and Georges River Christopher McArthur 35 balls.
- No deploy-safe fastest 50 is below 9 balls and no deploy-safe fastest 100 is below 17 balls after rebuild.
- HOF Iconic Performances and Fastest Innings now use active club theming variables instead of old FVCC purple accents.
- Detailed before/after counts are in `docs/multi_club_fastest_innings_audit.md`.
