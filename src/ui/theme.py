from __future__ import annotations

import html
import re

import streamlit as st

from src.config.club_config import get_active_club_id, get_branding_value


FVCC_PRODUCTION_BRANDING = {
    "primary_colour": "#A31952",
    "secondary_colour": "#28485F",
    "accent_colour": "#D4A83A",
    "background_colour": "#F6F8FB",
    "link_colour": "#28485F",
    "link_hover_colour": "#1E3748",
}


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --pitch: #5B4BEB;
            --pitch-2: #7C5CFF;
            --grass: #22c7dc;
            --ink: #080B3F;
            --muted: #6D728E;
            --line: #E7EAF5;
            --surface: #ffffff;
            --surface-soft: #F7F8FC;
            --danger: #e64b68;
            --card-border: #E8EAF5;
            --card-shadow: 0 8px 24px rgba(20, 22, 60, 0.06);
            --card-shadow-hover: 0 16px 36px rgba(20, 22, 60, 0.10);
            color-scheme: light;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(103, 56, 245, 0.08), transparent 32rem),
                #f7f8fc;
            color: var(--ink);
        }

        div[data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            z-index: 100001;
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
            background: linear-gradient(135deg, var(--club-primary, #6b3cff), var(--club-accent, #5630d7));
            border-color: rgba(255, 255, 255, 0.13);
            box-shadow: 0 16px 34px rgba(var(--club-primary-rgb, 99, 64, 255), 0.36), inset 0 1px 0 rgba(255, 255, 255, 0.16);
            color: #ffffff !important;
        }

        section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {
            display: none;
        }

        div.st-key-mobile_nav_fallback {
            display: none;
        }

        .mobile-page-footer {
            display: none;
        }

        @media (min-width: 761px) {
            section[data-testid="stSidebar"],
            section[data-testid="stSidebar"][aria-expanded="false"],
            section[data-testid="stSidebar"][aria-expanded="true"] {
                display: block !important;
                left: 0 !important;
                margin-left: 0 !important;
                max-width: 232px !important;
                min-width: 232px !important;
                opacity: 1 !important;
                pointer-events: auto !important;
                transform: translateX(0) !important;
                visibility: visible !important;
                width: 232px !important;
                z-index: 100000 !important;
            }

            section[data-testid="stSidebar"] > div,
            section[data-testid="stSidebar"][aria-expanded="false"] > div,
            section[data-testid="stSidebar"][aria-expanded="true"] > div {
                display: block !important;
                max-width: 232px !important;
                min-width: 232px !important;
                opacity: 1 !important;
                transform: translateX(0) !important;
                visibility: visible !important;
                width: 232px !important;
            }

            div[data-testid="collapsedControl"] {
                display: none !important;
                visibility: hidden !important;
            }
        }

        .block-container {
            padding: 4.1rem 2.25rem 3rem;
            max-width: 1720px;
        }

        .block-container:has(.sticky-filter-spacer) {
            padding-top: 1.5rem;
        }

        .block-container:has(.near-milestones-page) {
            padding-top: 1.15rem;
        }

        h1, h2, h3 {
            letter-spacing: -0.02em;
        }

        div[data-testid="stTabs"] button,
        div[data-testid="stTabs"] [data-testid="stTab"],
        div[data-testid="stTabs"] [role="tab"] {
            border-radius: 999px;
            color: #737998;
            font-weight: 750;
            margin-right: 8px;
            min-height: 38px;
            padding: 8px 16px;
        }

        div[data-testid="stTabs"] button[aria-selected="true"],
        div[data-testid="stTabs"] button[data-selected="true"],
        div[data-testid="stTabs"] button[data-state="active"],
        div[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"],
        div[data-testid="stTabs"] [data-testid="stTab"][data-selected="true"],
        div[data-testid="stTabs"] [role="tab"][aria-selected="true"],
        div[data-testid="stTabs"] [role="tab"][data-selected="true"] {
            background: linear-gradient(135deg, var(--club-primary, var(--pitch)), var(--club-accent, var(--pitch-2)));
            color: #ffffff;
            border-bottom-color: transparent;
            box-shadow: 0 10px 24px rgba(var(--club-primary-rgb, 91, 75, 235), 0.20);
        }

        div[data-testid="stTabs"] [role="tablist"] {
            background: #F7F8FD;
            border: 1px solid #E9ECF6;
            border-radius: 999px;
            display: inline-flex;
            gap: 4px;
            margin-bottom: 18px;
            padding: 5px;
            width: fit-content;
            max-width: 100%;
        }

        div[data-testid="stTabs"] [data-baseweb="tab-border"],
        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            display: none;
        }

        div[data-testid="stTabs"] .react-aria-SelectionIndicator {
            display: none;
        }

        div[data-testid="stButtonGroup"] [data-baseweb="button-group"] {
            align-items: center;
            background: var(--club-primary-soft, #F7F8FD) !important;
            border: 1px solid rgba(var(--club-primary-rgb, 91, 75, 235), 0.18) !important;
            border-radius: 999px !important;
            display: inline-flex !important;
            flex-wrap: nowrap !important;
            gap: 4px !important;
            max-width: 100%;
            overflow-x: auto;
            padding: 5px !important;
            width: fit-content !important;
        }

        div[data-testid="stButtonGroup"] [data-baseweb="button-group"] > button,
        div[data-testid="stButtonGroup"] button[data-testid^="stBaseButton-segmented_control"] {
            background: transparent !important;
            border: 0 !important;
            border-radius: 999px !important;
            box-shadow: none !important;
            color: var(--club-muted, #737998) !important;
            flex: 0 0 auto !important;
            font-size: 0.9rem !important;
            font-weight: 800 !important;
            line-height: 1 !important;
            min-height: 38px !important;
            padding: 8px 16px !important;
            white-space: nowrap !important;
        }

        div[data-testid="stButtonGroup"] [data-baseweb="button-group"] > button[aria-checked="true"],
        div[data-testid="stButtonGroup"] [data-baseweb="button-group"] > button[aria-pressed="true"],
        div[data-testid="stButtonGroup"] [data-baseweb="button-group"] > button[aria-selected="true"],
        div[data-testid="stButtonGroup"] button[data-testid$="segmented_controlActive"] {
            background: linear-gradient(135deg, var(--club-primary, var(--pitch)), var(--club-secondary, var(--pitch-2))) !important;
            border-color: transparent !important;
            box-shadow: 0 10px 24px rgba(var(--club-primary-rgb, 91, 75, 235), 0.20) !important;
            color: #ffffff !important;
        }

        div[data-testid="stButtonGroup"] [data-baseweb="button-group"] > button[aria-checked="true"] *,
        div[data-testid="stButtonGroup"] [data-baseweb="button-group"] > button[aria-pressed="true"] *,
        div[data-testid="stButtonGroup"] [data-baseweb="button-group"] > button[aria-selected="true"] *,
        div[data-testid="stButtonGroup"] button[data-testid$="segmented_controlActive"] * {
            color: inherit !important;
        }

        div[data-testid="stButtonGroup"] button:focus-visible {
            box-shadow: 0 0 0 3px rgba(var(--club-primary-rgb, 91, 75, 235), 0.24) !important;
            outline: none !important;
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

        .season-v2-hero {
            align-items: stretch;
            background:
                radial-gradient(circle at 12% 18%, rgba(109, 74, 255, 0.20), transparent 30%),
                linear-gradient(135deg, #ffffff 0%, #f5f2ff 58%, #fff7fa 100%);
            border: 1px solid rgba(109, 74, 255, 0.14);
            border-radius: 24px;
            box-shadow: 0 22px 54px rgba(18, 18, 72, 0.10);
            display: grid;
            gap: 22px;
            grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
            margin: 22px 0 30px;
            overflow: hidden;
            padding: 28px;
            position: relative;
        }

        .season-v2-hero:after {
            background: linear-gradient(180deg, rgba(94, 58, 235, 0.96), rgba(118, 28, 85, 0.90));
            border-radius: 999px;
            content: "";
            height: 76%;
            opacity: 0.10;
            position: absolute;
            right: -52px;
            top: 12%;
            transform: rotate(-14deg);
            width: 170px;
        }

        .season-v2-hero-copy,
        .season-v2-hero-grid {
            position: relative;
            z-index: 1;
        }

        .season-v2-eyebrow,
        .season-v2-card-kicker,
        .season-v2-tile-label {
            color: #6d4aff;
            font-size: 0.76rem;
            font-weight: 950;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .season-v2-hero h2 {
            color: var(--ink);
            font-size: clamp(2.1rem, 5vw, 4.5rem);
            letter-spacing: 0;
            line-height: 0.94;
            margin: 8px 0 12px;
        }

        .season-v2-hero p {
            color: var(--muted);
            font-size: 1.06rem;
            font-weight: 750;
            line-height: 1.52;
            margin: 0;
            max-width: 720px;
        }

        .season-v2-hero-grid,
        .season-v2-card-grid,
        .season-v2-performance-grid,
        .season-v2-insight-grid,
        .season-v2-role-grid {
            display: grid;
            gap: 14px;
        }

        .season-v2-hero-grid {
            align-self: center;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .season-v2-card-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin: 12px 0 30px;
        }

        .season-v2-performance-grid,
        .season-v2-insight-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin: 12px 0 30px;
        }

        .season-v2-role-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .season-v2-hero-tile,
        .season-v2-award-card,
        .season-v2-performance-card,
        .season-v2-role-card,
        .season-v2-record-card,
        .season-v2-insight-card,
        .season-v2-panel,
        .season-v2-empty {
            background: rgba(255, 255, 255, 0.90);
            border: 1px solid rgba(15, 20, 68, 0.08);
            border-radius: 18px;
            box-shadow: 0 14px 34px rgba(18, 18, 72, 0.07);
        }

        .season-v2-hero-tile {
            min-height: 126px;
            padding: 16px;
        }

        .season-v2-award-card,
        .season-v2-performance-card,
        .season-v2-role-card,
        .season-v2-record-card,
        .season-v2-insight-card,
        .season-v2-panel {
            padding: 16px;
        }

        .season-v2-tile-value,
        .season-v2-card-value,
        .season-v2-performance-value {
            color: #4d2ee8;
            font-weight: 950;
            letter-spacing: 0;
            line-height: 1.08;
            margin: 8px 0;
        }

        .season-v2-tile-value {
            color: var(--ink);
            font-size: 1.55rem;
        }

        .season-v2-card-value,
        .season-v2-performance-value {
            font-size: 1.36rem;
        }

        .season-v2-card-player,
        .season-v2-card-player a {
            color: var(--ink) !important;
            font-size: 1.05rem;
            font-weight: 950;
            line-height: 1.16;
            margin-top: 10px;
            text-decoration: none !important;
        }

        .season-v2-tile-detail,
        .season-v2-card-reason,
        .season-v2-pulse-meta {
            color: var(--muted);
            font-size: 0.85rem;
            font-weight: 750;
            line-height: 1.35;
        }

        .season-v2-pulse-strip {
            display: grid;
            gap: 14px;
            grid-auto-columns: minmax(248px, 1fr);
            grid-auto-flow: column;
            margin: 12px 0 30px;
            overflow-x: auto;
            padding-bottom: 6px;
        }

        .season-v2-pulse-card {
            background: #ffffff;
            border: 1px solid rgba(15, 20, 68, 0.08);
            border-radius: 18px;
            box-shadow: 0 12px 30px rgba(18, 18, 72, 0.07);
            min-height: 178px;
            padding: 16px;
        }

        .season-v2-result {
            border-radius: 999px;
            display: inline-flex;
            font-size: 0.72rem;
            font-weight: 950;
            letter-spacing: 0.08em;
            margin-bottom: 12px;
            padding: 6px 10px;
        }

        .season-v2-result.won { background: #dff8e9; color: #147a43; }
        .season-v2-result.lost { background: #fde8ee; color: #b82146; }
        .season-v2-result.draw,
        .season-v2-result.tie { background: #eef1f7; color: #5c657c; }
        .season-v2-result.unknown { background: #f4f0ff; color: #5b3bea; }

        .season-v2-pulse-opponent {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 950;
            line-height: 1.18;
            margin-bottom: 4px;
        }

        .season-v2-pulse-line {
            color: var(--ink);
            font-size: 0.88rem;
            font-weight: 800;
            margin-top: 8px;
        }

        .season-v2-pulse-link {
            margin-top: 10px;
        }

        .season-v2-pulse-link:empty {
            display: none;
        }

        .season-v2-depth-row {
            display: grid;
            gap: 8px;
            grid-template-columns: 92px minmax(120px, 1fr) 128px;
            padding: 10px 0;
        }

        .season-v2-depth-row + .season-v2-depth-row {
            border-top: 1px solid rgba(15, 20, 68, 0.08);
        }

        .season-v2-depth-label,
        .season-v2-depth-meta {
            color: var(--muted);
            font-size: 0.85rem;
            font-weight: 850;
        }

        .season-v2-depth-track {
            align-self: center;
            background: #eef1f7;
            border-radius: 999px;
            height: 11px;
            overflow: hidden;
        }

        .season-v2-depth-track span {
            background: linear-gradient(90deg, #6d4aff, #8b2e6b);
            border-radius: inherit;
            display: block;
            height: 100%;
        }

        .season-v2-record-badge {
            background: #f4f0ff;
            border-radius: 999px;
            color: #5b3bea;
            display: inline-flex;
            font-size: 0.72rem;
            font-weight: 950;
            padding: 5px 9px;
        }

        .season-v2-insight-card h3 {
            color: var(--ink);
            font-size: 1.25rem;
            font-weight: 950;
            margin: 0 0 10px;
        }

        .season-v2-insight-card ul {
            color: var(--muted);
            font-size: 0.95rem;
            font-weight: 760;
            line-height: 1.48;
            margin: 0;
            padding-left: 20px;
        }

        .season-v2-empty {
            color: var(--muted);
            font-size: 0.92rem;
            font-weight: 800;
            margin: 10px 0 28px;
            padding: 18px;
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
            line-height: 1.22 !important;
            min-height: 42px !important;
            white-space: normal !important;
            word-break: normal !important;
            overflow-wrap: anywhere !important;
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
            gap: 15px;
            margin-bottom: 36px;
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
            height: 58px;
            justify-content: center;
            width: 48px;
        }

        .side-shield-logo {
            background:
                radial-gradient(circle at 32% 18%, rgba(255,255,255,0.98), rgba(255,255,255,0.88) 58%, rgba(216,232,245,0.98) 100%);
            border: 1px solid rgba(255, 255, 255, 0.88);
            border-radius: 19px;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,0.92),
                0 16px 34px rgba(0,0,0,0.24),
                0 0 0 5px rgba(255,255,255,0.10);
            height: 64px;
            overflow: hidden;
            padding: 5px;
            width: 58px;
        }

        .side-shield-logo img {
            display: block;
            height: 100%;
            object-fit: contain;
            transform-origin: center;
            width: 100%;
        }

        .side-shield-logo-zoom img {
            transform: scale(1.12);
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
            margin-top: 28px;
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
            text-decoration: none !important;
            transition: background 160ms ease, box-shadow 160ms ease, color 160ms ease;
        }

        .side-nav-item span {
            color: inherit;
            font-size: 1rem;
            text-align: center;
            width: 22px;
        }

        .side-nav-item.active {
            background: linear-gradient(135deg, var(--club-primary, #6b3cff), var(--club-accent, #5630d7));
            box-shadow: 0 16px 34px rgba(var(--club-primary-rgb, 99, 64, 255), 0.38);
            color: #ffffff !important;
        }

        .side-nav-item:hover,
        .side-nav-item:focus-visible {
            background: rgba(255, 255, 255, 0.08);
            color: #ffffff !important;
            text-decoration: none !important;
        }

        .side-footer {
            border-top: 1px solid rgba(255, 255, 255, 0.14);
            color: rgba(255, 255, 255, 0.78);
            font-size: 0.74rem;
            margin-top: 52px;
            padding: 20px 2px 0;
            width: 100%;
        }

        .side-footer-label {
            color: rgba(255, 255, 255, 0.72);
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .side-footer-names {
            color: #ffffff;
            font-size: 0.8rem;
            font-weight: 500;
            line-height: 1.35;
            margin-bottom: 12px;
        }

        .side-footer-contact {
            color: rgba(255, 255, 255, 0.66);
            font-size: 0.66rem;
            line-height: 1.35;
        }

        .side-footer-contact a {
            color: rgba(255, 255, 255, 0.84);
            display: inline-block;
            text-decoration: none;
            word-break: normal;
            white-space: nowrap;
        }

        .scorebook-version {
            color: rgba(255, 255, 255, 0.58);
            font-size: 0.68rem;
            font-weight: 600;
            line-height: 1.35;
            margin-top: 10px;
            opacity: 0.78;
            overflow-wrap: anywhere;
        }

        .side-build-marker {
            color: rgba(255, 255, 255, 0.46);
            font-size: 0.52rem;
            font-weight: 650;
            line-height: 1.35;
            margin-top: 12px;
            overflow-wrap: anywhere;
        }

        .routing-debug {
            border-top: 1px solid rgba(255, 255, 255, 0.10);
            color: rgba(255, 255, 255, 0.48) !important;
            font-size: 0.58rem;
            line-height: 1.45;
            margin-top: 14px;
            padding-top: 10px;
            word-break: break-word;
        }

        .page-kicker {
            color: var(--ink);
            font-size: 18px;
            font-weight: 600;
            margin: 0 0 18px;
        }

        .club-label {
            color: var(--club-primary, #5B3DF5);
            font-size: clamp(1.5rem, 1.75vw, 1.75rem);
            font-weight: 800;
            letter-spacing: 0;
            line-height: 1.2;
            margin: 0 0 10px;
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
            padding-top: 1.15rem;
        }

        .block-container:has(.hall-of-fame-page) .page-title {
            font-size: clamp(2.8rem, 3.6vw, 3.75rem);
            margin: 0 0 4px;
        }

        .block-container:has(.hall-of-fame-page) .club-label {
            color: var(--club-primary, #5B3DF5);
            font-weight: 800;
            margin: 0 0 8px;
        }

        .block-container:has(.hall-of-fame-page) .page-subtitle {
            color: #747b98;
            font-size: 1rem;
            font-weight: 700;
            margin: 0 0 6px;
        }

        .page-note {
            color: #858ba6;
            font-size: 0.86rem;
            font-style: italic;
            font-weight: 500;
            line-height: 1.35;
            margin: 0 0 28px;
        }

        .block-container:has(.hall-of-fame-v2-page) {
            padding-top: 1.15rem;
        }

        .hof-v2-hero {
            background:
                linear-gradient(135deg, var(--club-primary, rgba(8, 11, 63, 0.95)), var(--club-accent, rgba(29, 22, 105, 0.94))),
                radial-gradient(circle at 82% 24%, rgba(255, 245, 221, 0.25), transparent 24rem);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 34px;
            box-shadow: 0 22px 52px rgba(23, 27, 77, 0.08);
            color: #ffffff;
            overflow: hidden;
            padding: 34px;
            position: relative;
        }

        .hof-v2-hero::after {
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 999px;
            content: "";
            height: 280px;
            position: absolute;
            right: -96px;
            top: -110px;
            width: 280px;
        }

        .hof-v2-hero-grid {
            display: grid;
            gap: 28px;
            grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.7fr);
            position: relative;
            z-index: 1;
        }

        .hof-v2-eyebrow {
            color: rgba(255, 255, 255, 0.82);
            font-size: 0.82rem;
            font-weight: 900;
            letter-spacing: 0.12em;
            margin-bottom: 14px;
            text-transform: uppercase;
        }

        .hof-v2-hero h1 {
            color: #ffffff;
            font-size: clamp(3.15rem, 7vw, 6.8rem);
            font-weight: 900;
            letter-spacing: 0;
            line-height: 0.88;
            margin: 0 0 18px;
            max-width: 780px;
        }

        .hof-v2-hero-copy {
            color: rgba(255, 255, 255, 0.86);
            font-size: clamp(1.02rem, 1.7vw, 1.26rem);
            font-weight: 650;
            line-height: 1.5;
            margin: 0;
            max-width: 700px;
        }

        .hof-v2-source-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 24px;
        }

        .hof-v2-source-badges span,
        .hof-v2-verified-badge {
            align-items: center;
            background: rgba(255, 255, 255, 0.10);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 999px;
            color: #ffffff;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 850;
            gap: 7px;
            padding: 8px 11px;
            white-space: nowrap;
        }

        .hof-v2-hero-stats {
            display: grid;
            gap: 12px;
            grid-template-columns: 1fr 1fr;
        }

        .hof-v2-hero-stat {
            background: rgba(255, 255, 255, 0.10);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 22px;
            min-height: 126px;
            padding: 17px;
        }

        .hof-v2-hero-stat strong {
            color: #ffffff;
            display: block;
            font-size: 1.95rem;
            font-weight: 950;
            line-height: 1;
            margin-bottom: 8px;
        }

        .hof-v2-hero-stat span {
            color: rgba(255, 255, 255, 0.80);
            display: block;
            font-size: 0.84rem;
            font-weight: 780;
            line-height: 1.3;
        }

        .hof-v2-record-nav {
            align-items: center;
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid rgba(231, 230, 245, 0.95);
            border-radius: 24px;
            box-shadow: 0 10px 26px rgba(23, 27, 77, 0.055);
            display: flex;
            gap: 8px;
            margin: 26px 0 34px;
            overflow-x: auto;
            padding: 8px;
        }

        .hof-v2-record-nav a {
            border-radius: 999px;
            color: #3f4565;
            display: inline-flex;
            font-size: 0.87rem;
            font-weight: 900;
            padding: 12px 16px;
            text-decoration: none;
            white-space: nowrap;
        }

        .hof-v2-record-nav a.active {
            background: var(--club-primary-soft, #f1edff);
            color: var(--club-primary, #4b37d8);
        }

        .hof-v2-section {
            margin: 34px 0 0;
        }

        .hof-v2-section-head {
            align-items: flex-end;
            display: flex;
            gap: 18px;
            justify-content: space-between;
            margin: 0 0 18px;
        }

        .hof-v2-section-title h2 {
            color: var(--ink);
            font-size: clamp(2rem, 4.5vw, 3.35rem);
            font-weight: 900;
            letter-spacing: 0;
            line-height: 1;
            margin: 0 0 8px;
        }

        .hof-v2-section-title p,
        .hof-v2-muted {
            color: #687093;
            font-size: 0.95rem;
            font-weight: 680;
            line-height: 1.45;
            margin: 0;
        }

        .hof-v2-trust-chip {
            align-items: center;
            background: #ffffff;
            border: 1px solid #e7e6f5;
            border-radius: 999px;
            color: var(--club-primary, #4b37d8);
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 900;
            gap: 7px;
            padding: 8px 11px;
            white-space: nowrap;
        }

        .hof-v2-grid-2,
        .hof-v2-grid-3,
        .hof-v2-grid-4,
        .hof-v2-record-grid {
            display: grid;
            gap: 16px;
        }

        .hof-v2-grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .hof-v2-grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .hof-v2-grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
        .hof-v2-record-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }

        .hof-v2-top-gap {
            margin-top: 16px;
        }

        .hof-v2-card {
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid rgba(231, 230, 245, 0.98);
            border-radius: 26px;
            box-shadow: 0 10px 26px rgba(23, 27, 77, 0.055);
            padding: 20px;
        }

        .hof-v2-gold-card {
            background:
                linear-gradient(90deg, rgba(244, 194, 79, 0.72) 0 5px, transparent 5px),
                radial-gradient(circle at 94% 0%, rgba(255, 210, 96, 0.17), transparent 12rem),
                #ffffff;
            border-color: #ebe5d7;
        }

        .hof-v2-kicker,
        .hof-v2-record-title {
            color: #687093;
            font-size: 0.78rem;
            font-weight: 950;
            letter-spacing: 0.08em;
            margin-bottom: 9px;
            text-transform: uppercase;
        }

        .hof-v2-card h3 {
            color: var(--ink);
            font-size: 1.32rem;
            font-weight: 900;
            letter-spacing: 0;
            line-height: 1.12;
            margin: 0 0 10px;
        }

        .hof-v2-timeline {
            display: grid;
            gap: 0;
        }

        .hof-v2-trophy-row {
            align-items: center;
            border-bottom: 1px solid #ece8dc;
            display: grid;
            gap: 14px;
            grid-template-columns: 110px minmax(0, 1fr) auto;
            padding: 14px 0;
        }

        .hof-v2-trophy-row:first-child {
            padding-top: 0;
        }

        .hof-v2-trophy-row:last-child {
            border-bottom: 0;
            padding-bottom: 0;
        }

        .hof-v2-trophy-year a {
            color: #4b37d8;
            font-size: 0.9rem;
            font-weight: 950;
            text-decoration: none;
        }

        .hof-v2-trophy-main strong {
            color: var(--ink);
            display: block;
            font-size: 0.98rem;
            line-height: 1.24;
        }

        .hof-v2-trophy-main span {
            color: #687093;
            display: block;
            font-size: 0.82rem;
            font-weight: 690;
            line-height: 1.38;
            margin-top: 4px;
        }

        .hof-v2-trophy-result {
            display: grid;
            gap: 7px;
            justify-items: end;
        }

        .hof-v2-result-pill {
            background: #fff5dd;
            border: 1px solid #f0d89e;
            border-radius: 999px;
            color: #a76800;
            display: inline-flex;
            font-size: 0.76rem;
            font-weight: 950;
            padding: 7px 10px;
            white-space: nowrap;
        }

        .hof-v2-subtle-link {
            background: var(--club-primary-soft, #f8f6ff);
            border: 1px solid rgba(var(--club-primary-rgb, 75, 55, 216), 0.20);
            border-radius: 999px;
            color: var(--club-link, #4b37d8) !important;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 900;
            padding: 8px 10px;
            text-decoration: none;
            white-space: nowrap;
        }

        .hof-v2-leader-list {
            display: grid;
            gap: 10px;
            margin-top: 14px;
        }

        .hof-v2-rank-row {
            align-items: center;
            border-bottom: 1px solid #eef0f6;
            display: grid;
            gap: 10px;
            grid-template-columns: 32px minmax(0, 1fr) auto;
            padding: 8px 0;
        }

        .hof-v2-rank-row:last-child {
            border-bottom: 0;
        }

        .hof-v2-rank {
            align-items: center;
            background: var(--club-primary-soft, #f1edff);
            border: 1px solid rgba(var(--club-primary-rgb, 75, 55, 216), 0.20);
            border-radius: 999px;
            color: var(--club-primary, #4b37d8);
            display: inline-flex;
            font-size: 0.8rem;
            font-weight: 950;
            height: 28px;
            justify-content: center;
            width: 28px;
        }

        .hof-v2-rank.gold {
            background: #fff5dd;
            border-color: #f0d89e;
            color: #a76800;
        }

        .hof-v2-rank-row strong,
        .hof-v2-rank-row a {
            color: var(--ink);
            font-size: 0.94rem;
            font-weight: 900;
            min-width: 0;
            overflow-wrap: anywhere;
            text-decoration: none;
        }

        .hof-v2-rank-row span:last-child {
            color: #687093;
            font-size: 0.82rem;
            font-weight: 800;
            text-align: right;
            white-space: nowrap;
        }

        .hof-v2-performance-hero {
            background:
                linear-gradient(180deg, #ffffff 0%, var(--club-bg, #fbfaff) 100%);
            min-height: 260px;
        }

        .hof-v2-performance-value {
            color: var(--club-primary, var(--ink));
            font-size: clamp(3.2rem, 8vw, 5.2rem);
            font-weight: 950;
            line-height: 0.9;
            margin: 14px 0 12px;
        }

        .hof-v2-performance-player,
        .hof-v2-record-player {
            color: var(--ink);
            font-size: 1.12rem;
            font-weight: 950;
            line-height: 1.18;
            margin-bottom: 8px;
        }

        .hof-v2-performance-player a,
        .hof-v2-record-player a,
        .hof-v2-season-card a {
            color: var(--club-link, #0068c9);
            text-decoration: none;
        }

        .hof-v2-fastest-panel {
            background:
                linear-gradient(135deg, var(--club-primary, #080b3f), var(--club-accent, #2d2280));
            border-radius: 28px;
            box-shadow: 0 22px 52px rgba(23, 27, 77, 0.08);
            color: #ffffff;
            overflow: hidden;
            padding: 24px;
        }

        .hof-v2-fastest-panel .hof-v2-kicker {
            color: rgba(255, 255, 255, 0.82);
            margin: 18px 0 12px;
        }

        .hof-v2-race-list {
            display: grid;
            gap: 10px;
        }

        .hof-v2-race-row {
            align-items: center;
            background: rgba(255, 255, 255, 0.10);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 18px;
            display: grid;
            gap: 12px;
            grid-template-columns: 30px minmax(0, 1fr) auto;
            padding: 12px;
        }

        .hof-v2-race-row strong,
        .hof-v2-race-row a {
            color: #ffffff;
            font-size: 0.92rem;
            font-weight: 900;
            text-decoration: none;
        }

        .hof-v2-race-row strong span {
            color: rgba(255, 255, 255, 0.74);
            display: block;
            font-size: 0.78rem;
            font-weight: 700;
            margin-top: 4px;
        }

        .hof-v2-performance-hero .hof-v2-muted a.season-overview-link,
        .hof-v2-performance-hero .hof-v2-muted a.season-overview-link:visited {
            color: var(--club-muted-text, #66758D) !important;
            font-weight: 800;
        }

        .hof-v2-race-time {
            color: var(--club-secondary-soft, #fff5dd);
            font-size: 0.9rem;
            font-weight: 950;
            white-space: nowrap;
        }

        .hof-v2-record-card {
            min-height: 190px;
        }

        .hof-v2-record-value {
            color: var(--club-primary, #4b37d8);
            font-size: 1.8rem;
            font-weight: 950;
            line-height: 1;
            margin: 12px 0 10px;
        }

        .hof-v2-burgundy-card {
            background:
                linear-gradient(135deg, #fff, #fff1f5);
            border-color: #f0d1dc;
        }

        .hof-v2-burgundy-card .hof-v2-record-value {
            color: #7a1735;
        }

        .hof-v2-season-card {
            align-items: end;
            display: grid;
            gap: 16px;
            grid-template-columns: minmax(0, 1fr) auto;
            min-height: 210px;
        }

        .hof-v2-season-score {
            color: var(--club-primary, #4b37d8);
            font-size: 2.2rem;
            font-weight: 950;
            line-height: 1;
            text-align: right;
        }

        .hof-v2-trust-note {
            color: #687093;
            font-size: 0.9rem;
            font-weight: 700;
            line-height: 1.45;
            margin-top: 14px;
        }

        .hof-v2-trust-note strong {
            color: var(--ink);
        }

        .hof-v2-decision-panel {
            display: grid;
            gap: 16px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .hof-v2-decision {
            background: #ffffff;
            border: 1px solid #e7e6f5;
            border-radius: 24px;
            box-shadow: 0 10px 26px rgba(23, 27, 77, 0.055);
            padding: 20px;
        }

        .hof-v2-decision h3 {
            color: var(--ink);
            font-size: 1.2rem;
            font-weight: 950;
            margin: 0 0 10px;
        }

        .hof-v2-decision ul {
            color: #687093;
            font-size: 0.9rem;
            font-weight: 680;
            line-height: 1.45;
            margin: 0;
            padding-left: 18px;
        }

        .block-container:has(.seasons-page) {
            padding-top: 1.15rem;
        }

        .block-container:has(.seasons-page) .page-title {
            font-size: clamp(2.8rem, 3.6vw, 3.75rem);
            margin: 0 0 4px;
        }

        .block-container:has(.seasons-page) .club-label {
            color: #5B3DF5;
            font-weight: 800;
            margin: 0 0 8px;
        }

        .block-container:has(.seasons-page) .page-subtitle {
            color: #747b98;
            font-size: 1rem;
            font-weight: 500;
            margin: 0 0 6px;
        }

        .seasons-context-line {
            color: #747b98;
            font-size: 0.9rem;
            font-weight: 400;
            margin: -4px 0 18px;
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
            transform: translateY(-2px);
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
            margin: 8px 0 0;
            padding-left: 0;
            transform: translateY(-2px);
        }

        .filter-context-line > span:first-child {
            color: #535a78;
            font-weight: 750;
        }

        div.st-key-season_controls {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid rgba(226, 230, 244, 0.96);
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(20, 22, 60, 0.06);
            margin: 0 0 26px;
            padding: 16px 18px 14px;
        }

        div.st-key-season_controls div[data-testid="stHorizontalBlock"] {
            align-items: flex-end;
        }

        div.st-key-season_controls div[data-baseweb="select"] > div {
            align-items: center;
            background: #ffffff;
            border: 1px solid #E4E8F4;
            border-radius: 14px;
            box-shadow: 0 5px 12px rgba(20, 23, 67, 0.03);
            display: flex;
            min-height: 48px;
            text-align: left;
        }

        div.st-key-season_controls div[data-baseweb="select"] div {
            text-align: left;
        }

        div.st-key-season_controls div[data-baseweb="select"] [role="button"],
        div.st-key-season_controls div[data-baseweb="select"] [aria-selected],
        div.st-key-season_controls div[data-baseweb="select"] [class*="singleValue"] {
            align-items: center;
            justify-content: flex-start;
            min-height: 48px;
            text-align: left;
        }

        .simple-filter-label {
            color: #525a78;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.055em;
            line-height: 1;
            margin: 0 0 7px;
            text-transform: uppercase;
            transform: translateY(-2px);
        }

        .simple-filter-context {
            color: #535a78;
            font-size: 0.9rem;
            font-weight: 750;
            line-height: 1.35;
            margin: 12px 0 0;
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

        .section-subtext {
            color: #747b99;
            font-size: 0.96rem;
            font-weight: 500;
            line-height: 1.45;
            margin: -14px 0 20px;
        }

        .section-title-mobile {
            display: none;
        }

        div[class*="st-key-hof_"][class*="_control"] {
            margin: -8px 0 18px;
        }

        div[class*="st-key-hof_"][class*="_control"] .stButton {
            align-items: flex-start;
            display: flex;
            justify-content: flex-start;
        }

        div[class*="st-key-hof_"][class*="_control"] .stButton > button {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: #5B3DF5 !important;
            display: inline-flex !important;
            font-size: 0.82rem !important;
            font-weight: 800 !important;
            line-height: 1.2 !important;
            min-height: 0 !important;
            padding: 2px 0 !important;
            text-align: left !important;
            width: auto !important;
        }

        div[class*="st-key-hof_"][class*="_control"] .stButton > button:hover,
        div[class*="st-key-hof_"][class*="_control"] .stButton > button:focus {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: #4324D8 !important;
            text-decoration: underline;
            text-underline-offset: 3px;
        }

        .improver-grid {
            display: grid;
            gap: 20px;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-bottom: 10px;
        }

        .improver-card,
        .improver-empty {
            background: #ffffff;
            border: 1px solid var(--card-border);
            border-radius: 20px;
            box-shadow: var(--card-shadow);
            padding: 22px 24px;
        }

        .improver-empty {
            color: #747b99;
            font-size: 0.95rem;
            margin-bottom: 10px;
        }

        .improver-label {
            color: #727999;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .improver-player {
            color: var(--ink);
            font-size: 1.14rem;
            font-weight: 900;
            line-height: 1.25;
            margin-top: 12px;
        }

        a.player-profile-link,
        a.season-overview-link,
        a.scorecard-link,
        a.player-profile-link:visited,
        a.season-overview-link:visited,
        a.scorecard-link:visited,
        a[href*="page=player-profile"][href*="player="],
        a[href*="page=player-profile"][href*="player="]:visited,
        a[href*="page=player-profile"][href*="player_id="],
        a[href*="page=player-profile"][href*="player_id="]:visited,
        a[href*="page=season-overview"][href*="season="],
        a[href*="page=season-overview"][href*="season="]:visited,
        a[href*="page=season_overview"][href*="season="],
        a[href*="page=season_overview"][href*="season="]:visited,
        a[href*="play.cricket.com.au/match/"],
        a[href*="play.cricket.com.au/match/"]:visited,
        div[data-testid="stDataFrame"] a[href*="page=player-profile"][href*="player="],
        div[data-testid="stDataFrame"] a[href*="page=player-profile"][href*="player="]:visited,
        div[data-testid="stDataFrame"] a[href*="page=player-profile"][href*="player_id="],
        div[data-testid="stDataFrame"] a[href*="page=player-profile"][href*="player_id="]:visited,
        div[data-testid="stDataFrame"] a[href*="page=season-overview"][href*="season="],
        div[data-testid="stDataFrame"] a[href*="page=season-overview"][href*="season="]:visited,
        div[data-testid="stDataFrame"] a[href*="page=season_overview"][href*="season="],
        div[data-testid="stDataFrame"] a[href*="page=season_overview"][href*="season="]:visited,
        div[data-testid="stDataFrame"] a[href*="play.cricket.com.au/match/"],
        div[data-testid="stDataFrame"] a[href*="play.cricket.com.au/match/"]:visited {
            color: inherit !important;
            cursor: pointer;
            font: inherit;
            font-weight: inherit;
            text-decoration: none !important;
        }

        a.player-profile-link:hover,
        a.season-overview-link:hover,
        a.scorecard-link:hover,
        a.player-profile-link:focus-visible,
        a.season-overview-link:focus-visible,
        a.scorecard-link:focus-visible,
        a[href*="page=player-profile"][href*="player="]:hover,
        a[href*="page=player-profile"][href*="player="]:focus-visible,
        a[href*="page=player-profile"][href*="player_id="]:hover,
        a[href*="page=player-profile"][href*="player_id="]:focus-visible,
        a[href*="page=season-overview"][href*="season="]:hover,
        a[href*="page=season-overview"][href*="season="]:focus-visible,
        a[href*="page=season_overview"][href*="season="]:hover,
        a[href*="page=season_overview"][href*="season="]:focus-visible,
        a[href*="play.cricket.com.au/match/"]:hover,
        a[href*="play.cricket.com.au/match/"]:focus-visible,
        div[data-testid="stDataFrame"] a[href*="page=player-profile"][href*="player="]:hover,
        div[data-testid="stDataFrame"] a[href*="page=player-profile"][href*="player="]:focus-visible,
        div[data-testid="stDataFrame"] a[href*="page=player-profile"][href*="player_id="]:hover,
        div[data-testid="stDataFrame"] a[href*="page=player-profile"][href*="player_id="]:focus-visible,
        div[data-testid="stDataFrame"] a[href*="page=season-overview"][href*="season="]:hover,
        div[data-testid="stDataFrame"] a[href*="page=season-overview"][href*="season="]:focus-visible,
        div[data-testid="stDataFrame"] a[href*="page=season_overview"][href*="season="]:hover,
        div[data-testid="stDataFrame"] a[href*="page=season_overview"][href*="season="]:focus-visible,
        div[data-testid="stDataFrame"] a[href*="play.cricket.com.au/match/"]:hover,
        div[data-testid="stDataFrame"] a[href*="play.cricket.com.au/match/"]:focus-visible {
            color: #4b37d8 !important;
            text-decoration: underline !important;
            text-underline-offset: 3px;
        }

        a.player-profile-link:focus-visible,
        a.season-overview-link:focus-visible,
        a.scorecard-link:focus-visible,
        a[href*="page=player-profile"][href*="player="]:focus-visible,
        a[href*="page=player-profile"][href*="player_id="]:focus-visible,
        a[href*="page=season-overview"][href*="season="]:focus-visible,
        a[href*="page=season_overview"][href*="season="]:focus-visible,
        a[href*="play.cricket.com.au/match/"]:focus-visible {
            border-radius: 4px;
            outline: 2px solid rgba(75, 55, 216, 0.35);
            outline-offset: 2px;
        }

        a.scorecard-link,
        a.scorecard-link:visited,
        a[href*="play.cricket.com.au/match/"],
        a[href*="play.cricket.com.au/match/"]:visited,
        div[data-testid="stDataFrame"] a[href*="play.cricket.com.au/match/"],
        div[data-testid="stDataFrame"] a[href*="play.cricket.com.au/match/"]:visited {
            color: #4b37d8 !important;
            font-weight: 700;
        }

        .improver-gain {
            color: #109768;
            font-size: 1.4rem;
            font-weight: 950;
            line-height: 1.1;
            margin-top: 12px;
        }

        .improver-gain span {
            background: rgba(16, 151, 104, 0.10);
            border-radius: 999px;
            color: #0f8f63;
            display: inline-flex;
            font-size: 0.76rem;
            font-weight: 850;
            margin-left: 8px;
            padding: 5px 8px;
            vertical-align: middle;
        }

        .improver-meta {
            color: #7e849e;
            font-size: 0.88rem;
            font-weight: 600;
            margin-top: 10px;
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
            position: relative;
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

        .hall-of-fame-page .progress-name a.player-profile-link,
        .hall-of-fame-page .progress-name a.player-profile-link:visited,
        .hall-of-fame-page .performance-player strong a.player-profile-link,
        .hall-of-fame-page .performance-player strong a.player-profile-link:visited,
        .hall-of-fame-page .hof-v2-performance-player a.player-profile-link,
        .hall-of-fame-page .hof-v2-performance-player a.player-profile-link:visited,
        .hall-of-fame-page .hof-v2-record-player a.player-profile-link,
        .hall-of-fame-page .hof-v2-record-player a.player-profile-link:visited,
        .hall-of-fame-page .hof-v2-rank-row strong,
        .hall-of-fame-page .hof-v2-rank-row strong a,
        .hall-of-fame-page .hof-v2-rank-row strong a:visited,
        .hall-of-fame-page .hof-v2-race-row strong,
        .hall-of-fame-page .hof-v2-race-row strong a,
        .hall-of-fame-page .hof-v2-race-row strong a:visited,
        .hall-of-fame-page .premiership-season,
        .hall-of-fame-page .premiership-season a,
        .hall-of-fame-page .premiership-season a:visited {
            color: var(--club-link) !important;
        }

        .hall-of-fame-page .progress-name a.player-profile-link:hover,
        .hall-of-fame-page .performance-player strong a.player-profile-link:hover,
        .hall-of-fame-page .hof-v2-performance-player a.player-profile-link:hover,
        .hall-of-fame-page .hof-v2-record-player a.player-profile-link:hover,
        .hall-of-fame-page .hof-v2-rank-row strong a:hover,
        .hall-of-fame-page .hof-v2-race-row strong a:hover,
        .hall-of-fame-page .premiership-season a:hover {
            color: var(--club-link) !important;
        }

        .seasons-page .progress-name,
        .seasons-page .progress-name a.player-profile-link,
        .seasons-page .progress-name a.player-profile-link:visited,
        .block-container:has(.seasons-page) .progress-name,
        .block-container:has(.seasons-page) .progress-name a.player-profile-link,
        .block-container:has(.seasons-page) .progress-name a.player-profile-link:visited {
            color: var(--club-link) !important;
        }

        .seasons-page .progress-name a.player-profile-link:hover,
        .block-container:has(.seasons-page) .progress-name a.player-profile-link:hover {
            color: var(--club-link) !important;
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

        .featured-record-source {
            display: block;
            margin-top: 0.15rem;
            color: var(--muted-text);
            font-size: 0.7rem;
            font-weight: 500;
            line-height: 1.2;
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
            background: linear-gradient(90deg, var(--club-primary, #4b37d8), var(--club-link-hover, var(--club-accent, #6d4dff)));
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
            background: linear-gradient(90deg, var(--club-primary, #4b37d8), var(--club-link-hover, var(--club-accent, #6d4dff)));
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
            background: var(--club-primary-soft, #F0EDFF);
            border-radius: 999px;
            color: var(--club-primary, #6D4DFF);
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
            color: var(--club-primary, #4b37d8);
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
            background: linear-gradient(90deg, var(--club-primary, #4b37d8), var(--club-link-hover, var(--club-accent, #6d4dff)));
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
            position: relative;
        }

        .block-container:has(.hall-of-fame-page) .hof-progress-row {
            margin: 9px 0;
        }

        .block-container:has(.hall-of-fame-page) .hof-leader-scroll {
            max-height: calc(var(--hof-visible-rows, 6) * 58px);
            overflow-y: auto;
            padding-right: 7px;
            scrollbar-color: var(--club-border) transparent;
            scrollbar-width: thin;
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

        .premiership-wall-grid {
            align-items: start;
            display: grid;
            gap: 20px;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
            margin: 6px 0 30px;
        }

        .premiership-wall-card {
            background:
                linear-gradient(90deg, rgba(244, 194, 79, 0.72) 0 4px, transparent 4px),
                radial-gradient(circle at 94% 0%, rgba(255, 210, 96, 0.17), transparent 12rem),
                #ffffff;
            border-color: #ebe5d7;
            display: flex;
            flex-direction: column;
            padding: 20px 22px;
        }

        .premiership-card-title {
            color: var(--ink);
            font-size: 1.02rem;
            font-weight: 950;
            letter-spacing: 0;
            margin: 0 0 14px;
        }

        .premiership-card-scroll {
            flex: 1;
            max-height: 691px;
            overflow-y: auto;
            padding-right: 7px;
            scrollbar-color: var(--club-border) transparent;
            scrollbar-width: thin;
        }

        .premiership-wins-scroll {
            max-height: calc(6 * 111px);
        }

        .premiership-win-row {
            border-bottom: 1px solid #eef0f6;
            padding: 11px 0 12px;
        }

        .premiership-win-row:last-child {
            border-bottom: 0;
            padding-bottom: 0;
        }

        .premiership-win-row:first-child {
            padding-top: 0;
        }

        .premiership-grade {
            color: #7b829c;
            font-size: 0.72rem;
            font-weight: 850;
            line-height: 1.24;
            margin-bottom: 5px;
        }

        .premiership-row-body {
            align-items: start;
            display: grid;
            gap: 12px;
            grid-template-columns: minmax(0, 1fr) auto;
        }

        .premiership-row-copy {
            min-width: 0;
        }

        .premiership-sideblock {
            align-items: flex-start;
            display: flex;
            flex-direction: column;
            justify-self: end;
            min-width: max-content;
        }

        .premiership-season {
            align-items: center;
            color: var(--club-value, var(--club-primary, #4b37d8));
            display: inline-flex;
            font-size: 1.05rem;
            font-weight: 950;
            line-height: 1.12;
            text-transform: uppercase;
        }

        .premiership-cup {
            align-items: center;
            background: #fff4ca;
            border: 1px solid #eac961;
            border-radius: 999px;
            box-shadow: 0 5px 13px rgba(196, 138, 33, 0.14);
            display: inline-flex;
            font-size: 0.8rem;
            height: 23px;
            justify-content: center;
            margin-left: 7px;
            width: 23px;
        }

        .premiership-title {
            color: var(--ink);
            font-size: 0.84rem;
            font-weight: 950;
            line-height: 1.2;
            min-width: 0;
        }

        .premiership-title span {
            color: var(--club-secondary);
            font-weight: 850;
        }

        .premiership-captain {
            color: #737994;
            font-size: 0.72rem;
            font-weight: 800;
            line-height: 1.26;
            margin-top: 5px;
        }

        .premiership-result {
            align-items: center;
            color: var(--club-secondary);
            display: inline-flex;
            font-size: 0.88rem;
            font-weight: 950;
            line-height: 1.16;
            white-space: nowrap;
        }

        .premiership-link {
            align-self: flex-start;
            font-size: 0.74rem;
            font-weight: 900;
            margin-top: 5px;
            white-space: nowrap;
        }

        .premiership-player-card {
            margin-top: 0;
        }

        .premiership-player-card .performance-row {
            align-items: center;
            grid-template-columns: 30px minmax(0, 1fr) auto;
            min-height: 58px;
            padding: 9px 0;
        }

        .compact-year-premiership-player-card .performance-player strong {
            font-size: 0.96rem;
        }

        .premiership-year-summary {
            color: var(--club-muted-text, #66758D);
            display: block;
            font-size: 0.72rem;
            font-weight: 750;
        }

        .premiership-player-row .performance-value {
            color: var(--club-value, var(--club-primary, #4b37d8));
        }

        .premiership-player-row .performance-player span {
            display: block;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .premiership-player-row .performance-player span.premiership-year-summary {
            display: block;
        }

        .premiership-player-row .performance-player span a.season-overview-link,
        .premiership-player-row .performance-player span a.season-overview-link:visited,
        .premiership-player-row .performance-player span a.hof-season-text,
        .premiership-player-row .performance-player span a.hof-season-text:visited {
            color: var(--club-muted-text, #66758D) !important;
            font-weight: 750;
        }

        .premiership-player-row .premiership-more-seasons {
            color: var(--club-muted-text, #66758D);
            font-weight: 750;
        }

        .fastest-innings-card .performance-player span a.season-overview-link,
        .fastest-innings-card .performance-player span a.season-overview-link:visited {
            color: var(--club-muted-text, #66758D) !important;
            font-weight: 750;
        }

        .hof-five-row-scroll {
            max-height: 360px;
            overflow-y: auto;
            padding-right: 7px;
            scrollbar-color: var(--club-border) transparent;
            scrollbar-width: thin;
        }

        .hof-responsive-record-scroll {
            max-height: 505px;
            overflow-y: auto;
            padding-right: 7px;
            scrollbar-color: var(--club-border) transparent;
            scrollbar-width: thin;
        }

        .hof-responsive-record-scroll.iconic-performance-scroll {
            max-height: 474px;
        }

        .iconic-performance-scroll .performance-player > span,
        .iconic-performance-scroll .performance-player > span a,
        .iconic-performance-scroll .performance-player > span a:visited {
            color: var(--club-muted-text, #66758D) !important;
        }

        .iconic-performance-scroll .performance-player > span a.scorecard-link,
        .iconic-performance-scroll .performance-player > span a.scorecard-link:visited {
            color: var(--club-link) !important;
        }

        .fastest-innings-card .fastest-final-score {
            color: #566074;
        }

        .hof-active-badge {
            background: rgba(var(--club-secondary-rgb), 0.17);
            border: 1px solid rgba(var(--club-primary-rgb), 0.18);
            border-radius: 999px;
            color: var(--club-primary-dark);
            display: inline-flex;
            font-size: 0.56rem;
            font-weight: 900;
            letter-spacing: 0.04em;
            margin-left: 6px;
            padding: 2px 6px;
            text-transform: uppercase;
            vertical-align: middle;
        }

        @media (max-width: 760px) {
            .block-container:has(.hall-of-fame-page) .hof-leader-scroll {
                max-height: calc(5 * 58px);
            }

            .block-container:has(.hall-of-fame-page) .hof-five-row-scroll {
                max-height: 360px;
            }

            .block-container:has(.hall-of-fame-page) .hof-responsive-record-scroll {
                max-height: 505px;
                overflow-y: auto;
                padding-right: 7px;
                scrollbar-color: var(--club-border) transparent;
                scrollbar-width: thin;
            }

            .block-container:has(.hall-of-fame-page) .hof-responsive-record-scroll.iconic-performance-scroll {
                max-height: 395px;
            }

            .premiership-wins-scroll {
                max-height: 826px;
            }

            .premiership-player-scroll {
                max-height: calc(5 * 58px);
            }
        }

        .premiership-empty p {
            color: var(--muted);
            font-weight: 750;
            margin: 6px 0 0;
        }

        .block-container:has(.player-dna-page) {
            max-width: 1440px;
        }

        .dna-hero-card {
            background:
                radial-gradient(circle at 88% 8%, rgba(122, 23, 53, 0.16), transparent 15rem),
                linear-gradient(135deg, #ffffff 0%, #fbfbff 100%);
            border: 1px solid #e7e9f4;
            border-radius: 22px;
            box-shadow: 0 18px 42px rgba(23, 27, 77, 0.08);
            display: grid;
            gap: 24px;
            grid-template-columns: minmax(260px, 0.9fr) minmax(0, 1.4fr);
            margin: 10px 0 28px;
            overflow: hidden;
            padding: 28px 30px;
            position: relative;
        }

        .dna-hero-card::before {
            background: linear-gradient(180deg, #7A1735, #4b37d8);
            content: "";
            height: 100%;
            left: 0;
            position: absolute;
            top: 0;
            width: 6px;
        }

        .dna-kicker {
            color: #7a809d;
            font-size: 0.78rem;
            font-weight: 950;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .dna-player-name {
            color: var(--ink);
            font-size: clamp(2.1rem, 4vw, 4.2rem);
            font-weight: 950;
            letter-spacing: 0;
            line-height: 0.98;
            margin-top: 10px;
        }

        .dna-role-badge,
        .dna-mini-badge {
            background: rgba(122, 23, 53, 0.09);
            border: 1px solid rgba(122, 23, 53, 0.18);
            border-radius: 999px;
            color: #7A1735;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 900;
            margin-top: 18px;
            padding: 7px 11px;
        }

        .dna-hero-grid {
            display: grid;
            gap: 14px;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .dna-hero-tile {
            border-bottom: 1px solid #eceef7;
            padding: 4px 0 13px;
        }

        .dna-hero-tile span,
        .dna-bonus-card span,
        .dna-empty-detail {
            color: #858ba6;
            display: block;
            font-size: 0.76rem;
            font-weight: 850;
        }

        .dna-hero-tile strong {
            color: var(--ink);
            display: block;
            font-size: 1.03rem;
            font-weight: 950;
            line-height: 1.15;
            margin-top: 5px;
        }

        .dna-card,
        .dna-bonus-card,
        .dna-performance-card {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 16px;
            box-shadow: 0 14px 34px rgba(23, 27, 77, 0.055);
            margin-bottom: 18px;
            padding: 18px 20px;
        }

        .dna-card-title {
            color: var(--ink);
            font-size: 1.02rem;
            font-weight: 950;
            margin-bottom: 13px;
        }

        .dna-trait-row {
            border-bottom: 1px solid #eef0f6;
            padding: 12px 0;
        }

        .dna-trait-row:last-child {
            border-bottom: 0;
            padding-bottom: 0;
        }

        .dna-trait-head,
        .dna-ladder-top,
        .dna-fingerprint-label {
            align-items: center;
            display: flex;
            gap: 12px;
            justify-content: space-between;
        }

        .dna-trait-head strong,
        .dna-ladder-top strong,
        .dna-fingerprint-label strong,
        .dna-rank-main strong {
            color: var(--ink);
            font-size: 0.93rem;
            font-weight: 950;
        }

        .dna-trait-head span,
        .dna-ladder-top span,
        .dna-fingerprint-label span,
        .dna-rank-main span {
            color: #7a809d;
            font-size: 0.76rem;
            font-weight: 800;
            text-align: right;
        }

        .dna-trait-track,
        .dna-contribution-track,
        .dna-fingerprint-track {
            background: #EEF0F8;
            border-radius: 999px;
            height: 9px;
            margin-top: 9px;
            overflow: hidden;
        }

        .dna-trait-track div,
        .dna-contribution-track div,
        .dna-fingerprint-track div {
            background: linear-gradient(90deg, #7A1735, #4b37d8);
            border-radius: 999px;
            height: 100%;
        }

        .dna-trait-copy,
        .dna-insight-line,
        .dna-empty-message,
        .dna-performance-body small {
            color: #7d839e;
            font-size: 0.8rem;
            font-weight: 750;
            line-height: 1.38;
            margin-top: 8px;
        }

        .block-container:has(.player-dna-page) .dna-native-trait-score {
            color: #7a809d;
            font-size: 0.82rem;
            font-weight: 900;
            text-align: right;
        }

        .block-container:has(.player-dna-page) div[data-testid="stProgress"] > div > div > div {
            background: linear-gradient(90deg, #7A1735, #4b37d8);
        }

        .block-container:has(.player-dna-page) div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border-color: #e9ebf4;
            border-radius: 16px;
            box-shadow: 0 14px 34px rgba(23, 27, 77, 0.055);
        }

        .dna-ladder-row,
        .dna-fingerprint-row {
            border-bottom: 1px solid #eef0f6;
            padding: 11px 0;
        }

        .dna-ladder-row:last-child,
        .dna-fingerprint-row:last-child {
            border-bottom: 0;
        }

        .dna-rank-row {
            align-items: center;
            border-bottom: 1px solid #eef0f6;
            display: grid;
            gap: 12px;
            grid-template-columns: 28px minmax(0, 1fr) auto;
            padding: 11px 0;
        }

        .dna-rank-row:last-child {
            border-bottom: 0;
            padding-bottom: 0;
        }

        .dna-rank-main span {
            display: block;
            margin-top: 4px;
            text-align: left;
        }

        .dna-rank-value {
            color: #4b37d8;
            font-size: 1.05rem;
            font-weight: 950;
            text-align: right;
            white-space: nowrap;
        }

        .dna-rank-value span {
            color: #858ba6;
            display: block;
            font-size: 0.72rem;
            font-weight: 850;
        }

        .dna-performance-grid,
        .dna-bonus-grid {
            display: grid;
            gap: 16px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin-bottom: 22px;
        }

        .dna-performance-card {
            align-items: center;
            display: grid;
            gap: 12px;
            grid-template-columns: 28px minmax(0, 1fr) auto;
            margin-bottom: 0;
            min-height: 118px;
        }

        .dna-performance-rank {
            align-self: start;
        }

        .dna-performance-body strong {
            color: var(--ink);
            display: block;
            font-size: 0.94rem;
            font-weight: 950;
            line-height: 1.18;
        }

        .dna-performance-body span,
        .dna-performance-body em {
            color: #7a809d;
            display: block;
            font-size: 0.78rem;
            font-style: normal;
            font-weight: 800;
            margin-top: 4px;
        }

        .dna-performance-value {
            color: #4b37d8;
            font-size: 1.05rem;
            font-weight: 950;
            text-align: right;
            white-space: nowrap;
        }

        .dna-fingerprint-row {
            align-items: center;
            display: grid;
            gap: 12px;
            grid-template-columns: minmax(110px, 0.65fr) minmax(0, 1fr) 54px;
        }

        .dna-fingerprint-track {
            margin-top: 0;
        }

        .dna-fingerprint-pct {
            color: #4b37d8;
            font-size: 0.86rem;
            font-weight: 950;
            text-align: right;
        }

        .dna-bonus-card {
            margin-bottom: 0;
            min-height: 116px;
        }

        .dna-bonus-card strong {
            color: var(--ink);
            display: block;
            font-size: 1.35rem;
            font-weight: 950;
            margin-top: 10px;
        }

        .dna-bonus-card em {
            color: #7a809d;
            display: block;
            font-size: 0.78rem;
            font-style: normal;
            font-weight: 800;
            margin-top: 8px;
        }

        .dna-empty-card {
            min-height: 120px;
        }

        .block-container:has(.scorebook-lab-page) {
            max-width: 1480px;
        }

        .lab-sentence-card {
            background:
                radial-gradient(circle at 96% 0%, rgba(122, 23, 53, 0.09), transparent 12rem),
                #ffffff;
        }

        .lab-feature-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .lab-badge-line {
            color: #7A1735 !important;
            font-weight: 900 !important;
        }

        .lab-impact-stack {
            display: flex;
            flex-direction: column;
            gap: 14px;
            justify-content: center;
        }

        .lab-stack-row {
            display: grid;
            gap: 12px;
            grid-template-columns: 86px minmax(0, 1fr);
            align-items: center;
        }

        .lab-stack-row span {
            color: #7a809d;
            font-size: 0.8rem;
            font-weight: 900;
        }

        .lab-story-card {
            overflow: hidden;
        }

        .lab-story-row {
            display: grid;
            gap: 14px;
            grid-template-columns: 18px minmax(0, 1fr);
            padding: 12px 0;
            position: relative;
        }

        .lab-story-row::before {
            background: #e8eaf4;
            content: "";
            height: 100%;
            left: 8px;
            position: absolute;
            top: 18px;
            width: 2px;
        }

        .lab-story-row:last-child::before {
            display: none;
        }

        .lab-story-row > span {
            background: linear-gradient(135deg, #7A1735, #4b37d8);
            border: 3px solid #ffffff;
            border-radius: 999px;
            box-shadow: 0 5px 14px rgba(23, 27, 77, 0.16);
            height: 18px;
            margin-top: 2px;
            position: relative;
            width: 18px;
            z-index: 1;
        }

        .lab-story-row strong {
            color: var(--ink);
            font-size: 0.94rem;
            font-weight: 950;
        }

        .lab-story-row p {
            color: #7d839e;
            font-size: 0.82rem;
            font-weight: 760;
            line-height: 1.38;
            margin: 4px 0 0;
        }

        @media (max-width: 980px) {
            .dna-hero-card {
                grid-template-columns: 1fr;
                padding: 22px;
            }

            .dna-hero-grid,
            .dna-performance-grid,
            .dna-bonus-grid,
            .lab-feature-grid {
                grid-template-columns: 1fr;
            }

            .premiership-wall-grid {
                grid-template-columns: 1fr;
            }

            .premiership-wall-card {
                min-height: 0;
            }

            .premiership-row-body {
                display: block;
            }

            .premiership-sideblock {
                align-items: flex-start;
                justify-self: start;
                margin-top: 6px;
                min-width: 0;
                width: 100%;
            }

            .premiership-result {
                justify-content: flex-start;
                text-align: left;
            }

            .premiership-link {
                align-self: flex-start;
                text-align: left;
            }

            .dna-performance-card {
                grid-template-columns: 28px minmax(0, 1fr);
            }

            .dna-performance-value {
                grid-column: 2;
                text-align: left;
            }

            .dna-fingerprint-row {
                grid-template-columns: 1fr;
                gap: 8px;
            }

            .dna-fingerprint-pct {
                text-align: left;
            }
        }

        .record-card-grid {
            display: grid;
            gap: 18px;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-bottom: 26px;
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

        .hall-of-fame-page .performance-player strong {
            color: var(--club-link, var(--ink));
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
            color: var(--club-primary, #4b37d8);
            font-size: 0.95rem;
            font-weight: 950;
            text-align: right;
            white-space: nowrap;
        }

        .best-season-grid {
            display: grid;
            gap: 18px;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-bottom: 28px;
        }

        .best-season-card {
            background:
                radial-gradient(circle at 100% 0%, rgba(var(--club-primary-rgb, 109, 77, 255), 0.09), transparent 16rem),
                #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 16px;
            box-shadow: 0 14px 34px rgba(23, 27, 77, 0.055);
            min-height: 188px;
            padding: 20px 22px;
        }

        .best-season-label {
            color: #7a809d;
            font-size: 0.78rem;
            font-weight: 900;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .best-season-player {
            color: var(--ink);
            font-size: 1.25rem;
            font-weight: 950;
            line-height: 1.14;
            margin-top: 14px;
        }

        .best-season-season {
            color: #7a809d;
            font-size: 0.82rem;
            font-weight: 760;
            margin-top: 4px;
        }

        .best-season-primary {
            color: var(--club-primary, #4b37d8);
            font-size: 1.58rem;
            font-weight: 950;
            margin-top: 16px;
        }

        .best-season-stats {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 16px;
        }

        .best-season-stats span {
            align-items: center;
            background: #f3f4fb;
            border: 1px solid #e6e8f2;
            border-radius: 999px;
            color: #68708f;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 800;
            gap: 6px;
            padding: 7px 10px;
        }

        .best-season-stats b {
            color: var(--ink);
            font-weight: 950;
        }

        .identity-note {
            background: rgba(var(--club-primary-rgb, 109, 77, 255), 0.08);
            border: 1px solid rgba(var(--club-primary-rgb, 109, 77, 255), 0.15);
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
            border: 1px solid #e7e9f4;
            border-radius: 24px;
            box-shadow: 0 18px 44px rgba(23, 27, 77, 0.07);
            color: #747b98;
            font-weight: 800;
            margin-top: 18px;
            padding: 30px 28px;
            text-align: center;
        }

        .empty-profile-title {
            color: var(--ink);
            font-size: 1.35rem;
            font-weight: 950;
            letter-spacing: -0.01em;
            line-height: 1.18;
            margin: 0 0 10px;
        }

        .empty-profile-copy {
            color: #747b98;
            font-size: 0.96rem;
            font-weight: 700;
            line-height: 1.45;
            margin: 0 auto 18px;
            max-width: 760px;
        }

        .empty-profile-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
        }

        .empty-profile-pill-row span {
            background: linear-gradient(135deg, rgba(var(--club-primary-rgb, 11, 63, 159), 0.10), rgba(var(--club-secondary-rgb, 121, 200, 238), 0.08));
            border: 1px solid rgba(var(--club-primary-rgb, 11, 63, 159), 0.16);
            border-radius: 999px;
            color: #45496a;
            display: inline-flex;
            font-size: 0.86rem;
            font-weight: 850;
            padding: 9px 13px;
        }

        .player-hero-card {
            align-items: flex-start;
            background:
                radial-gradient(circle at right top, rgba(var(--club-primary-rgb, 11, 63, 159), 0.14), transparent 20rem),
                #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 18px;
            box-shadow: 0 16px 38px rgba(23, 27, 77, 0.06);
            display: flex;
            justify-content: space-between;
            gap: 24px;
            margin: 16px 0 16px;
            padding: 22px 24px;
        }

        .profile-main-block {
            min-width: 0;
        }

        .profile-kicker {
            color: var(--club-primary, #6D4DFF);
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
            line-height: 1.32;
            margin-top: 8px;
            max-width: 980px;
        }

        .profile-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: flex-start;
            margin-top: 14px;
            max-width: 920px;
            min-width: 0;
        }

        .profile-badge {
            background: var(--club-secondary-soft, #eef4f8);
            border: 1px solid rgba(var(--club-secondary-rgb, 40, 72, 95), 0.22);
            border-radius: 999px;
            color: var(--club-link, #28485F);
            font-size: 0.76rem;
            font-weight: 900;
            padding: 8px 11px;
            white-space: nowrap;
        }

        .profile-badge-gold {
            background: linear-gradient(135deg, #fff4bf, #f7c948 52%, #d99a12) !important;
            border-color: rgba(180, 83, 9, 0.42) !important;
            box-shadow: 0 10px 22px rgba(217, 154, 18, 0.18) !important;
            color: #6f3d00 !important;
        }

        .block-container:has(.player-profile-page) {
            padding-top: 1.15rem;
        }

        .block-container:has(.player-profile-page) .page-title {
            font-size: clamp(2.8rem, 3.6vw, 3.75rem);
            margin: 0 0 6px;
        }

        .block-container:has(.player-profile-page) .club-label {
            color: var(--club-primary, #6D4DFF);
            font-weight: 800;
            margin: 0 0 10px;
        }

        .block-container:has(.player-profile-page) .page-subtitle {
            color: #747b98;
            font-size: 1rem;
            font-weight: 700;
            margin: 0 0 22px;
            max-width: 920px;
        }

        div.st-key-player_selector_card {
            background:
                radial-gradient(circle at 100% 0%, rgba(var(--club-primary-rgb, 11, 63, 159), 0.08), transparent 18rem),
                #ffffff;
            border: 1px solid #e7e9f4;
            border-radius: 22px;
            box-shadow: 0 16px 38px rgba(23, 27, 77, 0.06);
            margin: 0 0 18px;
            padding: 18px 22px 14px;
        }

        div.st-key-player_selector_card label {
            color: var(--ink) !important;
            font-size: 0.92rem !important;
            font-weight: 900 !important;
            letter-spacing: 0.02em;
        }

        div.st-key-player_selector_card [data-baseweb="select"] > div {
            border-color: #e2e6f3;
            border-radius: 16px;
            min-height: 52px;
        }

        div.st-key-player_selector_card [data-baseweb="select"] div {
            align-items: center;
        }

        div.st-key-player_selector_card [data-baseweb="select"] [data-testid="stMarkdownContainer"],
        div.st-key-player_selector_card [data-baseweb="select"] span {
            line-height: 1.2;
        }

        .profile-selector-help {
            color: #777e9c;
            font-size: 0.88rem;
            font-weight: 700;
            margin-top: -12px;
        }

        .profile-kpi-card {
            background:
                linear-gradient(135deg, rgba(109, 77, 255, 0.045), rgba(255,255,255,0) 70%),
                #ffffff;
            border: 1px solid #e8eaf5;
            border-radius: 18px;
            box-shadow: 0 12px 28px rgba(23, 27, 77, 0.055);
            min-height: 94px;
            padding: 15px 16px;
        }

        .profile-kpi-label {
            color: #727999;
            font-size: 0.67rem;
            font-weight: 900;
            letter-spacing: 0.055em;
            line-height: 1.25;
            min-height: 24px;
            text-transform: uppercase;
        }

        .profile-kpi-value {
            color: var(--ink);
            font-size: 1.48rem;
            font-weight: 950;
            line-height: 1.05;
            margin-top: 6px;
            white-space: nowrap;
        }

        div.st-key-profile_chart_runs,
        div.st-key-profile_chart_wickets,
        div.st-key-profile_chart_batting_average,
        div.st-key-profile_chart_bowling_average {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 18px;
            box-shadow: 0 14px 34px rgba(23, 27, 77, 0.055);
            margin-bottom: 18px;
            overflow: hidden;
            padding: 18px 20px 12px;
        }

        div.st-key-profile_chart_runs iframe,
        div.st-key-profile_chart_wickets iframe,
        div.st-key-profile_chart_batting_average iframe,
        div.st-key-profile_chart_bowling_average iframe {
            max-width: 100%;
        }

        .profile-chart-title {
            color: var(--ink);
            font-size: 1.02rem;
            font-weight: 950;
            margin: 0 0 12px;
        }

        .profile-season-summary-card {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 18px;
            box-shadow: 0 14px 34px rgba(23, 27, 77, 0.055);
            margin-bottom: 18px;
            padding: 20px 22px;
        }

        .profile-season-summary-card span {
            color: #6d4dff;
            display: block;
            font-size: 0.74rem;
            font-weight: 950;
            letter-spacing: 0.06em;
            margin-bottom: 9px;
            text-transform: uppercase;
        }

        .profile-season-summary-card h4 {
            color: var(--ink);
            font-size: 1.08rem;
            font-weight: 950;
            margin: 0 0 6px;
        }

        .profile-season-summary-card strong {
            color: var(--ink);
            display: block;
            font-size: 1.45rem;
            font-weight: 950;
            line-height: 1.05;
            margin: 8px 0;
        }

        .profile-season-summary-card div,
        .profile-season-summary-card p {
            color: #626a88;
            font-size: 0.88rem;
            font-weight: 700;
            line-height: 1.35;
            margin: 0;
        }

        .profile-season-summary-card p {
            color: #7b829d;
            font-weight: 600;
            margin-top: 10px;
        }

        .profile-insight {
            color: #555d7b;
            font-size: 0.95rem;
            font-weight: 500;
            line-height: 1.35;
            margin-top: 6px;
            max-width: 820px;
        }

        .block-container:has(.player-profile-page) .overview-section-title {
            margin-top: 24px;
            margin-bottom: 14px;
        }

        .block-container:has(.player-profile-page) .record-card {
            min-height: 146px;
            padding: 18px 19px;
        }

        .block-container:has(.player-profile-page) .milestone-watch-card {
            min-height: 0;
            padding: 18px 20px;
        }

        .block-container:has(.player-profile-page) .milestone-watch-row {
            padding: 10px 0;
        }

        .block-container:has(.player-profile-page) .profile-breakdown-card {
            padding: 18px 20px;
        }

        .block-container:has(.player-profile-page) .profile-breakdown-card div {
            padding: 8px 0;
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

        .profile-intelligence-intro {
            align-items: center;
            background: linear-gradient(135deg, rgba(109, 77, 255, 0.07), rgba(255,255,255,0.78));
            border: 1px solid #e7e9f4;
            border-radius: 18px;
            box-shadow: 0 12px 28px rgba(23, 27, 77, 0.045);
            display: flex;
            gap: 14px;
            justify-content: space-between;
            margin: -4px 0 16px;
            padding: 14px 18px;
        }

        .profile-intelligence-intro span {
            color: #5b3df5;
            font-size: 0.78rem;
            font-weight: 950;
            letter-spacing: 0.055em;
            text-transform: uppercase;
            white-space: nowrap;
        }

        .profile-intelligence-intro p {
            color: #626a88;
            font-size: 0.88rem;
            font-weight: 700;
            line-height: 1.35;
            margin: 0;
            text-align: right;
        }

        .profile-intelligence-card,
        .profile-breakdown-empty {
            background: #ffffff;
            border: 1px solid #e8ebf5;
            border-radius: 20px;
            box-shadow: 0 16px 38px rgba(23, 27, 77, 0.06);
            margin-bottom: 18px;
            padding: 18px 20px;
        }

        .profile-intelligence-card-head {
            margin-bottom: 14px;
        }

        .profile-intelligence-card-head > span {
            background: #f0edff;
            border: 1px solid #dfd8ff;
            border-radius: 999px;
            color: #5b3df5;
            display: inline-flex;
            font-size: 0.66rem;
            font-weight: 950;
            letter-spacing: 0.055em;
            margin-bottom: 9px;
            padding: 5px 9px;
            text-transform: uppercase;
        }

        .profile-intelligence-card-head > span:empty {
            display: none;
        }

        .profile-intelligence-card-head h3,
        .profile-intelligence-card-head .profile-card-title {
            color: var(--ink);
            font-size: 1.02rem;
            font-weight: 950;
            line-height: 1.18;
            margin: 0;
        }

        .profile-empty-card p,
        .profile-breakdown-empty span,
        .profile-intelligence-note {
            color: #747b98;
            font-size: 0.84rem;
            font-weight: 700;
            line-height: 1.36;
            margin: 8px 0 0;
        }

        .profile-breakdown-empty strong {
            color: var(--ink);
            display: block;
            font-size: 0.98rem;
            font-weight: 950;
            margin-bottom: 4px;
        }

        .position-row,
        .fingerprint-row {
            border-top: 1px solid #eef0f7;
            padding: 10px 0;
        }

        .position-row:first-of-type,
        .fingerprint-row:first-of-type {
            border-top: 0;
        }

        .position-row-top,
        .fingerprint-top {
            align-items: center;
            display: flex;
            justify-content: space-between;
            gap: 10px;
        }

        .position-row-top strong,
        .fingerprint-top strong {
            color: var(--ink);
            font-size: 0.93rem;
            font-weight: 950;
        }

        .position-row-label {
            align-items: center;
            display: inline-flex;
            gap: 10px;
            min-width: 0;
        }

        .fingerprint-label-block {
            align-items: baseline;
            display: flex;
            flex-wrap: wrap;
            gap: 5px 8px;
            min-width: 0;
        }

        .fingerprint-detail {
            color: #747b98;
            font-size: 0.72rem;
            font-weight: 800;
            line-height: 1.2;
        }

        .position-row-summary {
            color: #69718f;
            flex: 0 0 auto;
            font-size: 0.78rem;
            font-weight: 850;
            text-align: right;
            white-space: nowrap;
        }

        .fingerprint-player-pct {
            color: #5b3df5;
            font-size: 0.84rem;
            font-weight: 950;
            white-space: nowrap;
        }

        .position-row-meta {
            color: #69718f;
            display: flex;
            flex-wrap: wrap;
            gap: 9px;
            font-size: 0.78rem;
            font-weight: 800;
            margin: 5px 0 8px;
        }

        .profile-intelligence-note {
            color: #6D728E;
            font-size: 0.74rem;
            line-height: 1.4;
            margin: -2px 0 8px;
        }

        .profile-best-badge {
            background: #f7f1ff;
            border: 1px solid #ded2ff;
            border-radius: 999px;
            color: #5b3df5;
            font-size: 0.64rem;
            font-weight: 950;
            letter-spacing: 0.04em;
            line-height: 1;
            margin-left: 2px;
            padding: 4px 8px;
            text-transform: uppercase;
            white-space: nowrap;
        }

        .position-track,
        .fingerprint-track {
            background: #eef1f8;
            border-radius: 999px;
            height: 9px;
            margin-top: 8px;
            overflow: hidden;
            position: relative;
        }

        .position-track div,
        .fingerprint-bar {
            background: linear-gradient(90deg, #6d4dff, #8a63ff);
            border-radius: inherit;
            height: 100%;
        }

        .profile-segmented {
            align-items: center;
            background: #F7F8FD;
            border: 1px solid #E9ECF6;
            border-radius: 999px;
            box-shadow: none;
            display: inline-flex;
            gap: 4px;
            margin: 0 0 18px;
            padding: 5px;
        }

        .profile-segmented-compact {
            border-radius: 999px;
            box-shadow: none;
            margin: -2px 0 14px;
            padding: 5px;
        }

        .profile-segment {
            border-radius: 999px;
            color: #737998;
            font-size: 0.9rem;
            font-weight: 750;
            line-height: 1;
            min-height: 38px;
            padding: 11px 16px;
            text-decoration: none !important;
            transition: background 0.18s ease, color 0.18s ease;
            white-space: nowrap;
        }

        .profile-segment:hover,
        .profile-segment:focus-visible {
            background: #f5f2ff;
            color: #5b3df5;
        }

        .profile-segment.active {
            background: #F0EDFF;
            color: var(--pitch);
            box-shadow: none;
        }

        div.st-key-season_round_grade_folder_tabs,
        div.st-key-milestone_page_view_folder_tabs,
        div.st-key-player_profile_breakdown_folder_tabs {
            margin: 0 0 -1px;
            padding-left: 14px;
            position: relative;
            z-index: 3;
        }

        div[data-testid="stElementContainer"]:has(> div.st-key-season_round_grade_folder_tabs),
        div[data-testid="stElementContainer"]:has(> div.st-key-milestone_page_view_folder_tabs),
        div[data-testid="stElementContainer"]:has(> div.st-key-player_profile_breakdown_folder_tabs) {
            margin-bottom: 0 !important;
        }

        div.st-key-season_round_grade_folder_tabs div[data-testid="stSegmentedControl"],
        div.st-key-milestone_page_view_folder_tabs div[data-testid="stSegmentedControl"],
        div.st-key-player_profile_breakdown_folder_tabs div[data-testid="stSegmentedControl"],
        div.st-key-season_round_grade_folder_tabs [data-testid="stButtonGroup"],
        div.st-key-milestone_page_view_folder_tabs [data-testid="stButtonGroup"],
        div.st-key-player_profile_breakdown_folder_tabs [data-testid="stButtonGroup"] {
            align-items: flex-end;
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            max-width: 100%;
            overflow: visible;
            padding: 0 !important;
            width: fit-content;
        }

        div.st-key-season_round_grade_folder_tabs [data-testid="stButtonGroup"] > div,
        div.st-key-milestone_page_view_folder_tabs [data-testid="stButtonGroup"] > div,
        div.st-key-player_profile_breakdown_folder_tabs [data-testid="stButtonGroup"] > div {
            align-items: flex-end;
            display: flex !important;
            flex-wrap: wrap;
            gap: 6px;
            width: fit-content;
        }

        div.st-key-season_round_grade_folder_tabs div[data-testid="stSegmentedControl"] button,
        div.st-key-milestone_page_view_folder_tabs div[data-testid="stSegmentedControl"] button,
        div.st-key-player_profile_breakdown_folder_tabs div[data-testid="stSegmentedControl"] button,
        div.st-key-season_round_grade_folder_tabs [data-testid="stButtonGroup"] button,
        div.st-key-milestone_page_view_folder_tabs [data-testid="stButtonGroup"] button,
        div.st-key-player_profile_breakdown_folder_tabs [data-testid="stButtonGroup"] button,
        div.st-key-season_round_grade_folder_tabs button[data-testid^="stBaseButton-segmented_control"],
        div.st-key-milestone_page_view_folder_tabs button[data-testid^="stBaseButton-segmented_control"],
        div.st-key-player_profile_breakdown_folder_tabs button[data-testid^="stBaseButton-segmented_control"] {
            background: #fbfcff !important;
            border: 1px solid #e4e8f4 !important;
            border-bottom-color: #dfe4f2 !important;
            border-radius: 14px 14px 0 0 !important;
            box-shadow: 0 -3px 12px rgba(23, 27, 77, 0.035) !important;
            color: #737998 !important;
            flex: 0 0 auto;
            font-size: 0.88rem !important;
            font-weight: 850 !important;
            line-height: 1.08 !important;
            min-height: 40px !important;
            padding: 10px 16px 9px !important;
            position: relative;
            white-space: nowrap;
        }

        div.st-key-season_round_grade_folder_tabs [data-testid="stButtonGroup"] button[aria-checked="true"],
        div.st-key-milestone_page_view_folder_tabs [data-testid="stButtonGroup"] button[aria-checked="true"],
        div.st-key-player_profile_breakdown_folder_tabs [data-testid="stButtonGroup"] button[aria-checked="true"],
        div.st-key-season_round_grade_folder_tabs div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        div.st-key-milestone_page_view_folder_tabs div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        div.st-key-player_profile_breakdown_folder_tabs div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        div.st-key-season_round_grade_folder_tabs div[data-testid="stSegmentedControl"] button[kind="primary"],
        div.st-key-milestone_page_view_folder_tabs div[data-testid="stSegmentedControl"] button[kind="primary"],
        div.st-key-player_profile_breakdown_folder_tabs div[data-testid="stSegmentedControl"] button[kind="primary"],
        div.st-key-season_round_grade_folder_tabs button[data-testid$="segmented_controlActive"],
        div.st-key-milestone_page_view_folder_tabs button[data-testid$="segmented_controlActive"],
        div.st-key-player_profile_breakdown_folder_tabs button[data-testid$="segmented_controlActive"] {
            background: #F0EDFF !important;
            border-color: #ded8ff !important;
            border-bottom-color: #ffffff !important;
            box-shadow: 0 -7px 18px rgba(91, 61, 245, 0.08) !important;
            color: var(--pitch) !important;
            transform: translateY(1px);
            z-index: 2;
        }

        div.st-key-season_round_grade_folder_tabs button[data-testid^="stBaseButton"] p,
        div.st-key-milestone_page_view_folder_tabs button[data-testid^="stBaseButton"] p,
        div.st-key-player_profile_breakdown_folder_tabs button[data-testid^="stBaseButton"] p,
        div.st-key-season_round_grade_folder_tabs button[data-testid^="stBaseButton"] span,
        div.st-key-milestone_page_view_folder_tabs button[data-testid^="stBaseButton"] span,
        div.st-key-player_profile_breakdown_folder_tabs button[data-testid^="stBaseButton"] span {
            line-height: 1.08 !important;
            white-space: inherit !important;
        }

        .recent-form-card {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 18px;
            box-shadow: 0 16px 38px rgba(23, 27, 77, 0.06);
            margin-bottom: 20px;
            padding: 16px 18px;
        }

        .recent-form-line {
            align-items: center;
            display: grid;
            gap: 14px;
            grid-template-columns: 142px minmax(0, 1fr);
        }

        .recent-form-line + .recent-form-line {
            border-top: 1px solid #eef0f7;
            margin-top: 12px;
            padding-top: 12px;
        }

        .recent-form-label {
            color: var(--ink);
            font-size: 0.92rem;
            font-weight: 950;
            line-height: 1.16;
        }

        .recent-form-label small {
            color: #858ba3;
            display: block;
            font-size: 0.64rem;
            font-weight: 850;
            letter-spacing: 0.02em;
            margin-top: 4px;
            text-transform: uppercase;
        }

        .recent-form-chip-row {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding: 2px 0 5px;
        }

        .recent-form-chip {
            background: #f7f8fd;
            border: 1px solid #e8ebf7;
            border-radius: 999px;
            color: var(--ink);
            flex: 0 0 auto;
            font-size: 0.88rem;
            font-weight: 900;
            line-height: 1;
            padding: 9px 11px;
            white-space: nowrap;
        }

        .recent-form-chip.bat {
            background: var(--club-secondary-soft, #eef4f8);
            border-color: rgba(var(--club-secondary-rgb, 40, 72, 95), 0.22);
            color: var(--club-link, #28485F);
        }

        .recent-form-chip.bowl {
            background: var(--club-secondary-soft, #eef4f8);
            border-color: rgba(var(--club-secondary-rgb, 40, 72, 95), 0.22);
            color: var(--club-link, #28485F);
        }

        .recent-form-chip.hot {
            box-shadow: inset 0 0 0 2px rgba(18, 122, 75, 0.15);
        }

        .recent-form-chip.notout {
            box-shadow: inset 0 0 0 2px rgba(154, 107, 5, 0.18);
        }

        .recent-form-chip.quiet,
        .recent-form-empty {
            color: #747b98;
        }

        .recent-form-empty {
            background: #f8f8fd;
            border: 1px dashed #d8ddeb;
            border-radius: 999px;
            display: inline-flex;
            flex: 0 0 auto;
            font-size: 0.82rem;
            font-weight: 800;
            padding: 8px 11px;
        }

        div.st-key-season_by_round_card {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 0 20px 20px 20px;
            box-shadow: 0 16px 38px rgba(23, 27, 77, 0.06);
            margin-bottom: 24px;
            margin-top: -15px;
            overflow: visible;
            padding: 16px 20px 20px;
        }

        .season-round-card-head {
            align-items: flex-start;
            display: flex;
            gap: 14px;
            justify-content: space-between;
            margin-bottom: 14px;
        }

        .season-round-card-head h3 {
            color: var(--ink);
            font-size: 1.12rem;
            font-weight: 950;
            line-height: 1.12;
            margin: 0;
        }

        .season-round-card-head p {
            color: #747b98;
            font-size: 0.88rem;
            font-weight: 700;
            line-height: 1.36;
            margin: 5px 0 0;
        }

        .season-round-card-head > span {
            background: #ffffff;
            border: 1px solid #e8ebf7;
            border-radius: 999px;
            color: #747b98;
            flex: 0 0 auto;
            font-size: 0.74rem;
            font-weight: 900;
            padding: 7px 10px;
        }

        div.st-key-season_round_grade_filter_control {
            display: flex;
            flex-wrap: nowrap;
            gap: 8px;
            margin: -2px 0 14px;
            max-width: 100%;
            overflow-x: auto;
            overflow-y: hidden;
            padding-bottom: 4px;
            width: 100%;
        }

        div.st-key-season_round_grade_filter_control div[data-testid="stHorizontalBlock"] {
            align-items: stretch;
            display: flex;
            flex-wrap: nowrap;
            gap: 8px;
            width: 100%;
        }

        div.st-key-season_round_grade_filter_control div[data-testid="stVerticalBlock"] {
            align-items: stretch;
            display: flex !important;
            flex-wrap: nowrap;
            gap: 8px;
            min-width: max-content;
        }

        div.st-key-season_round_grade_filter_control div[data-testid="stElementContainer"] {
            flex: 0 1 auto;
            width: auto !important;
        }

        div.st-key-season_round_grade_filter_control div[data-testid="stSegmentedControl"],
        div.st-key-season_round_grade_filter_control [data-testid="stButtonGroup"] {
            background: #F7F8FD;
            border: 1px solid #E9ECF6;
            border-radius: 999px;
            box-shadow: none;
            display: inline-flex;
            flex-wrap: nowrap;
            gap: 4px;
            max-width: 100%;
            overflow-x: auto;
            padding: 5px;
            width: fit-content;
        }

        div.st-key-season_round_grade_filter_control div[data-testid="stSegmentedControl"] button,
        div.st-key-season_round_grade_filter_control [data-testid="stButtonGroup"] button,
        div.st-key-season_round_grade_filter_control button[data-testid^="stBaseButton-segmented_control"] {
            background: transparent !important;
            border: 0 !important;
            border-radius: 999px !important;
            color: #737998 !important;
            flex: 0 0 auto;
            font-size: 0.9rem !important;
            font-weight: 750 !important;
            line-height: 1 !important;
            min-height: 38px !important;
            padding: 8px 16px !important;
            white-space: nowrap;
        }

        div.st-key-season_round_grade_filter_control [data-testid="stButtonGroup"] button[aria-checked="true"],
        div.st-key-season_round_grade_filter_control div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        div.st-key-season_round_grade_filter_control div[data-testid="stSegmentedControl"] button[kind="primary"],
        div.st-key-season_round_grade_filter_control button[data-testid$="segmented_controlActive"] {
            background: #F0EDFF !important;
            box-shadow: none !important;
            color: var(--pitch) !important;
        }

        div.st-key-season_round_grade_filter_control button[data-testid^="stBaseButton"] {
            background: #F7F8FD !important;
            border: 1px solid #E4E8F4 !important;
            border-radius: 14px !important;
            box-shadow: none !important;
            color: #737998 !important;
            font-size: 0.86rem !important;
            font-weight: 800 !important;
            line-height: 1.14 !important;
            min-height: 42px !important;
            padding: 8px 10px !important;
            white-space: nowrap !important;
        }

        div.st-key-season_round_grade_filter_control button[data-testid="stBaseButton-primary"],
        div.st-key-season_round_grade_filter_control button[kind="primary"] {
            background: #F0EDFF !important;
            border-color: #ded8ff !important;
            color: var(--pitch) !important;
        }

        div.st-key-season_round_grade_filter_control button[data-testid^="stBaseButton"] p,
        div.st-key-season_round_grade_filter_control button[data-testid^="stBaseButton"] span {
            line-height: 1.14 !important;
            text-align: center !important;
            white-space: nowrap !important;
        }

        .season-round-grade-card {
            border: 1px solid #e8ebf7;
            border-radius: 16px;
            flex: 0 0 min(980px, 92vw);
            margin-top: 0;
            overflow: hidden;
            min-width: 0;
        }

        .season-round-scroll-shell {
            max-width: 100%;
            overflow: visible;
            width: 100%;
        }

        .season-round-panel-strip {
            display: flex;
            flex-wrap: nowrap;
            gap: 14px;
            max-width: 100%;
            overflow-x: auto;
            overflow-y: hidden;
            overscroll-behavior-inline: contain;
            padding: 2px 2px 12px;
            scroll-snap-type: x proximity;
            scrollbar-color: var(--club-border) transparent;
            scrollbar-width: thin;
            width: 100%;
            -webkit-overflow-scrolling: touch;
        }

        .season-round-panel-strip .season-round-grade-card {
            scroll-snap-align: start;
        }

        .season-round-grade-head {
            align-items: center;
            background: #fbfbff;
            border-bottom: 1px solid #e8ebf7;
            display: flex;
            gap: 12px;
            justify-content: space-between;
            padding: 12px 14px;
            min-width: 0;
        }

        .season-round-grade-head h3 {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 950;
            line-height: 1.16;
            margin: 0;
            min-width: 0;
            overflow-wrap: anywhere;
        }

        .season-round-grade-head .season-round-record {
            background: #F0EDFF;
            border: 1px solid #ded8ff;
            border-radius: 999px;
            color: #5b3df5;
            flex: 0 0 auto;
            font-size: 0.74rem;
            font-weight: 950;
            padding: 6px 9px;
            white-space: nowrap;
        }

        .season-round-grade-trophy {
            display: inline-block;
            margin-left: 6px;
        }

        .season-round-scroll {
            max-height: 312px;
            overflow-y: auto;
            overscroll-behavior: contain;
        }

        .season-round-scroll::-webkit-scrollbar {
            width: 8px;
        }

        .season-round-scroll::-webkit-scrollbar-thumb {
            background: #d8ddee;
            border-radius: 999px;
        }

        .season-round-row {
            align-items: center;
            border-top: 1px solid #e8ebf7;
            display: grid;
            gap: 10px;
            grid-template-columns: 54px minmax(190px, 1.5fr) minmax(132px, 1.05fr) minmax(118px, 0.9fr) minmax(118px, 0.9fr) 112px;
            min-height: 44px;
            padding: 8px 12px;
        }

        .season-round-grade-card.single-grade .season-round-row {
            grid-template-columns: 54px minmax(132px, 0.9fr) minmax(190px, 1.45fr) minmax(132px, 1.05fr) minmax(118px, 0.9fr) minmax(118px, 0.9fr) 112px;
        }

        .season-round-row:first-child {
            border-top: 0;
        }

        .season-round-premiership-row {
            background: linear-gradient(90deg, rgba(255, 246, 218, 0.78), rgba(255, 255, 255, 0.96));
            border-top-color: #f1dfad;
            box-shadow: inset 3px 0 0 #d9a441;
        }

        .season-round-head {
            background: #f8f8fd;
            color: #747b98;
            font-size: 0.68rem;
            font-weight: 950;
            letter-spacing: 0.04em;
            min-height: 38px;
            position: sticky;
            text-transform: uppercase;
            top: 0;
            z-index: 2;
        }

        .season-round-row strong {
            color: var(--ink);
            font-size: 0.86rem;
            font-weight: 950;
        }

        .season-round-row span {
            color: #626a88;
            font-size: 0.82rem;
            font-weight: 750;
            min-width: 0;
        }

        .season-round-opponent {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .season-round-result {
            align-items: center;
            display: flex;
            gap: 7px;
            min-width: 0;
        }

        .season-result-pill {
            border-radius: 999px;
            display: inline-flex;
            flex: 0 0 auto;
            font-size: 0.62rem;
            font-weight: 950;
            letter-spacing: 0.04em;
            padding: 5px 8px;
            text-transform: uppercase;
        }

        .season-result-pill.win {
            background: #e9f8ef;
            color: #137a4d;
        }

        .season-result-pill.loss {
            background: #ffe8ef;
            color: #9f2747;
        }

        .season-result-pill.draw,
        .season-result-pill.tie {
            background: #fff5d8;
            color: #9a6b05;
        }

        .season-result-pill.none {
            background: #F0EDFF;
            color: #5b3df5;
        }

        .season-round-scorecard-link {
            color: var(--pitch) !important;
            font-size: 0.78rem;
            font-weight: 900;
            text-decoration: none !important;
            white-space: nowrap;
        }

        .season-round-pending {
            color: #747b98 !important;
            font-size: 0.78rem !important;
            font-weight: 850 !important;
        }

        .season-round-empty {
            background: #f8f8fd;
            border: 1px dashed #d8ddeb;
            border-radius: 14px;
            color: #747b98;
            font-size: 0.86rem;
            font-weight: 800;
            padding: 12px 13px;
        }

        .historical-coverage-card {
            background: #ffffff;
            border: 1px solid #e4d39b;
            border-radius: 14px;
            box-shadow: 0 14px 32px rgba(48, 31, 5, 0.06);
            margin-top: 8px;
            padding: 24px;
        }

        .historical-coverage-kicker {
            color: #A87500;
            font-size: 0.75rem;
            font-weight: 900;
            text-transform: uppercase;
        }

        .historical-coverage-card h2 {
            color: var(--ink);
            font-size: 1.35rem;
            margin: 6px 0 8px;
        }

        .historical-coverage-card p,
        .historical-coverage-card li,
        .historical-coverage-source {
            color: #68708a;
            font-size: 0.9rem;
            line-height: 1.5;
        }

        .historical-coverage-card ul {
            margin: 14px 0 0;
            padding-left: 20px;
        }

        .historical-coverage-source {
            border-top: 1px solid #ece7d8;
            margin-top: 16px;
            padding-top: 12px;
        }

        .profile-coverage-meta {
            color: #7a641f;
        }

        .mobile-label {
            display: none;
        }

        .profile-breakdown-controls {
            align-items: center;
            display: flex;
            gap: 14px;
            justify-content: space-between;
            margin: 0 0 18px;
        }

        .profile-breakdown-controls .profile-segmented {
            margin-bottom: 0;
        }

        div.st-key-player_profile_performance_breakdown {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 0 20px 20px 20px;
            box-shadow: 0 16px 38px rgba(23, 27, 77, 0.06);
            margin-bottom: 20px;
            margin-top: -15px;
            overflow: visible;
            padding: 16px 20px 20px;
        }

        div.st-key-player_profile_performance_breakdown div.st-key-profile_breakdown_controls {
            margin: 0 0 12px;
        }

        .phase-row {
            align-items: center;
            border-top: 1px solid #eef0f7;
            display: grid;
            gap: 8px;
            grid-template-columns: minmax(104px, 1.2fr) repeat(5, minmax(48px, 0.7fr));
            padding: 10px 0;
        }

        .phase-row:first-of-type {
            border-top: 0;
        }

        .phase-name {
            align-items: center;
            display: flex;
            gap: 8px;
            min-width: 0;
        }

        .phase-name strong {
            color: var(--ink);
            font-size: 0.9rem;
            font-weight: 950;
            white-space: nowrap;
        }

        .phase-row span:not(.profile-best-badge) {
            color: #626a88;
            font-size: 0.78rem;
            font-weight: 850;
            text-align: right;
            white-space: nowrap;
        }

        .profile-fingerprint-card {
            margin-top: 2px;
        }

        .profile-fingerprint-insight {
            color: #4d5576;
            font-size: 0.92rem;
            font-weight: 750;
            line-height: 1.4;
            margin: 0 0 12px;
        }

        .fingerprint-legend {
            display: flex;
            gap: 14px;
            margin: 0 0 4px;
        }

        .fingerprint-legend span {
            align-items: center;
            color: #747b98;
            display: inline-flex;
            font-size: 0.76rem;
            font-weight: 850;
            gap: 6px;
        }

        .fingerprint-legend i.player {
            background: var(--club-primary, #6D4DFF);
            border-radius: 999px;
            height: 8px;
            width: 20px;
        }

        .fingerprint-legend i.club {
            background: #6b7280;
            border-radius: 999px;
            box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.96), 0 3px 9px rgba(23, 27, 77, 0.18);
            display: inline-block;
            height: 17px;
            opacity: 0.95;
            width: 4px;
        }

        .fingerprint-marker {
            z-index: 1;
        }

        .profile-fingerprint-card .profile-intelligence-note {
            font-size: 0.78rem;
            font-weight: 500;
        }

        .profile-position-footnote {
            color: #858ba3;
            font-size: 0.68rem;
            font-weight: 500;
            margin-top: 8px;
        }

        div.st-key-profile_bowling_phase_card {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 18px;
            box-shadow: 0 16px 38px rgba(23, 27, 77, 0.06);
            margin: 2px 0 18px;
            padding: 18px 20px;
        }

        div.st-key-profile_bowling_phase_card .profile-intelligence-card-head {
            margin-bottom: 10px;
        }

        .phase-table {
            border: 1px solid #eef0f7;
            border-radius: 14px;
            overflow-x: auto;
        }

        .phase-table-row {
            align-items: center;
            border-top: 1px solid #eef0f7;
            display: grid;
            gap: 5px;
            grid-template-columns: minmax(78px, 1fr) minmax(36px, 0.42fr) minmax(36px, 0.42fr) minmax(44px, 0.5fr) minmax(42px, 0.48fr) minmax(42px, 0.48fr) minmax(62px, 0.62fr) minmax(68px, 0.66fr);
            min-width: 520px;
            padding: 9px 8px;
        }

        .phase-table-row:first-child {
            border-top: 0;
        }

        .phase-table-head {
            background: #f8f8fd;
            color: #747b98;
            font-size: 0.66rem;
            font-weight: 950;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }

        .phase-table-row span,
        .phase-table-phase {
            color: var(--ink);
            font-size: 0.78rem;
            font-weight: 900;
            text-align: right;
            white-space: nowrap;
        }

        .phase-table-head span {
            color: #747b98;
        }

        .phase-table-row:not(.phase-table-head) > span {
            color: var(--ink);
            font-size: 0.86rem;
            font-weight: 950;
        }

        .phase-table-row .phase-table-phase,
        .phase-table-head span:first-child {
            text-align: left;
        }

        .phase-table-phase {
            align-items: center;
            display: inline-flex;
            gap: 6px;
            justify-content: flex-start;
            min-width: 0;
        }

        .phase-table-phase strong {
            color: var(--ink);
            font-size: 0.88rem;
            font-weight: 950;
        }

        .profile-phase-footnote {
            color: #858ba3;
            font-size: 0.76rem;
            font-weight: 500;
            line-height: 1.36;
            margin: 10px 0 0;
        }

        .peer-card {
            background: #ffffff;
            border: 1px solid #e9ebf4;
            border-radius: 18px;
            box-shadow: 0 16px 38px rgba(23, 27, 77, 0.06);
            margin-bottom: 18px;
            padding: 20px 22px 18px;
        }

        .peer-card h4 {
            align-items: center;
            color: var(--ink);
            display: flex;
            font-size: 1.05rem;
            font-weight: 950;
            gap: 9px;
            margin: 0 0 14px;
        }

        .peer-card h4::before {
            background: var(--peer-accent, var(--club-primary, #28485F));
            border-radius: 999px;
            content: "";
            display: inline-block;
            height: 9px;
            width: 9px;
        }

        .peer-explainer {
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 8px 18px;
            margin: -8px 0 16px;
        }

        .peer-legend {
            align-items: center;
            color: #5d6684;
            display: flex;
            flex-wrap: wrap;
            font-size: 0.78rem;
            font-weight: 800;
            gap: 14px;
        }

        .peer-legend span {
            align-items: center;
            display: inline-flex;
            gap: 6px;
        }

        .legend-dot {
            background: var(--club-primary, #28485F);
            border-radius: 999px;
            box-shadow: 0 0 0 3px rgba(var(--club-primary-rgb), 0.12);
            display: inline-block;
            height: 9px;
            width: 9px;
        }

        .legend-marker {
            background: #6b7280;
            border-radius: 999px;
            box-shadow: 0 0 0 3px rgba(107, 114, 128, 0.12);
            display: inline-block;
            height: 14px;
            width: 4px;
        }

        .peer-note {
            color: #8a90aa;
            font-size: 0.76rem;
            font-weight: 650;
        }

        .peer-row {
            border-top: 1px solid #eef0f6;
            padding: 9px 0 8px;
        }

        .peer-row:first-of-type {
            border-top: 0;
            padding-top: 0;
        }

        .peer-row-top,
        .peer-row-meta {
            align-items: center;
            display: flex;
            justify-content: space-between;
            gap: 12px;
        }

        .peer-metric {
            color: #747b98;
            display: flex;
            flex-direction: column;
            font-size: 0.82rem;
            font-weight: 850;
            gap: 2px;
            line-height: 1.15;
        }

        .peer-metric-note {
            color: #9aa1b8;
            font-size: 0.68rem;
            font-weight: 700;
        }

        .peer-value {
            color: var(--ink);
            font-size: 0.95rem;
            font-weight: 950;
        }

        .peer-row-meta {
            color: #8a90aa;
            font-size: 0.72rem;
            font-weight: 700;
            margin-top: 2px;
        }

        .peer-status {
            border-radius: 999px;
            font-size: 0.68rem;
            font-weight: 900;
            padding: 3px 8px;
            white-space: nowrap;
        }

        .peer-status.positive {
            background: #e8f8ef;
            color: #087443;
        }

        .peer-status.neutral {
            background: #eef1f7;
            color: #59627f;
        }

        .peer-status.negative {
            background: #fdecef;
            color: #b42342;
        }

        .peer-range {
            background: #eef1f7;
            border-radius: 999px;
            height: 7px;
            margin-top: 6px;
            overflow: visible;
            position: relative;
            width: 100%;
        }

        .peer-fill {
            background: linear-gradient(90deg, var(--club-primary, #28485F), var(--club-link, #0B4EA2));
            border-radius: inherit;
            height: 100%;
            left: 0;
            position: absolute;
            top: 0;
        }

        .fingerprint-row .peer-range {
            margin-top: 7px;
        }

        .peer-marker {
            border-radius: 999px;
            position: absolute;
            top: 50%;
            transform: translate(-50%, -50%);
        }

        .player-marker {
            background: var(--club-primary, #28485F);
            box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.95), 0 5px 12px rgba(23, 27, 77, 0.16);
            height: 13px;
            width: 13px;
            z-index: 2;
        }

        .avg-marker {
            background: #6b7280;
            box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.96), 0 3px 9px rgba(23, 27, 77, 0.18);
            height: 17px;
            opacity: 0.95;
            width: 4px;
            z-index: 1;
        }

        .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control div[data-testid="stSegmentedControl"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control div[data-testid="stSegmentedControl"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control div[data-testid="stSegmentedControl"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control div[data-testid="stSegmentedControl"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control div[data-testid="stSegmentedControl"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control [data-testid="stButtonGroup"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control [data-testid="stButtonGroup"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control [data-testid="stButtonGroup"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control [data-testid="stButtonGroup"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control [data-testid="stButtonGroup"] {
            background: #F7F8FD;
            border: 1px solid #E9ECF6;
            border-radius: 999px;
            box-shadow: none;
            display: inline-flex;
            gap: 4px;
            max-width: 100%;
            overflow-x: auto;
            padding: 5px;
            width: fit-content;
        }

        .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control div[data-testid="stSegmentedControl"] button,
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control div[data-testid="stSegmentedControl"] button,
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control div[data-testid="stSegmentedControl"] button,
        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control div[data-testid="stSegmentedControl"] button,
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control div[data-testid="stSegmentedControl"] button,
        .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control [data-testid="stButtonGroup"] button,
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control [data-testid="stButtonGroup"] button,
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control [data-testid="stButtonGroup"] button,
        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control [data-testid="stButtonGroup"] button,
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control [data-testid="stButtonGroup"] button,
        .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control button[data-testid^="stBaseButton-segmented_control"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control button[data-testid^="stBaseButton-segmented_control"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control button[data-testid^="stBaseButton-segmented_control"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control button[data-testid^="stBaseButton-segmented_control"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control button[data-testid^="stBaseButton-segmented_control"] {
            background: transparent !important;
            border: 0 !important;
            border-radius: 999px !important;
            color: #737998 !important;
            flex: 0 0 auto;
            font-size: 0.9rem !important;
            font-weight: 750 !important;
            line-height: 1 !important;
            min-height: 38px !important;
            padding: 8px 16px !important;
            white-space: nowrap;
        }

        .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control [data-testid="stButtonGroup"] button[aria-checked="true"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control [data-testid="stButtonGroup"] button[aria-checked="true"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control [data-testid="stButtonGroup"] button[aria-checked="true"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control [data-testid="stButtonGroup"] button[aria-checked="true"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control [data-testid="stButtonGroup"] button[aria-checked="true"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control div[data-testid="stSegmentedControl"] button[kind="primary"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control div[data-testid="stSegmentedControl"] button[kind="primary"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control div[data-testid="stSegmentedControl"] button[kind="primary"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control div[data-testid="stSegmentedControl"] button[kind="primary"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control div[data-testid="stSegmentedControl"] button[kind="primary"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control button[data-testid$="segmented_controlActive"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control button[data-testid$="segmented_controlActive"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control button[data-testid$="segmented_controlActive"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control button[data-testid$="segmented_controlActive"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control button[data-testid$="segmented_controlActive"] {
            background: #F0EDFF !important;
            box-shadow: none !important;
            color: var(--pitch) !important;
        }

        .hof-progress-row {
            margin: 13px 0;
        }

        .record-card {
            min-height: 146px;
        }

        .profile-highlights-grid {
            display: grid;
            gap: 18px;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-bottom: 18px;
        }

        .profile-highlights-grid .record-card {
            height: 100%;
            margin-bottom: 0;
        }

        .record-label {
            color: #727999;
            font-size: 0.72rem;
            font-weight: 900;
            letter-spacing: 0.04em;
            text-transform: none;
        }

        .record-player {
            color: var(--ink);
            font-size: 1.08rem;
            font-weight: 950;
            line-height: 1.18;
            margin-top: 16px;
        }

        .record-value {
            color: var(--club-primary, #4b37d8);
            font-size: 1.38rem;
            font-weight: 950;
            margin-top: 8px;
        }

        .record-card-compact-value .record-value {
            color: var(--club-primary, #4b37d8);
            font-size: 1.08rem;
            font-weight: 950;
            line-height: 1.32;
            margin-top: 10px;
        }

        .table-total-line {
            color: #747b98;
            font-size: 0.84rem;
            font-weight: 800;
            margin: 10px 0 2px;
        }

        .record-meta {
            color: #858ba6;
            font-size: 0.8rem;
            font-weight: 700;
            margin-top: 12px;
        }

        .leader-highlight-card {
            min-height: 174px;
        }

        .leader-highlight-count {
            color: var(--ink);
            font-size: 1.08rem;
            font-weight: 950;
            line-height: 1.18;
            margin-top: 16px;
        }

        .leader-highlight-details {
            align-items: flex-start;
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 10px;
        }

        .leader-highlight-details a,
        .leader-highlight-more {
            color: var(--club-link, var(--club-primary));
            font-size: 0.74rem;
            font-weight: 950 !important;
            line-height: 1.1;
            text-decoration: none;
        }

        .leader-highlight-details a:hover {
            color: var(--club-link-hover);
            text-decoration: underline;
        }

        .leader-highlight-chip,
        .leader-highlight-more {
            background: rgba(var(--club-primary-rgb, 16, 74, 168), 0.08);
            border: 1px solid rgba(var(--club-primary-rgb, 16, 74, 168), 0.16);
            border-radius: 999px;
            max-width: 100%;
            min-width: 0;
            overflow: hidden;
            padding: 6px 8px;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .leader-highlight-chip {
            display: inline-grid;
            gap: 5px;
            grid-template-columns: minmax(0, 1fr) auto;
        }

        .leader-highlight-chip-stacked {
            align-items: flex-start;
            border-radius: 18px;
            display: inline-flex;
            flex-direction: column;
            gap: 2px;
            max-width: 100%;
            min-width: 0;
            padding: 7px 9px;
            text-align: left;
            width: 100%;
            white-space: normal;
        }

        .leader-highlight-more {
            display: inline-flex;
        }

        .leader-highlight-chip-grade {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .leader-highlight-chip-stacked .leader-highlight-chip-grade {
            display: block;
            font-size: 0.66rem;
            line-height: 1.1;
            max-width: 100%;
            overflow: hidden;
            overflow-wrap: anywhere;
            text-overflow: clip;
            white-space: normal;
        }

        .leader-highlight-chip-season {
            color: var(--ink);
            font-size: 0.68rem;
            font-weight: 950;
            white-space: nowrap;
        }

        .leader-highlight-chip-stacked .leader-highlight-chip-season {
            color: var(--club-link, var(--club-primary));
            display: block;
            font-size: 0.62rem;
            line-height: 1.05;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
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

        .milestone-segmented {
            align-items: center;
            background: #ffffff;
            border: 1px solid #e7e6f5;
            border-radius: 22px;
            box-shadow: 0 12px 26px rgba(23, 27, 77, 0.055);
            display: flex;
            gap: 8px;
            margin: 30px 0 38px;
            max-width: 100%;
            overflow-x: auto;
            padding: 8px;
            width: fit-content;
        }

        .milestone-segmented-compact {
            margin: 0 0 24px;
        }

        .milestone-segment {
            border-radius: 999px;
            color: #3f4565 !important;
            display: inline-flex;
            font-size: 0.88rem;
            font-weight: 900;
            justify-content: center;
            line-height: 1.1;
            padding: 12px 18px;
            text-decoration: none !important;
            transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
            white-space: nowrap;
        }

        .milestone-label-mobile {
            display: none;
        }

        .milestone-segment:hover,
        .milestone-segment:focus-visible {
            background: var(--club-primary-soft, #f1edff);
            color: var(--club-primary, #4b37d8) !important;
        }

        .milestone-segment.active {
            background: linear-gradient(135deg, var(--club-primary, #4b37d8), var(--club-accent, #6d4dff));
            box-shadow: 0 10px 24px rgba(var(--club-primary-rgb, 75, 55, 216), 0.18);
            color: #ffffff !important;
        }

        .milestone-view-panel,
        div.st-key-milestone_upcoming_panel,
        div.st-key-milestone_achieved_panel,
        div.st-key-milestone_exclusive_panel {
            background: #ffffff;
            border: 1px solid rgba(231, 230, 245, 0.92);
            border-radius: 0 28px 28px 28px;
            box-shadow: 0 22px 52px rgba(23, 27, 77, 0.055);
            margin-top: -15px;
            overflow: visible;
            padding: 24px 26px 26px;
        }

        div.st-key-milestone_upcoming_panel .milestone-section-heading,
        div.st-key-milestone_achieved_panel .milestone-section-heading,
        div.st-key-milestone_exclusive_panel .milestone-section-heading {
            padding-top: 0;
        }

        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control {
            margin: 0 0 20px;
        }

        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control {
            margin: 20px 0 24px;
        }

        div.st-key-milestone_exclusive_panel .milestone-segmented-compact {
            margin: 20px 0 24px;
        }

        .milestone-section-heading h2 {
            color: var(--ink);
            font-size: clamp(1.85rem, 3.8vw, 2.55rem);
            font-weight: 950;
            letter-spacing: 0;
            line-height: 1.05;
            margin: 0;
        }

        .milestone-section-subtitle {
            color: #687093;
            font-size: 0.95rem;
            font-weight: 720;
            margin: 8px 0 26px;
        }

        .milestone-watch-grid,
        .milestone-club-grid {
            display: grid;
            gap: 18px;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .milestone-group-card,
        .milestone-club-card {
            background: #ffffff;
            border: 1px solid #e7e6f5;
            border-radius: 22px;
            box-shadow: 0 10px 26px rgba(23, 27, 77, 0.055);
            padding: 18px;
        }

        .milestone-group-head {
            align-items: center;
            display: flex;
            gap: 12px;
            justify-content: space-between;
            margin-bottom: 14px;
        }

        .milestone-group-title {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 950;
        }

        .milestone-group-rule {
            background: #f8f6ff;
            border: 1px solid #e5e1ff;
            border-radius: 999px;
            color: #5b5f7d;
            flex: 0 0 auto;
            font-size: 0.72rem;
            font-weight: 850;
            padding: 6px 9px;
            white-space: nowrap;
        }

        .milestone-progress-card {
            background: linear-gradient(180deg, #ffffff 0%, #fbfbff 100%);
            border: 1px solid #e8e8f4;
            border-radius: 18px;
            margin-top: 12px;
            padding: 15px;
        }

        .milestone-progress-list {
            max-height: calc(6 * 98px);
            overflow-y: auto;
            padding-right: 7px;
            scrollbar-color: var(--club-border) transparent;
            scrollbar-width: thin;
        }

        .milestone-progress-top {
            align-items: flex-start;
            display: flex;
            gap: 12px;
            justify-content: space-between;
        }

        .milestone-progress-top strong {
            color: var(--ink);
            display: block;
            font-size: 1rem;
            font-weight: 950;
            line-height: 1.16;
            margin-bottom: 5px;
        }

        .milestone-progress-top span:not(.milestone-row-badge) {
            color: #687093;
            display: block;
            font-size: 0.88rem;
            font-weight: 820;
        }

        .milestone-row-badge {
            background: #eef0ff;
            border: 1px solid #dfe2ff;
            border-radius: 999px;
            color: #4b37d8;
            display: inline-flex;
            font-size: 0.68rem;
            font-weight: 950;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
            padding: 4px 8px;
            text-transform: uppercase;
        }

        .milestone-away {
            color: #4b37d8;
            flex: 0 0 auto;
            font-size: 0.83rem;
            font-weight: 900;
            text-align: right;
            white-space: nowrap;
        }

        .milestone-empty-card {
            background: #fbfbff;
            border: 1px dashed #d9dbec;
            border-radius: 18px;
            color: #687093;
            font-size: 0.9rem;
            font-weight: 760;
            line-height: 1.4;
            padding: 16px;
        }

        .milestone-hof-watch {
            background:
                linear-gradient(135deg, rgba(75, 55, 216, 0.09), rgba(122, 23, 53, 0.05)),
                #ffffff;
            border: 1px solid #e2dfff;
            border-radius: 24px;
            box-shadow: 0 10px 26px rgba(23, 27, 77, 0.055);
            margin-top: 22px;
            padding: 20px;
        }

        .milestone-hof-watch h3,
        .milestone-achievement-group h3 {
            color: var(--ink);
            font-size: 1.12rem;
            font-weight: 950;
            margin: 0 0 14px;
        }

        .milestone-hof-watch .milestone-group-head h3 {
            margin-bottom: 4px;
        }

        .milestone-mini-subtitle {
            color: #687093;
            font-size: 0.88rem;
            font-weight: 720;
        }

        .milestone-mini-grid {
            display: grid;
            gap: 14px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .milestone-mini-scroll,
        .milestone-achievement-scroll {
            max-height: 392px;
            overflow-y: auto;
            padding-right: 7px;
            scrollbar-color: var(--club-border) transparent;
            scrollbar-width: thin;
        }

        .milestone-mini-card {
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid rgba(231, 230, 245, 0.95);
            border-radius: 17px;
            padding: 14px;
        }

        .milestone-mini-card strong {
            display: block;
            font-size: 0.95rem;
            font-weight: 950;
            line-height: 1.16;
            margin-bottom: 5px;
        }

        .milestone-mini-card div {
            color: #687093;
            font-size: 0.82rem;
            font-weight: 760;
            line-height: 1.35;
        }

        .achievement-grid {
            display: grid;
            gap: 16px;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin-bottom: 28px;
        }

        .milestone-achievement-group {
            margin-top: 22px;
        }

        .milestone-achievement-group:first-of-type {
            margin-top: 0;
        }

        .achievement-card {
            background:
                linear-gradient(135deg, rgba(109, 77, 255, 0.09), rgba(128, 20, 55, 0.06)),
                #ffffff;
            border: 1px solid #e9e6fb;
            border-radius: 18px;
            box-shadow: 0 16px 34px rgba(23, 27, 77, 0.06);
            min-height: 164px;
            padding: 18px 19px;
        }

        .achievement-badge {
            background: #eaf8ef;
            border: 1px solid #c7ecd2;
            border-radius: 999px;
            color: #187a3f;
            display: inline-flex;
            font-size: 0.72rem;
            font-weight: 900;
            margin-bottom: 12px;
            padding: 5px 9px;
            text-transform: uppercase;
        }

        .achievement-badge-gold {
            background: #fff5dd;
            border-color: #ffe5a4;
            color: #a76800;
        }

        .achievement-player {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 950;
            line-height: 1.16;
            margin-bottom: 6px;
        }

        .achievement-value {
            color: #4b37d8;
            font-size: 1.08rem;
            font-weight: 950;
            line-height: 1.15;
            margin-bottom: 8px;
        }

        .achievement-meta,
        .achievement-total {
            color: #747b98;
            font-size: 0.82rem;
            font-weight: 750;
            line-height: 1.35;
        }

        .achievement-total {
            color: #3d4263;
            margin-top: 5px;
        }

        .milestone-club-card {
            margin-bottom: 14px;
            overflow: hidden;
            padding: 0;
        }

        .milestone-club-card-head {
            background: linear-gradient(135deg, #ffffff, #f7f5ff);
            border-bottom: 1px solid #ecebf7;
            padding: 16px 17px;
        }

        .milestone-club-name {
            color: var(--ink);
            font-size: 1.08rem;
            font-weight: 950;
            margin-bottom: 3px;
        }

        .milestone-club-count {
            color: #687093;
            font-size: 0.84rem;
            font-weight: 760;
        }

        .milestone-member-list {
            display: grid;
            gap: 9px;
            max-height: 259px;
            overflow-y: auto;
            padding: 14px 17px 17px;
            scrollbar-color: var(--club-border) transparent;
            scrollbar-width: thin;
        }

        .milestone-member-row {
            align-items: center;
            display: flex;
            gap: 8px;
            justify-content: space-between;
            min-height: 38px;
        }

        .milestone-member-row span {
            color: var(--ink);
            font-size: 0.9rem;
            font-weight: 850;
            min-width: 0;
        }

        .milestone-member-row strong {
            color: var(--club-link, #28485F);
            flex: 0 0 auto;
            font-size: 0.86rem;
            font-weight: 950;
        }

        .milestone-progress-top a,
        .milestone-watch-top a,
        .milestone-member-row a {
            color: #000000 !important;
        }

        div[class*="st-key-milestone_club_"][class*="_control"] {
            margin: -7px 0 18px;
        }

        div[class*="st-key-milestone_club_"][class*="_control"] .stButton {
            display: flex;
            justify-content: flex-start;
        }

        div[class*="st-key-milestone_club_"][class*="_control"] .stButton > button {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: #5B3DF5 !important;
            display: inline-flex !important;
            font-size: 0.82rem !important;
            font-weight: 850 !important;
            min-height: 0 !important;
            padding: 2px 0 !important;
            text-align: left !important;
            width: auto !important;
        }

        div[class*="st-key-milestone_club_"][class*="_control"] .stButton > button:hover,
        div[class*="st-key-milestone_club_"][class*="_control"] .stButton > button:focus {
            color: #4324D8 !important;
            text-decoration: underline !important;
        }

        .block-container:has(.near-milestones-page) .page-title {
            font-size: clamp(2.3rem, 3vw, 3.2rem);
            max-width: 1040px;
            margin: 0 0 6px;
        }

        .block-container:has(.near-milestones-page) .club-label {
            color: #5B3DF5;
            font-weight: 800;
            margin: 0;
        }

        .block-container:has(.near-milestones-page) .page-subtitle {
            color: #7a809d;
            font-size: 0.95rem;
            font-weight: 400;
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
            font-size: 0.83rem;
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

        .block-container:has(.player-profile-v2-page) {
            padding-top: 1.15rem;
        }

        .player-v2-topline {
            color: #6d4dff;
            font-size: 0.78rem;
            font-weight: 950;
            letter-spacing: 0.11em;
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .player-v2-title-row {
            align-items: flex-start;
            display: flex;
            gap: 18px;
            justify-content: space-between;
            margin-bottom: 24px;
        }

        .player-v2-page-title {
            color: var(--ink);
            font-size: clamp(2.4rem, 4vw, 4.25rem);
            letter-spacing: 0;
            line-height: 0.96;
            margin: 0 0 7px;
        }

        .block-container:has(.player-profile-v2-page) .club-label {
            color: #5B3DF5;
            font-weight: 800;
            margin: 0;
        }

        .player-v2-preview-badge {
            background: #f1edff;
            border: 1px solid #ded8ff;
            border-radius: 999px;
            color: #4b37d8;
            flex: 0 0 auto;
            font-size: 0.78rem;
            font-weight: 900;
            margin-top: 8px;
            padding: 9px 12px;
        }

        div.st-key-player_v2_selector_card {
            background:
                radial-gradient(circle at 100% 0%, rgba(109, 77, 255, 0.09), transparent 18rem),
                rgba(255, 255, 255, 0.95);
            border: 1px solid #e7e9f4;
            border-radius: 24px;
            box-shadow: 0 16px 38px rgba(23, 27, 77, 0.06);
            margin: 0 0 22px;
            padding: 18px 22px 14px;
        }

        div.st-key-player_v2_selector_card label {
            color: var(--ink) !important;
            font-size: 0.92rem !important;
            font-weight: 900 !important;
            letter-spacing: 0.02em;
        }

        div.st-key-player_v2_selector_card [data-baseweb="select"] > div {
            border-color: #e2e6f3;
            border-radius: 16px;
            min-height: 52px;
        }

        .player-v2-hero {
            background:
                linear-gradient(135deg, rgba(8, 11, 63, 0.97), rgba(25, 18, 91, 0.95)),
                radial-gradient(circle at 78% 18%, rgba(109, 77, 255, 0.32), transparent 24rem),
                radial-gradient(circle at 98% 75%, rgba(167, 104, 0, 0.20), transparent 22rem);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 34px;
            box-shadow: 0 22px 52px rgba(23, 27, 77, 0.08);
            color: #ffffff;
            margin: 0 0 20px;
            overflow: hidden;
            padding: 34px;
            position: relative;
        }

        .player-v2-hero::after {
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 999px;
            content: "";
            height: 290px;
            position: absolute;
            right: -105px;
            top: -112px;
            width: 290px;
        }

        .player-v2-hero-grid {
            display: grid;
            gap: 30px;
            grid-template-columns: minmax(0, 1.12fr) minmax(330px, 0.88fr);
            position: relative;
            z-index: 1;
        }

        .player-v2-club-eyebrow {
            color: #d8d1ff;
            font-size: 0.82rem;
            font-weight: 950;
            letter-spacing: 0.12em;
            margin-bottom: 14px;
            text-transform: uppercase;
        }

        .player-v2-hero h2 {
            color: #ffffff;
            font-size: clamp(3rem, 7vw, 6.1rem);
            letter-spacing: 0;
            line-height: 0.9;
            margin: 0 0 14px;
            max-width: 780px;
        }

        .player-v2-hero-copy {
            color: #e8e6ff;
            font-size: clamp(1rem, 1.7vw, 1.22rem);
            font-weight: 650;
            line-height: 1.5;
            margin: 0;
            max-width: 670px;
        }

        .player-v2-badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 9px;
            margin-top: 22px;
        }

        .player-v2-badge {
            align-items: center;
            background: rgba(255, 255, 255, 0.11);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 999px;
            color: #ffffff;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 870;
            padding: 8px 11px;
            white-space: nowrap;
        }

        .player-v2-badge.gold {
            background: rgba(255, 245, 221, 0.15);
            border-color: rgba(255, 230, 170, 0.32);
            color: #fff2c2;
        }

        .player-v2-badge.green {
            background: rgba(234, 248, 241, 0.14);
            border-color: rgba(177, 233, 207, 0.30);
            color: #cbf4e3;
        }

        .player-v2-identity-panel {
            background: rgba(255, 255, 255, 0.10);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 28px;
            padding: 18px;
        }

        .player-v2-signature-card {
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 22px;
            margin-bottom: 14px;
            padding: 18px;
        }

        .player-v2-signature-card small,
        .player-v2-fact small {
            color: #d8d1ff;
            display: block;
            font-size: 0.72rem;
            font-weight: 900;
            letter-spacing: 0.08em;
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .player-v2-signature-card strong {
            display: block;
            font-size: 1.8rem;
            font-weight: 950;
            line-height: 1.08;
            margin-bottom: 7px;
        }

        .player-v2-signature-card span {
            color: #eeeaff;
            display: block;
            font-size: 0.9rem;
            font-weight: 720;
            line-height: 1.4;
        }

        .player-v2-facts {
            display: grid;
            gap: 10px;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .player-v2-fact {
            background: rgba(255, 255, 255, 0.09);
            border: 1px solid rgba(255, 255, 255, 0.13);
            border-radius: 18px;
            padding: 14px;
        }

        .player-v2-fact strong {
            color: #ffffff;
            display: block;
            font-size: 1.1rem;
            font-weight: 950;
            line-height: 1.15;
        }

        .player-v2-stat-strip {
            background: rgba(255, 255, 255, 0.95);
            border: 1px solid #e7e6f5;
            border-radius: 28px;
            box-shadow: 0 10px 26px rgba(23, 27, 77, 0.055);
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            margin: 20px 0 28px;
            overflow: hidden;
        }

        .player-v2-stat-tile {
            border-bottom: 1px solid #e7e6f5;
            border-right: 1px solid #e7e6f5;
            padding: 18px;
        }

        .player-v2-stat-tile:nth-child(6n) {
            border-right: 0;
        }

        .player-v2-stat-tile:nth-last-child(-n+6) {
            border-bottom: 0;
        }

        .player-v2-stat-tile span,
        .player-v2-kicker {
            color: #687093;
            display: block;
            font-size: 0.76rem;
            font-weight: 950;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .player-v2-stat-tile strong {
            color: var(--ink);
            display: block;
            font-size: 1.34rem;
            font-weight: 950;
            line-height: 1.05;
            margin-top: 8px;
        }

        .player-v2-section {
            margin: 34px 0 0;
        }

        .player-v2-section-head {
            align-items: end;
            display: flex;
            gap: 18px;
            justify-content: space-between;
            margin-bottom: 16px;
        }

        .player-v2-section-head h2 {
            color: var(--ink);
            font-size: clamp(1.8rem, 3.4vw, 3rem);
            letter-spacing: 0;
            line-height: 1;
            margin: 0;
        }

        .player-v2-section-head p {
            color: #687093;
            font-size: 0.95rem;
            font-weight: 760;
            line-height: 1.45;
            margin: 9px 0 0;
            max-width: 740px;
        }

        .player-v2-trust-chip {
            background: #ffffff;
            border: 1px solid #e7e6f5;
            border-radius: 999px;
            color: #4b37d8;
            flex: 0 0 auto;
            font-size: 0.78rem;
            font-weight: 900;
            padding: 8px 11px;
            white-space: nowrap;
        }

        .player-v2-grid {
            display: grid;
            gap: 16px;
        }

        .player-v2-grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .player-v2-grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .player-v2-grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }

        .player-v2-card,
        .player-v2-performance-card,
        .player-v2-progress-card,
        .player-v2-coverage-card {
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid rgba(231, 230, 245, 0.98);
            border-radius: 26px;
            box-shadow: 0 10px 26px rgba(23, 27, 77, 0.055);
        }

        .player-v2-card {
            padding: 20px;
        }

        .player-v2-card h3,
        .player-v2-peer-card h3,
        .player-v2-coverage-card h3 {
            color: var(--ink);
            font-size: 1.32rem;
            letter-spacing: 0;
            line-height: 1.12;
            margin: 8px 0 10px;
        }

        .player-v2-card p,
        .player-v2-coverage-card p {
            color: #687093;
            font-size: 0.92rem;
            font-weight: 650;
            line-height: 1.48;
            margin: 0;
        }

        .player-v2-traits {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }

        .player-v2-traits span {
            background: var(--club-primary-soft, #EAF3FF);
            border: 1px solid rgba(var(--club-primary-rgb, 11, 63, 159), 0.16);
            border-radius: 999px;
            color: var(--club-primary, #6D4DFF);
            font-size: 0.76rem;
            font-weight: 900;
            padding: 7px 10px;
        }

        .player-v2-meter,
        .player-v2-progress-track,
        .player-v2-range {
            background: #eeedf8;
            border-radius: 999px;
            overflow: hidden;
        }

        .player-v2-meter {
            height: 8px;
            margin-top: 14px;
        }

        .player-v2-meter span,
        .player-v2-progress-track span {
            background: linear-gradient(90deg, var(--club-primary, #6D4DFF), var(--club-secondary, #22c7dc));
            border-radius: 999px;
            display: block;
            height: 100%;
        }

        .player-v2-coach-card {
            background:
                linear-gradient(135deg, rgba(var(--club-primary-rgb, 11, 63, 159), 0.055), rgba(255,255,255,0) 72%),
                #ffffff;
        }

        .player-v2-peer-card {
            display: grid;
            gap: 14px;
        }

        .player-v2-peer-row {
            display: grid;
            gap: 8px;
        }

        .player-v2-peer-top,
        .player-v2-peer-meta {
            align-items: center;
            display: flex;
            gap: 12px;
            justify-content: space-between;
        }

        .player-v2-peer-top strong {
            color: var(--ink);
            font-size: 0.94rem;
            font-weight: 950;
        }

        .player-v2-peer-top span {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 950;
        }

        .player-v2-peer-meta span,
        .player-v2-peer-meta em {
            color: #687093;
            font-size: 0.77rem;
            font-style: normal;
            font-weight: 850;
        }

        .player-v2-peer-meta em.positive {
            color: #166b55;
        }

        .player-v2-peer-meta em.negative {
            color: #7a1735;
        }

        .player-v2-range {
            height: 9px;
            position: relative;
        }

        .player-v2-marker {
            border: 3px solid #ffffff;
            border-radius: 999px;
            box-shadow: 0 2px 8px rgba(8, 11, 63, 0.18);
            height: 16px;
            position: absolute;
            top: 50%;
            transform: translate(-50%, -50%);
            width: 16px;
        }

        .player-v2-marker.player { background: var(--club-primary, #6D4DFF); }
        .player-v2-marker.peer { background: #8a90aa; }

        .player-v2-card-head {
            align-items: center;
            display: flex;
            gap: 10px;
            justify-content: space-between;
        }

        .player-v2-card-head span {
            background: var(--club-primary-soft, #EAF3FF);
            border: 1px solid rgba(var(--club-primary-rgb, 11, 63, 159), 0.16);
            border-radius: 999px;
            color: var(--club-primary, #6D4DFF);
            flex: 0 0 auto;
            font-size: 0.72rem;
            font-weight: 900;
            padding: 7px 9px;
        }

        .player-v2-break-row {
            align-items: center;
            display: grid;
            gap: 12px;
            grid-template-columns: 96px minmax(0, 1fr) 64px;
            margin-top: 13px;
        }

        .player-v2-break-row strong {
            color: var(--ink);
            font-size: 0.86rem;
            font-weight: 900;
            min-width: 0;
        }

        .player-v2-break-row div {
            background: #eeedf8;
            border-radius: 999px;
            height: 12px;
            overflow: hidden;
        }

        .player-v2-break-row div span {
            background: linear-gradient(90deg, var(--club-primary, #6D4DFF), var(--club-secondary, #22c7dc));
            border-radius: 999px;
            display: block;
            height: 100%;
        }

        .player-v2-break-row em {
            color: #687093;
            font-size: 0.82rem;
            font-style: normal;
            font-weight: 900;
            text-align: right;
        }

        .player-v2-insight {
            background: #f8f6ff;
            border: 1px solid #e1ddff;
            border-radius: 18px;
            color: #34395c !important;
            font-size: 0.9rem !important;
            font-weight: 730 !important;
            line-height: 1.45 !important;
            margin-top: 16px !important;
            padding: 13px 14px;
        }

        .player-v2-mini-grid {
            display: grid;
            gap: 10px;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin: 16px 0;
        }

        .player-v2-mini-grid div {
            background: #f8f6ff;
            border: 1px solid #e6e2ff;
            border-radius: 18px;
            padding: 13px;
        }

        .player-v2-mini-grid span {
            color: #687093;
            display: block;
            font-size: 0.72rem;
            font-weight: 900;
            letter-spacing: 0.06em;
            margin-bottom: 6px;
            text-transform: uppercase;
        }

        .player-v2-mini-grid strong {
            color: var(--ink);
            display: block;
            font-size: 1.12rem;
            font-weight: 950;
        }

        .player-v2-performance-card {
            overflow: hidden;
            padding: 0;
        }

        .player-v2-performance-head {
            background: linear-gradient(135deg, rgba(75, 55, 216, 0.10), rgba(122, 23, 53, 0.08));
            border-bottom: 1px solid #e7e6f5;
            padding: 18px;
        }

        .player-v2-performance-value {
            color: var(--ink);
            font-size: 2.05rem;
            font-weight: 950;
            line-height: 1;
            margin-top: 6px;
        }

        .player-v2-performance-body {
            padding: 18px;
        }

        .player-v2-performance-body h3 {
            color: var(--ink);
            font-size: 1.2rem;
            margin: 0 0 8px;
        }

        .player-v2-performance-body p {
            color: #687093;
            font-size: 0.86rem;
            font-weight: 740;
            line-height: 1.45;
            margin: 0;
        }

        .player-v2-subtle-link {
            background: #f8f6ff;
            border: 1px solid #e1ddff;
            border-radius: 999px;
            color: #4b37d8 !important;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 900;
            margin-top: 13px;
            padding: 8px 10px;
            text-decoration: none !important;
        }

        .player-v2-pair-card {
            display: grid;
            gap: 14px;
            grid-template-columns: auto minmax(0, 1fr);
        }

        .player-v2-pair-avatar {
            align-items: center;
            background: linear-gradient(135deg, #4b37d8, #7a1735);
            border-radius: 22px;
            color: #ffffff;
            display: flex;
            font-size: 1.05rem;
            font-weight: 950;
            height: 54px;
            justify-content: center;
            width: 54px;
        }

        .player-v2-progress-row {
            display: grid;
            gap: 14px;
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .player-v2-progress-card {
            padding: 17px;
        }

        .player-v2-progress-card strong {
            color: var(--ink);
            display: block;
            font-size: 1.15rem;
            font-weight: 950;
            margin-bottom: 7px;
        }

        .player-v2-away {
            color: #4b37d8;
            display: block;
            font-size: 0.84rem;
            font-weight: 900;
            margin-bottom: 13px;
        }

        .player-v2-progress-value {
            color: #687093;
            font-size: 0.86rem;
            font-weight: 850;
            margin-bottom: 10px;
        }

        .player-v2-progress-track {
            height: 8px;
        }

        .player-v2-season-strip,
        .player-v2-timeline {
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid #e7e6f5;
            border-radius: 28px;
            box-shadow: 0 10px 26px rgba(23, 27, 77, 0.055);
            display: grid;
            overflow: hidden;
        }

        .player-v2-season-strip {
            grid-template-columns: repeat(5, minmax(0, 1fr));
            margin-bottom: 16px;
        }

        .player-v2-season-strip-card,
        .player-v2-timeline-step {
            border-right: 1px solid #e7e6f5;
            padding: 18px;
        }

        .player-v2-season-strip-card:last-child,
        .player-v2-timeline-step:last-child {
            border-right: 0;
        }

        .player-v2-season-strip-card span a,
        .player-v2-timeline-step strong a {
            color: #0068c9;
            font-weight: 900;
            text-decoration: none;
        }

        .player-v2-season-strip-card strong {
            color: var(--ink);
            display: block;
            font-size: 1.05rem;
            font-weight: 950;
            margin-top: 8px;
        }

        .player-v2-season-strip-card em {
            color: #687093;
            display: block;
            font-size: 0.84rem;
            font-style: normal;
            font-weight: 850;
            margin-top: 4px;
        }

        .player-v2-timeline {
            grid-template-columns: repeat(5, minmax(0, 1fr));
        }

        .player-v2-timeline-dot {
            background: linear-gradient(135deg, #4b37d8, #6d4dff);
            border-radius: 999px;
            display: block;
            height: 10px;
            margin-bottom: 10px;
            width: 10px;
        }

        .player-v2-timeline-step small {
            color: #687093;
            display: block;
            font-size: 0.76rem;
            font-weight: 900;
            letter-spacing: 0.06em;
            margin-bottom: 7px;
            text-transform: uppercase;
        }

        .player-v2-timeline-step strong {
            color: var(--ink);
            display: block;
            font-size: 0.98rem;
            font-weight: 950;
            line-height: 1.25;
        }

        .player-v2-coverage-card {
            display: grid;
            gap: 18px;
            grid-template-columns: minmax(0, 0.86fr) minmax(0, 1.14fr);
            margin-top: 34px;
            padding: 22px;
        }

        .player-v2-coverage-card ul {
            display: grid;
            gap: 10px;
            margin: 0;
            padding: 0;
        }

        .player-v2-coverage-card li {
            background: #ffffff;
            border: 1px solid #e7e6f5;
            border-radius: 17px;
            color: #687093;
            font-size: 0.9rem;
            font-weight: 720;
            line-height: 1.42;
            list-style: none;
            padding: 12px 13px;
        }

        .player-v2-coverage-card li strong {
            color: var(--ink);
            display: block;
            font-weight: 950;
            margin-bottom: 3px;
        }

        .player-v2-coverage-card li span {
            display: block;
        }

        @media (max-width: 980px) {
            .player-v2-hero-grid,
            .player-v2-grid-2,
            .player-v2-grid-3,
            .player-v2-coverage-card {
                grid-template-columns: 1fr;
            }

            .player-v2-grid-4,
            .player-v2-progress-row {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .player-v2-stat-strip {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            .player-v2-stat-tile:nth-child(3n) {
                border-right: 0;
            }

            .player-v2-stat-tile:nth-child(6n) {
                border-right: 1px solid #e7e6f5;
            }

            .player-v2-season-strip,
            .player-v2-timeline {
                grid-template-columns: 1fr;
            }

            .player-v2-season-strip-card,
            .player-v2-timeline-step {
                border-bottom: 1px solid #e7e6f5;
                border-right: 0;
            }
        }

        @media (max-width: 760px) {
            .player-v2-title-row {
                flex-direction: column;
                gap: 10px;
            }

            .player-v2-page-title {
                font-size: clamp(2.05rem, 10vw, 2.9rem);
            }

            div.st-key-player_v2_selector_card {
                border-radius: 20px;
                padding: 14px;
            }

            .player-v2-hero {
                border-radius: 27px;
                padding: 24px;
            }

            .player-v2-hero h2 {
                font-size: clamp(3rem, 16vw, 4.8rem);
            }

            .player-v2-facts,
            .player-v2-grid-4,
            .player-v2-progress-row,
            .player-v2-mini-grid {
                grid-template-columns: 1fr;
            }

            .player-v2-stat-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .player-v2-stat-tile {
                border-bottom: 1px solid #e7e6f5;
                padding: 15px;
            }

            .player-v2-stat-tile:nth-child(2n) {
                border-right: 0;
            }

            .player-v2-section-head {
                align-items: flex-start;
                flex-direction: column;
                gap: 10px;
            }

            .player-v2-break-row {
                grid-template-columns: 76px minmax(0, 1fr) 52px;
            }

            .player-v2-pair-card {
                grid-template-columns: 1fr;
            }
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
            section[data-testid="stSidebar"] {
                display: none !important;
                width: 0 !important;
            }

            .block-container {
                padding: 1.1rem 0.85rem 2.25rem;
            }

            div.st-key-season_controls {
                border-radius: 18px;
                margin-bottom: 20px;
                padding: 14px;
            }

            div.st-key-season_controls div[data-testid="stHorizontalBlock"] {
                gap: 12px;
            }

            .section-subtext {
                font-size: 0.9rem;
                margin: -10px 0 16px;
            }

            .recent-form-card {
                border-radius: 16px;
                padding: 14px;
            }

            .recent-form-line {
                align-items: start;
                grid-template-columns: 1fr;
                gap: 8px;
            }

            .recent-form-label small {
                font-size: 0.6rem;
            }

            .recent-form-chip:nth-of-type(n+6) {
                display: none;
            }

            div.st-key-season_by_round_card {
                border-radius: 0 18px 18px 18px;
                margin-top: -15px;
                padding: 14px;
            }

            div.st-key-season_round_grade_folder_tabs,
            div.st-key-milestone_page_view_folder_tabs,
            div.st-key-player_profile_breakdown_folder_tabs {
                margin: 0 0 -1px;
                padding-left: 8px;
                width: 100%;
            }

            div.st-key-season_round_grade_folder_tabs div[data-testid="stSegmentedControl"],
            div.st-key-milestone_page_view_folder_tabs div[data-testid="stSegmentedControl"],
            div.st-key-player_profile_breakdown_folder_tabs div[data-testid="stSegmentedControl"] {
                display: grid !important;
                gap: 6px !important;
                grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
                width: 100% !important;
            }

            div.st-key-season_round_grade_folder_tabs [data-testid="stButtonGroup"],
            div.st-key-milestone_page_view_folder_tabs [data-testid="stButtonGroup"],
            div.st-key-player_profile_breakdown_folder_tabs [data-testid="stButtonGroup"] {
                display: block !important;
                gap: 6px !important;
                width: 100% !important;
            }

            div.st-key-season_round_grade_folder_tabs [data-testid="stButtonGroup"] > div,
            div.st-key-milestone_page_view_folder_tabs [data-testid="stButtonGroup"] > div,
            div.st-key-player_profile_breakdown_folder_tabs [data-testid="stButtonGroup"] > div {
                display: grid !important;
                gap: 6px !important;
                grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
                max-width: 100% !important;
                width: 100% !important;
            }

            div.st-key-milestone_page_view_folder_tabs [data-testid="stButtonGroup"] > div,
            div.st-key-player_profile_breakdown_folder_tabs [data-testid="stButtonGroup"] > div {
                grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
            }

            div.st-key-season_round_grade_folder_tabs button[data-testid^="stBaseButton"],
            div.st-key-milestone_page_view_folder_tabs button[data-testid^="stBaseButton"],
            div.st-key-player_profile_breakdown_folder_tabs button[data-testid^="stBaseButton"] {
                min-height: 42px !important;
                padding: 9px 10px 8px !important;
                text-align: center !important;
                white-space: normal !important;
                width: 100% !important;
            }

            div.st-key-milestone_page_view_folder_tabs button[data-testid^="stBaseButton"],
            div.st-key-player_profile_breakdown_folder_tabs button[data-testid^="stBaseButton"] {
                font-size: 0.72rem !important;
                min-height: 38px !important;
                padding: 7px 5px 6px !important;
                white-space: nowrap !important;
            }

            div.st-key-season_round_grade_filter_control {
                display: flex !important;
                gap: 8px !important;
                margin: 0 0 14px;
                max-width: 100%;
                overflow-x: auto;
                overflow-y: hidden;
                padding-bottom: 4px;
                width: 100%;
            }

            div.st-key-season_round_grade_filter_control div[data-testid="stHorizontalBlock"] {
                display: flex !important;
                gap: 8px !important;
                min-width: max-content !important;
                width: max-content !important;
            }

            div.st-key-season_round_grade_filter_control div[data-testid="stVerticalBlock"] {
                display: flex !important;
                gap: 8px !important;
                min-width: max-content !important;
                width: max-content !important;
            }

            div.st-key-season_round_grade_filter_control div[data-testid="stElementContainer"] {
                display: block !important;
                flex: 0 0 auto !important;
                max-width: none !important;
                width: auto !important;
            }

            div.st-key-season_round_grade_filter_control button[data-testid^="stBaseButton"] {
                min-height: 44px !important;
                white-space: nowrap !important;
                width: auto !important;
            }

            .season-round-scroll {
                max-height: 560px;
                overflow-x: hidden;
            }

            .season-round-grid {
                display: grid;
                gap: 9px;
                padding: 10px;
            }

            .season-round-panel-strip {
                gap: 10px;
                padding: 2px 0 12px;
            }

            .season-round-grade-card {
                flex-basis: min(100%, calc(100vw - 32px));
                width: min(100%, calc(100vw - 32px));
            }

            .season-round-grade-head {
                gap: 8px;
                padding: 10px;
            }

            .season-round-grade-head h3 {
                font-size: 0.94rem;
            }

            .season-round-grade-head .season-round-record {
                font-size: 0.66rem;
                padding: 5px 7px;
            }

            .season-round-head {
                display: none;
            }

            .season-round-row,
            .season-round-grade-card.single-grade .season-round-row {
                border: 1px solid #e8ebf7;
                border-radius: 15px;
                column-gap: 9px;
                grid-template-columns: minmax(0, 1fr) minmax(78px, 31%);
                min-height: 0;
                padding: 10px;
            }

            .season-round-row strong {
                grid-column: 1;
            }

            .season-round-row span,
            .season-round-row a {
                grid-column: 1;
            }

            .season-round-grade-cell {
                display: none;
            }

            .season-round-opponent {
                white-space: normal;
            }

            .season-round-row .season-round-result {
                align-items: flex-end;
                flex-direction: column;
                grid-column: 2;
                grid-row: 1 / span 3;
                justify-content: flex-start;
                min-width: 0;
                text-align: right;
            }

            .season-round-result .season-result-pill {
                align-self: flex-end;
            }

            .season-round-result span:not(.season-result-pill) {
                line-height: 1.2;
                overflow-wrap: anywhere;
                white-space: normal;
            }

            .season-round-scorecard {
                grid-column: 1 / -1 !important;
                grid-row: auto;
                margin-top: 2px;
                text-align: left;
            }

            .season-round-scorecard-link {
                font-size: 0.76rem !important;
                white-space: normal;
            }

            .leader-highlight-card {
                min-height: 150px;
            }

            .leader-highlight-count {
                font-size: 1rem;
                margin-top: 12px;
            }

            .leader-highlight-chip,
            .leader-highlight-more {
                font-size: 0.68rem;
                max-width: 100%;
                padding: 5px 7px;
            }

            .leader-highlight-chip-stacked {
                min-width: min(142px, 100%);
                padding: 6px 8px;
            }

            .leader-highlight-chip-stacked .leader-highlight-chip-grade {
                font-size: 0.66rem;
            }

            .leader-highlight-chip-stacked .leader-highlight-chip-season {
                font-size: 0.6rem;
            }

            .mobile-label {
                display: inline;
            }

            .improver-grid {
                grid-template-columns: 1fr;
            }

            .simple-filter-context {
                font-size: 0.82rem;
                margin-top: 10px;
            }

            .block-container:has(.hall-of-fame-page) div[data-testid="stHorizontalBlock"]:has(.kpi-card) {
                display: none !important;
            }

            .hof-v2-hero {
                border-radius: 26px;
                padding: 24px;
            }

            .hof-v2-hero-grid,
            .hof-v2-grid-2,
            .hof-v2-grid-3,
            .hof-v2-grid-4,
            .hof-v2-record-grid,
            .hof-v2-decision-panel {
                grid-template-columns: 1fr;
            }

            .hof-v2-hero h1 {
                font-size: clamp(3rem, 16vw, 4.8rem);
            }

            .hof-v2-hero-stats {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .hof-v2-section-head {
                align-items: flex-start;
                flex-direction: column;
                gap: 10px;
            }

            .hof-v2-trophy-row {
                align-items: start;
                grid-template-columns: 1fr;
            }

            .hof-v2-trophy-result {
                justify-items: start;
            }

            .hof-v2-rank-row {
                grid-template-columns: 28px minmax(0, 1fr);
            }

            .hof-v2-rank-row span:last-child {
                grid-column: 2;
                text-align: left;
            }

            .hof-v2-race-row {
                grid-template-columns: 28px minmax(0, 1fr);
            }

            .hof-v2-race-time {
                grid-column: 2;
            }

            .hof-v2-season-card {
                align-items: start;
                grid-template-columns: 1fr;
            }

            .hof-v2-season-score {
                text-align: left;
            }

            .record-card-grid {
                gap: 12px;
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .best-season-grid {
                grid-template-columns: 1fr;
            }

            .premiership-season {
                font-size: 0.98rem;
            }

            .premiership-card-scroll {
                max-height: 820px;
            }

            .premiership-wins-scroll {
                max-height: 826px;
            }

            .premiership-player-scroll {
                max-height: calc(5 * 58px);
            }

            .premiership-title {
                font-size: 0.9rem;
            }

            .premiership-captain {
                margin-top: 3px;
            }

            .record-card {
                border-radius: 16px;
                min-height: 118px;
                padding: 14px 15px;
            }

            .record-player {
                font-size: 0.92rem;
                line-height: 1.16;
                margin-top: 12px;
            }

            .record-value {
                font-size: 1.04rem;
                line-height: 1.16;
            }

            div.st-key-header_intro .club-label {
                margin-top: -2px;
            }

            .page-title {
                font-size: clamp(2.25rem, 13vw, 3.15rem);
            }

            .block-container:has(.seasons-page) .page-title {
                font-size: clamp(2.05rem, 9.4vw, 2.65rem);
                line-height: 1.02;
                white-space: nowrap;
            }

            .block-container:has(.near-milestones-page) .page-title {
                font-size: clamp(1.85rem, 10.5vw, 2.65rem);
            }

            .block-container:has(.player-profile-page) .page-title {
                font-size: clamp(1.72rem, 9.4vw, 2.45rem);
                line-height: 1.02;
                white-space: nowrap;
            }

            .block-container:has(.player-profile-page) .profile-career-card-fielding.profile-card-nonkeeper {
                display: none;
            }

            .profile-highlights-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 10px;
            }

            .profile-highlights-grid .record-card {
                border-radius: 17px;
                min-height: 0;
                padding: 13px 12px;
            }

            .profile-highlights-grid .record-label {
                font-size: 0.62rem;
                line-height: 1.18;
            }

            .profile-highlights-grid .record-player {
                font-size: 0.82rem;
                line-height: 1.16;
                margin-top: 10px;
            }

            .profile-highlights-grid .record-value {
                font-size: 1.02rem;
                line-height: 1.12;
                margin-top: 7px;
            }

            .profile-highlights-grid .record-meta {
                font-size: 0.64rem;
                line-height: 1.28;
                margin-top: 9px;
            }

            .milestone-segmented {
                border-radius: 18px;
                gap: 6px;
                margin-bottom: 22px;
                overflow-x: auto;
                padding: 6px;
                width: 100%;
            }

            .block-container:has(.near-milestones-page) .milestone-segmented:not(.milestone-segmented-compact) {
                display: grid;
                gap: 6px;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                overflow: visible;
            }

            .milestone-segmented-compact {
                margin-bottom: 16px;
            }

            .milestone-segment {
                align-items: center;
                font-size: 0.84rem;
                padding: 10px 13px;
            }

            .block-container:has(.near-milestones-page) .milestone-segmented:not(.milestone-segmented-compact) .milestone-segment {
                padding-left: 6px;
                padding-right: 6px;
                width: 100%;
            }

            .milestone-label-desktop {
                display: none;
            }

            .milestone-label-mobile {
                display: inline;
            }

            .milestone-view-panel,
            div.st-key-milestone_upcoming_panel,
            div.st-key-milestone_achieved_panel,
            div.st-key-milestone_exclusive_panel {
                border-radius: 0 24px 24px 24px;
                margin-top: -15px;
                padding: 18px 19px 19px;
            }

            .milestone-watch-grid,
            .milestone-club-grid,
            .milestone-mini-grid,
            .achievement-grid {
                grid-template-columns: 1fr;
            }

            .milestone-group-head,
            .milestone-progress-top,
            .milestone-member-row {
                align-items: flex-start;
                flex-direction: column;
            }

            .milestone-away,
            .milestone-member-row strong {
                text-align: left;
                white-space: normal;
            }

            .milestone-member-list {
                max-height: 344px;
            }

            .milestone-progress-list,
            .milestone-mini-scroll,
            .milestone-achievement-scroll {
                max-height: 430px;
            }

            .milestone-member-row {
                min-height: 55px;
            }

            .milestone-group-rule {
                white-space: normal;
            }

            .block-container:has(.near-milestones-page) .milestone-group-head {
                align-items: center;
                flex-direction: row;
                justify-content: space-between;
            }

            .block-container:has(.near-milestones-page) .milestone-group-title {
                min-width: 0;
            }

            .block-container:has(.near-milestones-page) .milestone-group-rule {
                flex: 0 0 auto;
                max-width: 52%;
                text-align: right;
                white-space: nowrap;
            }

            .block-container:has(.near-milestones-page) .milestone-progress-top {
                align-items: flex-start;
                flex-direction: row;
                justify-content: space-between;
            }

            .block-container:has(.near-milestones-page) .milestone-progress-top > div {
                min-width: 0;
            }

            .block-container:has(.near-milestones-page) .milestone-away {
                flex: 0 0 auto;
                text-align: right;
                white-space: nowrap;
            }

            .achievement-card {
                padding: 15px 16px;
            }

            div[data-testid="stDataFrame"],
            div[data-testid="stDataFrame"] > div,
            div[data-testid="stDataFrame"] [class*="gdg"],
            div[data-testid="stDataFrame"] [class*="glide"],
            div[data-testid="stDataFrame"] [role="grid"],
            div[data-testid="stDataFrame"] [role="row"],
            div[data-testid="stDataFrame"] [role="gridcell"],
            div[data-testid="stDataFrame"] [role="columnheader"] {
                background: #ffffff !important;
                color: #20243D !important;
                color-scheme: light !important;
            }

            div[data-testid="stDataFrame"] {
                border: 1px solid #E9ECF6 !important;
                border-radius: 16px !important;
                box-shadow: 0 12px 28px rgba(23, 27, 77, 0.055) !important;
                overflow: hidden !important;
            }

            div[data-testid="stDataFrame"] [role="columnheader"] {
                background: #F7F8FD !important;
                border-bottom: 1px solid #E6E9F4 !important;
                color: #5D6686 !important;
            }

            div[data-testid="stDataFrame"] [role="gridcell"] {
                border-color: #EEF1F8 !important;
            }

            div.st-key-full_stats_card,
            div.st-key-player_profile_season_table,
            div.st-key-player_profile_grade_table,
            div.st-key-player_profile_performance_breakdown,
            div.st-key-profile_chart_runs,
            div.st-key-profile_chart_wickets,
            div.st-key-profile_chart_batting_average,
            div.st-key-profile_chart_bowling_average,
            .profile-season-summary-card,
            div[data-testid="stVegaLiteChart"],
            div[data-testid="stVegaLiteChart"] > div,
            div[data-testid="stVegaLiteChart"] canvas,
            div[data-testid="stVegaLiteChart"] svg,
            div[data-testid="stVegaLiteChart"] iframe {
                background: #ffffff !important;
                color-scheme: light !important;
            }

            .block-container:has(.seasons-page) div.st-key-full_stats_card {
                border-radius: 18px;
                padding: 14px 10px 16px;
            }

            .block-container:has(.seasons-page) div.st-key-full_stats_card div[data-testid="stDataFrame"] {
                border-radius: 14px !important;
                font-size: 0.72rem !important;
            }

            .block-container:has(.seasons-page) div.st-key-full_stats_card div[data-testid="stDataFrame"] [role="columnheader"],
            .block-container:has(.seasons-page) div.st-key-full_stats_card div[data-testid="stDataFrame"] [role="gridcell"] {
                font-size: 0.72rem !important;
                line-height: 1.12 !important;
            }

            .block-container:has(.seasons-page) div.st-key-full_stats_card div[data-testid="stDataFrame"] a[href*="page=player-profile"] {
                display: inline-block;
                line-height: 1.12;
                max-width: 92px;
                white-space: normal;
                word-break: normal;
            }

            .block-container:has(.player-profile-page) div.st-key-player_profile_season_table div[data-testid="stDataFrame"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_grade_table div[data-testid="stDataFrame"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_performance_breakdown div[data-testid="stDataFrame"] {
                border-radius: 14px !important;
                font-size: 0.71rem !important;
            }

            .block-container:has(.player-profile-page) div.st-key-player_profile_season_table div[data-testid="stDataFrame"] [role="columnheader"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_season_table div[data-testid="stDataFrame"] [role="gridcell"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_grade_table div[data-testid="stDataFrame"] [role="columnheader"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_grade_table div[data-testid="stDataFrame"] [role="gridcell"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_performance_breakdown div[data-testid="stDataFrame"] [role="columnheader"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_performance_breakdown div[data-testid="stDataFrame"] [role="gridcell"] {
                font-size: 0.71rem !important;
                line-height: 1.11 !important;
                padding-left: 4px !important;
                padding-right: 4px !important;
            }

            .block-container:has(.player-profile-page) div.st-key-player_profile_grade_table div[data-testid="stDataFrame"] [role="gridcell"]:first-child,
            .block-container:has(.player-profile-page) div.st-key-player_profile_grade_table div[data-testid="stDataFrame"] [role="columnheader"]:first-child,
            .block-container:has(.player-profile-page) div.st-key-player_profile_performance_breakdown div[data-testid="stDataFrame"] [role="gridcell"]:first-child,
            .block-container:has(.player-profile-page) div.st-key-player_profile_performance_breakdown div[data-testid="stDataFrame"] [role="columnheader"]:first-child {
                max-width: 128px;
                white-space: normal !important;
                overflow-wrap: anywhere;
            }

            div.st-key-player_profile_performance_breakdown {
                border-radius: 0 18px 18px 18px;
                margin-top: -15px;
                padding: 12px 10px 16px;
            }

            .profile-intelligence-intro {
                align-items: flex-start;
                flex-direction: column;
                gap: 6px;
            }

            .profile-intelligence-intro p {
                text-align: left;
            }

            .profile-segmented {
                display: flex;
                overflow-x: auto;
                width: 100%;
            }

            .profile-segment {
                flex: 1 0 auto;
                text-align: center;
            }

            .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control div[data-testid="stSegmentedControl"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control div[data-testid="stSegmentedControl"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control div[data-testid="stSegmentedControl"],
            .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control div[data-testid="stSegmentedControl"],
            .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control div[data-testid="stSegmentedControl"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control [data-testid="stButtonGroup"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control [data-testid="stButtonGroup"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control [data-testid="stButtonGroup"],
            .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control [data-testid="stButtonGroup"],
            .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control [data-testid="stButtonGroup"] {
                display: flex;
                max-width: 100%;
                overflow-x: auto;
                width: fit-content;
            }

            .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control div[data-testid="stSegmentedControl"] button,
            .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control div[data-testid="stSegmentedControl"] button,
            .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control div[data-testid="stSegmentedControl"] button,
            .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control div[data-testid="stSegmentedControl"] button,
            .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control div[data-testid="stSegmentedControl"] button,
            .block-container:has(.player-profile-page) div.st-key-player_profile_breakdown_view_control button[data-testid^="stBaseButton-segmented_control"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control button[data-testid^="stBaseButton-segmented_control"],
            .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control button[data-testid^="stBaseButton-segmented_control"],
            .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_control button[data-testid^="stBaseButton-segmented_control"],
            .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control button[data-testid^="stBaseButton-segmented_control"] {
                flex: 0 0 auto;
                text-align: center;
            }

            .profile-breakdown-controls {
                align-items: stretch;
                flex-direction: column;
                gap: 10px;
            }

            div.st-key-profile_breakdown_controls div[data-testid="column"]:last-child {
                justify-content: flex-start;
            }

            .position-row {
                padding: 8px 0;
            }

            .position-row-top {
                align-items: flex-start;
                gap: 8px;
            }

            .position-row-summary {
                font-size: 0.74rem;
                line-height: 1.25;
                max-width: 62%;
                white-space: normal;
            }

            .phase-row {
                grid-template-columns: 1fr 1fr 1fr;
            }

            .phase-name {
                grid-column: 1 / -1;
            }

            .phase-row span:not(.profile-best-badge) {
                text-align: left;
            }

            .phase-table-phase {
                align-items: flex-start;
                flex-direction: column;
                gap: 5px;
                justify-content: flex-start;
                text-align: left;
            }

            .phase-table-phase .profile-best-badge {
                margin-left: 0;
                margin-top: 1px;
            }

            .profile-season-summary-card {
                padding: 17px 18px;
            }

            .player-hero-card {
                display: block;
                margin: 14px 0 16px;
                padding: 18px 18px 20px;
            }

            .profile-name {
                font-size: clamp(2rem, 11vw, 2.7rem);
                line-height: 1.04;
            }

            .profile-meta {
                font-size: 0.86rem;
                line-height: 1.28;
                margin-top: 10px;
            }

            .profile-insight {
                font-size: 0.86rem;
                line-height: 1.34;
                margin-top: 10px;
            }

            .profile-badges {
                justify-content: flex-start;
                margin-top: 14px;
                max-width: none;
                min-width: 0;
            }

            .profile-badge {
                font-size: 0.7rem;
                padding: 7px 10px;
            }

            .mini-leader-grid {
                grid-template-columns: 1fr;
                gap: 16px;
            }

            .mini-leader + .mini-leader {
                border-left: 0;
                border-top: 1px solid #EEF1F8;
                padding-left: 0;
                padding-top: 16px;
            }

            .mini-value-row {
                align-items: flex-start;
                flex-direction: column;
                gap: 8px;
            }

            .mini-stat-block {
                text-align: left;
            }

            .overview-section-title {
                font-size: clamp(1.35rem, 7vw, 1.78rem);
                line-height: 1.14;
                margin: 34px 0 18px;
            }

            .overview-section-title .section-title-desktop {
                display: none;
            }

            .overview-section-title .section-title-mobile {
                display: inline;
            }

            div[class*="st-key-hof_"][class*="_control"] {
                margin: -10px 0 16px;
            }

            div.st-key-mobile_nav_fallback {
                background: rgba(255, 255, 255, 0.96);
                border: 1px solid #E6E9F5;
                border-radius: 18px;
                box-shadow: 0 12px 28px rgba(23, 27, 77, 0.08);
                display: block;
                margin: 0 0 18px;
                padding: 20px 24px;
                position: sticky;
                top: 10px;
                z-index: 9999;
            }

            div.st-key-mobile_nav_fallback div[data-testid="stMarkdownContainer"] {
                display: block;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-label {
                color: var(--ink) !important;
                font-size: 0.98rem !important;
                font-weight: 850 !important;
                line-height: 1.1;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-helper {
                color: #6D728E !important;
                font-size: 0.78rem !important;
                font-weight: 550 !important;
                line-height: 1.28;
                margin: 0 0 12px;
            }

            div.st-key-mobile_nav_fallback div[data-testid="stSelectbox"] {
                clear: both;
                display: block;
                margin-top: 14px;
                position: relative;
                width: 100%;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-help {
                display: block;
                margin: 0;
                min-height: 26px;
                position: relative;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-help summary {
                align-items: center;
                cursor: pointer;
                display: flex;
                gap: 8px;
                list-style: none;
                min-height: 24px;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-help summary::-webkit-details-marker {
                display: none;
            }

            div.st-key-mobile_nav_fallback .mobile-info-icon {
                align-items: center;
                background: #F4F1FF !important;
                border: 1px solid #DDD7FF !important;
                border-radius: 999px !important;
                color: var(--pitch) !important;
                display: inline-flex;
                font-size: 0.9rem !important;
                font-weight: 850 !important;
                height: 22px;
                justify-content: center;
                width: 22px;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-help-panel {
                background: #F8F7FF;
                border: 1px solid #E7E2FF;
                border-radius: 14px;
                color: #4F5875;
                font-size: 0.76rem;
                line-height: 1.32;
                margin: 9px 0 8px;
                padding: 10px 11px;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-help-panel p {
                margin: 0 0 8px;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-help-panel p:last-child {
                margin-bottom: 0;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-links {
                display: grid;
                gap: 8px;
                margin-top: 14px;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-link {
                background: #ffffff;
                border: 1px solid #E6E9F5;
                border-radius: 14px;
                color: var(--ink) !important;
                display: block;
                font-size: 0.88rem;
                font-weight: 850;
                padding: 11px 13px;
                text-decoration: none !important;
            }

            div.st-key-mobile_nav_fallback .mobile-nav-link.active {
                background: #F0EDFF;
                border-color: #DCD4FF;
                color: #5B3DF5 !important;
            }

            .mobile-page-footer {
                border-top: 1px solid #ECEEFA;
                color: #7d839d;
                display: block;
                margin: 36px 28px 24px;
                padding-top: 14px;
            }

            .mobile-page-footer .mobile-footer-label {
                color: #737998;
                font-size: 0.62rem;
                font-weight: 700;
                letter-spacing: 0.06em;
                text-transform: uppercase;
            }

            .mobile-page-footer .mobile-footer-names {
                color: var(--ink);
                font-size: 0.74rem;
                font-weight: 500;
                line-height: 1.32;
                margin-top: 4px;
            }

            .mobile-page-footer .mobile-footer-contact {
                color: #7d839d;
                font-size: 0.64rem;
                line-height: 1.3;
                margin-top: 5px;
            }

            .mobile-page-footer .mobile-footer-contact a {
                color: #5B3DF5;
                display: inline-block;
                text-decoration: none;
                word-break: normal;
                white-space: nowrap;
            }

            .mobile-page-footer .scorebook-version {
                color: #7d839d;
                margin-top: 7px;
            }

            div.st-key-mobile_nav_fallback label {
                color: var(--ink) !important;
                font-size: 0.78rem !important;
                font-weight: 900 !important;
                letter-spacing: 0.06em;
                text-transform: uppercase;
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

            .season-v2-hero,
            .season-v2-card-grid,
            .season-v2-performance-grid,
            .season-v2-insight-grid {
                grid-template-columns: 1fr;
            }

            .season-v2-hero {
                padding: 20px;
            }

            .season-v2-hero-grid,
            .season-v2-role-grid {
                grid-template-columns: 1fr;
            }

            .season-v2-depth-row {
                grid-template-columns: 74px minmax(96px, 1fr);
            }

            .season-v2-depth-meta {
                grid-column: 2;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(active_club_theme_css(), unsafe_allow_html=True)


def active_club_theme_css() -> str:
    active_club_id = get_active_club_id()
    branding = FVCC_PRODUCTION_BRANDING if active_club_id == "fvcc" else {}
    primary = safe_hex_colour(branding.get("primary_colour", get_branding_value("primary_colour", "#5B4BEB")), "#5B4BEB")
    secondary = safe_hex_colour(branding.get("secondary_colour", get_branding_value("secondary_colour", "#7C5CFF")), "#7C5CFF")
    accent = safe_hex_colour(branding.get("accent_colour", get_branding_value("accent_colour", primary)), primary)
    background = safe_hex_colour(branding.get("background_colour", get_branding_value("background_colour", "#F7F8FC")), "#F7F8FC")
    text = safe_hex_colour(get_branding_value("text_colour", "#080B3F"), "#080B3F")
    muted = safe_hex_colour(get_branding_value("muted_text_colour", "#6D728E"), "#6D728E")
    line = safe_hex_colour(get_branding_value("border_colour", "#E7EAF5"), "#E7EAF5")
    surface = safe_hex_colour(get_branding_value("surface_colour", "#FFFFFF"), "#FFFFFF")
    value_colour = safe_hex_colour(
        branding.get("value_colour", get_branding_value("value_colour", primary)),
        primary,
    )
    link = safe_hex_colour(
        branding.get("link_colour", get_branding_value("link_colour", secondary if active_club_id == "fvcc" else primary)),
        secondary if active_club_id == "fvcc" else primary,
    )
    link_hover = safe_hex_colour(
        branding.get(
            "link_hover_colour",
            get_branding_value(
                "link_hover_colour",
                darken_hex(secondary, 0.24) if active_club_id == "fvcc" else secondary,
            ),
        ),
        darken_hex(secondary, 0.24) if active_club_id == "fvcc" else secondary,
    )
    highlight = tint_hex(accent, 0.86)
    primary_soft = tint_hex(primary, 0.90)
    secondary_soft = tint_hex(secondary, 0.88)
    sidebar_start = secondary if active_club_id == "fvcc" else primary
    sidebar_bg = (
        darken_hex(secondary, 0.24)
        if active_club_id == "fvcc"
        else safe_hex_colour(get_branding_value("primary_dark_colour", darken_hex(primary, 0.24)), darken_hex(primary, 0.24))
    )
    sidebar_active = safe_hex_colour(
        branding.get("nav_active_colour", get_branding_value("nav_active_colour", primary)),
        primary,
    )
    primary_rgb = hex_to_rgb(primary)
    accent_rgb = hex_to_rgb(accent)
    secondary_rgb = hex_to_rgb(secondary)
    highlight_rgb = hex_to_rgb(highlight)
    sidebar_shadow = rgba(primary_rgb, 0.34)
    active_shadow = rgba(primary_rgb, 0.32)
    fvcc_only_css = (
        """
        .block-container:has(.player-profile-page) .recent-form-label,
        .block-container:has(.player-profile-page) .recent-form-chip.bat,
        .block-container:has(.player-profile-page) .recent-form-chip.bowl {
            color: var(--club-link) !important;
        }
        """
        if active_club_id == "fvcc"
        else ""
    )
    gwhcc_only_css = (
        """
        .block-container:has(.hall-of-fame-page) .performance-value {
            color: var(--club-value) !important;
        }

        div.st-key-milestone_page_view_folder_tabs button:is(
            [aria-checked="true"],
            [aria-pressed="true"],
            [kind="primary"],
            [data-testid$="segmented_controlActive"]
        ),
        div.st-key-player_profile_breakdown_folder_tabs button:is(
            [aria-checked="true"],
            [aria-pressed="true"],
            [kind="primary"],
            [data-testid$="segmented_controlActive"]
        ) {
            color: var(--club-value) !important;
        }

        div.st-key-milestone_page_view_folder_tabs button:is(
            [aria-checked="true"],
            [aria-pressed="true"],
            [kind="primary"],
            [data-testid$="segmented_controlActive"]
        ) *,
        div.st-key-player_profile_breakdown_folder_tabs button:is(
            [aria-checked="true"],
            [aria-pressed="true"],
            [kind="primary"],
            [data-testid$="segmented_controlActive"]
        ) * {
            color: inherit !important;
        }
        """
        if active_club_id == "glen-waverley-hawks"
        else ""
    )
    return f"""
        <style>
        :root {{
            --club-primary: {primary};
            --club-primary-dark: {sidebar_bg};
            --club-secondary: {secondary};
            --club-accent: {accent};
            --club-bg: {background};
            --club-text: {text};
            --club-muted: {muted};
            --club-border: {line};
            --club-surface: {surface};
            --club-link: {link};
            --club-link-hover: {link_hover};
            --club-value: {value_colour};
            --club-highlight: {highlight};
            --club-primary-soft: {primary_soft};
            --club-secondary-soft: {secondary_soft};
            --club-sidebar-bg: {sidebar_bg};
            --club-sidebar-start: {sidebar_start};
            --club-sidebar-active: {sidebar_active};
            --club-primary-rgb: {primary_rgb};
            --club-accent-rgb: {accent_rgb};
            --club-secondary-rgb: {secondary_rgb};
            --club-highlight-rgb: {highlight_rgb};
            --ink: var(--club-text);
            --muted: var(--club-muted);
            --line: var(--club-border);
            --surface: var(--club-surface);
            --surface-soft: var(--club-bg);
            --card-border: var(--club-border);
            --pitch: var(--club-primary);
            --pitch-2: var(--club-secondary);
        }}

        {fvcc_only_css}
        {gwhcc_only_css}

        .stApp {{
            background:
                radial-gradient(circle at top right, rgba(var(--club-secondary-rgb), 0.09), transparent 32rem),
                var(--club-bg);
        }}

        section[data-testid="stSidebar"] {{
            background:
                radial-gradient(circle at 18% 0%, rgba(var(--club-secondary-rgb), 0.22), transparent 14rem),
                radial-gradient(circle at 80% 42%, rgba(var(--club-secondary-rgb), 0.16), transparent 12rem),
                linear-gradient(180deg, var(--club-sidebar-start) 0%, var(--club-sidebar-bg) 100%) !important;
        }}

        section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {{
            background:
                linear-gradient(135deg, rgba(255,255,255,0.20), rgba(255,255,255,0.04)),
                linear-gradient(135deg, var(--club-sidebar-active), var(--club-sidebar-bg)) !important;
            border: 1px solid rgba(var(--club-primary-rgb), 0.58) !important;
            box-shadow:
                0 16px 34px {active_shadow},
                0 0 0 1px rgba(255,255,255,0.10),
                inset 0 1px 0 rgba(255,255,255,0.26) !important;
        }}

        section[data-testid="stSidebar"] .side-nav-item,
        section[data-testid="stSidebar"] .side-nav-item span,
        section[data-testid="stSidebar"] .side-title,
        section[data-testid="stSidebar"] .side-shield,
        section[data-testid="stSidebar"] .side-footer,
        section[data-testid="stSidebar"] .side-footer *,
        section[data-testid="stSidebar"] label[data-baseweb="radio"],
        section[data-testid="stSidebar"] label[data-baseweb="radio"] * {{
            color: rgba(255, 255, 255, 0.86) !important;
        }}

        section[data-testid="stSidebar"] .side-nav-item:not(.active),
        section[data-testid="stSidebar"] .side-nav-item:not(.active) * {{
            color: rgba(255, 255, 255, 0.76) !important;
            opacity: 1 !important;
        }}

        section[data-testid="stSidebar"] .side-nav-item.active,
        section[data-testid="stSidebar"] .side-nav-item.active *,
        section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked),
        section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) * {{
            color: #ffffff !important;
        }}

        section[data-testid="stSidebar"] .side-nav-item.active {{
            background:
                linear-gradient(135deg, rgba(255,255,255,0.20), rgba(255,255,255,0.04)),
                linear-gradient(135deg, var(--club-sidebar-active), var(--club-sidebar-bg)) !important;
            border: 1px solid rgba(var(--club-primary-rgb), 0.58) !important;
            box-shadow:
                0 16px 34px {active_shadow},
                0 0 0 1px rgba(255,255,255,0.10),
                inset 0 1px 0 rgba(255,255,255,0.26) !important;
        }}

        section[data-testid="stSidebar"] .side-nav-item:not(.active):hover,
        section[data-testid="stSidebar"] .side-nav-item:not(.active):focus-visible {{
            background: rgba(255, 255, 255, 0.12) !important;
            color: #ffffff !important;
        }}

        section[data-testid="stSidebar"] a,
        section[data-testid="stSidebar"] a:visited {{
            color: rgba(255, 255, 255, 0.90) !important;
        }}

        section[data-testid="stSidebar"] .side-footer-contact a,
        section[data-testid="stSidebar"] .side-footer-contact a:visited {{
            color: rgba(255, 255, 255, 0.94) !important;
            font-weight: 700 !important;
        }}

        section[data-testid="stSidebar"] a:hover {{
            color: #ffffff !important;
        }}

        div[data-testid="stTabs"] button,
        div[data-testid="stTabs"] [data-testid="stTab"],
        div[data-testid="stTabs"] [role="tab"] {{
            color: var(--muted) !important;
        }}

        div[data-testid="stTabs"] [role="tablist"] {{
            background: var(--surface-soft) !important;
            border: 1px solid var(--line) !important;
            display: inline-flex !important;
            width: fit-content !important;
            max-width: 100% !important;
        }}

        div[data-testid="stTabs"] button[aria-selected="true"],
        div[data-testid="stTabs"] button[data-selected="true"],
        div[data-testid="stTabs"] button[data-state="active"],
        div[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"],
        div[data-testid="stTabs"] [data-testid="stTab"][data-selected="true"],
        div[data-testid="stTabs"] [role="tab"][aria-selected="true"],
        div[data-testid="stTabs"] [role="tab"][data-selected="true"],
        .profile-segment.active {{
            background: linear-gradient(135deg, var(--club-primary), var(--club-secondary)) !important;
            color: #ffffff !important;
            box-shadow: 0 10px 24px rgba(var(--club-primary-rgb), 0.22) !important;
        }}

        div[data-testid="stTabs"] button[aria-selected="true"] *,
        div[data-testid="stTabs"] button[data-selected="true"] *,
        div[data-testid="stTabs"] button[data-state="active"] *,
        div[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] *,
        div[data-testid="stTabs"] [data-testid="stTab"][data-selected="true"] *,
        div[data-testid="stTabs"] [role="tab"][aria-selected="true"] *,
        div[data-testid="stTabs"] [role="tab"][data-selected="true"] *,
        .profile-segment.active * {{
            color: #ffffff !important;
        }}

        div[data-testid="stTabs"] .react-aria-SelectionIndicator {{
            display: none !important;
        }}

        a,
        a:visited,
        a.player-profile-link,
        a.player-profile-link:visited,
        a.season-overview-link,
        a.season-overview-link:visited,
        a.scorecard-link,
        a.scorecard-link:visited,
        a.season-round-scorecard-link,
        a.season-round-scorecard-link:visited,
        a.full-link,
        a.full-link:visited,
        .stDataFrame a,
        div[data-testid="stDataFrame"] a,
        div[data-testid="stMetricValue"] {{
            color: var(--club-link) !important;
        }}

        a:hover,
        a.player-profile-link:hover,
        a.season-overview-link:hover,
        a.scorecard-link:hover,
        a.season-round-scorecard-link:hover,
        a.full-link:hover {{
            color: var(--club-link-hover) !important;
        }}

        .block-container:has(.hall-of-fame-page) a:hover,
        .block-container:has(.hall-of-fame-page) a:focus-visible {{
            color: var(--club-link) !important;
        }}

        .premiership-season,
        .premiership-season a,
        .premiership-season a:visited {{
            color: var(--club-value) !important;
        }}

        .hof-card a.player-profile-link,
        .hof-card a.season-overview-link,
        .hof-card a.scorecard-link,
        .performance-player a.player-profile-link,
        .progress-name a.player-profile-link,
        .premiership-link a.scorecard-link,
        .season-round-scorecard a.season-round-scorecard-link,
        .season-overview-link,
        .player-profile-link {{
            color: var(--club-link) !important;
        }}

        .block-container:has(.near-milestones-page) a.player-profile-link,
        .block-container:has(.near-milestones-page) a.player-profile-link:visited,
        .block-container:has(.near-milestones-page) .milestone-progress-top a,
        .block-container:has(.near-milestones-page) .milestone-watch-top a,
        .block-container:has(.near-milestones-page) .milestone-member-row a {{
            color: #000000 !important;
        }}

        .block-container:has(.near-milestones-page) a.player-profile-link:hover,
        .block-container:has(.near-milestones-page) a.player-profile-link:focus-visible {{
            color: #000000 !important;
        }}

        .club-label,
        .page-subtitle strong {{
            color: var(--club-value) !important;
        }}

        .mobile-nav-link.active,
        div.st-key-mobile_nav_fallback .mobile-nav-link.active {{
            background: linear-gradient(135deg, var(--club-primary), var(--club-secondary)) !important;
            border-color: rgba(var(--club-primary-rgb), 0.22) !important;
            color: #ffffff !important;
        }}

        a:focus-visible,
        a.scorecard-link:focus-visible {{
            outline-color: rgba(var(--club-secondary-rgb), 0.44) !important;
        }}

        div[class*="st-key-hof_"][class*="_control"] .stButton > button,
        div[class*="st-key-hof_"][class*="_control"] .stButton > button * {{
            color: var(--club-link) !important;
        }}

        div[class*="st-key-hof_"][class*="_control"] .stButton > button:hover,
        div[class*="st-key-hof_"][class*="_control"] .stButton > button:hover * {{
            color: var(--club-link-hover) !important;
        }}

        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {{
            background: linear-gradient(135deg, var(--club-primary), var(--club-secondary)) !important;
            border-color: var(--club-primary) !important;
        }}

        .stButton > button:focus-visible,
        .stDownloadButton > button:focus-visible {{
            box-shadow: 0 0 0 0.2rem rgba(var(--club-secondary-rgb), 0.22) !important;
            border-color: var(--club-secondary) !important;
        }}

        div[data-testid="stMetricValue"],
        .profile-intelligence-intro span,
        .fingerprint-player-pct,
        .profile-best-badge,
        .mobile-info-icon {{
            color: var(--club-value) !important;
        }}

        .cv-hero {{
            background:
                linear-gradient(135deg, {primary} 0%, {secondary} 100%),
                repeating-linear-gradient(90deg, rgba(255,255,255,0.06) 0 1px, transparent 1px 54px) !important;
            box-shadow: 0 22px 52px {sidebar_shadow} !important;
        }}

        .cv-callout,
        .season-detail-card,
        .profile-intelligence-card {{
            border-color: rgba(var(--club-secondary-rgb), 0.28) !important;
        }}

        .position-track div,
        .fingerprint-bar,
        .hof-leader-progress,
        .leader-progress-fill,
        .scorebook-progress-fill,
        .progress-track div,
        .peer-fill,
        .player-v2-progress-track span,
        .milestone-progress-card .progress-track div,
        .hof-progress-row .progress-track div {{
            background: linear-gradient(90deg, var(--club-primary), var(--club-secondary)) !important;
        }}

        .team-leader-card::before,
        .team-leader-card .mini-track div,
        .kpi-icon.purple,
        .pill.purple,
        .score-dot.purple,
        .legend-dot.current {{
            background: linear-gradient(135deg, var(--club-primary), var(--club-secondary)) !important;
        }}

        .team-leader-card .mini-icon {{
            background: var(--club-primary-soft) !important;
            border-color: rgba(var(--club-primary-rgb), 0.22) !important;
            color: var(--club-value) !important;
        }}

        .team-leader-card .mini-stat {{
            color: var(--club-value) !important;
        }}

        .team-leader-card .team-card-meta {{
            background: var(--club-secondary-soft) !important;
            border-color: rgba(var(--club-secondary-rgb), 0.24) !important;
            color: var(--club-secondary) !important;
        }}

        .profile-segment:hover,
        .profile-segment:focus-visible,
        .folder-tab:hover,
        .folder-tab:focus-visible {{
            border-color: rgba(var(--club-secondary-rgb), 0.34) !important;
            color: var(--club-primary) !important;
        }}

        .folder-tab.active,
        .folder-tab[aria-selected="true"],
        .profile-segment.active {{
            background: linear-gradient(135deg, var(--club-primary), var(--club-secondary)) !important;
            border-color: rgba(var(--club-secondary-rgb), 0.38) !important;
            color: #ffffff !important;
            box-shadow: 0 12px 28px rgba(var(--club-primary-rgb), 0.12) !important;
        }}

        .hof-card::before,
        .record-card::before,
        .profile-season-summary-card::before,
        .season-v2-card::before {{
            background: linear-gradient(90deg, var(--club-primary), var(--club-secondary)) !important;
        }}

        .record-value,
        .hof-v2-record-value,
        .hof-v2-season-score,
        .hof-v2-rank,
        .hof-v2-record-nav a.active,
        .hof-v2-trust-chip,
        .hof-v2-trophy-year a,
        .best-season-primary,
        .premiership-player-row .performance-value,
        .milestone-away,
        .milestone-group-title,
        .player-v2-progress-card strong,
        .player-v2-progress-value,
        .player-v2-kicker,
        .player-v2-marker-label,
        .player-v2-summary-value,
        .profile-phase-value,
        .season-v2-highlight-value {{
            color: var(--club-value) !important;
        }}

        .profile-badge,
        .player-v2-badge,
        .recent-form-chip.bat,
        .recent-form-chip.bowl {{
            background: var(--club-secondary-soft) !important;
            border-color: rgba(var(--club-secondary-rgb), 0.24) !important;
            color: var(--club-link) !important;
        }}

        .profile-badge.profile-badge-gold {{
            background: linear-gradient(135deg, #fff4bf, #f7c948 52%, #d99a12) !important;
            border-color: rgba(180, 83, 9, 0.42) !important;
            box-shadow: 0 10px 22px rgba(217, 154, 18, 0.18) !important;
            color: #6f3d00 !important;
        }}

        .milestone-progress-top span:not(.milestone-row-badge),
        .milestone-watch-top span {{
            color: var(--club-muted) !important;
        }}

        .milestone-segment.active,
        .impact-marker,
        .peer-marker,
        .profile-best-dot {{
            background: linear-gradient(135deg, var(--club-primary), var(--club-secondary)) !important;
            color: #ffffff !important;
        }}

        .player-v2-marker.player {{
            background: var(--club-primary) !important;
            color: #ffffff !important;
        }}

        .player-marker {{
            background: var(--club-primary) !important;
            color: #ffffff !important;
        }}

        div[data-testid="stTabs"] [role="tablist"],
        .profile-segmented,
        .milestone-segmented {{
            background: var(--club-primary-soft) !important;
            border-color: rgba(var(--club-primary-rgb), 0.18) !important;
        }}

        div.st-key-hof_team_group_filter_control div[data-testid="stSegmentedControl"],
        div.st-key-hof_team_group_filter_control [data-testid="stButtonGroup"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control div[data-testid="stSegmentedControl"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control div[data-testid="stSegmentedControl"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control div[data-testid="stSegmentedControl"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control [data-testid="stButtonGroup"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control [data-testid="stButtonGroup"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control [data-testid="stButtonGroup"] {{
            background: var(--club-primary-soft) !important;
            border: 1px solid rgba(var(--club-primary-rgb), 0.18) !important;
            border-radius: 999px !important;
            display: inline-flex !important;
            gap: 4px !important;
            padding: 5px !important;
            width: fit-content !important;
        }}

        div.st-key-hof_team_group_filter_control {{
            margin: 14px 0 28px !important;
        }}

        div.st-key-hof_team_group_filter_control [data-testid="stButtonGroup"] button,
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control [data-testid="stButtonGroup"] button,
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control [data-testid="stButtonGroup"] button,
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control [data-testid="stButtonGroup"] button,
        div.st-key-hof_team_group_filter_control button[data-testid^="stBaseButton-segmented_control"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control button[data-testid^="stBaseButton-segmented_control"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control button[data-testid^="stBaseButton-segmented_control"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control button[data-testid^="stBaseButton-segmented_control"] {{
            background: transparent !important;
            border: 0 !important;
            border-radius: 999px !important;
            color: rgba(8, 10, 63, 0.68) !important;
            font-weight: 800 !important;
            min-height: 38px !important;
            padding: 8px 16px !important;
        }}

        div.st-key-hof_team_group_filter_control [data-testid="stButtonGroup"] button[aria-checked="true"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control [data-testid="stButtonGroup"] button[aria-checked="true"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control [data-testid="stButtonGroup"] button[aria-checked="true"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control [data-testid="stButtonGroup"] button[aria-checked="true"],
        div.st-key-hof_team_group_filter_control button[data-testid$="segmented_controlActive"],
        div.st-key-hof_team_group_filter_control div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        div.st-key-hof_team_group_filter_control div[data-testid="stSegmentedControl"] button[kind="primary"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control button[data-testid$="segmented_controlActive"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control button[data-testid$="segmented_controlActive"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control button[data-testid$="segmented_controlActive"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control div[data-testid="stSegmentedControl"] button[kind="primary"],
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control div[data-testid="stSegmentedControl"] button[kind="primary"],
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control div[data-testid="stSegmentedControl"] button[kind="primary"] {{
            background: linear-gradient(135deg, var(--club-primary), var(--club-secondary)) !important;
            box-shadow: 0 10px 24px rgba(var(--club-primary-rgb), 0.18) !important;
            color: #ffffff !important;
        }}

        div.st-key-hof_team_group_filter_control button[data-testid^="stBaseButton-segmented_control"] *,
        .block-container:has(.player-profile-page) div.st-key-player_profile_discipline_view_control button[data-testid^="stBaseButton-segmented_control"] *,
        .block-container:has(.player-profile-page) div.st-key-player_profile_phase_model_control button[data-testid^="stBaseButton-segmented_control"] *,
        .block-container:has(.near-milestones-page) div.st-key-milestone_club_category_control button[data-testid^="stBaseButton-segmented_control"] * {{
            color: inherit !important;
        }}

        .block-container:has(.near-milestones-page) div.st-key-milestone_page_view_folder_tabs {{
            margin-top: 12px !important;
            margin-bottom: -1px !important;
        }}

        .premiership-wall-card,
        .hof-card,
        .record-card {{
            border-color: rgba(var(--club-primary-rgb), 0.16) !important;
        }}
        </style>
    """


def safe_hex_colour(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.upper()
    return fallback


def hex_to_rgb(value: str) -> str:
    clean = value.lstrip("#")
    return f"{int(clean[0:2], 16)}, {int(clean[2:4], 16)}, {int(clean[4:6], 16)}"


def rgba(rgb: str, alpha: float) -> str:
    return f"rgba({rgb}, {alpha:.2f})"


def darken_hex(value: str, amount: float) -> str:
    clean = value.lstrip("#")
    channels = [int(clean[index:index + 2], 16) for index in (0, 2, 4)]
    darkened = [max(0, min(255, round(channel * (1 - amount)))) for channel in channels]
    return "#" + "".join(f"{channel:02X}" for channel in darkened)


def tint_hex(value: str, amount: float) -> str:
    clean = value.lstrip("#")
    channels = [int(clean[index:index + 2], 16) for index in (0, 2, 4)]
    tinted = [max(0, min(255, round(channel + (255 - channel) * amount))) for channel in channels]
    return "#" + "".join(f"{channel:02X}" for channel in tinted)


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
