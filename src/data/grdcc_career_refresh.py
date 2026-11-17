"""Preserve governed career baselines while adding later official season totals."""
from functools import lru_cache

import pandas as pd

from src.config.club_config import REPO_ROOT, get_processed_path

CLUB = 'georges-river-district'
BASELINE_PATH = REPO_ROOT / 'clubs' / CLUB / 'data/source/career_refresh_baselines.csv'
METRICS = {
    'batting': {'Runs': 'battingAggregate', 'Innings': 'battingInnings', 'Matches': 'matches',
                'Not Outs': 'battingNotOuts', '50s': 'batting50s', '100s': 'batting100s'},
    'bowling': {'Wickets': 'bowlingWickets', 'Maidens': 'bowlingMaidens', 'Balls Bowled': 'bowlingBalls'},
    'fielding': {'Catches': 'fieldingTotalCatches', 'Stumpings': 'fieldingStumpings', 'Run Outs': 'fieldingRunOuts'},
}


def refresh_baseline_paths():
    return [BASELINE_PATH, reviewed_corrections_path(), report_baselines_path(), report_identity_path(),
            reviewed_report_identity_path(),
            BASELINE_PATH.with_name('summary_identity_namespace_aliases.csv'),
            reviewed_playcricket_career_exceptions_path()]


def reviewed_playcricket_career_exceptions_path():
    return BASELINE_PATH.with_name('reviewed_playcricket_career_exceptions.csv')


def _valid_sha256(value):
    return len(str(value or '').strip()) == 64 and all(
        char in '0123456789abcdef' for char in str(value or '').strip().casefold()
    )


@lru_cache(maxsize=4)
def _reviewed_playcricket_career_exceptions(signature):
    if not signature:
        return pd.DataFrame()
    path = reviewed_playcricket_career_exceptions_path()
    rows = pd.read_csv(path, dtype=str).fillna('')
    required = {
        'canonical_player_id', 'source_participant_id', 'player_name', 'metric',
        'governed_value', 'scope_type', 'club_filter', 'competition_filter',
        'match_format_filter', 'profile_all_clubs_value', 'profile_grdcc_value',
        'profile_seasons', 'historical_excel_value', 'processed_runs_same_scope',
        'processed_runs_included_in_profile', 'annual_report_subset_value',
        'annual_report_subset_scope', 'profile_later_performances_included',
        'eligible_post_cutoff_rows', 'through_season_start', 'status',
        'source_reference', 'source_profile_body_sha256', 'source_receipt_sha256',
        'excel_workbook_sha256', 'processed_source_sha256',
        'annual_report_decisions_sha256', 'owner_approval_reference', 'source_note',
    }
    if not required.issubset(rows.columns):
        raise ValueError('Reviewed PlayCricket career exception ledger is incomplete')
    rows = rows.loc[rows.status.eq('source_verified')].copy()
    if rows.duplicated(['canonical_player_id', 'metric']).any():
        raise ValueError('Duplicate exact-ID PlayCricket career exception')
    for row in rows.itertuples(index=False):
        participant_id = str(row.source_participant_id).strip()
        expected_canonical = f"raw_{participant_id.replace('-', '_')}"
        if str(row.canonical_player_id).strip() != expected_canonical:
            raise ValueError('PlayCricket career exception canonical ID does not match its exact participant ID')
        if str(row.metric).strip() != 'Runs' or str(row.scope_type).strip() != 'exact_playcricket_club_career_total':
            raise ValueError('Unsupported metric or scope in PlayCricket career exception')
        if str(row.club_filter).strip() != 'Georges River Cricket Club':
            raise ValueError('PlayCricket career exception is not scoped to GRDCC')
        if str(row.competition_filter).strip() != 'All Competitions' or str(row.match_format_filter).strip() != 'All formats':
            raise ValueError('PlayCricket career exception must use the reviewed all-competition, all-format scope')
        if int(float(row.through_season_start)) != 2024:
            raise ValueError('PlayCricket career exception must use the reviewed historical cutoff')
        governed = pd.to_numeric(pd.Series([row.governed_value]), errors='coerce').iloc[0]
        club_value = pd.to_numeric(pd.Series([row.profile_grdcc_value]), errors='coerce').iloc[0]
        all_clubs_value = pd.to_numeric(pd.Series([row.profile_all_clubs_value]), errors='coerce').iloc[0]
        excel_value = pd.to_numeric(pd.Series([row.historical_excel_value]), errors='coerce').iloc[0]
        processed_value = pd.to_numeric(pd.Series([row.processed_runs_same_scope]), errors='coerce').iloc[0]
        subset_value = pd.to_numeric(pd.Series([row.annual_report_subset_value]), errors='coerce').iloc[0]
        excel_season_values = pd.to_numeric(
            pd.Series(str(row.historical_excel_season_runs).split(';')), errors='coerce'
        )
        if any(pd.isna(value) for value in (
            governed, club_value, all_clubs_value, excel_value, processed_value, subset_value
        )) or excel_season_values.isna().any():
            raise ValueError('PlayCricket career exception contains an invalid governed value')
        if len({float(governed), float(club_value), float(all_clubs_value), float(excel_value)}) != 1:
            raise ValueError('PlayCricket career total, GRDCC scope, all-club view, and Excel cross-check disagree')
        if float(excel_season_values.sum()) != float(excel_value):
            raise ValueError('PlayCricket career exception Excel season rows do not reconcile')
        if str(row.processed_runs_included_in_profile).strip().casefold() != 'yes':
            raise ValueError('Processed pre-cutoff runs must be explicitly marked as included, not additive')
        if float(processed_value) < 0 or float(subset_value) < 0:
            raise ValueError('Non-additive source comparisons cannot be negative')
        if int(float(row.profile_later_performances_included)) != 0 or int(float(row.eligible_post_cutoff_rows)) != 0:
            raise ValueError('The verified profile includes unreviewed later-season performances')
        if not str(row.owner_approval_reference).strip() or participant_id not in str(row.source_reference):
            raise ValueError('PlayCricket career exception lacks its exact source and owner approval')
        for column in (
            'source_profile_body_sha256', 'source_receipt_sha256', 'excel_workbook_sha256',
            'processed_source_sha256', 'annual_report_decisions_sha256',
        ):
            if not _valid_sha256(getattr(row, column)):
                raise ValueError(f'Invalid source fingerprint in PlayCricket career exception: {column}')
    rows['governed_value'] = pd.to_numeric(rows.governed_value, errors='raise')
    rows['through_season_start'] = pd.to_numeric(rows.through_season_start, errors='raise').astype(int)
    return rows.reset_index(drop=True)


