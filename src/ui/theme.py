from __future__ import annotations

import html

import streamlit as st


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --pitch: #5B4BEB;
            --pitch-2: #7C5CFF;
            --grass: #22c7dc;
            --gold: #ffcc4d;
            --ink: #080B3F;
            --muted: #6D728E;
            --line: #E7EAF5;
            --surface: #ffffff;
            --surface-soft: #F7F8FC;
            --danger: #e64b68;
            --card-border: #E8EAF5;
            --card-shadow: 0 8px 24px rgba(20, 22, 60, 0.06);
            --card-shadow-hover: 0 16px 36px rgba(20, 22, 60, 0.10);
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(103, 56, 245, 0.08), transparent 32rem),
                #f7f8fc;
            color: var(--ink);
        }

        div[data-testid="collapsedControl"] {
            display: none;
        }

        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        .stAppDeployButton {
            display: none !important;
        }

        header[data-testid="stHeader"] {
            background: transparent;
            height: 0;
        }

        section[data-testid="stSidebar"] {
            background:
                radial-gradient(circle at 18% 0%, rgba(113, 82, 255, 0.55), transparent 14rem),
                radial-gradient(circle at 80% 42%, rgba(59, 130, 246, 0.14), transparent 12rem),
                linear-gradient(180deg, #17105F 0%, #08063B 100%);
            border-right: 0;
            width: 232px !important;
        }

        section[data-testid="stSidebar"] > div {
            padding: 28px 16px;
        }

        section[data-testid="stSidebar"] * {
            color: #ffffff;
        }

        section[data-testid="stSidebar"] div[data-testid="stExpander"] {
            background: transparent;
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 14px;
            box-shadow: none;
            margin-top: 18px;
        }

        section[data-testid="stSidebar"] div[data-testid="stExpander"] details {
            background: transparent;
        }

        section[data-testid="stSidebar"] div[role="radiogroup"] {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-top: 28px;
        }

        section[data-testid="stSidebar"] label[data-baseweb="radio"] {
            align-items: center;
            border: 1px solid transparent;
            border-radius: 16px;
            color: rgba(255, 255, 255, 0.72) !important;
            display: flex;
            font-size: 0.96rem;
            font-weight: 700;
            gap: 14px;
            margin: 0;
            padding: 13px 15px;
            transition: background 160ms ease, box-shadow 160ms ease, color 160ms ease, border-color 160ms ease;
            white-space: nowrap;
        }

        section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
            background: linear-gradient(135deg, #6b3cff, #5630d7);
            border-color: rgba(255, 255, 255, 0.13);
            box-shadow: 0 16px 34px rgba(99, 64, 255, 0.36), inset 0 1px 0 rgba(255, 255, 255, 0.16);
            color: #ffffff !important;
        }

        section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {
            display: none;
        }

        .block-container {
            padding: 5.6rem 2.25rem 3rem;
            max-width: 1720px;
        }

        .block-container:has(.sticky-filter-spacer) {
            padding-top: 1.5rem;
        }

        .block-container:has(.near-milestones-page) {
            padding-top: 1.65rem;
        }

        h1, h2, h3 {
            letter-spacing: -0.02em;
        }

        div[data-testid="stTabs"] button {
            border-radius: 999px;
            color: #737998;
            font-weight: 750;
            margin-right: 8px;
            min-height: 38px;
            padding: 8px 16px;
        }

        div[data-testid="stTabs"] button[aria-selected="true"] {
            background: #F0EDFF;
            color: var(--pitch);
            border-bottom-color: transparent;
        }

        div[data-testid="stTabs"] [role="tablist"] {
            background: #F7F8FD;
            border: 1px solid #E9ECF6;
            border-radius: 999px;
            display: inline-flex;
            gap: 4px;
            margin-bottom: 18px;
            padding: 5px;
        }

        div[data-testid="stTabs"] [data-baseweb="tab-border"] {
            display: none;
        }

        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            display: none;
        }

        div[data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 18px 18px 16px;
            box-shadow: 0 12px 30px rgba(8, 42, 36, 0.08);
        }

        div[data-testid="stMetricLabel"] {
            color: var(--muted);
            font-weight: 700;
        }

        div[data-testid="stMetricValue"] {
            color: var(--pitch);
            font-weight: 800;
        }

        .cv-hero {
            position: relative;
            overflow: hidden;
            border-radius: 14px 14px 0 0;
            background:
                linear-gradient(135deg, rgba(181, 72, 248, 0.98) 0%, rgba(103, 56, 245, 0.97) 48%, rgba(68, 101, 246, 0.97) 100%),
                repeating-linear-gradient(90deg, rgba(255,255,255,0.06) 0 1px, transparent 1px 54px);
            color: #ffffff;
            padding: 10px 20px 8px;
            margin-bottom: 0;
            box-shadow: 0 22px 52px rgba(103, 56, 245, 0.18);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
        }

        .cv-hero:after {
            content: "";
            position: absolute;
            right: 22px;
            top: 14px;
            bottom: 14px;
            width: 44px;
            border-top: 2px solid rgba(255, 255, 255, 0.38);
            border-bottom: 2px solid rgba(255, 255, 255, 0.38);
            opacity: 0.9;
        }

        .cv-kicker {
            color: rgba(255, 255, 255, 0.76);
            font-size: 0.66rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 2px;
        }

        .cv-title {
            color: #ffffff;
            font-size: clamp(1.18rem, 2vw, 1.62rem);
            line-height: 1.1;
            font-weight: 900;
            margin: 0;
            max-width: 620px;
        }

        .cv-subtitle {
            color: rgba(255, 255, 255, 0.84);
            font-size: 0.76rem;
            line-height: 1.25;
            max-width: 640px;
            margin: 0;
        }

        .cv-context-row {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 18px;
        }

        .cv-pill {
            background: rgba(255, 255, 255, 0.10);
            border: 1px solid rgba(255, 255, 255, 0.20);
            border-radius: 999px;
            color: #ffffff;
            font-size: 0.82rem;
            font-weight: 700;
            padding: 7px 12px;
        }

        .cv-panel {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 18px;
            box-shadow: 0 12px 30px rgba(8, 42, 36, 0.08);
            margin-bottom: 18px;
        }

        .cv-section-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin: 8px 0 14px;
        }

        .cv-section-title h2,
        .cv-section-title h3 {
            margin: 0;
            color: var(--ink);
        }

        .cv-section-title span {
            color: var(--muted);
            font-size: 0.9rem;
            font-weight: 700;
        }

        .cv-callout {
            border-left: 4px solid var(--pitch-2);
            background: #fbf7ff;
            border-radius: 8px;
            padding: 14px 16px;
            color: #58327d;
            font-weight: 650;
        }

        .stButton > button {
            border-radius: 8px;
            border: 1px solid var(--pitch);
            background: var(--pitch);
            color: #ffffff;
            font-weight: 800;
            min-height: 42px;
            box-shadow: 0 10px 24px rgba(6, 60, 53, 0.20);
        }

        .stButton > button:hover {
            border-color: var(--pitch-2);
            background: var(--pitch-2);
            color: #ffffff;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid #E9ECF6;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: none;
        }

        div[data-testid="stDataFrame"] [role="columnheader"],
        div[data-testid="stDataFrame"] [data-testid="stTableStyledTable"] thead th {
            background: #F7F8FD !important;
            color: #5D6686 !important;
            font-weight: 850 !important;
            border-bottom: 1px solid #E6E9F4 !important;
        }

        div[data-testid="stDataFrame"] [role="gridcell"] {
            color: #20243D;
            border-color: #EEF1F8 !important;
            min-height: 42px !important;
        }

        div[data-testid="stDataFrame"] [role="row"]:nth-child(even) [role="gridcell"] {
            background: #FBFCFF !important;
        }

        div[data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"] {
            background: #F7F5FF !important;
        }

        .side-brand {
            display: flex;
            align-items: center;
            gap: 13px;
            margin-bottom: 34px;
        }

        .side-shield {
            align-items: center;
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.58);
            border-radius: 16px 16px 20px 20px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.18), 0 12px 26px rgba(0,0,0,0.18);
            display: flex;
            font-size: 0.85rem;
            font-weight: 900;
            height: 56px;
            justify-content: center;
            width: 46px;
        }

        .side-title {
            font-size: 1.35rem;
            font-weight: 900;
            line-height: 1.05;
        }

        .side-subtitle {
            color: rgba(255, 255, 255, 0.78);
            font-size: 0.82rem;
            font-weight: 700;
            margin-top: 4px;
        }

        .side-nav {
            display: grid;
            gap: 9px;
        }

        .side-nav-item {
            align-items: center;
            border-radius: 14px;
            color: rgba(255, 255, 255, 0.78) !important;
            display: flex;
            font-size: 0.98rem;
            font-weight: 750;
            gap: 14px;
            padding: 13px 15px;
        }

        .side-nav-item span {
            color: inherit;
            font-size: 1rem;
            text-align: center;
            width: 22px;
        }

        .side-nav-item.active {
            background: linear-gradient(135deg, #6b3cff, #5630d7);
            box-shadow: 0 16px 34px rgba(99, 64, 255, 0.46);
            color: #ffffff !important;
        }

        .side-footer {
            border-top: 1px solid rgba(255, 255, 255, 0.14);
            color: rgba(255, 255, 255, 0.66);
            font-size: 0.78rem;
            margin-top: 52px;
            padding: 20px 2px 0;
            width: 100%;
        }

        .side-footer div {
            margin-bottom: 6px;
        }

        .page-kicker {
            color: var(--ink);
            font-size: 18px;
            font-weight: 600;
            margin: 0 0 18px;
        }

        .club-label {
            color: #5B3DF5;
            font-size: clamp(1.5rem, 1.75vw, 1.75rem);
            font-weight: 750;
            letter-spacing: 0;
            line-height: 1.2;
            margin: 0 0 12px;
            padding-top: 0;
        }

        .page-title {
            color: var(--ink);
            font-size: clamp(3.15rem, 4vw, 4rem);
            font-weight: 800;
            line-height: 1.06;
            margin: 0 0 7px;
        }

        .page-subtitle {
            color: #676d8c;
            font-size: 0.96rem;
            font-weight: 650;
            margin: 8px 0 10px;
        }

        .hof-context {
            margin-top: 10px;
        }

        .block-container:has(.hall-of-fame-page) {
            padding-top: 1.65rem;
        }

        .block-container:has(.hall-of-fame-page) .page-title {
            font-size: clamp(2.8rem, 3.6vw, 3.75rem);
            margin: 0 0 9px;
        }

        .block-container:has(.hall-of-fame-page) .club-label {
            color: #5B3DF5;
            margin: 0 0 15px;
        }

        .block-container:has(.hall-of-fame-page) .page-subtitle {
            color: #747b98;
            font-size: 1rem;
            font-weight: 700;
            margin: 0 0 30px;
        }

        div.st-key-header_intro {
            margin-bottom: 14px;
        }

        div.st-key-sticky_controls {
            background: rgba(255, 255, 255, 0.94);
            backdrop-filter: blur(14px);
            border: 1px solid rgba(226, 230, 244, 0.96);
            border-radius: 22px;
            box-shadow: 0 10px 28px rgba(20, 22, 60, 0.08);
            left: calc(232px + 2.25rem);
            margin: 0;
            padding: 24px 28px 22px;
            position: fixed !important;
            right: 2.25rem;
            top: 24px;
            width: auto;
            z-index: 2000;
        }

        div[data-testid="stElementContainer"]:has(div.st-key-sticky_controls) {
            min-height: auto;
            overflow: visible !important;
            position: relative !important;
            z-index: 2000;
        }

        div[data-testid="stElementContainer"]:has(.sticky-filter-spacer) {
            margin: 0;
        }

        .sticky-filter-spacer {
            height: 154px;
            margin: 0;
            padding: 0;
        }

        div[data-testid="stVerticalBlock"]:has(div.st-key-sticky_controls),
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.st-key-sticky_controls),
        div[data-testid="stVerticalBlockBorderWrapper"]:has(+ div div.st-key-sticky_controls),
        div[data-testid="stElementContainer"]:has(+ div div.st-key-sticky_controls) {
            contain: none !important;
            overflow: visible !important;
            transform: none !important;
        }

        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] div.st-key-sticky_controls) {
            overflow: visible !important;
        }

        div.st-key-sticky_controls div[data-testid="stHorizontalBlock"] {
            align-items: center;
            flex-wrap: nowrap;
            gap: 18px;
        }

        div.st-key-sticky_controls div[data-testid="stHorizontalBlock"]:has(.filter-inline-label) {
            align-items: center;
            flex-wrap: nowrap;
            gap: 14px;
        }

        div.st-key-sticky_controls div[data-testid="column"]:has(.filter-inline-label) {
            flex: 0 0 auto !important;
            min-width: max-content !important;
            width: auto !important;
        }

        div.st-key-sticky_controls div[data-testid="column"]:has(div[data-baseweb="select"]) {
            min-width: 0;
        }

        div.st-key-sticky_controls label {
            display: none;
        }

        div.st-key-sticky_controls div[data-baseweb="select"] > div {
            align-items: center;
            background: #ffffff;
            border: 1px solid #E4E8F4;
            border-radius: 15px;
            box-shadow: 0 6px 14px rgba(20, 23, 67, 0.035);
            display: flex;
            min-height: 56px;
            width: 100%;
            text-align: left;
        }

        div.st-key-sticky_controls div[data-baseweb="select"] div {
            text-align: left;
        }

        div.st-key-sticky_controls div[data-baseweb="select"] [role="button"],
        div.st-key-sticky_controls div[data-baseweb="select"] [aria-selected],
        div.st-key-sticky_controls div[data-baseweb="select"] [class*="singleValue"] {
            align-items: center;
            justify-content: flex-start;
            min-height: 56px;
            padding-left: 4px;
            text-align: left;
        }

        div.st-key-sticky_controls div[data-baseweb="select"] svg {
            margin-left: auto;
        }

        .filter-inline-label {
            align-items: center;
            color: #525a78;
            display: flex;
            font-size: 14px;
            font-weight: 600;
            justify-content: flex-start;
            letter-spacing: 0.035em;
            line-height: 1;
            margin: 0;
            min-height: 56px;
            min-width: max-content;
            overflow: visible;
            padding: 0;
            text-transform: uppercase;
            white-space: nowrap;
        }

        .filter-context-line {
            align-items: center;
            color: #8b91aa;
            display: flex;
            flex-wrap: wrap;
            font-size: 0.9rem;
            gap: 12px;
            justify-content: flex-start;
            line-height: 1.35;
            margin: 12px 0 0;
            padding-left: 0;
        }

        .filter-context-line > span:first-child {
            color: #535a78;
            font-weight: 750;
        }

        .context-line {
            align-items: center;
            color: #7a7f9f;
            display: flex;
            font-size: 0.94rem;
            gap: 10px;
            justify-content: flex-start;
            margin: 0 0 24px;
        }

        .context-line > span:first-child {
            color: #4d5371;
            font-weight: 750;
        }

        .source-note {
            color: #9aa0b8;
            font-size: 0.8rem;
        }

        .filter-spacer {
            min-height: 52px;
        }

        .top-sync {
            align-items: center;
            background: rgba(16, 185, 129, 0.09);
            border: 1px solid rgba(16, 185, 129, 0.18);
            border-radius: 999px;
            color: #737998;
            display: flex;
            font-size: 0.84rem;
            gap: 8px;
            justify-content: center;
            margin-top: 0;
            min-height: 46px;
            padding: 0 12px;
        }

        .sync-dot {
            background: #16c784;
            border-radius: 999px;
            height: 9px;
            width: 9px;
        }

        .sync-muted {
            color: #8c91ad;
        }

        .kpi-card {
            align-items: stretch;
            background: #ffffff;
            border: 1px solid var(--card-border);
            border-radius: 22px;
            box-shadow: var(--card-shadow);
            display: flex;
            justify-content: space-between;
            height: 150px;
            min-height: 150px;
            overflow: hidden;
            padding: 26px 28px;
            position: relative;
            transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
        }

        .kpi-content {
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            min-width: 0;
            padding-right: 18px;
            position: relative;
            z-index: 1;
        }

        .kpi-card::after {
            background: radial-gradient(circle, rgba(109, 77, 255, 0.10), transparent 68%);
            content: "";
            height: 120px;
            position: absolute;
            right: -38px;
            top: -38px;
            width: 120px;
        }

        .kpi-card:hover {
            border-color: #dddffc;
            box-shadow: var(--card-shadow-hover);
            transform: translateY(-3px);
        }

        .kpi-label {
            color: #727999;
            font-size: 0.78rem;
            font-weight: 750;
            letter-spacing: 0.06em;
            line-height: 1.25;
            max-width: 150px;
            min-height: 34px;
            text-transform: uppercase;
        }

        .kpi-value {
            color: var(--ink);
            font-size: 2.18rem;
            font-weight: 900;
            line-height: 1.1;
            margin-top: 10px;
            white-space: nowrap;
        }

        .kpi-detail {
            color: #697091;
            font-size: 0.94rem;
            margin-top: 9px;
        }

        .kpi-icon {
            align-items: center;
            border-radius: 999px;
            color: #ffffff;
            display: flex;
            font-size: 1.28rem;
            font-weight: 950;
            height: 64px;
            justify-content: center;
            width: 64px;
            flex: 0 0 64px;
            align-self: center;
            position: relative;
            z-index: 1;
            box-shadow: 0 14px 28px rgba(91, 75, 235, 0.20);
        }

        .kpi-icon-asset {
            display: block;
            height: 32px;
            max-height: 32px;
            max-width: 32px;
            object-fit: contain;
            width: 32px;
        }

        .kpi-icon-asset-png {
            filter: brightness(0) invert(1);
        }

        .kpi-icon-fallback {
            align-items: center;
            display: inline-flex;
            height: 32px;
            justify-content: center;
            line-height: 1;
            width: 32px;
        }

        .kpi-icon.purple { background: linear-gradient(135deg, #7b42ff, #5b32e8); }
        .kpi-icon.blue { background: linear-gradient(135deg, #6aa9ff, #2f72ff); }
        .kpi-icon.green { background: linear-gradient(135deg, #34d399, #12b981); }

        .dashboard-spacer {
            height: 20px;
        }

        .overview-section-title {
            color: var(--ink);
            font-size: clamp(1.5rem, 1.9vw, 2rem);
            font-weight: 800;
            letter-spacing: -0.02em;
            line-height: 1.2;
            margin: 44px 0 22px;
        }

        .quick-strip {
            display: flex;
            gap: 18px;
            justify-content: flex-end;
            margin: 10px 0 18px;
        }

        .quick-strip div {
            align-items: baseline;
            color: #737998;
            display: flex;
            gap: 7px;
        }

        .quick-strip strong {
            color: var(--ink);
            font-size: 1rem;
        }

        div.st-key-runs_chart_card,
        div.st-key-top_scorers_card,
        div.st-key-top_wickets_card,
        div.st-key-form_card,
        div.st-key-batting_card,
        div.st-key-bowling_card,
        div.st-key-fielding_card {
            background: #ffffff;
            border: 1px solid var(--card-border);
            border-radius: 22px;
            box-shadow: var(--card-shadow);
            margin-bottom: 24px;
            min-height: 100%;
            padding: 26px 28px;
            transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
        }

        div.st-key-top_scorers_card:hover,
        div.st-key-top_wickets_card:hover,
        div.st-key-batting_card:hover,
        div.st-key-bowling_card:hover,
        div.st-key-fielding_card:hover {
            border-color: #DEE2F4;
            box-shadow: var(--card-shadow-hover);
            transform: translateY(-2px);
        }

        div.st-key-full_stats_card {
            background: #ffffff;
            border: 1px solid var(--card-border);
            border-radius: 22px;
            box-shadow: var(--card-shadow);
            margin-bottom: 24px;
            padding: 22px 24px 24px;
        }

        div.st-key-runs_chart_card h4,
        div.st-key-top_scorers_card h4,
        div.st-key-top_wickets_card h4,
        div.st-key-form_card h4 {
            color: var(--ink);
            font-size: clamp(1.12rem, 1.35vw, 1.35rem);
            font-weight: 750;
            line-height: 1.25;
            margin: 0 0 20px;
        }

        div.st-key-top_scorers_card,
        div.st-key-top_wickets_card {
            padding: 22px 26px;
        }

        div.st-key-top_scorers_card h4,
        div.st-key-top_wickets_card h4 {
            margin-bottom: 14px;
        }

        div.st-key-top_scorers_card .progress-row,
        div.st-key-top_wickets_card .progress-row {
            gap: 12px;
            margin: 14px 0;
        }

        div.st-key-top_scorers_card .progress-row:first-child .progress-track,
        div.st-key-top_wickets_card .progress-row:first-child .progress-track {
            height: 8px;
        }

        div.st-key-top_scorers_card .progress-rank,
        div.st-key-top_wickets_card .progress-rank {
            height: 24px;
            width: 24px;
        }

        div.st-key-top_scorers_card .progress-average,
        div.st-key-top_wickets_card .progress-average {
            margin-top: 3px;
        }

        div.st-key-top_scorers_card .progress-track,
        div.st-key-top_wickets_card .progress-track {
            height: 8px;
        }

        .panel-header {
            align-items: flex-start;
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }

        .panel-header h4 {
            color: var(--ink);
            font-size: 1.08rem;
            margin: 0 0 14px;
        }

        .chart-legend,
        .form-legend {
            align-items: center;
            color: #727999;
            display: flex;
            flex-wrap: wrap;
            font-size: 0.84rem;
            gap: 18px;
        }

        .chart-legend span,
        .form-legend span {
            align-items: center;
            display: inline-flex;
            gap: 7px;
        }

        .legend-dot {
            border-radius: 999px;
            display: inline-block;
            height: 10px;
            width: 10px;
        }

        .legend-dot.current { background: #6D4DFF; }
        .legend-dot.previous { background: #C7C3FF; }
        .legend-dot.green { background: #10B981; }
        .legend-dot.slate { background: #94A3B8; }
        .legend-dot.red { background: #F43F5E; }

        .mini-select {
            background: #ffffff;
            border: 1px solid #e6e9f4;
            border-radius: 10px;
            color: #4d5371;
            font-size: 0.86rem;
            font-weight: 750;
            padding: 8px 13px;
        }

        .progress-row {
            align-items: center;
            display: grid;
            grid-template-columns: 30px minmax(0, 1fr) auto;
            gap: 14px;
            margin: 22px 0;
        }

        .progress-row:first-child .progress-name {
            font-size: 1.03rem;
            font-weight: 950;
        }

        .progress-row:first-child .progress-track {
            height: 10px;
        }

        .progress-rank {
            align-items: center;
            background: #F1F3FB;
            border-radius: 999px;
            color: #4B5374;
            display: inline-flex;
            font-size: 0.82rem;
            font-weight: 850;
            height: 26px;
            justify-content: center;
            width: 26px;
        }

        .progress-name {
            color: var(--ink);
            font-size: 0.98rem;
            font-weight: 850;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .progress-value {
            color: var(--ink);
            font-size: 0.94rem;
            text-align: right;
        }

        .progress-value strong {
            display: block;
            font-weight: 900;
            white-space: nowrap;
        }

        .progress-average {
            color: #858ba6;
            display: block;
            font-size: 0.78rem;
            font-weight: 650;
            margin-top: 5px;
            white-space: nowrap;
        }

        .progress-track {
            background: #EEF0F8;
            border-radius: 999px;
            grid-column: 2 / 4;
            height: 9px;
            overflow: hidden;
        }

        .progress-track div {
            background: linear-gradient(90deg, #8B5CF6, #4F46E5);
            border-radius: 999px;
            height: 100%;
        }

        .team-leader-card {
            background: #ffffff;
            border: 1px solid var(--card-border);
            border-radius: 22px;
            box-shadow: var(--card-shadow);
            margin-bottom: 24px;
            overflow: hidden;
            padding: 24px 26px;
            position: relative;
            transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
        }

        .team-leader-card:hover {
            border-color: #DEE2F4;
            box-shadow: var(--card-shadow-hover);
            transform: translateY(-2px);
        }

        .team-leader-card::before {
            background: linear-gradient(90deg, #6D4DFF, #3B82F6);
            content: "";
            height: 4px;
            left: 0;
            position: absolute;
            right: 0;
            top: 0;
        }

        .team-card-header {
            align-items: center;
            display: flex;
            justify-content: space-between;
            gap: 14px;
            margin-bottom: 20px;
        }

        .team-card-title {
            color: var(--ink);
            font-size: 1.14rem;
            font-weight: 850;
            line-height: 1.22;
        }

        .team-card-meta {
            background: #F3F5FC;
            border: 1px solid #E7EAF5;
            border-radius: 999px;
            color: #6D728E;
            font-size: 0.76rem;
            font-weight: 750;
            padding: 6px 10px;
            white-space: nowrap;
        }

        .mini-leader-grid {
            display: grid;
            gap: 24px;
            grid-template-columns: 1fr 1fr;
        }

        .mini-leader + .mini-leader {
            border-left: 1px solid #EEF1F8;
            padding-left: 24px;
        }

        .mini-leader {
            min-width: 0;
        }

        .mini-label-row {
            align-items: center;
            display: flex;
            gap: 7px;
        }

        .mini-icon {
            align-items: center;
            background: #F0EDFF;
            border-radius: 999px;
            color: #6D4DFF;
            display: inline-flex;
            font-size: 0.75rem;
            font-weight: 900;
            height: 24px;
            justify-content: center;
            width: 24px;
        }

        .mini-label {
            color: #727999;
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .mini-value-row {
            align-items: flex-start;
            display: flex;
            gap: 14px;
            justify-content: space-between;
            margin-top: 12px;
        }

        .mini-player {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 850;
            line-height: 1.22;
            min-width: 0;
        }

        .mini-stat {
            color: #4b37d8;
            font-size: 0.98rem;
            font-weight: 950;
            white-space: nowrap;
        }

        .mini-stat-block {
            flex: 0 0 auto;
            text-align: right;
        }

        .mini-average {
            color: #858ba6;
            font-size: 0.8rem;
            font-weight: 650;
            margin-top: 5px;
        }

        .mini-track {
            background: #EEF0F8;
            border-radius: 999px;
            height: 8px;
            margin-top: 14px;
            overflow: hidden;
        }

        .mini-track div {
            background: linear-gradient(90deg, #8B5CF6, #3B82F6);
            border-radius: 999px;
            height: 100%;
        }

        .form-row {
            align-items: center;
            border-bottom: 1px solid #eef0f6;
            display: grid;
            grid-template-columns: minmax(120px, 1fr) auto;
            gap: 12px;
            justify-content: space-between;
            padding: 12px 0;
        }

        .form-row strong {
            color: var(--ink);
            display: block;
            font-size: 0.9rem;
        }

        .form-row span {
            color: #7a7f9f;
            font-size: 0.78rem;
        }

        .pill-row {
            display: flex;
            gap: 8px;
            justify-content: flex-end;
        }

        .pill,
        .score-dot {
            border-radius: 999px;
            color: #ffffff !important;
            display: inline-flex;
            font-size: 0.74rem !important;
            font-weight: 850;
            justify-content: center;
            min-width: 30px;
            padding: 5px 7px;
        }

        .score-dot {
            align-items: center;
            height: 30px;
            min-width: 30px;
            padding: 0 7px;
        }

        .pill.green,
        .score-dot.green { background: #10B981; }
        .pill.purple,
        .score-dot.purple { background: #6D4DFF; }
        .pill.slate,
        .score-dot.slate,
        .score-dot.muted { background: #94A3B8; }
        .score-dot.duck { background: #F43F5E; }

        .form-legend {
            border-top: 1px solid #eef0f6;
            margin-top: 10px;
            padding-top: 14px;
        }

        .hof-card,
        .record-card,
        .milestone-card,
        .milestone-watch-card {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 16px;
            box-shadow: 0 14px 34px rgba(23, 27, 77, 0.055);
            margin-bottom: 18px;
            padding: 20px 22px;
        }

        .block-container:has(.hall-of-fame-page) .hof-card {
            margin-bottom: 18px;
            padding: 17px 19px;
        }

        .block-container:has(.hall-of-fame-page) .hof-progress-row {
            margin: 9px 0;
        }

        .block-container:has(.hall-of-fame-page) .progress-row {
            gap: 12px;
        }

        .block-container:has(.hall-of-fame-page) .progress-rank {
            height: 24px;
            width: 24px;
        }

        .block-container:has(.hall-of-fame-page) .progress-track {
            height: 7px;
        }

        .performance-card {
            min-height: 0;
        }

        .performance-row {
            align-items: center;
            border-bottom: 1px solid #eef0f6;
            display: grid;
            gap: 12px;
            grid-template-columns: 28px minmax(0, 1fr) auto;
            padding: 9px 0;
        }

        .performance-row:last-child {
            border-bottom: 0;
            padding-bottom: 0;
        }

        .performance-player strong {
            color: var(--ink);
            display: block;
            font-size: 0.9rem;
            font-weight: 950;
            line-height: 1.15;
        }

        .performance-player span {
            color: #7a809d;
            display: block;
            font-size: 0.73rem;
            font-weight: 750;
            margin-top: 3px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .performance-value {
            color: #4b37d8;
            font-size: 0.95rem;
            font-weight: 950;
            text-align: right;
            white-space: nowrap;
        }

        .identity-note {
            background: rgba(109, 77, 255, 0.08);
            border: 1px solid rgba(109, 77, 255, 0.15);
            border-radius: 14px;
            color: #4c4f75;
            font-size: 0.86rem;
            font-weight: 750;
            margin: 6px 0 18px;
            padding: 12px 14px;
        }

        .audit-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 4px 0 16px;
        }

        .audit-chip {
            background: #f1f4fb;
            border: 1px solid #e2e7f3;
            border-radius: 999px;
            color: #4c5171;
            display: inline-flex;
            font-size: 0.76rem;
            font-weight: 850;
            padding: 7px 10px;
        }

        .empty-profile-state {
            background: #ffffff;
            border: 1px dashed #d8ddec;
            border-radius: 16px;
            color: #747b98;
            font-weight: 800;
            margin-top: 18px;
            padding: 30px;
            text-align: center;
        }

        .player-hero-card {
            align-items: flex-start;
            background:
                radial-gradient(circle at right top, rgba(109, 77, 255, 0.14), transparent 20rem),
                #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 18px;
            box-shadow: 0 16px 38px rgba(23, 27, 77, 0.06);
            display: flex;
            justify-content: space-between;
            gap: 24px;
            margin: 18px 0 18px;
            padding: 24px 26px;
        }

        .profile-kicker {
            color: #6D4DFF;
            font-size: 0.74rem;
            font-weight: 900;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .profile-name {
            color: var(--ink);
            font-size: 1.8rem;
            font-weight: 950;
            line-height: 1.1;
        }

        .profile-meta {
            color: #747b98;
            font-size: 0.9rem;
            font-weight: 750;
            margin-top: 8px;
            max-width: 920px;
        }

        .profile-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: flex-end;
            min-width: 190px;
        }

        .profile-badge {
            background: linear-gradient(135deg, rgba(109,77,255,0.12), rgba(59,130,246,0.12));
            border: 1px solid rgba(109, 77, 255, 0.18);
            border-radius: 999px;
            color: #4b37d8;
            font-size: 0.76rem;
            font-weight: 900;
            padding: 8px 11px;
            white-space: nowrap;
        }

        .profile-breakdown-card {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 16px;
            box-shadow: 0 14px 34px rgba(23, 27, 77, 0.055);
            margin-bottom: 18px;
            padding: 20px 22px;
        }

        .profile-breakdown-card h4 {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 950;
            margin: 0 0 14px;
        }

        .profile-breakdown-card div {
            align-items: center;
            border-top: 1px solid #eef0f6;
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
        }

        .profile-breakdown-card div:first-of-type {
            border-top: 0;
        }

        .profile-breakdown-card span {
            color: #747b98;
            font-size: 0.82rem;
            font-weight: 800;
        }

        .profile-breakdown-card strong {
            color: var(--ink);
            font-size: 0.92rem;
            font-weight: 950;
        }

        .hof-progress-row {
            margin: 13px 0;
        }

        .record-card {
            min-height: 172px;
        }

        .record-label {
            color: #727999;
            font-size: 0.72rem;
            font-weight: 900;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .record-player {
            color: var(--ink);
            font-size: 1.08rem;
            font-weight: 950;
            line-height: 1.18;
            margin-top: 16px;
        }

        .record-value {
            color: #4b37d8;
            font-size: 1.38rem;
            font-weight: 950;
            margin-top: 8px;
        }

        .record-meta {
            color: #858ba6;
            font-size: 0.8rem;
            font-weight: 700;
            margin-top: 12px;
        }

        .milestone-group {
            border-bottom: 1px solid #eef0f6;
            padding: 14px 0;
        }

        .milestone-group:first-child {
            padding-top: 0;
        }

        .milestone-group:last-child {
            border-bottom: 0;
            padding-bottom: 0;
        }

        .milestone-group h4 {
            color: var(--ink);
            font-size: 0.96rem;
            font-weight: 950;
            margin: 0 0 10px;
        }

        .milestone-chip {
            background: #f1f4fb;
            border: 1px solid #e5e8f3;
            border-radius: 999px;
            color: #3d4263;
            display: inline-flex;
            font-size: 0.82rem;
            font-weight: 800;
            margin: 0 8px 8px 0;
            padding: 8px 11px;
        }

        .milestone-watch-card {
            min-height: 312px;
        }

        .block-container:has(.near-milestones-page) .page-title {
            font-size: clamp(2.3rem, 3vw, 3.2rem);
            max-width: 1040px;
            margin: 0 0 7px;
        }

        .block-container:has(.near-milestones-page) .club-label {
            color: #5B3DF5;
            margin: 0 0 9px;
        }

        .block-container:has(.near-milestones-page) .page-subtitle {
            color: #7a809d;
            font-size: 0.95rem;
            font-weight: 700;
            margin: 0 0 44px;
        }

        .block-container:has(.near-milestones-page) .overview-section-title {
            margin-top: 4px;
            margin-bottom: 16px;
        }

        .block-container:has(.near-milestones-page) .milestone-watch-card {
            margin-bottom: 24px;
            min-height: 0;
            padding: 17px 19px;
        }

        .block-container:has(.near-milestones-page) .milestone-watch-card .card-title {
            margin-bottom: 8px;
        }

        .block-container:has(.near-milestones-page) .milestone-watch-row {
            padding: 9px 0;
        }

        .block-container:has(.near-milestones-page) .milestone-watch-top {
            gap: 10px;
            margin-bottom: 6px;
        }

        .block-container:has(.near-milestones-page) .milestone-watch-top strong {
            font-size: 0.9rem;
        }

        .block-container:has(.near-milestones-page) .milestone-watch-top span {
            font-size: 0.75rem;
            margin-top: 3px;
        }

        .block-container:has(.near-milestones-page) .milestone-away {
            font-size: 0.76rem;
        }

        .block-container:has(.near-milestones-page) .milestone-watch-card .progress-track {
            height: 7px;
        }

        .milestone-watch-row {
            border-bottom: 1px solid #eef0f6;
            padding: 12px 0;
        }

        .milestone-watch-row:last-child {
            border-bottom: 0;
            padding-bottom: 0;
        }

        .milestone-watch-top {
            align-items: flex-start;
            display: flex;
            gap: 14px;
            justify-content: space-between;
            margin-bottom: 9px;
        }

        .milestone-watch-top strong {
            color: var(--ink);
            display: block;
            font-size: 0.93rem;
            font-weight: 950;
            line-height: 1.15;
        }

        .milestone-watch-top span {
            color: #7a809d;
            display: block;
            font-size: 0.78rem;
            font-weight: 750;
            margin-top: 4px;
        }

        .milestone-away {
            color: #4b37d8;
            flex: 0 0 auto;
            font-size: 0.8rem;
            font-weight: 900;
            text-align: right;
            white-space: nowrap;
        }

        .empty-state {
            color: #7a809d;
            font-size: 0.88rem;
            font-weight: 700;
            line-height: 1.45;
            padding: 18px 0 6px;
        }

        .card-title {
            color: var(--ink);
            font-size: 1.05rem;
            font-weight: 900;
            margin-bottom: 12px;
        }

        .compact-card-header {
            align-items: center;
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }

        .compact-card-header .card-title {
            margin-bottom: 0;
        }

        .compact-card-header a,
        .full-link {
            color: #6738f5 !important;
            font-size: 0.86rem;
            font-weight: 850;
            text-decoration: none;
        }

        .full-link {
            display: inline-block;
            margin-top: 10px;
        }

        div[data-testid="stExpander"] {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 16px;
            box-shadow: 0 14px 28px rgba(23, 27, 77, 0.05);
            overflow: hidden;
        }

        div[data-testid="stAlert"] {
            border-radius: 8px;
        }

        [data-testid="stHeadingWithActionElements"] h3 {
            font-size: 1.25rem;
            margin-top: 0.35rem;
        }

        @media (max-width: 760px) {
            .block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }

            .cv-hero {
                align-items: flex-start;
                flex-direction: column;
                padding: 11px 16px 9px;
            }

            .cv-hero:after {
                display: none;
            }

            div.st-key-filters_panel {
                padding: 10px 14px 8px;
            }

            .cv-section-title {
                align-items: flex-start;
                flex-direction: column;
                gap: 4px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(
    title: str,
    subtitle: str,
    context_items: list[str] | None = None,
) -> None:
    pills = "".join(
        f'<span class="cv-pill">{html.escape(item)}</span>'
        for item in (context_items or [])
        if item
    )
    context = f'<div class="cv-context-row">{pills}</div>' if pills else ""
    subtitle_html = (
        f'<p class="cv-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
    )
    hero_html = (
        '<section class="cv-hero">'
        '<div>'
        '<div class="cv-kicker">Cricket Club Intelligence</div>'
        f'<h1 class="cv-title">{html.escape(title)}</h1>'
        f"{subtitle_html}"
        f"{context}"
        "</div>"
        "</section>"
    )

    st.markdown(hero_html, unsafe_allow_html=True)


def section_title(title: str, detail: str | None = None) -> None:
    detail_html = f"<span>{html.escape(detail)}</span>" if detail else ""
    st.markdown(
        f"""
        <div class="cv-section-title">
            <h2>{html.escape(title)}</h2>
            {detail_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def callout(text: str) -> None:
    st.markdown(
        f'<div class="cv-callout">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )
