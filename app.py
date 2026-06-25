import time

import streamlit as st

from src.ui.layout import render_page
from src.utils.performance import record_club_load_profile


def main() -> None:
    started_at = time.perf_counter()
    st.set_page_config(
        page_title="Cricket Club Analytics",
        page_icon="🏏",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    render_page()
    record_club_load_profile(
        "app_startup_and_render",
        (time.perf_counter() - started_at) * 1000,
        notes="Full Streamlit script run for the selected route.",
    )


if __name__ == "__main__":
    main()