def load_reviewed_playcricket_career_exceptions(club_id=None):
    if str(club_id or '').strip().casefold() not in {'', CLUB}:
        return pd.DataFrame()
    path = reviewed_playcricket_career_exceptions_path()
    if not path.exists():
        return pd.DataFrame()
    stat = path.stat()
    return _reviewed_playcricket_career_exceptions((str(path), stat.st_mtime_ns, stat.st_size)).copy()



def mask_unapproved_playcricket_exception_metrics(frame, club_id):
    """Keep exact-ID reviewed exceptions free of unsupported prepared metrics."""
    if str(club_id or "").strip().casefold() != CLUB or frame.empty or "canonical_player_id" not in frame:
        return frame
    exceptions = load_reviewed_playcricket_career_exceptions(club_id)
    if exceptions.empty:
        return frame
    from src.data.grdcc_career_quarantine import CAREER_COLUMNS, REVIEW_FLAG
    from src.data.grdcc_historical_records import SOURCE_NOTE

    output = frame.copy()
    for exception in exceptions.itertuples(index=False):
        selected = output.canonical_player_id.fillna("").astype(str).eq(str(exception.canonical_player_id))
        if int(selected.sum()) > 1:
            raise ValueError("PlayCricket career exception requires one exact canonical row")
        if not selected.any():
            continue
        metric_columns = set(CAREER_COLUMNS).union(
            column for column in output.columns
            if column.startswith(("batting", "bowling", "fielding", "ballByBall"))
        )
        for column in metric_columns.intersection(output.columns):
            if output[column].dtype == bool:
                output[column] = output[column].astype(object)
            output.loc[selected, column] = float("nan")
        if REVIEW_FLAG in output:
            output.loc[selected, REVIEW_FLAG] = True
        for column in ["Matches Source", "Matches Proxy", "Featured Record Source", "Featured Record Metric", "Featured Record Source Note"]:
            if column in output:
                output.loc[selected, column] = ""
        if "Featured Record Override" in output:
            output.loc[selected, "Featured Record Override"] = False
        if SOURCE_NOTE in output:
            output.loc[selected, SOURCE_NOTE] = str(exception.source_note)
    return output

