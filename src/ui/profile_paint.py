"""Start profile analysis after the browser has had a frame to paint the summary."""
from collections.abc import Callable
from functools import lru_cache

import streamlit as st


@lru_cache(maxsize=1)
def _paint_gate():
    return st.components.v2.component(
        "profile_paint_gate",
        js="""
        export default function ({ data, setStateValue }) {
            if (data.ready) return;
            let second;
            const first = requestAnimationFrame(() => {
                second = requestAnimationFrame(() => {
                    const card = document.querySelector('[data-profile-choice]');
                    if (!data.choice || (card?.dataset.profileChoice === data.choice &&
                        !document.documentElement.hasAttribute("data-grdcc-profile-pending"))) {
                        setStateValue("ready", true);
                    }
                });
            });
            return () => {
                cancelAnimationFrame(first);
                if (second !== undefined) cancelAnimationFrame(second);
            };
        }
        """,
    )


def summary_painted(club: str, player: str, show_pending: Callable[[], None]) -> bool:
    state = st.session_state
    selection = (club, player)
    generation = state.get("profile_analysis_generation", 0)
    if state.get("profile_analysis_selection") != selection:
        generation += 1
        state["profile_analysis_selection"] = selection
        state["profile_analysis_generation"] = generation
    key = f"profile_paint_{generation}_{club}_{player}"
    previous = state.get(key, {})
    ready = bool(previous and previous.get("ready"))
    if not ready:
        show_pending()
    result = _paint_gate()(
        key=key, data={"ready": ready, "choice": state.get("grdcc_profile_choice")},
        default={"ready": False}, on_ready_change=lambda: None,
    )
    return bool(result.ready)
