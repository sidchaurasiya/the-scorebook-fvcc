# Three-Club Weekly Refresh and Release Handover

Updated: 14 November 2026 (Australia/Melbourne)

This is the operational handover for future GRDCC, Glen Waverley Hawks, and FVCC refreshes. It describes the verified local baseline and existing refresh entry points. It does not authorize a new refresh, publication, push, merge to main, or deployment.

## Verified integration baseline

- Repository: **sidchaurasiya/the-scorebook-fvcc**.
- Local integration branch: **integration/three-club-release-2026-11-11**.
- Application and data acceptance commit: **41c565b26876ca10e260c478d0098eacffaf66fd**.
- Authenticated rollback baseline: **7c893f19328f29c92743b8ac2ee66652ce93670f**.
- Approved source commits: clean GRDCC reconstruction **f966ab3f53d658c972bebe54d22f59d3d707d476**, Hawks **09bebc7f78e6e161a4802193d6d9efce7f74775a**, and FVCC **7386e4f4a36ee70d7f95e0529f19a31308b1fb0c**.
- The GRDCC reconstruction and all three candidates descend from the rollback. Rejected commits f525fc4, d7eaa15, 7f6d483, and f0695cf are excluded from integration ancestry.
- Local main, origin/main, and GitHub main were verified at the rollback SHA. No production action was performed.

After this handover is committed, the exact branch tip including documentation is recorded in the restricted final acceptance receipt. Use that receipt to identify the current accepted candidate SHA; do not rely on a branch name alone.

## Application and data locations

The shared Streamlit application is **app.py**. **app_grdcc.py** and **app_gwhcc.py** select their club before importing the shared app. Each club also has a streamlit_entrypoint in its config.

| Club | Config | Public processed data | Match Centre source paths |
|---|---|---|---|
| GRDCC | clubs/georges-river-district/club_config.yaml | clubs/georges-river-district/data/processed/ | data/raw/match_centre/georges-river-district/; data/processed/match_centre/georges-river-district/ |
| Hawks | clubs/glen-waverley-hawks/club_config.yaml | clubs/glen-waverley-hawks/data/processed/ | data/raw/match_centre/glen-waverley-hawks/; data/processed/match_centre/glen-waverley-hawks/ |
| FVCC | clubs/fvcc/club_config.yaml | clubs/fvcc/data/processed/ | data/raw/match_centre/; data/processed/match_centre/ |

GRDCC and Hawks disable legacy processed-data fallback. FVCC permits fallback for offline-builder compatibility; the accepted serving files were verified to resolve from FVCC's own club tree. Keep the legacy root data unchanged unless the selected club adapter explicitly requires a candidate-scoped source there. Never use the legacy-output flag for a club refresh.

Club IDs are **georges-river-district**, **glen-waverley-hawks**, and **fvcc**. Always pass the ID explicitly. Do not infer a club from the application default or from a stale URL.

## Source authority and accepted rules

### Rules shared by all clubs

- Official PlayCricket scorecards govern match results, team and innings totals, batting and bowling figures, wickets, fielding contributions, appearances, and match summaries.
- Verified original delivery events govern ball-by-ball strike rates, fastest batting milestones, delivery-derived insights, and ball-by-ball partnerships. Display strike rates as runs per 100 balls, without a percent sign, and identify ball-by-ball provenance where those figures are shown.
- Keep source values and provenance when scorecard and delivery arithmetic differs. Do not create balancing deliveries, assign unexplained runs to players, or force equality between sources.
- Reconcile source matches, teams, innings, and participants with exact identifiers. Names alone do not prove identity.
- Current verified privacy status governs both historical and current public visibility. Resolve the exact participant first. A current-private player remains masked in all derived public outputs; a current-public player may appear only after exact identity verification.
- Repeated masked placeholders are not person-unique identities. Keep ambiguous records generic and unlinked. Never transfer one club's privacy classification or identity mapping to another club.

### GRDCC

