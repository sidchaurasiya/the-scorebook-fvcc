"""Opt-in phase measurements for the private GRDCC profile benchmark."""
import base64
import json
import os
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

import streamlit as st

WORKER = uuid4().hex[:12]
_current = ContextVar("grdcc_profile_trace", default=None)


def begin(start, epoch, cpu):
    _current.set(None)
    if st.query_params.get("profile_trace") != "1" and not st.session_state.get("_profile_trace_session"):
        return
    session = st.session_state.setdefault("_profile_trace_session", uuid4().hex[:12])
    _current.set({"worker": WORKER, "session": session, "run": uuid4().hex[:12],
                  "epoch": epoch, "start": start, "initial_cpu": cpu, "phases": [],
                  "python": sys.version.split()[0], "streamlit": st.__version__})
    event("imports_complete")


def event(phase, **fields):
    record = _current.get()
    if record is not None:
        record["phases"].append({"phase": phase, "ms": round((time.perf_counter()-record["start"])*1000, 3),
                                 "process_cpu_ms": round((time.process_time()-record["initial_cpu"])*1000, 3), **fields})


def finish():
    record = _current.get()
    if record is None:
        return
    event("script_complete")
    try:
        import resource
        record["process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    except ImportError:
        pass
    payload = json.dumps(record, separators=(",", ":"))
    print("GRDCC_PROFILE_TRACE "+payload, flush=True)
    encoded = base64.b64encode(payload.encode()).decode("ascii")
    st.markdown(f'<span hidden data-profile-run="{encoded}"></span>', unsafe_allow_html=True)
    _current.set(None)


@contextmanager
def phase(name):
    """Time one operation in an existing opt-in script or fragment trace."""
    event(name + "_start")
    try:
        yield
    finally:
        event(name + "_end")


@contextmanager
def section_run(name):
    """Correlate standalone fragment executions with the same browser session."""
    own_run = _current.get() is None
    if own_run:
        begin(time.perf_counter(), time.time(), time.process_time())
    event(name + "_start")
    try:
        yield
    finally:
        event(name + "_end")
        if own_run:
            finish()