def apply_reviewed_playcricket_career_exceptions(frame, club_id, *, later_source=None):
    """Apply only exact, source-verified metric exceptions on a career summary."""
    if str(club_id or '').strip().casefold() != CLUB or frame.empty or 'canonical_player_id' not in frame:
        return frame
    exceptions = load_reviewed_playcricket_career_exceptions(club_id)
    if exceptions.empty:
        return frame
    from src.data.grdcc_career_quarantine import CAREER_COLUMNS, REVIEW_FLAG
    from src.data.grdcc_historical_records import SOURCE_NOTE

    source = later_source if later_source is not None else public_career_source('batting')
    output = frame.copy()
    for exception in exceptions.itertuples(index=False):
        selected = output.canonical_player_id.fillna('').astype(str).eq(str(exception.canonical_player_id))
        if int(selected.sum()) == 0:
            continue
        if int(selected.sum()) != 1:
            raise ValueError('PlayCricket career exception requires one exact canonical career row')
        if source.empty or not {'canonical_player_id', 'battingAggregate', 'season'}.issubset(source.columns):
            player_rows = pd.DataFrame()
            later_rows = pd.DataFrame()
        else:
            source_years = pd.to_numeric(
                source.season.astype(str).str.extract(r'(\d{4})')[0], errors='coerce'
            )
            player_rows = source.loc[
                source.canonical_player_id.astype(str).eq(str(exception.canonical_player_id))
            ].copy()
            player_years = source_years.loc[player_rows.index]
            if player_years.isna().any():
                raise ValueError('PlayCricket career exception source contains an unclassified season')
            historical_rows = player_rows.loc[player_years.le(int(exception.through_season_start))]
            later_rows = player_rows.loc[player_years.gt(int(exception.through_season_start))]
            if not historical_rows.empty:
                historical_runs = pd.to_numeric(historical_rows.battingAggregate, errors='coerce')
                if historical_runs.isna().any() or historical_runs.lt(0).any():
                    raise ValueError('Pre-cutoff PlayCricket runs are incomplete for the reviewed exception')
                if float(historical_runs.sum()) != float(exception.processed_runs_same_scope):
                    raise ValueError('Pre-cutoff PlayCricket rows changed since the career exception review')
                observed_seasons = set(historical_rows.season.astype(str).str.strip())
                reviewed_seasons = {
                    part.strip() for part in str(exception.profile_seasons).split(';') if part.strip()
                }
                if observed_seasons != reviewed_seasons:
                    raise ValueError('Pre-cutoff PlayCricket season scope changed since the career exception review')
        if later_rows.empty:
            later_runs = 0.0
        else:
            later_values = pd.to_numeric(later_rows.battingAggregate, errors='coerce')
            if later_values.isna().any() or later_values.lt(0).any():
                raise ValueError('Eligible later PlayCricket runs are incomplete for the reviewed exception')
            later_runs = float(later_values.sum())

        output.loc[selected, 'Runs'] = float(exception.governed_value) + later_runs
        metric_columns = set(CAREER_COLUMNS).union(
            column for column in output.columns
            if column.startswith(('batting', 'bowling', 'fielding', 'ballByBall'))
        ) - {'Runs'}
        for column in metric_columns.intersection(output.columns):
            if output[column].dtype == bool:
                output[column] = output[column].astype(object)
            output.loc[selected, column] = float('nan')
        seasons = [part.strip() for part in str(exception.profile_seasons).split(';') if part.strip()]
        for column, value in (
            ('Seasons Played', len(seasons)),
            ('Debut Season', seasons[0] if seasons else ''),
            ('Latest Season', seasons[-1] if seasons else ''),
            ('Career Span', f'{seasons[0]} - {seasons[-1]}' if seasons else ''),
            ('Seasons', ', '.join(seasons)),
            ('Teams/Grades', ''),
            ('Grades Played', ''),
            (REVIEW_FLAG, True),
            (SOURCE_NOTE, str(exception.source_note)),
            ('Historical Source Scope', str(exception.source_note)),
            ('Reviewed Career Metric', 'Runs'),
            ('Reviewed Career Source URL', str(exception.source_reference)),
            ('Featured Record Source', 'Official PlayCricket career profile (GRDCC filter)'),
            ('Featured Record Metric', 'Runs'),
            ('Featured Record Source Note', str(exception.source_note)),
        ):
            if column == 'Seasons Played' and column not in output.columns:
                continue
            output.loc[selected, column] = value
        for column in ('Matches Source', 'Matches Proxy'):
            if column in output:
                output.loc[selected, column] = ''
        if 'Featured Record Override' in output:
            output.loc[selected, 'Featured Record Override'] = False
    return output


