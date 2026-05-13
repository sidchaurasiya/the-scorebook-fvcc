# Player Profile Tags & Summaries Audit

This audit documents the current Player Profile classification/tag and summary sentence logic after the badge system refresh. The implementation lives in `player_role_badges()`, `select_profile_badges()`, and `player_profile_insight()` in `src/ui/layout.py`.

## Tags / Badges

Badge candidates are evaluated by priority and every applicable badge is displayed. There is no hard display cap; badges wrap inside the player profile card so heavily qualified players can show their full cricket profile while stronger tags still appear first.

| Tag | Logic | Thresholds | Metrics Used | Priority | Notes |
| --- | --- | --- | --- | --- | --- |
| Club Legend | Shows if the player reaches any major legend threshold. | Matches >= 200 OR Runs >= 4000 OR Wickets >= 250. | Matches, Runs, Wickets. | 1 | Highest priority. Club Veteran is not added when this applies. |
| Genuine All-rounder | Shows for a strong two-skill contributor. | Runs >= 1000; Wickets >= 100. | Runs, Wickets. | 2 | Role badge. Higher priority than All-round Contributor. No matches or batting-average threshold. |
| All-round Contributor | Shows for meaningful contribution with bat and ball. | Matches >= 30; Bat Avg > 12; Runs >= 300; Wickets >= 30. | Matches, Bat Avg, Runs, Wickets. | 3 | Not shown when Genuine All-rounder applies. |
| Upcoming Star | Shows for early-career players with strong returns. | Matches >= 20 and < 50; plus Bat Avg > 20 OR 0 < Bowl Avg < 20 and Wickets >= 15. | Matches, Bat Avg, Bowl Avg, Wickets. | 4 | Role badge for under-50-match players. |
| Star Batter | Shows for high batting average over a meaningful sample. | Matches >= 30; Bat Avg > 25. | Matches, Bat Avg. | 5 | High batting priority. |
| Star Bowler | Shows for high-impact bowling average over a meaningful sample. | Matches >= 30; Wickets >= 30; 0 < Bowl Avg < 20. | Matches, Wickets, Bowl Avg. | 6 | Does not require wickets per match >= 0.80. |
| Run Machine | Shows for high-volume run scorers. | Runs >= 2000 OR Runs per match >= 25 and Matches >= 50. | Runs, Matches, Runs per match. | 7 | Batting badge. |
| Dependable Batter | Shows for consistent batting return below Star Batter tier. | Matches >= 30; Bat Avg > 18; Star Batter not applied. | Matches, Bat Avg. | 7 | Batting badge. |
| Wicket Taker | Shows for players taking more than one wicket per match. | Matches >= 20; Wickets per match > 1. | Matches, Wickets, Wickets per match. | 8 | Bowling badge. |
| Golden Arm | Shows for low-volume bowlers with strong impact when used. | Matches >= 30; Wickets per match < 0.60; Wickets >= 15; 0 < Bowl Avg < 25. | Matches, Wickets, Wickets per match, Bowl Avg. | 9 | Bowling badge. |
| Partnership Breaker | Shows for bowlers with strong wicket frequency and workload. | Overs > 150; Wickets >= 30; 0 < Bowl SR < 35. | Balls bowled converted to overs, Wickets, Bowl SR. | 10 | Bowling badge. Display label is Partnership Breaker. |
| Economy Controller | Shows for bowlers who keep scoring rates down across a meaningful workload. | Overs > 150; 0 < Economy < 3.5; Wickets >= 30 OR Matches >= 30. | Balls bowled converted to overs, Economy, Wickets, Matches. | 11 | Bowling badge. |
| Big Hitter | Shows for six-hitting profile. | Matches >= 30; 6s per match > 0.3. | Matches, 6s. | 12 | Style badge. |
| Values His Wicket | Shows for patient batting profile. | Matches >= 20; Balls faced per dismissal >= 30. | Matches, BF, Outs. | 13 | Style badge. |
| Gap Finder | Shows for four-hitting profile. | Matches >= 30; 4s per match > 2. | Matches, 4s. | 14 | Style badge. |
| Quick Scorer | Shows for strong verified scoring tempo. | Matches >= 20; verified Bat SR >= 90; verified BF >= 125; verified Runs >= 125. | Matches, verified ball-by-ball Bat SR, verified ball-by-ball balls faced, verified ball-by-ball runs. | 15 | Bat SR uses verified ball-by-ball runs and balls from the same covered innings only. |
| Boundary Maker | Shows only when Big Hitter and Gap Finder do not already apply. | Matches >= 20; boundaries per match > 2.5; no Big Hitter; no Gap Finder. | Matches, 4s, 6s. | 15 | Demoted overlap badge. |
| Workhorse | Shows for bowlers trusted with a heavy workload. | Overs >= 250; Matches >= 30. | Balls bowled converted to overs, Matches. | 16 | Bowling badge. |
| Safe Hands | Shows for non-keeper fielding contribution. | Stumpings <= 0; Matches >= 20; Dismissals per match > 0.4. | Matches, Catches, Stumpings, Run Outs, Dismissals. | 17 | Fielding badge. |
| Keeper Impact | Shows for wicketkeeping impact. | Stumpings > 0. | Stumpings. | 18 | Fielding/keeping badge. Can apply below 20 matches. |
| Premiership Winner | Shows when deploy-safe premiership evidence lists the player in a winning FVCC premiership side. | Player has >= 1 verified premiership in `player_premierships.csv`. | Canonical player name, premiership count, evidence match IDs. | 18 | Gold achievement badge. If count > 1, display is `Premiership Winner xN`. |
| Premiership Winning Captain | Shows when deploy-safe premiership win evidence records the player as captain of the winning side. | Player appears as recorded captain in `premiership_wins.csv`. | Canonical player name matched to recorded captain name. | 18 | Gold achievement badge. Captaincy is not inferred when captain is missing. If count > 1, display is `Premiership Winning Captain xN`. |
| Season Standout | Shows when the player has season-level leader achievements. | At least one club/grade run or wicket leader achievement in a season. | Unique season labels from club run leader, grade run leader, club wicket leader, and grade wicket leader details. | 19 | Achievement badge. Multiple achievements in the same season count once. If count > 1, display is `Season Standout xN`. |
| Milestone Maker | Shows for major club milestone totals, unless Club Legend already applies. | Runs >= 1000 OR Wickets >= 100 OR Matches >= 100; no Club Legend. | Runs, Wickets, Matches. | 20 | Legacy badge. Low priority so it does not crowd out cricket-style badges. |
| Club Veteran | Shows for long-serving players, unless Club Legend already applies. | Matches >= 100; no Club Legend. | Matches. | 21 | Legacy badge. Low priority. |
| Mr Consistent | Shows for multi-season delivery. | At least 3 seasons with 200+ runs OR at least 3 seasons with 15+ wickets. | Season-level Runs, season-level Wickets. | 22 | Achievement badge. |
| Club Contributor | Fallback when no other badge applies and player has 20+ matches. | No badge candidates; Matches >= 20. | Matches. | Fallback | Only appears if no other badge qualifies. |
| Emerging Player | Fallback when no other badge applies and player has fewer than 20 matches. | No badge candidates; Matches < 20. | Matches. | Fallback | Only appears if no other badge qualifies. |