- The 2024/25 Annual Report cumulative ALL GRADES baselines govern accepted career totals, including 98 verified baseline equations. Competition-specific subtotals do not replace full-career totals.
- Mark Burgess has 225 approved official career runs. His 177 Frank Gray Shield runs are a competition subtotal; the processed 48 runs already included in 225 are not added again.
- Percy Eldridge has 2,208 official runs and 184 recorded incomplete-coverage wickets. Phil Eldridge remains a separate report-only profile with 227 report-backed wickets; unsupported career metrics stay unavailable.
- Other verified anchors include Nick Condylios (3,539 runs), Ryan Croom (6,186), Daniel Yates (491 wickets), Gavin Scott (7,395 runs and 497 wickets), and Ali Ali (2,213 runs and 332 wickets).
- Preserve the other verified report anchors: Bruce Carrington 3,524 runs, Peter Huthnance 3,240, Ian Fleming 2,558, Eric Reid 3,790, and Gordon Parsons 2,599. The two Bruce Carrington rows remain separate exact identities; do not merge by name.
- The accepted partnership snapshot is 2,464 historical plus 239 current-season events through 31 October 2026, 2,703 total. The accepted six-run, six-ball event remains source-as-recorded: official innings 116 and delivery reconstruction 117. Its private partner remains masked and unlinked.
- The accepted population is 2,125 canonical identities and 2,128 display records, including three report-only entries.
- Refresh the GRDCC exact-ID privacy snapshot from current official source evidence. Its signature is part of cache invalidation. Do not replace the accepted 31 October cutoff during a handover or integration-only task.

### Glen Waverley Hawks

- The accepted snapshot has 57 eligible matches: 53 completed and four abandoned with verified play. Ten terminal no-play fixtures are excluded.
- Match appearances use 0.5 for T20 and 1.0 for other played matches. Abandoned fixtures count only when verified play exists; no-play fixtures count zero.
- The accepted population has 1,295 public profiles and three new source-ID profiles. Preserve exact-ID display aliases, including “Lincoln Martin”.
- Preserve selected career anchors: Chris Briginshaw 392.5 matches, 7,055 runs, 35 wickets; Matthew Briginshaw 300 matches, 2,430 runs, 538 wickets; Noel Blacker 108 matches with the documented 106/107 historical issue; Mujib Timori 25.5 matches; Jarrod Greaves 170 matches; Akshath Mantripragada 45.5; Sundara Moorthi 4; Yojit Sardana 9; Cameron Stow 4; Jordin Dias 11; and Nathan Bungey 341.
- Preserve approved source-as-recorded exceptions: D Grade official total 106 versus component sum 111; U12 C Grade official 171 and a 53-run win with 21 unallocated; Lincoln Martin official 42 from 40 versus delivery evidence 43 from 41; format-specific Super 7s dismissal/retirement rules; and corrected Jordin Dias DNB handling.
- The accepted partnership output has 3,643 events. The accepted fastest-milestone output has 831 rows: 780 historical plus 51 current through its approved source snapshot.

### Fiji Victorian Cricket Club

- The accepted snapshot has 16 eligible completed Summer matches, including four newly eligible matches from 7 November 2026.
- The accepted public population has 298 profiles, 9,800 career appearances, 127,792 runs, 6,833 wickets, and 3,684 catches.
- Accepted achievement totals are 998 partnerships, 66 verified fastest 50s, two fastest 100s, and zero confirmed hat-tricks. Arun Sevugan is the verified new public identity.
- Preserve all 669 authentic restored deliveries. Accepted scorecard/delivery innings totals are Fourth XI 115/113, Third XI opponent 146/145, and Third XI FVCC 148/149. No synthetic adjustments or arithmetic-based quarantines are permitted solely to close these differences.
- FVCC has separately governed eligibility and career rules. Do not copy the Hawks appearance policy or GRDCC career baselines into FVCC.

### Current historical-coverage limits

The recovered authenticated archive establishes the tested snapshots, not exhaustive history. GRDCC match coverage in the recovered historical source begins at Summer 2002/03; delivery coverage is sparse for both GRDCC and FVCC. Preserve these coverage limits in reports. A missing delivery or innings record is not proof that a player did not participate.

## Controlled weekly workflow

Run a weekly refresh only after a separate explicit instruction names the baseline, date cutoffs, and clubs. Work in a new isolated candidate worktree from the accepted integration SHA. Keep each club's source bundle, candidate outputs, and report separate so a failure in one club does not contaminate the others.

