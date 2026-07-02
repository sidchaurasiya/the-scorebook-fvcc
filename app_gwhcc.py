"""Dedicated Streamlit Cloud entrypoint for the Glen Waverley Hawks app."""

import os

os.environ["CLUB_ID"] = "glen-waverley-hawks"
os.environ.setdefault("SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES", "false")

from app import main  # noqa: E402

main()
