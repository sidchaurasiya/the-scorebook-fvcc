# Hall of Fame Current State

This document records the Hall of Fame implementation on `main` after the May 2026 Hall of Fame production fixes.

The Hall of Fame page is implemented in `src/ui/layout.py` and is rendered by `render_hall_of_fame_page()`. It uses the shared processed PlayCricket aggregate data plus deploy-safe Hall of Fame CSV summaries for records that depend on match-centre or ball-by-ball data.

## Page Structure

Current visible page order:

1. Page intro
2. Premierships 🛡️
3. All-Time Leaders 👑
4. Iconic Performances 🌟
5. Fastest Innings ⚡
6. Record Holders 📘
7. Greatest Individual Seasons 🎖️
8. Detailed Records 📊

The intro contains:

- `Hall of Fame 🏆`
- `Fiji Victorian Cricket Club`
- `The players who shaped the club’s history.`
- `Players with multiple PlayCricket profiles are merged into one profile.`

## Primary Data Sources

The Hall of Fame starts from shared processed aggregate files:

- `data/processed/all_seasons_batting.csv`
- `data/processed/all_seasons_bowling.csv`
- `data/processed/all_seasons_fielding.csv`
- `data/processed/seasons.csv`
- `data/processed/players.csv`

Canonical player identity and team/grade display cleaning are applied before Hall of Fame summaries are built.

## Deploy-Safe Hall Of Fame Files

These tracked files under `data/processed/hall_of_fame/` are intentionally small deploy-safe summaries. They allow Streamlit Cloud to render records without committing full match-centre archives.

| File | Current Rows | Purpose |
| --- | ---: | --- |
| `fastest_batting_milestones.csv` | 57 | Fastest 50s and Fastest 100s from verified ball-by-ball innings. |
| `player_bbb_batting_rates.csv` | 97 | Verified ball-by-ball batting strike rate inputs for Detailed Records Bat SR. |
| `player_bowling_milestones.csv` | 254 | Scorecard bowling milestone counts such as 3WI, plus BBI helper fields. |
| `player_premierships.csv` | 63 | Player premiership counts and evidence match IDs. |
| `player_scorecard_milestones.csv` | 297 | Scorecard batting milestones: 30s, 50s, 100s, ducks, HS. |
| `player_win_rates.csv` | 297 | Result-mapped player win counts and win percentage. |
| `premiership_wins.csv` | 8 | Verified FVCC premiership wins and scorecard links. |
| `scorecard_record_links.csv` | 3,747 | Deploy-safe match IDs for scorecard links on Iconic Performances and profile highlights. |

## Runtime Data Boundaries

The production Hall of Fame should not depend on these ignored local-only folders at runtime:

- `data/raw/match_centre/`
- `data/processed/match_centre/`
- `data/processed/experimental/`
- debug outputs such as `data/debug_biggest_improvers.csv` or `data/debug_player_vs_peers.csv`

Local-only match-centre files may be used to regenerate deploy-safe Hall of Fame CSVs, but the full raw or processed match-centre archive should not be committed.

## Section Details

### Premierships 🛡️

Source files:

- `data/processed/hall_of_fame/premiership_wins.csv`
- `data/processed/hall_of_fame/player_premierships.csv`

The section contains:

- `FVCC Premiership Wins`
- `Most Premierships`

Premiership wins are detected from verified finals scorecards. The tracked premiership win file stores season, grade, round, match date, FVCC team, opponent, captain, result text, venue, scorecard URL, confidence, and detection reason.

Player premiership counts use `player_premierships.csv`. The loader verifies that `premiership_count` matches the number of evidence match IDs before displaying a row. Player leaders are sorted by:

1. premiership count descending
2. all-time match count descending
3. earliest premiership season ascending
4. player name ascending

### All-Time Leaders 👑

Metrics:

- Most Matches
- Most Runs
- Most Wickets
- Most Catches

Each card shows 6 rows by default and can expand to top 10 with the subtle `Show top 10 ↓` control. Expanded cards show `Show less ↑`.

Leader sorting:

- Batting metric cards sort by metric descending, then batting average descending, then player name.
- Bowling metric cards sort by metric descending, then bowling average ascending, then player name.
- Fielding/matches-style cards sort by metric descending, then matches ascending, then player name.

### Iconic Performances 🌟

Cards:

- Highest Individual Scores
- Best Bowling Innings

Each card shows 6 rows by default and can expand to top 10.

Highest scores are sorted by score descending, then not-out score ahead of out score. Best bowling innings uses BBI sorting: wickets descending, then runs conceded ascending.

Scorecard links are attached from scorecard match IDs where available.

### Fastest Innings ⚡

Subtitle:

`Based on matches with verified ball-by-ball data.`

Cards:

- Fastest 50s
- Fastest 100s

Source file:

- `data/processed/hall_of_fame/fastest_batting_milestones.csv`

Only verified ball-by-ball innings are used. The record value is balls to milestone. Rows are sorted by:

1. balls to milestone ascending
2. final runs descending
3. match date descending

The final score display preserves not-out notation where known. No-balls faced by the batter follow the same interpretation used by the milestone builder; wides do not count as balls faced.

