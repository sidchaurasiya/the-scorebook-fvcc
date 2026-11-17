"""GRDCC presentation helpers. No source statistics or identity rules live here."""
from __future__ import annotations

import base64
import html
import json
import re
from functools import lru_cache
from pathlib import Path
from numbers import Number

import pandas as pd

from src.config.club_config import REPO_ROOT


def premium_css() -> str:
    files = [Path(__file__).with_name('grdcc_premium.css')]
    files.extend(REPO_ROOT / 'clubs/georges-river-district/assets/fonts' / name for name in ['Manrope-Variable.ttf', 'BarlowCondensed-SemiBold.ttf'])
    return _premium_css_cached(tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in files))


@lru_cache(maxsize=2)
def _premium_css_cached(signature: tuple) -> str:
    _ = signature
    css = Path(__file__).with_name('grdcc_premium.css').read_text()
    fonts = REPO_ROOT / 'clubs/georges-river-district/assets/fonts'
    for token, filename in [('MANROPE', 'Manrope-Variable.ttf'), ('BARLOW', 'BarlowCondensed-SemiBold.ttf')]:
        encoded = base64.b64encode((fonts / filename).read_bytes()).decode('ascii')
        css = css.replace('__' + token + '__', encoded)
    return css


def ordered_hat_tricks(records: pd.DataFrame) -> pd.DataFrame:
    """Date descending, natural first delivery and event ID: stable under input order."""
    if records.empty:
        return records.copy()
    rows = records.copy()
    rows['_date'] = pd.to_datetime(rows.get('match_date'), errors='coerce', utc=True)
    rows['_name'] = rows.get('canonical_player_name', pd.Series('', index=rows.index)).fillna('').astype(str).str.casefold()
    def delivery_key(value):
        found = re.search(r'(\d+)\.(\d+)', str(value))
        return (int(found[1]), int(found[2])) if found else (10**6, 10**6)
    rows['_delivery'] = rows.get('delivery_sequence', pd.Series('', index=rows.index)).map(delivery_key)
    rows['_event'] = rows.get('event_id', pd.Series('', index=rows.index)).fillna('').astype(str)
    return rows.sort_values(['_date', '_name', '_delivery', '_event'], ascending=[False, True, True, True], kind='stable', na_position='last').drop(columns=['_date', '_name', '_delivery', '_event'])


def overlapping_hat_trick_events(records: pd.DataFrame) -> set[str]:
    """Annotate retained sliding windows, without changing their governed count."""
    required = {'event_id', 'match_id', 'canonical_player_id', 'delivery_sequence'}
    if not required.issubset(records.columns):
        return set()
    overlap = set()
    group_columns = ['match_id', 'canonical_player_id'] + (['innings_id'] if 'innings_id' in records else [])
    for _, group in records.groupby(group_columns, dropna=False):
        events = [(str(row.event_id), set(re.findall(r'\d+\.\d+', str(row.delivery_sequence)))) for row in group.itertuples()]
        for index, (event, sequence) in enumerate(events):
            for other, second in events[index + 1:]:
                if len(sequence) == len(second) == 3 and len(sequence & second) == 2 and len(sequence | second) == 4:
                    overlap.update([event, other])
    return overlap


def playing_dates_html(value: object) -> str:
    """Render official dates only; never infer the second day from the first."""
    values = value if isinstance(value, (list, tuple)) else [value]
    dates = set()
    for raw in values:
        if isinstance(raw, Number):
            continue
        if isinstance(raw, str) and not re.match(r'^\d{4}-\d{2}-\d{2}(?:[T ].*)?$', raw.strip()):
            continue
        if raw is None or (not isinstance(raw, (list, dict)) and pd.isna(raw)):
            continue
        try:
            date = pd.Timestamp(raw)
        except (ValueError, TypeError):
            continue
        if pd.isna(date):
            continue
        if date.tzinfo is not None:
            date = date.tz_convert('Australia/Sydney')
        dates.add(date.date())
    if not dates:
        return '<span class="grdcc-date-unavailable">Date unavailable</span>'
    return ''.join(f'<time datetime="{date.isoformat()}">{html.escape(date.strftime("%d-%m-%Y"))}</time>' for date in sorted(dates))


@lru_cache(maxsize=4)
def load_playing_date_index(path: str, version: int) -> dict[str, list[str]]:
    _ = version
    source = Path(path)
    if not source.exists():
        return {}
    data = json.loads(source.read_text())
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported fixture date evidence')
    return {str(key): list(value['playing_dates']) for key, value in data.get('matches', {}).items()}


def grade_scroll_script(render_key: str = '') -> str:
    import hashlib
    key = hashlib.sha256(render_key.encode()).hexdigest()[:12]
    return '<!-- grdcc-grade-scroll:' + key + ' -->' + """
    <script>
    (() => {
      let doc;
      try { doc = window.parent.document; } catch (_) { doc = document; }
      doc.querySelectorAll('.grdcc-round-shell').forEach(shell => {
        const strip = shell.querySelector('[data-grdcc-grade-strip]');
        if (!strip || strip.dataset.grdccBound === 'true') return;
        strip.dataset.grdccBound = 'true';
        const next = shell.querySelector('.grdcc-grade-next');
        const prev = shell.querySelector('.grdcc-grade-prev');
        const hint = shell.querySelector('[data-grade-scroll-hint]');
        const update = () => {
          const max = Math.max(0, strip.scrollWidth - strip.clientWidth);
          const right = strip.scrollLeft < max - 2;
          const left = strip.scrollLeft > 2;
          next.hidden = !right; prev.hidden = !left;
          hint.hidden = max <= 2;
          hint.textContent = right ? 'Scroll for more grades' : 'Earlier grades to the left';
        };
        const move = direction => strip.scrollBy({
          left: direction * Math.max(240, strip.clientWidth * 0.85),
          behavior: window.parent.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
        });
        next.addEventListener('click', () => move(1));
        prev.addEventListener('click', () => move(-1));
        strip.addEventListener('scroll', update, {passive:true});
        strip.addEventListener('keydown', event => {
          if (event.target !== strip || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
          event.preventDefault();
          if (event.key === 'Home') strip.scrollTo({left:0});
          else if (event.key === 'End') strip.scrollTo({left:strip.scrollWidth});
          else move(event.key === 'ArrowRight' ? 1 : -1);
        });
        if (window.parent.ResizeObserver) new window.parent.ResizeObserver(update).observe(strip);
        window.parent.addEventListener('resize', update, {passive:true});
        requestAnimationFrame(update);
      });
    })();
    </script>
    """