## Summary Sentences

Only one summary sentence is displayed. The summary logic first checks blended Club Legend combinations, then role/style/fielding tags in priority order.

| Summary | Logic | Priority | Notes |
| --- | --- | --- | --- |
| Long-serving club figure with major contributions across bat and ball. | Club Legend plus Genuine All-rounder or All-round Contributor. | 1 | Blended legacy/all-round summary. |
| Long-serving club figure with a major batting footprint across the record book. | Club Legend plus Star Batter, Run Machine, Dependable Batter, Big Hitter, or Gap Finder. | 2 | Blended legacy/batting summary. |
| Long-serving club figure with sustained bowling impact across seasons. | Club Legend plus Star Bowler, Partnership Breaker, Wicket Taker, Economy Controller, or Workhorse. | 3 | Blended legacy/bowling summary. |
| Long-serving club figure with strong fielding impact across the available records. | Club Legend plus Safe Hands or Keeper Impact. | 4 | Blended legacy/fielding summary. |
| Long-serving club figure with a major footprint across the record book. | Club Legend fallback. | 5 | Used when no more specific Club Legend pairing applies. |
| Strong two-skill contributor across bat and ball. | Genuine All-rounder. | 6 | Role summary. |
| Contributes meaningfully with both bat and ball. | All-round Contributor. | 7 | Role summary. |
| Early-career player already showing strong signs of future impact. | Upcoming Star. | 8 | Early-career summary. |
| High-impact run-maker with strong batting returns across seasons. | Star Batter. | 9 | Batting summary. |
| Consistent run scorer with a strong footprint across seasons. | Run Machine. | 10 | Batting volume summary. |
| Reliable batting contributor with consistent returns across the record book. | Dependable Batter. | 11 | Batting summary. |
| Boundary-focused batter with a strong six-hitting profile. | Big Hitter. | 12 | Style summary. |
| Finds the boundary regularly through consistent four-hitting. | Gap Finder or Boundary Maker. | 13 | Style summary. |
| Patient batter who spends time at the crease and values his wicket. | Values His Wicket. | 14 | Style summary. |
| Tempo-setting batter with strong recent scoring rate. | Quick Scorer. | 15 | Uses reliable recent Bat SR. |
| High-impact bowler with strong wicket-taking and average profile. | Star Bowler. | 16 | Bowling summary. |
| Regular wicket threat who can break games open with the ball. | Partnership Breaker. | 17 | Bowling style summary. |
| Consistently finds wickets across the available club records. | Wicket Taker. | 18 | Bowling summary. |
| Makes an impact with the ball despite limited bowling volume. | Golden Arm. | 19 | Bowling style summary. |
| Disciplined bowler who keeps scoring rates under control. | Economy Controller. | 20 | Bowling style summary. |
| Trusted to carry a heavy bowling workload across seasons. | Workhorse. | 21 | Bowling workload summary. |
| Delivers across seasons, not just in one standout year. | Mr Consistent. | 22 | Season consistency summary. |
| Reliable fielding contributor across the available records. | Safe Hands. | 23 | Fielding summary. |
| Wicketkeeping contributor with impact behind the stumps. | Keeper Impact. | 24 | Keeping summary. |
| Has produced standout season-level performances in the club record book. | Season Standout. | 25 | Achievement summary. |
| Has crossed major club milestones across the available records. | Milestone Maker. | 26 | Milestone summary. |
| Experienced club contributor with a long record across seasons. | Club Veteran. | 27 | Legacy summary. |
| Early career profile building across the available club records. | Emerging Player or matches < 20. | 28 | Early-career fallback. |
| Club contributor across the available records. | No earlier summary condition applies. | Fallback | Default summary. |

