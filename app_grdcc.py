"""Dedicated Streamlit Cloud entrypoint for the GRDCC production app."""

import os

os.environ["CLUB_ID"] = "georges-river-district"
os.environ.setdefault("SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES", "false")

import app  # noqa: E402,F401
