# FVCC Stats Hub

A Streamlit cricket analytics dashboard for Fiji Victorian Cricket Club.

The MVP uses locally backed-up PlayCricket Australia public data to power:

- Overview dashboard for the current season
- Hall of Fame all-time club records
- Near Milestone career watchlists
- Player Profile career summaries
- Canonical player identity mapping for duplicate PlayCricket profiles

## Run Locally

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the app:

```bash
streamlit run app.py
```

Streamlit will print a local URL, usually:

```text
http://localhost:8501
```

## Deployment Notes

Main entry file:

```text
app.py
```

The app is designed for Streamlit Cloud. Push this repository to GitHub, then create a Streamlit Cloud app pointing at `app.py`.

The MVP is local-data-first. It reads dashboard-ready files from:

```text
data/processed/
```

The committed `data/` folder includes the local backup needed for the beta dashboard to load without calling the live PlayCricket endpoints during normal app usage.

Do not commit real secrets. Local secrets belong in:

```text
.streamlit/secrets.toml
```

That file is ignored by Git. A safe template is available at:

```text
.streamlit/secrets.toml.example
```

## Data Folders

```text
data/
├── raw/          # backed-up public PlayCricket responses
├── processed/    # dashboard-ready CSV files used by the app
├── cache/        # local response cache, ignored by Git
├── backups/      # alias/identity backup files
└── metadata.json # refresh summary and source metadata
```

## Known MVP Limitations

- The beta is FVCC-specific.
- Normal app usage reads local processed files; live refresh should be used sparingly.
- Public PlayCricket data can contain duplicate player profiles, so all-time views depend on the editable player alias mapping in `data/player_aliases.csv`.
- Some historical fields are incomplete or inconsistent across older seasons.
- Batting strike rate is treated as reliable only from Summer 2024/25 onwards.

## Credits

Created by Siddhanth Chaurasiya & Preet Kaur.
