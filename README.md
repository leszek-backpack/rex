# clay-internal-api

> A reverse-engineered Python client for Clay's internal API — the same API the Clay web app uses.

**⚠️ Unofficial. Not supported by Clay. May break without notice.**

---

## What's this?

Clay exposes a rich internal REST API at `https://api.clay.com/v3/`. This repo documents that API and provides a Python client to automate Clay workflows programmatically — building tables, creating columns, running enrichments, and extracting results.

Useful when you want to:
- Create Clay tables and columns from code (reproducible pipelines)
- Clone table schemas across workspaces
- Trigger enrichments and poll for results programmatically
- Build Clay tables as part of a larger automation workflow

Authentication is done via your browser session cookie — no API keys needed.

---

## Contents

| File | What it is |
|------|-----------|
| `clay_client.py` | Python client wrapping Clay's internal API (~750 lines) |
| `clay-api-reference.md` | Comprehensive API reference — endpoints, column schemas, action types, gotchas |
| `COOKIE_SETUP.md` | Step-by-step guide to extract your session cookie from Chrome |
| `clay-session.json.example` | Template for the session file |

---

## Requirements

```
Python 3.8+
requests
```

Install:
```bash
pip install requests
```

---

## Quick Start

**1. Get your session cookie** — follow [COOKIE_SETUP.md](COOKIE_SETUP.md)

**2. Create `clay-session.json`** in the same directory:
```json
{"claysession": "s%3Ayour-cookie-value-here"}
```

**3. Use the client:**
```python
from clay_client import ClayClient

clay = ClayClient()
# → [clay] logged in as you@company.com | workspace 12345

# List all tables
tables = clay.list_tables()
for t in tables:
    print(t["name"], t["id"])

# Get records
records = clay.list_records(table_id)
for r in records:
    print(r["cells"])
```

---

## Key Features

### Table management
```python
table_id, view_id = clay.create_table("My New Table")
clay.list_tables()
clay.reorder_columns(table_id, [col_id_1, col_id_2, ...])
```

### Column creation
```python
# Text column
clay.create_column(table_id, {"type": "text", "name": "Company Name"})

# AI column (Create Content / Use AI)
clay.create_action_column(table_id, {
    "type": "action",
    "name": "Qualify Company",
    "typeSettings": {
        "actionKey": "use-ai",
        "actionPackageId": "67ba01e9-1898-4e7d-afe7-7ebe24819a57",
        "authAccountId": "YOUR_AUTH_ACCOUNT_ID",
        "dataTypeSettings": {"type": "text"},  # ⚠️ MUST be "text", NOT "json"
        "inputsBinding": [
            {"name": "useCase",      "formulaText": '"use-ai"'},
            {"name": "model",        "formulaText": '"gemini-2.5-flash"'},
            {"name": "systemPrompt", "formulaText": '"You qualify B2B companies. Return JSON."'},
            {"name": "prompt",       "formulaText": '"Company: " + {{f_name_field_id}}'},
        ]
    }
})
```

### Run enrichments and wait
```python
run_id = clay.run_column(table_id, col_id, record_ids=[...])
results = clay.run_and_wait(table_id, col_id, record_ids=[...], timeout=120)
```

### Schema export/import (ClayMate)
```python
# Export a table schema (field IDs → column names)
schema = clay.export_schema(table_id)
with open("my-table-schema.json", "w") as f:
    json.dump(schema, f, indent=2)

# Import schema into a new table (column names → field IDs resolved automatically)
new_table_id, new_view_id = clay.import_schema(schema, "Cloned Table")
```

---

## How the session cookie works

Clay authenticates via a `claysession` cookie set when you log in via the browser. The Python client reads this cookie from `clay-session.json` and replays it with every API request — exactly like the browser does.

See [COOKIE_SETUP.md](COOKIE_SETUP.md) for how to extract the cookie from Chrome DevTools.

---

## Important gotchas

A few things that cost hours to figure out — see `clay-api-reference.md` for the full list:

- **`GET /views/{id}/records` returns `"results"`, not `"records"`**
- **Pagination is broken** — the API always returns the same first N records regardless of offset/cursor. Use the 2-step `ids → bulk-fetch` approach in `clay_client.py`
- **`queryString` and `headers` in HTTP API columns must use `formulaMap`, not `formulaText`** (formulaText splits JSON character-by-character)
- **Formula columns must be created as text first**, then PATCHed with `formulaText` + `formulaType: "text"`
- **`answerSchemaType` requires `formulaMap`** — `formulaText` silently fails. `jsonSchema` must be double JSON-encoded. `_metadata` with `modelSource: '"user"'` (inner quotes) is required.
- **`dataTypeSettings` must be `{"type": "text"}`** — `{"type": "json"}` works via API but breaks Clay UI with "Could not find properties for data type json"
- **`actionKey` must be `"use-ai"`** — using `"ai"` silently drops all `inputsBinding`
- **Prompt escaping**: No `{single_braces}` in prompt text (Clay parses as field ref). No unescaped `"quotes"` inside formula strings (silently empties prompt). Use `Clay.formatForAIPrompt({{field}})` for field injection.
- **Formula `.indexOf()` and `.includes()` are unreliable** — use `/pattern/i.test(String({{f_id}}) || "")` instead
- **Lookup columns use `fields|` prefix** for filter inputs: `fields|targetColumn`, `fields|filterOperator`, `fields|rowValue`
- **Webhook source tables need formula extractors** — data columns are NOT auto-populated; PATCH with `formulaText` + `formulaType`

---

## Disclaimer

This repo documents behavior observed via browser network requests (HAR files). It is not affiliated with Clay and may break if Clay changes their internal API. Use at your own risk.

---

## License

MIT
