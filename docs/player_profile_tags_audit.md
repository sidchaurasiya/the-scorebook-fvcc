# Player Profile Tags & Summaries Audit

This audit documents the current Player Profile classification/tag and summary sentence logic. It is based on `player_role_badges()` and `player_profile_insight()` in `src/ui/layout.py`.

## Tags / Badges

Badges are evaluated in the order shown below. The final displayed list is capped at the first 4 badges that pass. Most performance-based badges use canonical career totals from the selected player's merged profile.

| Tag | Logic | Thresholds | Metrics Used | Priority | Notes |
| --- | --- | --- | --- | --- | --- |
| Club Legend | Shows when career matches are greater than 200. | Matches > 200. | Matches. | 1 | Highest-priority badge. Can appear with other badges, but the 4-badge display cap may hide lower-priority badges. |
| All-round Contributor | Shows when player has at least 20 matches, batting average above 12, at least 50 wickets, and at least 0.80 wickets per match. | Matches >= 20; Bat Avg > 12; Wickets >= 50; Wickets per match >= 0.80. | Matches, Bat Avg, Wickets, Wickets per match. | 2 | Requires meaningful bowling contribution and batting average above 12. |
| Star Batter | Shows when player has at least 20 matches and batting average above 25. | Matches >= 20; Bat Avg > 25. | Matches, Bat Avg. | 3 | Mutually exclusive in practice with Dependable Batter because Dependable Batter checks that Star Batter has not already been added. |
| Dependable Batter | Shows when player has at least 20 matches, batting average above 18, and Star Batter has not already applied. | Matches >= 20; Bat Avg > 18; no Star Batter badge. | Matches, Bat Avg. | 4 | Lower batting tier than Star Batter. |
| Star Bowler | Shows when player has a bowler profile, at least 20 wickets, and bowling average is greater than 0 and below 20. | Matches >= 20; Wickets per match >= 0.80; Wickets >= 20; 0 < Bowl Avg < 20. | Matches, Wickets, Wickets per match, Bowl Avg. | 5 | Depends on `bowler_profile`, so low-volume wicket takers are excluded. |
| Wicket Taker | Shows when player has a bowler profile and takes more than 1 wicket per match. | Matches >= 20; Wickets per match >= 0.80; Wickets per match > 1. | Matches, Wickets, Wickets per match. | 6 | Can appear with Star Bowler, Partnership Breaker, or Economy Controller. |
| Partnership Breaker | Shows when player has a bowler profile, has bowled more than 150 overs, and bowling strike rate is greater than 0 and below 35. | Matches >= 20; Wickets per match >= 0.80; Overs > 150; 0 < Bowl SR < 35. | Matches, Wickets per match, balls bowled converted to overs, Bowl SR. | 7 | Display label was previously Strike Bowler; current display text is Partnership Breaker. |
| Economy Controller | Shows when player has a bowler profile, has bowled more than 150 overs, and economy rate is greater than 0 and below 3. | Matches >= 20; Wickets per match >= 0.80; Overs > 150; 0 < Economy < 3. | Matches, Wickets per match, balls bowled converted to overs, Economy. | 8 | Can be hidden by the 4-badge cap if earlier badges apply. |
| Big Hitter | Shows when player has at least 20 matches and sixes per match is above 0.3. | Matches >= 20; 6s / Matches > 0.3. | Matches, 6s. | 9 | Uses career sixes. |
| Gap Finder | Shows when player has at least 20 matches and fours per match is above 2. | Matches >= 20; 4s / Matches > 2. | Matches, 4s. | 10 | Uses career fours. |
| Boundary Maker | Shows when player has at least 20 matches and boundaries per match is above 2.5. | Matches >= 20; (4s + 6s) / Matches > 2.5. | Matches, 4s, 6s. | 11 | Can overlap with Big Hitter and Gap Finder. |
| Quick Scorer | Shows when player has at least 20 matches, at least 250 career runs, and reliable batting strike rate is at least 85. | Matches >= 20; Runs >= 250; Bat SR >= 85. | Matches, Runs, reliable Bat SR. | 12 | Bat SR is calculated only from Summer 2024/25 onward. |
| Keeper Impact | Shows when stumpings are greater than 0. | Stumpings > 0. | Stumpings. | 13 | Does not require 20 matches. |
| Safe Hands | Shows when player is not classified as keeper by stumpings, has at least 20 matches, and dismissals per match is above 0.4. | Stumpings <= 0; Matches >= 20; Dismissals / Matches > 0.4. | Matches, Catches, Stumpings, Run Outs, Dismissals. | 14 | Dismissals = catches + stumpings + run outs. Mutually exclusive with Keeper Impact in practice because it requires stumpings <= 0. |
| Club Veteran | Shows when career matches are at least 100. | Matches >= 100. | Matches. | 15 | Also independently triggers Milestone Maker through matches >= 100. |
| Milestone Maker | Shows when player has at least 1,000 runs, 100 wickets, or 100 matches. | Runs >= 1000 OR Wickets >= 100 OR Matches >= 100. | Runs, Wickets, Matches. | 16 | Can overlap with Club Veteran. |
| Season Standout | Shows when the player has any season-level leader achievement count greater than 0. | At least one of the leader detail lists has length > 0. | Club run leader count, grade run leader count, club wicket leader count, grade wicket leader count. | 17 | Uses `player_leader_counts()`, backed by cached historical leader details. |
| Club Contributor | Fallback when no other badge applies and the player has at least 20 matches. | No badges; Matches >= 20. | Matches. | Fallback | Only appears if no prior badge was added. |
| Emerging Player | Fallback when no other badge applies and the player has fewer than 20 matches. | No badges; Matches < 20. | Matches. | Fallback | Only appears if no prior badge was added. |

