# GWHCC Document Override Import Guide

The OneDrive links supplied for Hawks records and premierships returned Microsoft `403` responses from the local build environment. Manual download is required before document values can be extracted or applied.

Save the files here:

- `clubs/glen-waverley-hawks/data/source/document_overrides/raw/gwhcc_records_source.docx`
- `clubs/glen-waverley-hawks/data/source/document_overrides/raw/gwhcc_premierships_source.docx`

Then run:

```bash
./.venv-app/bin/python scripts/extract_gwhcc_document_overrides.py
./.venv-app/bin/python scripts/refresh_gwhcc_app_data.py
./.venv-app/bin/python scripts/validate_gwhcc_document_overrides.py
```

Rules:

- PlayCricket remains the base source.
- Document all-time values are used only when they are higher than PlayCricket values.
- Lower document values are retained for audit but are not applied.
- Premiership rows are combined conservatively and duplicates are flagged for review.