def report_identity_path():
    return BASELINE_PATH.with_name('annual_report_player_identity_governance.csv')


def reviewed_report_identity_path():
    return BASELINE_PATH.with_name('reviewed_annual_report_identity_targets.csv')


def report_baselines_path():
    return BASELINE_PATH.with_name('reviewed_annual_report_baselines.csv')


def apply_report_baselines(baseline, reports, identity_governance=None):
    """Replace compatible exact-ID seeds at the owner's report/PlayCricket boundary."""
    output = baseline.copy()
    output['report_applied'] = False
    if reports.empty:
        return output
    approved = reports.loc[reports.status.eq('source_verified')].copy()
    if approved.duplicated(['canonical_player_id', 'metric']).any():
        raise ValueError('Duplicate authoritative report baseline')
    verified = set()
    if identity_governance is not None and not identity_governance.empty:
        for row in identity_governance.loc[identity_governance.status.eq('MATCHED_EXISTING_CANONICAL_PLAYER')].itertuples():
            verified.add((row.canonical_player_id, str(row.report_name).strip().casefold()))
    for row in approved.itertuples():
        if row.scope_type != 'all_grades_cumulative' or row.through_season_start != 2024:
            raise ValueError('Incompatible report scope or season boundary')
        if row.metric not in {metric for metrics in METRICS.values() for metric in metrics}:
            raise ValueError('Unsupported additive report metric')
        selected = output.canonical_player_id.eq(row.canonical_player_id) & output.metric.eq(row.metric)
        if selected.sum() == 0 and (row.canonical_player_id, str(getattr(row, 'player_name', '')).strip().casefold()) in verified:
            addition = {'canonical_player_id':row.canonical_player_id, 'metric':row.metric,
                        'through_season_start':2024, 'governed_value':float(row.governed_value),
                        'correction_applied':True, 'report_applied':True}
            output = pd.concat([output, pd.DataFrame([addition])], ignore_index=True)
            selected = output.canonical_player_id.eq(row.canonical_player_id) & output.metric.eq(row.metric)
        if selected.sum() != 1:
            raise ValueError('Report baseline requires one approved canonical seed')
        output.loc[selected, 'governed_value'] = float(row.governed_value)
        output.loc[selected, 'through_season_start'] = 2024
        if 'through_season' in output:
            output.loc[selected, 'through_season'] = 'Summer 2024/25'
        output.loc[selected, 'correction_applied'] = True
        output.loc[selected, 'report_applied'] = True
    return output


def _complete_counter(frame, column):
    if frame.empty or column not in frame:
        return None
    values = pd.to_numeric(frame[column], errors='coerce')
    return float(values.sum()) if values.notna().all() and values.ge(0).all() else None


def _report_rates(source, years, anchor, category, field):
    """A report total alone cannot establish missing career rate denominators."""
    player = source.loc[source.canonical_player_id.eq(anchor.canonical_player_id)]
    historical = source.loc[source.canonical_player_id.eq(anchor.canonical_player_id) & years.le(2024)]
    covered = _complete_counter(historical, field) == float(anchor.governed_value)
    def ratio(numerator, denominator, scale=1):
        return numerator * scale / denominator if covered and numerator is not None and denominator is not None and denominator > 0 else float('nan')
    if category == 'batting' and anchor.metric == 'Runs':
        innings = _complete_counter(player, 'battingInnings')
        not_outs = _complete_counter(player, 'battingNotOuts')
        outs = innings - not_outs if innings is not None and not_outs is not None and innings >= not_outs else None
        return {'Bat Avg': ratio(float(anchor.updated_value), outs)}, covered
    if category == 'bowling' and anchor.metric == 'Wickets':
        conceded = _complete_counter(player, 'bowlingRuns')
        balls = _complete_counter(player, 'bowlingBalls')
        wickets = float(anchor.updated_value)
        return {'Bowl Avg': ratio(conceded, wickets), 'Bowl SR': ratio(balls, wickets), 'Econ': ratio(conceded, balls, 6)}, covered
    return {}, covered


