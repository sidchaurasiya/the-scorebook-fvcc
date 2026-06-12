# GRDCC Most Premierships Scorecard Update

## Purpose

The GRDCC Hall of Fame Most Premierships list is calculated from explicit player participation in accepted premiership scorecards. It does not infer participation from season squads, aggregates or player profiles.

## Evidence Rule

- The Annual Report establishes that GRDCC won the premiership.
- A player is counted only when listed for the GRDCC team in the associated PlayCricket scorecard evidence.
- Existing verified finals use the scorecard participant export.
- Additional linked wins use the captured PlayCricket Summary team list.
- Captain markers such as `(c)` are retained as role evidence but removed from display names.
- Annual Report-only wins without a scorecard player list are not counted.

## Coverage

- Premiership matches with player lists: 16
- Annual Report-only wins excluded due to no player list: 6
- Unique player-match participation rows: 187
- Players in the calculated leaderboard: 116
- Duplicate player-match rows: 0
- Current leader: Curtis Cheney, 6 confirmed scorecard premiership appearances

Five accepted supporting rows use the current Premiership Wins `last_available_match` context. They remain explicitly identified by `match_context` in the participation audit and should not be interpreted as independently verified grand finals.

## App Behaviour

Only GRDCC replaces the legacy player-premiership export with the calculated scorecard participation file. The card shows player name, confirmed count, and compact season/grade evidence. Other clubs retain their existing data path.

## Caveats

The result reflects available and accepted scorecard player lists, not every historical GRDCC premiership. Future confirmed scorecards can expand the calculation without crediting unsupported historical participation.
