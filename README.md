# Rex

AI-powered Clay automation toolkit. Named after a dog.

> **Unofficial. Not affiliated with or supported by Clay. May break without notice.**

---

## What is Rex

Rex gives [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (or any AI coding agent) direct access to Clay's internal API. Three components:

- **`clay_client.py`** — Python SDK for Clay's internal REST API. Create tables, add columns, run enrichments, export/import schemas.
- **`clay_browser.py`** — Playwright daemon that captures `api.clay.com` traffic in real time. Use it to discover input parameter names for undocumented action types.
- **`action-registry.md`** — Reference catalog of known Clay actions with exact keys, package IDs, inputs, outputs, and gotchas.

Authentication uses your browser session cookie — no API keys needed.

---

## What's in the box

| File | What it is |
|------|-----------|
| `clay_client.py` | Python client wrapping Clay's internal API (~750 lines) |
| `clay_browser.py` | Playwright browser daemon for API traffic capture (~600 lines) |
| `action-registry.md` | Catalog of known Clay actions — keys, inputs, outputs, gotchas |
| `clay-api-reference.md` | Comprehensive API reference — endpoints, column schemas, action types |
| `COOKIE_SETUP.md` | Step-by-step guide to extract your session cookie from Chrome |
| `clay-session.json.example` | Template for the session file |
| `requirements.txt` | Python dependencies |

---

## Requirements

```
Python 3.8+
requests
playwright (for clay_browser.py only)
```

```bash
pip install -r requirements.txt
python -m playwright install chromium  # only if using clay_browser.py
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

## clay_client.py — The SDK

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
        "dataTypeSettings": {"type": "text"},
        "inputsBinding": [
            {"name": "useCase",      "formulaText": '"use-ai"'},
            {"name": "model",        "formulaText": '"gemini-2.5-flash"'},
            {"name": "systemPrompt", "formulaText": '"You qualify B2B companies."'},
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

### Schema export/import
```python
# Export (field IDs → portable column name references)
schema = clay.export_schema(table_id)

# Import into a new table (resolves dependencies automatically)
new_table_id, new_view_id = clay.import_schema(schema, "Cloned Table")
```

### Other operations
- `clay.create_records(table_id, [{"col_id": "value"}, ...])` — add records
- `clay.update_record(table_id, record_id, {"col_id": "value"})` — update a record
- `clay.delete_records(table_id, [record_ids])` — delete records
- `clay.set_condition(table_id, col_id, condition)` — add "Only run if" logic
- `clay.generate_formula(table_id, "natural language description")` — AI formula generation
- `clay.search_enrichments("keyword")` — discover available actions
- `clay.list_auth_accounts()` — list connected integrations

---

## clay_browser.py — API Discovery

A Playwright daemon that runs in the background, captures all `api.clay.com` requests/responses, and lets you query them. Useful when you need to discover input parameter names for action types not yet in the registry.

### Usage

```bash
# Start the daemon
python clay_browser.py launch --headless

# Navigate to a Clay table
python clay_browser.py goto "https://app.clay.com/workbooks/..."

# Interact with the UI
python clay_browser.py click "Add enrichment" --role button
python clay_browser.py fill "LeadMagic" --placeholder "Search"
python clay_browser.py click "Find Work Email"

# See what API calls were made
python clay_browser.py requests --filter fields --last 5

# Other commands
python clay_browser.py snapshot          # accessibility tree of current page
python clay_browser.py screenshot out.png
python clay_browser.py eval "document.title"

# Stop the daemon
python clay_browser.py close
```

### How it works

- Forks a daemon process listening on a UNIX socket (`/tmp/clay-browser/server.sock`)
- Injects your session cookie from `clay-session.json`
- Attaches Playwright request/response listeners to capture all `api.clay.com` traffic
- Writes captured requests as JSONL to `/tmp/clay-browser/requests.jsonl`

### Commands

| Command | Description |
|---------|-------------|
| `launch [--headless]` | Start the browser daemon |
| `close` | Shut down the daemon |
| `goto <url>` | Navigate to a URL |
| `snapshot` | Accessibility tree snapshot of the page |
| `screenshot [path]` | Save a PNG screenshot |
| `click <text> [--role] [--nth]` | Click an element by text |
| `fill <text> [--placeholder]` | Type text into an input |
| `requests [--filter] [--last N]` | Show captured API calls |
| `eval <js>` | Execute JavaScript in page context |
| `click_selector <selector>` | Click by CSS selector |

---

## action-registry.md — Action Catalog

A reference of all known Clay actions with exact specifications. Each entry includes:

- `key` — the `actionKey` identifier
- `package` — the `actionPackageId` UUID
- `inputs` — exact field names, types, required/optional
- `output` — keys accessible via `?.field_name` formulas
- `auth` — which auth account type to use
- `gotchas` — common mistakes

Categories covered: AI & Content, Enrichment (MixRank), Sources (Find People/Companies), Lookups, HTTP API, Integrations (Instantly, HeyReach, Google Sheets), Social (LinkedIn Posts).

When you encounter an action not in the registry, use `clay_browser.py` to discover its inputs.

---

## Authentication

Clay authenticates via a `claysession` cookie set when you log in through the browser. The Python client reads this cookie from `clay-session.json` and replays it with every API request — exactly like the browser does.

See [COOKIE_SETUP.md](COOKIE_SETUP.md) for how to extract the cookie from Chrome DevTools.

---

## Gotchas

Things that cost hours to figure out — see `clay-api-reference.md` for the full list:

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

[MIT](LICENSE)
