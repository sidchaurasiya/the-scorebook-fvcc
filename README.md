# Cricket Club Analytics

A low-cost Streamlit analytics dashboard for local cricket clubs.

## Step 1: Project setup + basic Streamlit app scaffold

This step creates the initial runnable application shell:

- Streamlit entry point
- Modular UI folder
- Sidebar filter placeholders
- Dashboard tabs for leaderboards, milestones, records, and trends
- PlayHQ API and public-page scraping starter modules
- Dependency file for local setup and Streamlit Cloud

## Data strategy

The scalable path is:

1. Use PlayCricket public stats endpoints for data already visible without login.
2. Use PlayHQ public APIs when an official API key is available.
3. Use public-page scraping only where an endpoint is not available.
4. Store/cache cleaned results later so dashboards do not repeatedly hit PlayCricket pages.

Do not scrape private pages, logged-in pages, or hidden participant data.

## Current PlayCricket discovery

The public team stats pages load JSON from Cricket Australia's public proxy:

```text
https://grassrootsapiproxy.cricket.com.au
```

The app currently supports these public stats categories:

- `batting`
- `bowling`
- `fielding`
- `championPlayer`

## Local-first PlayCricket backup

The app now keeps a durable local backup under `data/`:

```text
data/
├── raw/          # timestamped raw PlayCricket responses
├── processed/    # dashboard-ready CSV files
├── cache/        # local response cache to avoid repeated API calls
├── exports/      # reserved for generated exports
└── metadata.json # refresh summary, source endpoints, counts, failures
```

Normal dashboard use reads `data/processed/` first and does not call PlayCricket
when a local backup exists. Use the sidebar `Refresh PlayCricket Data` control
sparingly; it adds polite delays, retries failures with backoff, saves raw
responses, and updates `data/metadata.json`.

Public aggregate stats are available for all discovered club seasons. Public
match/result/scorecard endpoints were not available without API access during
implementation, so stable empty processed tables are created for those future
fields.

Example source URL:

```text
https://play.cricket.com.au/grade/c0420577-837e-46d9-80ed-79a16e4e67cb?tab=stats&teamId=fa410898-8244-46e6-a9c6-d02e6dd1b8b5&category=batting
```

## Folder structure

```text
.
├── app.py
├── requirements.txt
├── README.md
├── .streamlit
│   └── secrets.toml.example
└── src
    ├── __init__.py
    ├── config.py
    ├── data
    │   ├── __init__.py
    │   ├── playhq_api.py
    │   └── public_scraper.py
    └── ui
        ├── __init__.py
        └── layout.py
```

## Run locally

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If you have a PlayHQ public API key, copy the example secrets file:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Then edit `.streamlit/secrets.toml` and add your key:

```toml
PLAYHQ_API_KEY = "your-key-here"
PLAYHQ_TENANT = "ca"
PLAYHQ_BASE_URL = "https://api.playhq.com"
```

Start the app:

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints in your terminal, usually:

```text
http://localhost:8501
```

## Next step

Step 2 should use a real public club/team/grade URL to discover the IDs and response shapes we need.
