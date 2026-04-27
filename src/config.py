from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class PlayHQSettings:
    api_key: str
    tenant: str
    base_url: str


def get_playhq_settings() -> PlayHQSettings:
    """Read PlayHQ settings from Streamlit secrets."""
    return PlayHQSettings(
        api_key=st.secrets.get("PLAYHQ_API_KEY", ""),
        tenant=st.secrets.get("PLAYHQ_TENANT", "ca"),
        base_url=st.secrets.get("PLAYHQ_BASE_URL", "https://api.playhq.com"),
    )