1. Record the accepted integration SHA, clean worktree status, source cutoffs, and backup location. Do not update an existing approved branch or worktree.
2. For each club, identify the active season, participating teams, and exact official season/team IDs. Record the local cutoff and retrieval time in Australia/Melbourne.
3. Retrieve finalized official scorecards and preserve raw responses, retrieval metadata, source IDs, and SHA-256 receipts. Re-fetch or replace an existing match when its finalized source changes; do not process only unseen IDs.
4. Keep unplayed fixtures out. Apply only the selected club's existing eligibility code and tests. Do not transfer Hawks' abandoned-with-play or T20 rules to the other clubs.
5. Reconcile each match, innings, team, and player using exact source identifiers. Check duplicate match IDs, participant mapping changes, scorecard corrections, and event uniqueness before building public outputs.
6. Recheck current public/private status from official source evidence. Record public/private transitions by exact club and player ID in restricted evidence. Rebuild every affected public artifact and cache signature. Do not infer registration or payment circumstances.
7. Rebuild scorecard-derived career and match statistics separately from delivery-derived statistics. Preserve historical career-source authority, approved baselines, and original historical rows. Confirm that corrections replace earlier versions idempotently and do not double-count.
8. Build the club candidate from its frozen source snapshot. Keep candidate roots outside the integration worktree until each club's source and output audit passes.
9. Rebuild Hall of Fame, Season Overview, Milestones, Player Profile, prepared data, and fallback data using the verified club-aware export path. Confirm club configuration, per-club file resolution, data-version signatures, and privacy-aware cache invalidation.
10. Run focused source reconciliation, then the full test selections below. Do not convert skipped tests into a pass; mount their pinned source archive or record the exact blocker.
11. Run two isolated builds with the same source bundle and configuration. Compare file lists and SHA-256 hashes, explain version markers that are intentionally finalized later, and compare prepared/fallback outputs.
12. Run real Chrome desktop and mobile checks for all four pages and all three clubs. Test cold and warm navigation, exact player search, masked records, source links, and console/page errors.
13. Produce a per-club and combined change report. Review the public artifact and Git path manifests for private identifiers, restricted receipts, stale links, root fallbacks, and cross-club changes.
14. Commit only after acceptance. Keep the candidate local until separate owner release approval. Do not push, merge to main, deploy, clear production caches, or enable scheduled refreshes from this procedure.

### Verified refresh entry points

The commands below were verified in dry-run mode for each club on 14 November 2026. Dry runs made no network requests and wrote no files:

~~~sh
rtk /Users/preetkaur/CodexLocal/.venv-app/bin/python scripts/refresh_data.py --club georges-river-district --dry-run
rtk /Users/preetkaur/CodexLocal/.venv-app/bin/python scripts/refresh_club_outputs.py --club georges-river-district --dry-run
rtk /Users/preetkaur/CodexLocal/.venv-app/bin/python scripts/refresh_data.py --club glen-waverley-hawks --dry-run
rtk /Users/preetkaur/CodexLocal/.venv-app/bin/python scripts/refresh_club_outputs.py --club glen-waverley-hawks --dry-run
rtk /Users/preetkaur/CodexLocal/.venv-app/bin/python scripts/refresh_data.py --club fvcc --dry-run
rtk /Users/preetkaur/CodexLocal/.venv-app/bin/python scripts/refresh_club_outputs.py --club fvcc --dry-run
~~~

**scripts/refresh_data.py --club ID** performs an external PlayCricket aggregate refresh and writes to the selected club's processed tree by default. It also uses shared raw/cache roots. It is not a frozen-source candidate builder. Do not run it in the shared accepted checkout; first create a protected candidate and inventory all changed paths. The force-all flag is not a weekly option. The with-current-match-centre flag invokes an optional current-scope refresh; use it only after season/team IDs, cutoff, source bundle, and output scope have been verified for that club.

**scripts/refresh_club_outputs.py --club ID** rebuilds deploy-safe summaries from existing local inputs and makes no external fetch. Use it only in the isolated candidate after the input tables are reconciled. Its dry-run prints the current sequence, including the match-centre commands and output roots.

Two offline candidate builders are available:

- Hawks: **scripts/build_gwhcc_weekly_candidate.py** requires **--source-bundle**, **--candidate-root**, **--historical-ref**, and **--cutoff**. It requires a new candidate directory outside the repository and performs no network fetch or publication.
- FVCC: **scripts/build_fvcc_incremental_refresh.py** requires **--source-bundle** and **--candidate-root**; **--baseline-root** is optional. It builds from a frozen bundle and retains historical rows.
- GRDCC has no single verified weekly candidate builder. Preserve its report-baseline and exact-ID privacy governance, and inspect every generated path from the selected existing refresh/export steps. Do not invent a GRDCC refresh command or use a Hawks/FVCC builder as a substitute.