## Calculation Notes

- Player Profile data is loaded through `get_player_profile_data(canonical_player_id, metadata_mtime(), player_aliases_mtime())`.
- Processed all-season batting, bowling, and fielding tables are mapped through player aliases and filtered by `canonical_player_id`, so merged PlayCricket profiles contribute to one canonical profile.
- Career totals come from `build_player_career_totals()` and are recalculated from raw totals where possible.
- Batting average uses total runs / total outs. Outs are innings minus not-outs.
- Bowling average uses runs conceded / wickets.
- Economy uses runs conceded and balls bowled.
- Bowling strike rate uses balls bowled / wickets.
- Overs are derived from balls bowled.
- Dismissals are catches + stumpings + run outs.
- Quick Scorer and career Bat SR use verified ball-by-ball batting summaries only. They must never divide all-scorecard runs by ball-by-ball balls.
- Values His Wicket currently uses career balls faced per dismissal from available data.
- Mr Consistent uses the already-built Player Profile season table and checks season totals.
- Season Standout uses cached historical leader details but counts unique season labels only. Multiple club/grade or batting/bowling achievements in the same season still show as one standout season.
- Premiership Winner and Premiership Winning Captain use deploy-safe Hall of Fame premiership CSVs. Winner tags come from `data/processed/hall_of_fame/player_premierships.csv`; captain tags come from recorded `captain_name` values in `data/processed/hall_of_fame/premiership_wins.csv`.

## Concerns / Follow-Up Ideas

- There is no badge display cap; very highly qualified players can now show all applicable tags.
- Star Bowler remains the display label for the high-priority bowling-average badge. Partnership Breaker remains the strike-rate style badge.
- Keeper Impact can still apply with fewer than 20 matches because the current rule is stumpings > 0.
- Boundary Maker is retained only as a fallback style badge when Big Hitter and Gap Finder are not already present.