def reviewed_corrections_path():
    return BASELINE_PATH.with_name('reviewed_career_baseline_corrections.csv')


def apply_reviewed_baseline_corrections(baseline, corrections):
    """Apply independently reviewed exact-ID corrections, retaining old seed evidence."""
    output = baseline.copy()
    output['correction_applied'] = False
    if corrections.empty:
        return output
    keys = ['canonical_player_id', 'metric', 'through_season_start']
    approved = corrections.loc[corrections.status.eq('source_verified')].copy()
    if approved.duplicated(keys).any():
        raise ValueError('Duplicate reviewed career correction')
    for correction in approved.itertuples():
        selected = output.canonical_player_id.eq(correction.canonical_player_id) & output.metric.eq(correction.metric)
        selected &= pd.to_numeric(output.through_season_start, errors='coerce').eq(correction.through_season_start)
        if selected.sum() != 1:
            raise ValueError('Reviewed correction requires one exact governed seed')
        current = float(output.loc[selected, 'governed_value'].iloc[0])
        if current not in [float(correction.previous_governed_value), float(correction.corrected_value)]:
            raise ValueError('Career seed changed since source reconciliation')
        output.loc[selected, 'governed_value'] = float(correction.corrected_value)
        output.loc[selected, 'correction_applied'] = True
    return output


@lru_cache(maxsize=4)
def _public_career_source(category, signature):
    from src.utils.player_identity import apply_player_identity_mapping, filter_public_player_rows
    source = pd.read_csv(get_processed_path(f'all_seasons_{category}.csv', club_id=CLUB), low_memory=False)
    return filter_public_player_rows(
        apply_player_identity_mapping(source, club_id=CLUB),
        club_id=CLUB,
    )


def public_career_source(category):
    from src.utils.player_identity import player_aliases_mtime
    path = get_processed_path(f'all_seasons_{category}.csv', club_id=CLUB)
    return _public_career_source(category, (path.stat().st_mtime_ns, path.stat().st_size,
                                          player_aliases_mtime(club_id=CLUB))).copy()


@lru_cache(maxsize=4)
def _later_totals(signature):

    if not BASELINE_PATH.exists():
        return pd.DataFrame()
    baseline = pd.read_csv(BASELINE_PATH)
    corrections_path = reviewed_corrections_path()
    corrections = pd.read_csv(corrections_path) if corrections_path.exists() else pd.DataFrame()
    baseline = apply_reviewed_baseline_corrections(baseline, corrections)
    report_path = report_baselines_path()
    reports = pd.read_csv(report_path) if report_path.exists() else pd.DataFrame()
    identity_path = report_identity_path()
    governance = pd.read_csv(identity_path).fillna('') if identity_path.exists() else pd.DataFrame()
    reviewed_identity_path = reviewed_report_identity_path()
    if reviewed_identity_path.exists():
        reviewed = pd.read_csv(reviewed_identity_path).fillna('')
        governance = pd.concat([governance, reviewed], ignore_index=True)
    namespace_path = BASELINE_PATH.with_name('summary_identity_namespace_aliases.csv')
    if namespace_path.exists():
        continuity = pd.read_csv(namespace_path).fillna('')
        continuity = continuity.loc[continuity.verification_rule.str.startswith('Exact native source ID retained')]
        continuity = continuity.rename(columns={'canonical_player_name':'report_name'})
        continuity['status'] = 'MATCHED_EXISTING_CANONICAL_PLAYER'
        governance = pd.concat([governance, continuity], ignore_index=True)
    baseline = apply_report_baselines(baseline, reports, governance)
    result = []
    for category, metrics in METRICS.items():
        source = public_career_source(category)
        years = pd.to_numeric(source.season.astype(str).str.extract(r'(\d{4})')[0], errors='coerce')
        for year, anchors in baseline.groupby('through_season_start'):
            later = source.loc[years.gt(year)].copy()
            for metric, field in metrics.items():
                if field not in later:
                    continue
                totals = pd.to_numeric(later[field], errors='coerce').groupby(later.canonical_player_id).sum(min_count=1)
                selected = anchors.loc[anchors.metric.eq(metric)].copy()
                selected['increment'] = selected.canonical_player_id.map(totals).fillna(0)
                selected['updated_value'] = selected.governed_value + selected.increment
                selected['report_rates'] = [{} for _ in range(len(selected))]
                selected['report_source_covered'] = False
                for index, anchor in selected.loc[selected.report_applied].iterrows():
                    rates, covered = _report_rates(source, years, anchor, category, field)
                    selected.at[index, 'report_rates'] = rates
                    selected.at[index, 'report_source_covered'] = covered
                result.append(selected)
    return pd.concat(result, ignore_index=True) if result else pd.DataFrame()