## Summary Sentences

Summary sentences are evaluated in the order below. The first matching condition returns the final summary, so only one sentence is shown.

| Summary | Logic | Priority | Notes |
| --- | --- | --- | --- |
| Long-serving club figure with a major footprint across the record book. | Shown when Club Legend badge is present. | 1 | Highest-priority summary. |
| Contributes meaningfully with both bat and ball. | Shown when All-round Contributor badge is present. | 2 | Only appears if Club Legend is not present. |
| Reliable run-maker with consistent batting impact across seasons. | Shown when Star Batter or Dependable Batter badge is present. | 3 | Covers both batting tiers. |
| Boundary-focused batter with a strong six-hitting profile. | Shown when Big Hitter badge is present. | 4 | Only appears if higher-priority summaries do not apply. |
| Consistent boundary scorer who regularly finds gaps. | Shown when Gap Finder, Boundary Maker, or Quick Scorer badge is present. | 5 | Groups boundary and tempo scoring tags together. |
| Regular wicket threat with strong bowling impact. | Shown when Star Bowler, Partnership Breaker, or Wicket Taker badge is present. | 6 | Economy Controller has its own later summary. |
| Disciplined bowler who keeps scoring rates under control. | Shown when Economy Controller badge is present. | 7 | Can be pre-empted by earlier bowling summary if both tags are displayed. |
| Strong fielding contributor across the available records. | Shown when Safe Hands or Keeper Impact badge is present. | 8 | Covers fielding and wicketkeeping impact. |
| Early career profile building across the available club records. | Shown when Emerging Player badge is present or matches are fewer than 20. | 9 | Applies to under-20-match profiles unless a higher-priority badge triggers first, such as Keeper Impact. |
| Club contributor across the available records. | Fallback when no earlier summary condition applies. | Fallback | Default summary for profiles with a badge combination not matched above. |

## Calculation Notes

- The Player Profile page calls `get_player_profile_data(canonical_player_id, metadata_mtime(), player_aliases_mtime())`, then `build_player_profile_view(profile)`.
- `get_player_profile_data()` reads processed all-season batting, bowling, and fielding tables, reapplies player alias mapping, and filters rows by `canonical_player_id`.
- Tag logic uses canonical merged profile data, not a raw player name only. Duplicate or merged PlayCricket profiles flow into the same career totals if they map to the same `canonical_player_id`.
- Career totals are built in `build_player_career_totals()` from the profile's season table plus source batting, bowling, and fielding rows.
- Batting average is recalculated from total runs divided by total outs. Outs are innings minus not-outs.
- Bowling average is recalculated from runs against divided by wickets.
- Economy is recalculated from runs against and balls bowled.
- Bowling strike rate is recalculated from balls bowled divided by wickets.
- Dismissals are calculated as catches + stumpings + run outs.
- Batting strike rate follows the reliability rule: `reliable_batting_strike_rate()` only uses batting rows from Summer 2024/25 onward. This value flows into career `Bat SR`, season table `Bat SR`, grade table `Bat SR`, and the Quick Scorer badge.
- The `bowler_profile` gate is `matches >= 20` and `wickets_per_match >= 0.80`. Star Bowler, Wicket Taker, Partnership Breaker, and Economy Controller all depend on this gate.
- The display is capped at 4 badges using `return badges[:4]`. This means lower-priority badges such as Club Veteran, Milestone Maker, or Season Standout may be calculated but not shown if four earlier badges already apply.
- Star Batter and Dependable Batter are mutually exclusive in practice because Dependable Batter only applies if Star Batter has not already been added.
- Keeper Impact and Safe Hands are mutually exclusive in practice because Safe Hands requires stumpings <= 0.

## Concerns / Inconsistencies To Review Later

- Season Standout is low priority and may often be hidden by the 4-badge cap, even though it could be an interesting profile signal.
- Club Veteran and Milestone Maker are also low priority despite being strong club-history badges.
- Economy Controller has a dedicated summary, but if a player also has Star Bowler, Partnership Breaker, or Wicket Taker, the bowling-threat summary appears first.
- Keeper Impact can appear for a player with fewer than 20 matches because it only requires stumpings > 0.
- Quick Scorer uses reliable recent Bat SR, but still requires career runs >= 250 and matches >= 20, so a player with strong recent scoring tempo but fewer career runs will not receive it.
