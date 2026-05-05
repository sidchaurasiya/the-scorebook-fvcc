from __future__ import annotations

import html
import json
import os
import re
from collections.abc import Mapping
from typing import Any

import streamlit as st
import streamlit.components.v1 as components


# Analytics are used to understand app usage. Do not track private user-entered
# text, emails, phone numbers, or sensitive data.
SENSITIVE_PARAM_HINTS = ("email", "phone", "password", "secret", "token")
MAX_PARAM_LENGTH = 160


def _measurement_id() -> str:
    value = str(os.getenv("GA4_MEASUREMENT_ID", "") or "").strip()
    if not value:
        try:
            value = str(st.secrets.get("GA4_MEASUREMENT_ID", "") or "").strip()
        except Exception:
            value = ""
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]{3,80}", value):
        return ""
    return value


def _clean_event_name(event_name: object) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(event_name or "").strip())
    return cleaned[:40]


def _clean_param_key(key: object) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(key or "").strip())
    return cleaned[:40]


def _clean_params(params: Mapping[str, Any] | None) -> dict[str, str | int | float | bool]:
    output: dict[str, str | int | float | bool] = {}
    for raw_key, raw_value in dict(params or {}).items():
        key = _clean_param_key(raw_key)
        if not key or any(hint in key.casefold() for hint in SENSITIVE_PARAM_HINTS):
            continue
        if raw_value is None:
            continue
        if isinstance(raw_value, bool):
            output[key] = raw_value
        elif isinstance(raw_value, int | float):
            output[key] = raw_value
        else:
            value = str(raw_value).strip()
            if value:
                output[key] = value[:MAX_PARAM_LENGTH]
    return output


def _ga4_script(
    measurement_id: str,
    event_name: str | None = None,
    params: Mapping[str, Any] | None = None,
) -> str:
    event_name_json = json.dumps(_clean_event_name(event_name) if event_name else None)
    params_json = json.dumps(_clean_params(params), sort_keys=True)
    measurement_id_json = json.dumps(measurement_id)
    return f"""
    <script>
    (function() {{
        const measurementId = {measurement_id_json};
        const eventName = {event_name_json};
        const eventParams = {params_json};

        function rootWindow() {{
            try {{
                if (window.parent && window.parent.document) {{
                    return window.parent;
                }}
            }} catch (error) {{}}
            return window;
        }}

        const root = rootWindow();
        const doc = root.document || document;
        root.dataLayer = root.dataLayer || [];
        root.gtag = root.gtag || function() {{ root.dataLayer.push(arguments); }};

        if (!root.__scorebookGa4Loaded) {{
            if (!doc.querySelector('script[data-scorebook-ga4="true"]')) {{
                const script = doc.createElement("script");
                script.async = true;
                script.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(measurementId);
                script.setAttribute("data-scorebook-ga4", "true");
                (doc.head || doc.body || doc.documentElement).appendChild(script);
            }}
            root.gtag("js", new Date());
            root.gtag("config", measurementId, {{ send_page_view: false }});
            root.__scorebookGa4Loaded = true;
        }}

        if (eventName) {{
            root.gtag("event", eventName, eventParams);
        }}
    }})();
    </script>
    """


def inject_ga4() -> None:
    measurement_id = _measurement_id()
    if not measurement_id:
        return
    session_key = f"_scorebook_ga4_injected_{measurement_id}"
    if st.session_state.get(session_key):
        return
    components.html(_ga4_script(measurement_id), height=0, width=0)
    st.session_state[session_key] = True


def track_event(event_name: str, params: Mapping[str, Any] | None = None) -> None:
    measurement_id = _measurement_id()
    cleaned_event = _clean_event_name(event_name)
    if not measurement_id or not cleaned_event:
        return
    components.html(_ga4_script(measurement_id, cleaned_event, params), height=0, width=0)


def track_event_once(
    event_name: str,
    params: Mapping[str, Any] | None = None,
    *,
    key: str | None = None,
) -> None:
    cleaned_params = _clean_params(params)
    signature = key or f"{_clean_event_name(event_name)}:{json.dumps(cleaned_params, sort_keys=True)}"
    tracked = st.session_state.setdefault("_scorebook_ga4_events_once", {})
    if tracked.get(signature):
        return
    tracked[signature] = True
    track_event(event_name, cleaned_params)


def track_page_view(page_slug: str, page_title: str | None = None) -> None:
    cleaned_slug = str(page_slug or "").strip()
    if not cleaned_slug:
        return
    page_title_text = str(page_title or cleaned_slug.replace("-", " ").title()).strip()
    signature = f"{cleaned_slug}:{page_title_text}"
    if st.session_state.get("_scorebook_ga4_last_page_view") == signature:
        return
    st.session_state["_scorebook_ga4_last_page_view"] = signature
    track_event(
        "page_view",
        {
            "page_slug": cleaned_slug,
            "page_title": page_title_text,
            "page_path": f"?page={cleaned_slug}",
        },
    )


def ga4_link_onclick(event_name: str, params: Mapping[str, Any] | None = None) -> str:
    if not _measurement_id():
        return ""
    cleaned_event = _clean_event_name(event_name)
    if not cleaned_event:
        return ""
    script = (
        "if(window.gtag){window.gtag('event',"
        f"{json.dumps(cleaned_event)},"
        f"{json.dumps(_clean_params(params), sort_keys=True)}"
        ");}"
    )
    return f' onclick="{html.escape(script, quote=True)}"'