def apply_later_season_totals(frame, club_id, source_frame=None):
    if str(club_id or '').strip().casefold() != CLUB or 'canonical_player_id' not in frame:
        return frame
    paths = [*refresh_baseline_paths(), REPO_ROOT / 'clubs' / CLUB / 'player_aliases.csv',
             REPO_ROOT / 'clubs' / CLUB / 'manual_player_merges.csv']
    paths.extend(get_processed_path(f'all_seasons_{category}.csv', club_id=CLUB) for category in METRICS)
    signature = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths if path.exists())
    updates = _later_totals(signature)
    if updates.empty:
        return frame
    output = frame.copy()
    for row in updates.itertuples():
        if (row.increment == 0 and not row.correction_applied) or row.metric not in output:
            continue
        matched = output.canonical_player_id.eq(row.canonical_player_id)
        if matched.sum() == 1:
            output.loc[matched, row.metric] = row.updated_value
    if source_frame is not None and 'canonical_player_id' in source_frame:
        anchors = set(updates.canonical_player_id)
        for _, source in source_frame.iterrows():
            player_id = source.canonical_player_id
            if player_id not in anchors:
                continue
            span = str(source.get('Career Span', ''))
            import re
            debut = re.search(r'\d{4}', str(source.get('Debut Season', span)))
            latest = re.findall(r'\d{4}', str(source.get('Latest Season', span)))
            if not debut or not latest or int(debut[0]) < 1972 or int(latest[-1]) <= 2025:
                continue
            matched = output.canonical_player_id.eq(player_id)
            if matched.sum() != 1:
                continue
            # Modern source-rule counters are not historical Excel supplements.
            for column in ['Matches', 'Innings', 'Bat Avg', '50s', '100s', 'Maidens',
                           'Balls Bowled', 'Overs', 'Outs', 'Bowl Avg', 'Bowl SR']:
                if column in output and pd.notna(source.get(column)):
                    output.loc[matched, column] = source[column]
            for column in ['Runs', 'Wickets']:
                report_metric = updates.report_applied & updates.canonical_player_id.eq(player_id) & updates.metric.eq(column)
                if report_metric.any():
                    continue
                if column in output and pd.notna(source.get(column)):
                    value = pd.to_numeric(output.loc[matched, column], errors='coerce').iloc[0]
                    output.loc[matched, column] = max(source[column], value) if pd.notna(value) else source[column]
            if 'Matches Proxy' in output:
                output.loc[matched, 'Matches Proxy'] = ''
            if 'Matches Source' in output:
                output.loc[matched, 'Matches Source'] = 'PlayCricket / PlayHQ'
    for row in updates.loc[updates.report_applied].itertuples():
        matched = output.canonical_player_id.eq(row.canonical_player_id)
        if matched.sum() != 1:
            continue
        for column, value in row.report_rates.items():
            if column in output:
                output[column] = pd.to_numeric(output[column], errors='coerce').astype(float)
                output.loc[matched, column] = value
        if row.metric == 'Runs' and 'Bat SR' in output:
            # The app's strike rate is verified ball-by-ball, not all scorecard runs.
            rate = float('nan')
            if row.report_source_covered and source_frame is not None:
                source = source_frame.loc[source_frame.canonical_player_id.eq(row.canonical_player_id)]
                if len(source) == 1:
                    runs = pd.to_numeric(source.iloc[0].get('ballByBallBatRuns'), errors='coerce')
                    balls = pd.to_numeric(source.iloc[0].get('ballByBallBatBalls'), errors='coerce')
                    if pd.notna(runs) and pd.notna(balls) and balls > 0:
                        rate = runs * 100 / balls
            output['Bat SR'] = pd.to_numeric(output['Bat SR'], errors='coerce').astype(float)
            output.loc[matched, 'Bat SR'] = rate
    from src.data.grdcc_career_quarantine import apply_career_quarantine
    return apply_career_quarantine(output,club_id)