### Record Holders 📘

Cards currently built:

- Most 100s
- Most 50s
- Most 4s
- Most 6s
- 5 Wicket Hauls
- Most Maidens
- Ducks
- Best Win %

Best Win %:

- Source: `data/processed/hall_of_fame/player_win_rates.csv`
- Minimum eligibility: 60 all-time matches
- Players with no result-mapped matches are excluded.
- Sorted by Win % descending, then matches descending, then player name.
- Display format: percentage with one decimal, plus metadata like `54 wins from 82 matches`.

### Greatest Individual Seasons 🎖️

Desktop title:

- `Greatest Individual Seasons 🎖️`

Mobile title:

- `Greatest Seasons 🎖️`

The section uses historical season aggregate rows. Batting season cards include matches and batting milestones. Bowling season cards include matches, wickets, average/economy/strike-rate fields where available, and 10WM where available.

### Detailed Records 📊

Detailed Records has three tabs:

- Batting
- Bowling
- Fielding

The table is a custom sortable HTML table with:

- numeric sorting for numeric columns
- HS sorting by runs, with not-out scores treated as stronger for tied runs
- BBI sorting by wickets descending, then runs conceded ascending
- Win % sorting numerically
- sticky Player column
- compact 13px table font

## Detailed Records Columns

### Batting

Visible column order:

1. Player
2. Seasons
3. Debut Season
4. Latest Season
5. Matches
6. Win %
7. Runs
8. Bat Avg
9. Bat SR
10. HS
11. 30s
12. 50s
13. 100s
14. 0s
15. 4s
16. 6s

Important definitions:

- Bat SR uses verified ball-by-ball data only from `player_bbb_batting_rates.csv`.
- Players without verified ball-by-ball batting data show `N/A` for Bat SR.
- 30s are counted from scorecard batting innings where the final score is 30 to 49 inclusive.
- Not-out scores in the 30 to 49 range count.
- 50s, 100s, ducks and HS come from aggregate and/or scorecard-derived milestone data as currently wired in the Hall of Fame table.

### Bowling

Visible column order:

1. Player
2. Seasons
3. Matches
4. Win %
5. Overs
6. Maidens
7. Wickets
8. Avg
9. Bowl SR
10. Econ
11. BBI
12. 3WI
13. 5WI
14. 10WM

Important definitions:

- 3WI is count of scorecard bowling innings with exactly 3 or 4 wickets.
- 5WI is count of bowling innings with 5 or more wickets.
- BBI sorting uses wickets descending, then runs conceded ascending.
- Bowl Avg, Bowl SR and Econ remain numeric-sortable where available.

### Fielding

Visible column order:

1. Player
2. Seasons
3. Matches
4. Catches
5. Stumpings
6. Run Outs
7. Dismissals

## Links And Navigation

Player links:

- Hall of Fame player names link to Player Profile deep links.
- Links use canonical player identity where available.

Season links:

- Hall of Fame season links open Season Overview with the selected season applied.
- Canonical query format: `?page=season-overview&season=<url-encoded season name>`.
- Example: `?page=season-overview&season=Summer%202001%2F02`.

Scorecard links:

- Scorecard links open PlayCricket scorecards.
- They are used in Premierships, Iconic Performances, Fastest Innings, and other record cards where match IDs are available.

## Deploy Notes

- Hall of Fame uses deploy-safe CSVs for match-centre-derived records.
- Full raw or processed match-centre folders are intentionally ignored and should not be committed.
- If Hall of Fame data is refreshed after new match-centre coverage, regenerate the relevant deploy-safe CSVs:
  - `fastest_batting_milestones.csv`
  - `scorecard_record_links.csv`
  - `premiership_wins.csv`
  - `player_premierships.csv`
  - `player_win_rates.csv`
  - `player_bbb_batting_rates.csv`
  - `player_scorecard_milestones.csv`
  - `player_bowling_milestones.csv`
- GA4 analytics is separate from Hall of Fame rendering and should not affect records or table output.
- `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES` should remain `False` for production.

## Future Release Verification Checklist

- [ ] Hall of Fame loads without Streamlit errors.
- [ ] Premierships render.
- [ ] All-Time Leaders render and expand/collapse between top 6 and top 10.
- [ ] Iconic Performances render and expand/collapse between top 6 and top 10.
- [ ] Fastest 50s and Fastest 100s render.
- [ ] Record Holders render, including Best Win %.
- [ ] Greatest Individual Seasons render.
- [ ] Detailed Records Batting, Bowling and Fielding tabs render.
- [ ] Bat SR populates for verified ball-by-ball players and shows `N/A` otherwise.
- [ ] 30s populate from scorecard batting innings.
- [ ] 3WI populates from scorecard bowling innings.
- [ ] HS sorting works by numeric score and not-out status.
- [ ] BBI sorting works by wickets descending, then runs ascending.
- [ ] Season links open the correct Season Overview season.
- [ ] Player links open the correct Player Profile.
- [ ] Scorecard links open PlayCricket scorecards.
- [ ] No `NaN`, `None`, raw IDs or internal debug values are visible.
- [ ] Experimental pages remain hidden.