For all three clubs, dry-run is an inventory aid, not evidence that source retrieval, match eligibility, or resulting statistics are correct.

## Required source receipt and weekly report

Keep source evidence restricted. For each club, record:

| Area | Required fields |
|---|---|
| Source snapshot | Retrieval time and timezone, cutoff, official source URL/ID, file list, row counts, SHA-256 hashes, parser/build version |
| Matches | New, corrected, abandoned, excluded, and no-play fixtures; exact match IDs; replacement/idempotency result |
| Players | New or changed exact IDs, mapping decisions, current privacy status, public/private transitions |
| Career statistics | Before/after values, governing source, baseline or later overlay, reconciliation and missing coverage |
| Achievements | Partnership and milestone deltas, source event IDs, eligibility, privacy |
| Exceptions | Official scorecard value, delivery reconstruction, difference, source receipt, disposition |
| Privacy | Exact-ID lookup, source timestamp/hash, prepared and fallback scans, public artifact scans, cache signature |
| Validation | Commands, pass/fail/skip counts, deterministic hashes, parity, browser results |
| Git | Parent, candidate SHA, changed-file manifest, source manifest, clean-worktree result |
| Release | Readiness decision, limitations, reviewer, separate owner approval status |

Do not include credentials, private source payloads, or raw private participant IDs in tracked docs, public outputs, or logs. Store the exact record-level privacy register and raw receipts under the restricted checkpoint.

## Required regression and serving checks

Use the pinned historical archive and current-season GRDCC snapshot for archive-backed integration tests. The verified 14 November paths were:

- Historical root: **/Users/preetkaur/CodexArchiveRecovery-2026-11-10/data/processed/match_centre**.
- GRDCC current-season snapshot through 31 October 2026: **/Users/preetkaur/Documents/Codex/checkpoints/grdcc-archive-policy-audit-2026-11-10/current-season-snapshots/grdcc-summer-2026-27-finalized**.

The historical test fixture verifies source hashes and row counts before building. For a later weekly snapshot, use that snapshot's own verified root and receipt; do not reuse the October cutoff as a new source.

Run these selections from the integration worktree:

~~~sh
rtk proxy env SCOREBOOK_MATCH_CENTRE_ROOT=/Users/preetkaur/CodexArchiveRecovery-2026-11-10/data/processed/match_centre SCOREBOOK_GRDCC_CURRENT_MATCH_CENTRE_ROOT=/Users/preetkaur/Documents/Codex/checkpoints/grdcc-archive-policy-audit-2026-11-10/current-season-snapshots/grdcc-summer-2026-27-finalized /Users/preetkaur/CodexLocal/.venv-app/bin/python -m pytest -q -rs tests/test_grdcc*.py tests/test_fastest_innings_governance.py tests/test_fvcc_grdcc_partnerships.py tests/test_fvcc_grdcc_hat_tricks.py tests/test_fvcc_hof_public_filtering.py tests/test_match_centre_milestones.py tests/test_gwhcc_targeted_ui.py tests/test_shared_club_layout_regressions.py
rtk /Users/preetkaur/CodexLocal/.venv-app/bin/python -m pytest -q -rs tests/test_gwhcc*.py
rtk proxy env SCOREBOOK_MATCH_CENTRE_ROOT=/Users/preetkaur/CodexArchiveRecovery-2026-11-10/data/processed/match_centre SCOREBOOK_GRDCC_CURRENT_MATCH_CENTRE_ROOT=/Users/preetkaur/Documents/Codex/checkpoints/grdcc-archive-policy-audit-2026-11-10/current-season-snapshots/grdcc-summer-2026-27-finalized /Users/preetkaur/CodexLocal/.venv-app/bin/python -m pytest -q -rs tests/test_fvcc*.py tests/test_hat_tricks.py tests/test_not_outs_visibility.py
rtk /Users/preetkaur/CodexLocal/.venv-app/bin/python -m pytest -q tests/test_multi_club_onboarding.py tests/test_release_version_tracking.py
~~~

