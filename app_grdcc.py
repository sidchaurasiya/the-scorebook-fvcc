"""Dedicated Streamlit Cloud entrypoint for the GRDCC production app."""

import time

script_start = time.perf_counter()
entry_epoch = time.time()
entry_cpu = time.process_time()

import os

os.environ["CLUB_ID"] = "georges-river-district"
os.environ.setdefault("SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES", "false")

from app import main  # noqa: E402

from src.utils import profile_trace

profile_trace.begin(script_start, entry_epoch, entry_cpu)
try:
    main()
finally:
    profile_trace.finish()