The acceptance run on the application/data baseline passed 362 GRDCC/shared tests, 382 Hawks tests, 167 FVCC tests, and 14 multi-club/version tests; none were skipped after the verified archive roots were supplied. The two archive-focused files passed 21 tests. See the restricted final acceptance receipt for timestamps and exact commands.

Also verify:

- All six authenticated historical archive integrations and current GRDCC cutoff tests run without skips.
- Prepared and fallback profiles agree for the complete public population in each club.
- Current-private names and identifiers do not appear in public artifacts, generated diagnostics, search, profiles, partnerships, milestones, scorecard links, or cached outputs.
- Data-version and cache signatures change when source or privacy input changes.
- Each serving file resolves from the selected club tree; FVCC fallback remains compatibility-only.
- All source exception receipts are retained; never assert universal scorecard/delivery arithmetic equality.

## Chrome acceptance

Use installed Chrome through the supported Playwright runner in the restricted checkpoint. The integrated acceptance runner and screenshots are stored at:

The candidate-specific browser runner, machine-readable receipt, and screenshots are stored in the restricted checkpoint under names derived from the exact tested SHA. Keep older acceptance evidence; do not replace it with screenshots from a different candidate.

Capture four active pages (Hall of Fame, Season Overview, Milestones, Player Profile) for all three clubs at 1440×1000 and 390×844. Test both cold and warm navigation, search, exact profile links, representative current and historical records, privacy-safe masked rows, valid scorecard links, no horizontal overflow, and no console/page exceptions. Confirm the served data version and exact selected club before saving each screenshot. Save the machine-readable result, hashes, and screenshots under a new restricted directory named for the accepted candidate SHA; do not reuse candidate-specific screenshots as evidence for a different application/data build.

Representative searches: GRDCC Mark Burgess, Percy Eldridge, and Phil Eldridge; Hawks Chris Briginshaw, Matthew Briginshaw, and Lincoln Martin; FVCC Arun Sevugan and one accepted historical profile. Include a masked partnership and Hawks fastest-milestone rows where source placeholders remain unresolved.

## Deterministic builds, backups, and rollback

- Pin source bundles and configuration before building. Run each club build twice in separate empty output roots. Compare complete relative file lists and SHA-256 hashes; explain any final version marker separately.
- Preserve the input receipt, the two build manifests, prepared/fallback parity output, privacy snapshot signature, and changed-file manifest in the restricted checkpoint.
- Never overwrite a candidate output in place. Keep the original approved inputs and each club's candidate directory until the combined acceptance is reviewed.
- For a local rollback, create a fresh worktree at the exact last accepted integration SHA or the authenticated rollback SHA. Keep main and existing worktrees untouched. The rollback baseline for this integration is **7c893f19328f29c92743b8ac2ee66652ce93670f**.
- No production state changed during this integration. Before any separately approved deployment, record the currently deployed SHA for each app. If release smoke checks fail, restore that exact previously deployed SHA through the approved hosting workflow; do not clear caches or change production data as a troubleshooting shortcut.

## Deployment handover

The repository's **STREAMLIT_DEPLOYMENT.md** documents Streamlit Community Cloud, Python 3.12, repository **sidchaurasiya/the-scorebook-fvcc**, branch **main**, and **app_gwhcc.py** for Hawks. Club configs identify **app_grdcc.py** for GRDCC, **app_gwhcc.py** for Hawks, and **app.py** for FVCC.

The actual hosted project settings for GRDCC and FVCC were not inspected during this local-only task. Before owner production approval, verify each app's hosting project, branch, entrypoint, Python version, club context, and deployed build SHA. Do not assume the Hawks Cloud settings apply to the other clubs. After a separately approved release, run the full desktop/mobile browser checklist against each live app and record the deployed SHA and rollback target. This procedure itself does not push, merge, or deploy.

## Restricted evidence

The restricted integration checkpoint is:

**/Users/preetkaur/Documents/Codex/checkpoints/three-club-integration-2026-11-11/restricted/**

Key records include the final acceptance receipt, source manifest, ancestry and changed-file manifests, GRDCC reconstruction provenance, Hawks assertion reconciliation, placeholder source-context register, prepared/fallback receipts, and integrated Chrome screenshots. Keep them outside public application output and Git.

The exact updated release classification, branch tip, source hashes, test outputs, screenshots, and remaining source/deployment limitations are in **final_acceptance_receipt_2026-11-14.json**.
