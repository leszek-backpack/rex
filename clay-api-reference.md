# Clay Internal API Reference

> Reverse-engineered internal API for programmatically building and updating Clay tables.
> Validated in production March 2026. See `clay_client.py` for the Python client.

---

## Setup

```python
from clay_client import ClayClient

clay = ClayClient()  # reads clay-session.json, prints logged-in email + workspace
```

**Auth:** Session cookie from Chrome DevTools → `app.clay.com` → Application → Cookies → `claysession`.
Paste value into `clay-session.json`:
```json
{"claysession": "s%3A..."}
```
Cookie expires every few weeks — refresh manually. No Keychain, no browser automation needed.

**Workspace ID:** `YOUR_WORKSPACE_ID` (auto-discovered via API if not provided)
**Base URL:** `https://api.clay.com/v3/`

---

## Known Action Package IDs

| Action | `actionKey` | `actionPackageId` |
|--------|-------------|-------------------|
| Use AI (Claude/Gemini/GPT) | `use-ai` | `67ba01e9-1898-4e7d-afe7-7ebe24819a57` |
| Enrich Company (Mixrank) | `enrich-company-with-mixrank-v2` | `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2` |
| HTTP API v2 | `http-api-v2` | `4299091f-3cd3-4d68-b198-0143575f471d` |
| Lookup Multiple Rows | `lookup-multiple-rows` | `4299091f-3cd3-4d68-b198-0143575f471d` |
| LinkedIn Posts | `social-posts-get-post-activity-posts-and-shares` | `b210a16b-cdaf-4cbd-ad9b-42d762cd165f` |
| Instantly: Add Lead to Campaign | `instantly-v2-add-lead-to-campaign` | `70cda03a-a576-4a6c-b3b3-55e241f828b5` |
| Instantly: Find Leads | `instantly-v2-find-leads` | `70cda03a-a576-4a6c-b3b3-55e241f828b5` |
| Instantly: Update Lead | `instantly-v2-update-lead` | `70cda03a-a576-4a6c-b3b3-55e241f828b5` |
| Lookup Single Row | `lookup-row-in-other-table` | `4299091f-3cd3-4d68-b198-0143575f471d` |
| Lookup Multiple Rows | `lookup-multiple-rows-in-other-table` | `4299091f-3cd3-4d68-b198-0143575f471d` |
| LeadMagic: Find Work Email | `leadmagic-find-work-email` | `edb58209-a62d-42be-992a-e41b87eeacc2` |
| Prospeo: Find Work Email | `prospeo-find-work-email-v2` | `48a31bbb-63e6-4461-8a62-d88bb2cd6b0f` |
| FindyMail: Find Work Email | `findymail-find-work-email` | `9515bb04-4267-4074-94eb-653545c3c38f` |

To find other action package IDs:
```python
results = clay.search_enrichments("leadmagic email")
# → [{"entity_id": "pkg_id/action_key", "name": "...", ...}]
# entity_id format: "{actionPackageId}/{actionKey}"
```

---

## AI Model Names (valid as of March 2026)

| Model | formulaText value | Auth Account | Notes |
|-------|-------------------|--------------|-------|
| Grok 4.1 Fast Reasoning ✅ | `"grok-4-1-fast-reasoning"` | `YOUR_XAI_AUTH_ACCOUNT_ID` | Best for structured JSON via `answerSchemaType` |
| Gemini 2.5 Flash ✅ | `"gemini-2.5-flash"` | `YOUR_CLAY_GEMINI_AUTH_ACCOUNT_ID` | Fast, Clay credits. Wraps JSON in code fences. |
| Gemini 2.5 Pro | `"gemini-2.5-pro"` | `YOUR_CLAY_GEMINI_AUTH_ACCOUNT_ID` | Wraps JSON in code fences. |
| GPT-4o-mini | `"gpt-4o-mini"` | `YOUR_CLAY_OPENAI_AUTH_ACCOUNT_ID` | Also wraps JSON in code fences. |
| GPT 5 Nano | `"gpt-5-nano"` | `YOUR_CLAY_OPENAI_AUTH_ACCOUNT_ID` or custom | Cheapest (0.5 credits). Successor to GPT 4.1 Nano. |
| GPT 4.1 Nano | `"gpt-4.1-nano"` | `YOUR_CLAY_OPENAI_AUTH_ACCOUNT_ID` or custom | 0.5 credits. Use for lightweight Claygent tasks. |
| GPT 4.1 Mini | `"gpt-4.1-mini"` | `YOUR_CLAY_OPENAI_AUTH_ACCOUNT_ID` or custom | 1 credit. |
| GPT 4.1 | `"gpt-4.1"` | `YOUR_CLAY_OPENAI_AUTH_ACCOUNT_ID` or custom | 9.7 credits. Smartest non-reasoning OpenAI model. |
| o4 Mini | `"o4-mini"` | `YOUR_CLAY_OPENAI_AUTH_ACCOUNT_ID` or custom | ~2.9 credits. Reasoning model. |
| ~~Gemini 2.0 Flash~~ ❌ | deprecated | — | throws "No model found" error |

**For structured JSON output:** Use Grok 4.1 + `answerSchemaType` (see below). Both Gemini and GPT wrap output in markdown code fences which breaks `?.key` formula extractors.

### AI Column Use Cases: Claygent vs Create Content

Two distinct `useCase` values control AI column behavior:

| useCase input | Clay UI Name | What it does |
|---------|-------------|-------------|
| `"claygent"` | Web Research (Claygent) | AI agent with web search — browses the internet to find answers. Use for data enrichment tasks like "Get employee count from {{@Company LI URL}}". |
| `"use-ai"` | Create Content | Simple text/JSON generation from provided inputs — no web access. Use for qualification, copy generation, data transformation. |

**CRITICAL: Both use `actionKey: "use-ai"`** (not `"ai"`). The `useCase` input differentiates them.
Using `actionKey: "ai"` causes all `inputsBinding` to be silently dropped.

**Key differences:**
- **Claygent** burns more credits (agent loop + web search) but can look up live data
- **Create Content** is cheaper, faster, deterministic — works only with data already in the table
- Both support `answerSchemaType` for structured output and `conditionalRunFormulaText` for conditional execution
- Both use `actionKey: "use-ai"` and `actionPackageId: "67ba01e9-1898-4e7d-afe7-7ebe24819a57"`
- Both require an `authAccountId` — Clay-managed (`YOUR_CLAY_GEMINI_AUTH_ACCOUNT_ID` for Gemini, `YOUR_CLAY_OPENAI_AUTH_ACCOUNT_ID` for OpenAI) or custom (`YOUR_AUTH_ACCOUNT_ID` for your-custom-key)

**Output formats:**
- **Fields** — typed output fields (Number, Text, etc). Claygent default for single-value lookups.
- **JSON Schema** — structured JSON via `answerSchemaType` + `formulaMap`. Better for multi-field outputs.

### Creating a Use AI Column (Step-by-Step)

**1. Create the column** — single POST with all config:

```python
import json

body = {
    "type": "action",
    "name": "My AI Column",
    "viewId": VIEW_ID,
    "typeSettings": {
        "actionKey": "use-ai",                                          # ALWAYS "use-ai", never "ai"
        "actionPackageId": "67ba01e9-1898-4e7d-afe7-7ebe24819a57",     # same for all AI columns
        "actionVersion": 1,
        "authAccountId": "YOUR_AUTH_ACCOUNT_ID",                     # required — pick from Known Auth Accounts table
        "dataTypeSettings": {"type": "text"},                            # ⚠ MUST be "text", NOT "json" — "json" works via API but breaks Clay UI ("Could not find properties for data type json")
        "inputsBinding": [
            {"name": "useCase",      "formulaText": '"claygent"'},      # or "use-ai" for Create Content
            {"name": "model",        "formulaText": '"gpt-4.1-nano"'},  # see model table above
            {"name": "prompt",       "formulaText": '"Do X from " + {{f_input_field}}'},
            # For structured output — add these two (REQUIRED for ?.key extractors to work):
            {"name": "answerSchemaType", "formulaMap": {
                "type": '"json"',
                "jsonType": '"JSONSchema"',
                "jsonSchema": json.dumps(json.dumps({                   # double-encoded!
                    "type": "object",
                    "properties": {
                        "field_1": {"type": "string"},
                        "field_2": {"type": "number"},
                    },
                    "required": ["field_1", "field_2"]
                }))
            }},
            {"name": "_metadata", "formulaMap": {"modelSource": '"user"'}},
        ]
    }
}
r = clay.session.post(f"{BASE}/tables/{TABLE_ID}/fields", json=body)
ai_field_id = r.json()["field"]["id"]
```

**2. Add extractor columns** — one formula per output field:

```python
clay.create_formula_column(TABLE_ID, "Field 1", f"{{{{{ai_field_id}}}}}?.field_1", view_id=VIEW_ID, data_type="text")
clay.create_formula_column(TABLE_ID, "Field 2", f"{{{{{ai_field_id}}}}}?.field_2", view_id=VIEW_ID, data_type="number")
```

**3. Run:**

```python
clay.run_column(TABLE_ID, [ai_field_id], record_ids=RECORD_IDS)
```

**Checklist (common mistakes):**
- `actionKey` must be `"use-ai"` — `"ai"` silently drops all inputs
- `authAccountId` is required — without it the column never runs
- `answerSchemaType` uses `formulaMap` not `formulaText` — `formulaText` silently fails
- `jsonSchema` value is **double JSON-encoded**: `json.dumps(json.dumps(schema))` — single encoding produces a dict where Clay expects a string; column creates OK but never runs
- `_metadata` with `modelSource: '"user"'` (inner quotes!) is required when using `answerSchemaType`
- `dataTypeSettings` must be `{"type": "text"}` — `{"type": "json"}` breaks Clay UI rendering
- `answerSchemaType` + `_metadata` are REQUIRED for `?.key` extractors to work — without them, Clay shows "Unable to parse output schema" even if the column was created successfully
- `systemPrompt` must be < ~1,000 chars — put long instructions in `prompt` instead
- For Claygent: expect 1-2 min per record (web research). For Create Content: seconds.

---

## CRITICAL: Formula Reference Rules

**Always use field IDs, never column names.**

```python
# ✅ CORRECT — field ID reference
"{{f_0tb9vdhxn5TpvGGAUCg}}"

# ❌ WRONG — Clay formula parser ignores name references
"{{Company URL}}"
```

Get field IDs from the table:
```python
raw = clay.get_table(table_id)
fields = raw["table"].get("fields", [])
field_map = {f["name"]: f["id"] for f in fields}

# Build ref helper
def ref(name): return "{{" + field_map[name] + "}}"
```

---

## CRITICAL: `inputsBinding` Rules

### 1. `authAccountId` goes top-level, NOT in `inputsBinding`

```python
# ✅ CORRECT
typeSettings = {
    "actionKey": "use-ai",
    "actionPackageId": "67ba01e9-1898-4e7d-afe7-7ebe24819a57",
    "authAccountId": "YOUR_GEMINI_AUTH_ACCOUNT_ID",   # ← top level
    "inputsBinding": [
        {"name": "useCase", "formulaText": '"use-ai"'},
        ...
    ]
}

# ❌ WRONG — authAccountId in inputsBinding silently fails, Gemini won't connect
"inputsBinding": [
    {"name": "authAccountId", "value": "aa_..."},  # ← wrong place
    ...
]
```

### 2. ALL inputs MUST use `"formulaText"` — `"value"` is silently dropped

```python
# ✅ CORRECT — all inputs use formulaText
{"name": "systemPrompt", "formulaText": '"You are a qualification specialist..."'}  # static string in quotes
{"name": "model",        "formulaText": '"gemini-2.5-flash"'}
{"name": "useCase",      "formulaText": '"use-ai"'}
{"name": "prompt",       "formulaText": '"Company: " + ' + ref("Name") + ' + "\\n"'}

# ❌ WRONG — "value" key is SILENTLY DROPPED, field reads back as empty
{"name": "systemPrompt", "value": "You are a qualification specialist..."}
```

**Rule:** Always use `"formulaText"`. Static strings must be wrapped in `"outer quotes"` so Clay treats them as string literals.

### 3. `systemPrompt` must be SHORT (< ~1,000 chars)

Long text in `formulaText` breaks Clay's formula parser:
- Markdown characters (`**`, `#`, backticks) cause "Invalid formula"
- Strings > ~2,000 chars fail at parse time

```python
# ❌ Too long — causes "Invalid formula" in Clay UI
{"name": "systemPrompt", "formulaText": json.dumps(long_760_line_prompt)}

# ✅ Works — short, clean string literal (no markdown, under ~1,000 chars)
{"name": "systemPrompt", "formulaText": (
    '"You qualify companies for YourClient. Return ONLY valid JSON.\\n\\n'
    'T1: NYC startup 50-500 employees, Series A+\\n'
    'T2: US-based, similar profile\\n'
    'DISQUALIFY: non-US, <20 or >2000 employees\\n\\n'
    'Return ONLY valid JSON."'
)}
```

Keep `systemPrompt` to ~500-1,000 chars max. Put the full instructions in `prompt` if needed.

---

## Column Definitions by Type

### Source column (Webhook)
```python
{
    "type": "source",
    "name": "Webhook",
    "typeSettings": {"sourceType": "webhook", "sourceIds": []}
}
```

### Text / Number / Basic column
```python
{"type": "text", "name": "Company Name"}
{"type": "number", "name": "Employee Count"}
```

### Formula column (extracts from another column)
```python
# Extract a JSON field from an action column result
{
    "type": "formula",
    "name": "Tier",
    "typeSettings": {
        "formulaText": "{{f_qualification_col_id}}?.tier",
        "dataTypeSettings": {"type": "text"}
    }
}

# The ?.key pattern safely accesses object properties (returns null if missing)
# Works for: strings, numbers, nested objects, arrays
```

### Enrich Company (Mixrank v2)
```python
{
    "type": "action",
    "name": "Enrich Company",
    "typeSettings": {
        "actionKey": "enrich-company-with-mixrank-v2",
        "actionPackageId": "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2",
        "dataTypeSettings": {"type": "text"},
        "inputsBinding": [
            # ⚠️ Input name is "company_identifier", NOT "url"
            {"name": "company_identifier", "formulaText": ref("Company URL")}
        ]
    }
}
```

**Mixrank v2 confirmed output keys** (validated live March 2026, Spacelift test):

| Formula | Value returned | Notes |
|---------|---------------|-------|
| `?.name` | `"Spacelift"` | Company name |
| `?.url` | `"https://www.linkedin.com/company/spacelift-io"` | ⚠️ LinkedIn URL, NOT website |
| `?.website` | `"https://spacelift.io"` | Actual website URL |
| `?.description` | `"Spacelift is an infrastructure..."` | Full company description |
| `?.employee_count` | `141` | Headcount (number) |
| `?.industry` | `"Software Development"` | Industry string |
| `?.country` | `"US"` | Country code |
| `?.founded` | `"2020"` | Founded year |
| `?.org_id` | _(string)_ | Internal Mixrank org ID |

**NOT available from Mixrank v2:** `domain`, `city`, `funding_stage`, `linkedin_url`, `short_description`

```python
# Correct extractor formulas:
"{{f_enrich_col_id}}?.name"           # company name
"{{f_enrich_col_id}}?.website"        # ✅ website URL (NOT ?.url)
"{{f_enrich_col_id}}?.url"            # ✅ LinkedIn company URL (NOT website)
"{{f_enrich_col_id}}?.description"    # full description
"{{f_enrich_col_id}}?.employee_count" # headcount (number)
"{{f_enrich_col_id}}?.industry"       # industry string
"{{f_enrich_col_id}}?.country"        # country code
```

### Enrich Person
```python
{
    "type": "action",
    "name": "Enrich Person",
    "typeSettings": {
        "actionKey": "enrich-person",   # find via search_enrichments("enrich person")
        "actionPackageId": "<pkg_id>",  # from search_enrichments result
        "dataTypeSettings": {"type": "text"},
        "inputsBinding": [
            # ⚠️ Input name is "person_identifier" — NOT linkedin_url, url, profile_url
            {"name": "person_identifier", "formulaText": ref(f_linkedin_url)},
            {"name": "email"}   # include empty email binding
        ]
    }
}
```

**Person enrichment output keys** (top-level, accessible via `?.key`):
| Formula | Returns |
|---------|---------|
| `?.title` | Job title |
| `?.org` | Current company name |
| `?.location_name` | Location string |
| `?.headline` | LinkedIn headline |
| `?.url` | LinkedIn profile URL |
| `?.num_followers` | Follower count |
| `?.connections` | Connection count |

**Nested data (e.g. experience) requires `mappedResultPath`** — see below.

### Enrich Company — Input Gotcha

The Enrich Company (Mixrank) input `company_identifier` works best with a **LinkedIn company URL** (e.g., `https://www.linkedin.com/company/spacelift-io`). Company names like "Stealth", "Cuez" fail with `ERROR_INVALID_INPUT`. Extract the company LinkedIn URL from person enrichment's `experience[0].url` using `mappedResultPath`.

### mappedResultPath — Extracting Nested Enrichment Data

Formula columns using `?.key` can only access **top-level** enrichment keys. For nested paths (e.g., `experience > 0 > url`), you MUST use `mappedResultPath`:

```python
# Extract company LinkedIn URL from person enrichment (nested: experience[0].url)
f_co_url = clay.create_column(table_id, {"type": "text", "name": "Company LI URL"})["id"]
clay.session.patch(
    f"https://api.clay.com/v3/tables/{table_id}/fields/{f_co_url}",
    json={"typeSettings": {
        "dataTypeSettings": {"type": "url"},
        "formulaType": "text",
        "formulaText": ref(f_enrich_person) + "?.experience?.[0]?.url",
        "mappedResultPath": ["experience", "0", "url"],   # ← REQUIRED for nested paths
    },
    "attributionData": {"created_from": "object_mapper"}}
)
# Without mappedResultPath, the same formula returns empty
```

Use `mappedResultPath` columns as inputs to downstream action columns (e.g., Enrich Company).

### Use AI column
```python
{
    "type": "action",
    "name": "Qualification",
    "typeSettings": {
        "actionKey": "use-ai",
        "actionPackageId": "67ba01e9-1898-4e7d-afe7-7ebe24819a57",
        "dataTypeSettings": {"type": "text"},
        "authAccountId": "YOUR_GEMINI_AUTH_ACCOUNT_ID",   # ← top level, not in inputsBinding
        "inputsBinding": [
            {"name": "useCase",      "formulaText": '"use-ai"'},
            {"name": "model",        "formulaText": '"gemini-2.5-flash"'},
            # ⚠️ "value" key is SILENTLY DROPPED — always use "formulaText"
            # Keep systemPrompt short (< ~1,000 chars), no markdown
            {"name": "systemPrompt", "formulaText": '"You qualify companies for YourClient. Return ONLY valid JSON."'},
            {"name": "prompt",       "formulaText": (
                '"Company: " + ' + ref("Name") + ' + "\\n" + '
                '"Domain: " + ' + ref("Domain") + ' + "\\n" + '
                '"Return JSON with keys: tier, score, status"'
            )},
        ]
    }
}
```

The `prompt` formulaText is a Clay formula expression (JS-like):
- String literals: `"text"` (double-quoted)
- Concatenation: `"text" + {{f_id}} + "more text"`
- Newlines in strings: `"line1\\nline2"` (double-escaped in Python → `\n` in formula)
- Null-safe access: `{{f_id}}?.property`
- Type conversion: `String({{f_number_id}})`

### Use AI with structured JSON output (answerSchemaType)

**When you need formula extractors (`?.key`) to work, use `answerSchemaType` with Grok.**
Without it, both Gemini and GPT wrap JSON in code fences which breaks `?.key` accessors.

```python
import json

# Define your output schema
schema = json.dumps({
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["QUALIFY", "DISQUALIFY"]},
        "reason": {"type": "string"},
        "signals": {"type": "string"}
    },
    "required": ["decision", "reason", "signals"],
    "additionalProperties": False
})

{
    "type": "action",
    "name": "AI Qualification",
    "typeSettings": {
        "actionKey": "use-ai",
        "actionPackageId": "67ba01e9-1898-4e7d-afe7-7ebe24819a57",
        "dataTypeSettings": {"type": "text"},
        "authAccountId": "YOUR_XAI_AUTH_ACCOUNT_ID",  # Grok xAI
        "inputsBinding": [
            {"name": "useCase",      "formulaText": '"use-ai"'},
            {"name": "model",        "formulaText": '"grok-4-1-fast-reasoning"'},
            {"name": "systemPrompt", "formulaText": '"You are a qualification specialist. Return JSON only."'},
            {"name": "prompt",       "formulaText": '"Company: " + {{f_name}} + "\\nReturn JSON"'},
            # ✅ CRITICAL: answerSchemaType uses formulaMap, NOT formulaText
            {"name": "answerSchemaType", "formulaMap": {
                "type": '"json"',
                "jsonType": '"JSONSchema"',
                "jsonSchema": json.dumps(schema)  # double-encoded string
            }},
            # ✅ Required metadata for user-provided model
            {"name": "_metadata", "formulaMap": {"modelSource": '"user"'}},
        ]
    }
}
```

The `answerSchemaType` input enforces structured JSON output — the AI returns a parsed JSON object, not a string. Formula extractors (`?.decision`, `?.reason`) work correctly.

Ask for JSON output by including it in the prompt text:
```
"Return valid JSON with keys: tier (string), score (number 0-100)"
```

Extract results with formula columns:
```python
"{{f_ai_col_id}}?.tier"    # string field
"{{f_ai_col_id}}?.score"   # number field
```

### HTTP API v2 column (e.g. RapidAPI GET)

**CRITICAL: `queryString` and `headers` use `formulaMap`, NOT `formulaText`.**
Using `formulaText` with a JSON object `{"key": val}` causes Clay to split the string character-by-character into numbered rows — completely broken.

```python
# ✅ BEST — use auth account (YOUR_RAPIDAPI_AUTH_ACCOUNT_ID) — no hardcoded keys
{
    "type": "action",
    "name": "Step 4a | Company Profile | RapidAPI",
    "typeSettings": {
        "actionKey": "http-api-v2",
        "actionPackageId": "4299091f-3cd3-4d68-b198-0143575f471d",
        "authAccountId": "YOUR_RAPIDAPI_AUTH_ACCOUNT_ID",   # ← injects X-RapidAPI-Key + Host automatically
        "dataTypeSettings": {"type": "text"},
        "inputsBinding": [
            {"name": "method", "formulaText": '"GET"'},
            {"name": "url",    "formulaText": '"https://fresh-linkedin-scraper-api.p.rapidapi.com/api/v1/company/profile"'},
            # ✅ queryString as formulaMap — each key maps to a formula
            {"name": "queryString", "formulaMap": {
                "company": "{{f_name_field_id}}"
            }},
            # No headers needed — auth account injects them
            {"name": "removeNull",      "formulaText": "true"},
            {"name": "followRedirects", "formulaText": "true"},
            {"name": "shouldRetry",     "formulaText": "true"},
        ]
    }
}

# Step 4b — chain: extract id from Step 4a response
{"name": "queryString", "formulaMap": {
    "company_id": "String({{f_step4a_id}}?.data?.id)"
}}

# ❌ WRONG — formulaText with JSON object: Clay splits chars into numbered rows
{"name": "queryString", "formulaText": '{"company": {{f_name}}}'}
{"name": "headers",     "formulaText": '{"X-RapidAPI-Key": "..."}'}

# ✅ CORRECT — formulaMap for key-value inputs (if not using auth account)
{"name": "queryString", "formulaMap": {"company": "{{f_name}}"}}
{"name": "headers",     "formulaMap": {"X-RapidAPI-Key": '"your-key"'}}
```

> **Note on bulk-fetch-records API:** For `http-api-v2` action columns, `clay.get_records()` returns `value: "Status Code: 200"` (a display summary). The full JSON response body is stored internally and IS accessible to Clay's formula engine — downstream columns referencing `{{f_http_col}}?.data?.id` work correctly despite the API showing only the status string.

### Lookup Multiple Rows in Other Table

**CRITICAL: Input names use `fields|` prefix for filter parameters.**

```python
{
    "type": "action",
    "name": "People at Company",
    "typeSettings": {
        "actionKey": "lookup-multiple-rows-in-other-table",
        "actionPackageId": "4299091f-3cd3-4d68-b198-0143575f471d",
        "actionVersion": 1,
        "dataTypeSettings": {"type": "text"},
        "inputsBinding": [
            {"name": "tableId",               "formulaText": '"t_target_table_id"'},
            {"name": "fields|targetColumn",    "formulaText": '"f_field_in_target_table"'},
            {"name": "fields|filterOperator",  "formulaText": '"EQUAL"'},
            {"name": "fields|rowValue",        "formulaText": "{{f_field_in_current_table}}"},
            # Optional:
            # {"name": "fields|limit",         "formulaText": "20"},
        ]
    }
}
```

**Input names mapping:**

| UI Label | Input Name | Value |
|----------|-----------|-------|
| Table to Search | `tableId` | `"t_xxx"` (string literal) |
| Target Column | `fields\|targetColumn` | `"f_xxx"` (field ID in target table, string literal) |
| Filter Operator | `fields\|filterOperator` | `"EQUAL"`, `"CONTAINS"`, etc. |
| Row Value | `fields\|rowValue` | `{{f_xxx}}` (formula ref from current table) |
| Limit | `fields\|limit` | number |

**Lookup Single Row** (`lookup-row-in-other-table`) uses the same pattern — same package ID, same `fields|` prefix inputs.

**Response:** `value` is a display string like `"✅ 3 Records Found"`. Use formula extractors to access matched record data.

### Instantly: Add Lead to Campaign

```python
{
    "type": "action",
    "name": "Add to Instantly",
    "typeSettings": {
        "actionKey": "instantly-v2-add-lead-to-campaign",
        "actionPackageId": "70cda03a-a576-4a6c-b3b3-55e241f828b5",
        "authAccountId": "YOUR_INSTANTLY_AUTH_ACCOUNT_ID",  # your-instantly
        "dataTypeSettings": {"type": "text"},
        "inputsBinding": [
            {"name": "email",        "formulaText": "{{f_email_field}}"},
            {"name": "first_name",   "formulaText": "{{f_first_name_field}}"},
            {"name": "last_name",    "formulaText": "{{f_last_name_field}}"},
            {"name": "company_name", "formulaText": "{{f_company_field}}"},
            {"name": "campaign",     "formulaText": '"campaign-uuid-here"'},
        ]
    }
}
```

**Campaign IDs** are fetched dynamically via `POST /actions/dynamicFields` with `parameterPath: "campaign"`.

### HTTP API v2 column (POST with JSON body, e.g. HubSpot)
```python
{
    "type": "action",
    "name": "Check Company in HS",
    "typeSettings": {
        "actionKey": "http-api-v2",
        "actionPackageId": "4299091f-3cd3-4d68-b198-0143575f471d",
        "dataTypeSettings": {"type": "text"},
        "authAccountId": "YOUR_HUBSPOT_AUTH_ACCOUNT_ID",
        "inputsBinding": [
            {"name": "method", "formulaText": '"POST"'},
            {"name": "url",    "formulaText": '"https://api.hubapi.com/crm/v3/objects/companies/search"'},
            {"name": "body",   "formulaText": (
                '\'{"filterGroups":[{"filters":[{"propertyName":"domain","operator":"EQ",'
                '"value":"\' + ' + ref("Domain") + ' + \'"}]}]}\''
            )},
            {"name": "headers", "formulaMap": {
                "Authorization":  '"Bearer " + Clay.secret("hubspot_token")',
                "Content-Type":   '"application/json"',
            }},
        ],
    }
}
```

---

## Export

### How CSV export works

Export is **fully server-side** — no scrolling, no pagination. Two variants:

```python
# With view (respects filters)
POST /v3/tables/{TABLE_ID}/views/{VIEW_ID}/export

# All rows (ignores all filters)
POST /v3/tables/{TABLE_ID}/export
```

Poll until done, then download from a signed S3 URL (valid 24h):

```python
GET /v3/exports/{job_id}
# → {"status": "FINISHED", "downloadUrl": "https://s3.amazonaws.com/...", "recordsExportedCount": 556}
```

Client method: `clay.export_csv(table_id, view_id=None)` — returns the download URL. Completes in ~1 second for 556 rows.

### Action column values in CSV export

**Problem:** Action ("Response") columns always export as the literal string `"Response"` in the native CSV. The full enrichment JSON is intentionally omitted.

**Two solutions:**

**Option A — Formula columns (no code, recommended):**
Add a formula column in Clay UI with `JSON.stringify({{f_action_field_id}})`. This gets included in the native CSV export with the full JSON. Best when you control the table.

**Option B — Parallel API fetch:**
```python
# GET /v3/tables/{TABLE_ID}/records/{record_id}
# → cells[field_id].externalContent.fullValue = full JSON

results = clay.fetch_all_records_full(table_id, view_id, field_id, workers=20)
# [{record_id, value, status}, ...]
# ~27ms/record with 20 workers → 556 rows in ~15s, 10k rows in ~4.5 min
```

Note: `bulk-fetch-records` does NOT return `externalContent` — you must hit the single-record endpoint `/tables/{TABLE_ID}/records/{record_id}` individually.

### Key export endpoints

```
# Start export
POST https://api.clay.com/v3/tables/{TABLE_ID}/views/{VIEW_ID}/export  # filtered view
POST https://api.clay.com/v3/tables/{TABLE_ID}/export                  # all rows

# Poll job
GET  https://api.clay.com/v3/exports/{job_id}

# Single record with full action data
GET  https://api.clay.com/v3/tables/{TABLE_ID}/records/{record_id}
     → cells[field_id].externalContent.fullValue

# All record IDs (no pagination)
GET  https://api.clay.com/v3/tables/{TABLE_ID}/views/{VIEW_ID}/records/ids
```

---

## Records

### Create records
```python
# POST /tables/{id}/records
r = clay.session.post(
    f"https://api.clay.com/v3/tables/{table_id}/records",
    json={"records": [
        {"cells": {
            field_id_1: "https://spacelift.io",
            field_id_2: "Spacelift"
        }}
    ]}
)
# Returns: {"records": [{"id": "r_xxx", "cells": {...}, ...}]}
record_id = r.json()["records"][0]["id"]
```

Note: The `cells` key takes `{field_id: raw_value}` — not `fieldValues`, not `initialFieldValues`.

### Read records
```python
results = clay.get_records(table_id, [record_id])
cells = results[0]["cells"]
# Each cell: {"value": ..., "metadata": {...}}
value = cells.get(field_id, {}).get("value")
```

### List all records in a table (2-step process)

**CRITICAL:** There is no single endpoint to list records. The old `/views/{view_id}/records` returns 404 ("NoMatchingURL"). Use this 2-step approach:

```python
# Step 1: Get all record IDs from a view
r = clay.session.get(f"https://api.clay.com/v3/tables/{table_id}/views/{view_id}/records/ids")
all_ids = r.json()["results"]   # ← list of record ID strings ["r_xxx", "r_yyy", ...]

# ⚠️ Filter out "search" placeholder entry if present
record_ids = [rid for rid in all_ids if rid != "search"]

# Step 2: Bulk-fetch full record data
r = clay.session.post(
    f"https://api.clay.com/v3/tables/{table_id}/bulk-fetch-records",
    json={"recordIds": record_ids}   # ← REQUIRED, cannot be empty or omitted
)
records = r.json()["records"]   # full record objects with cells

# Access cell values:
for rec in records:
    value = rec["cells"].get(field_id, {}).get("value")
```

**Key points:**
- `/views/{view_id}/records` does NOT exist — returns 404 "NoMatchingURL"
- `bulk-fetch-records` requires a non-empty `recordIds` array
- The `/records/ids` endpoint may return a `"search"` placeholder — always filter it out

### Update record cells
```python
clay.update_record(table_id, record_id, {field_id: new_value})
```

---

## Running Columns

```python
# ⚠️ runRecords is REQUIRED — omitting causes 400 error
r = clay.session.patch(
    f"https://api.clay.com/v3/tables/{table_id}/run",
    json={
        "fieldIds": [field_id_1, field_id_2],
        "callerName": "clay-client",
        "runRecords": {"recordIds": [record_id]}   # specific records
        # OR: "runRecords": {"viewId": view_id}    # all records in view
    }
)
# Returns: {"recordCount": 1, "runMode": "INDIVIDUAL"}
```

See "Running Columns — Rate Limits" section below for `ERROR_TOO_MANY_RUNS` and `isPreview` behavior.

---

## Reordering Columns (View)

Column order is per-view and stored as a lexicographic string (e.g. `'x'`, `'xi'`, `'xr'`, `'y'`).

```python
# Move a field to appear after another field in a specific view
r = clay.session.patch(
    f"https://api.clay.com/v3/tables/{table_id}/views/{view_id}/fields/{field_id}",
    json={"afterFieldId": "f_target_field_id"}
)
# Clay computes a new order string between target and the next field

# ⚠️ The table-level PATCH with afterFieldId only works for the first move
# For subsequent moves use the view-level endpoint above
```

Get the view ID from the table:
```python
r = clay.session.get(f"https://api.clay.com/v3/tables/{table_id}")
views = r.json()["table"]["views"]
# Find by name: "Default view", "All rows", "Errored rows", etc.
view_id = next(v["id"] for v in views if v["name"] == "Default view")
```

---

## Table Schema Access

```python
raw = clay.get_table(table_id)
# Response structure: {"table": {...}, "extraData": {...}}
table = raw["table"]

# Key fields on table object:
view_id   = table["firstViewId"]           # needed for get_schema()
fields    = table["fields"]                # list of all column definitions
wb_id     = table["workbookId"]
settings  = table["tableSettings"]        # usually {}

# Build field map
field_map = {f["name"]: f["id"] for f in fields}

# Get full schema (includes typeSettings for all columns)
schema = clay.get_schema(table_id, view_id)
fields_dict = schema["tableSchema"]       # dict keyed by field ID
# Note: view schema omits some typeSettings detail — use table["fields"] for full data
```

---

## Creating a Table

```python
# 1. Create workbook + table (new workbook)
table = clay.create_table("My Table Name")
table_id  = table["id"]
wb_id     = table["workbookId"]

# 2. Add columns
field = clay.create_column(table_id, {
    "type": "text",
    "name": "Company URL"
})
field_id = field["id"]   # e.g. "f_0tb9vdhxn5TpvGGAUCg"

# 3. Create in existing workbook
table = clay.create_table("My Table", workbook_id="wb_xxx")
```

---

## Updating Columns

```python
import copy

# Read current state first
raw = clay.get_table(table_id)
fields = raw["table"]["fields"]
target = next(f for f in fields if f["name"] == "Qualification")
fid = target["id"]

# Make a deep copy, modify, patch
ts = copy.deepcopy(target["typeSettings"])
ts["authAccountId"] = "aa_new_account_id"
ts["inputsBinding"][0]["formulaText"] = '"new-model"'

result = clay.update_column(table_id, fid, {"typeSettings": ts})
```

Always deep-copy typeSettings before modifying. Patching replaces the full typeSettings object.

---

## Workflow: Build a Table from Scratch

```python
from clay_client import ClayClient
import copy

clay = ClayClient()

# 1. Create table
table = clay.create_table("Company Qualification")
table_id = table["id"]

# 2. Add input columns
f_url  = clay.create_column(table_id, {"type": "text", "name": "Company URL"})["id"]
f_name = clay.create_column(table_id, {"type": "text", "name": "Company Name"})["id"]

# 3. Add enrichment column
def ref(fid): return "{{" + fid + "}}"

f_enrich = clay.create_column(table_id, {
    "type": "action", "name": "Enrich Company",
    "typeSettings": {
        "actionKey": "enrich-company-with-mixrank-v2",
        "actionPackageId": "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2",
        "dataTypeSettings": {"type": "text"},
        "inputsBinding": [{"name": "company_identifier", "formulaText": ref(f_url)}]
    }
})["id"]

# 4. Add formula extractors
# ⚠️ Clay API ignores "type": "formula" on create — columns come back as "text" type.
# To set a formula, PATCH the typeSettings with formulaType + formulaText AFTER creation.
f_website = clay.create_column(table_id, {"type": "text", "name": "Website"})["id"]
clay.session.patch(
    f"https://api.clay.com/v3/tables/{table_id}/fields/{f_website}",
    json={"typeSettings": {
        "dataTypeSettings": {"type": "text"},
        "formulaType": "text",
        "formulaText": ref(f_enrich) + "?.website",  # ✅ ?.website (not ?.url which = LinkedIn URL)
        "mappedResultPath": ["website"]
    }}
)

# 5. Add AI column
# ⚠️ systemPrompt "value" is silently dropped — use "formulaText" with quoted string
f_qual = clay.create_column(table_id, {
    "type": "action", "name": "Qualification",
    "typeSettings": {
        "actionKey": "use-ai",
        "actionPackageId": "67ba01e9-1898-4e7d-afe7-7ebe24819a57",
        "dataTypeSettings": {"type": "text"},
        "authAccountId": "YOUR_GEMINI_AUTH_ACCOUNT_ID",
        "inputsBinding": [
            {"name": "useCase",      "formulaText": '"use-ai"'},
            {"name": "model",        "formulaText": '"gemini-2.5-flash"'},
            {"name": "systemPrompt", "formulaText": '"You are a B2B qualification specialist. Return JSON only."'},
            {"name": "prompt",       "formulaText": (
                '"Company: " + ' + ref(f_name) + ' + "\\n" + '
                '"Website: " + ' + ref(f_website) + ' + "\\n" + '
                '"Return JSON: {tier, score}"'
            )},
        ]
    }
})["id"]

# 6. Extract AI results — same PATCH pattern as formula extractors
f_tier = clay.create_column(table_id, {"type": "text", "name": "Tier"})["id"]
clay.session.patch(
    f"https://api.clay.com/v3/tables/{table_id}/fields/{f_tier}",
    json={"typeSettings": {
        "dataTypeSettings": {"type": "text"},
        "formulaType": "text",
        "formulaText": ref(f_qual) + "?.tier",
        "mappedResultPath": ["tier"]
    }}
)

# 7. Inject a test record
r = clay.session.post(
    f"https://api.clay.com/v3/tables/{table_id}/records",
    json={"records": [{"cells": {f_url: "https://spacelift.io", f_name: "Spacelift"}}]}
)
record_id = r.json()["records"][0]["id"]
print(f"Record created: {record_id}")
print(f"Table: https://app.clay.com/workspaces/YOUR_WORKSPACE_ID/workbooks/{table['workbookId']}/tables/{table_id}")
```

---

## Formula Columns — How They Actually Work

**Key insight:** In Clay's API, "formula column" = any column with `typeSettings.formulaText` set. The `type` field is the DATA type (`text`, `number`, `url`), not whether it's computed.

```python
# ❌ WRONG — "type": "formula" is silently ignored by the API
clay.create_column(table_id, {
    "type": "formula", "name": "Tier",
    "typeSettings": {"formulaText": "...", "dataTypeSettings": {"type": "text"}}
})
# Returns a plain text column with no formulaText

# ✅ CORRECT — create column first, then PATCH formulaText
fid = clay.create_column(table_id, {"type": "text", "name": "Tier"})["id"]
clay.session.patch(
    f"https://api.clay.com/v3/tables/{table_id}/fields/{fid}",
    json={"typeSettings": {
        "dataTypeSettings": {"type": "text"},
        "formulaType": "text",
        "formulaText": "{{f_qual_id}}?.tier",
        "mappedResultPath": ["tier"]   # optional but recommended
    }}
)
```

**`url` and `number` columns CAN accept formulaText** — `dataTypeSettings.type` can stay as `url`/`number`:
```python
# url/number typed columns accept formulaText as long as formulaType is included
clay.session.patch(
    f"https://api.clay.com/v3/tables/{table_id}/fields/{fid}",
    json={"typeSettings": {
        "dataTypeSettings": {"type": "url"},  # can stay as url/number
        "formulaType": "text",                # ← REQUIRED (the real gatekeeper)
        "formulaText": "{{f_enrich_id}}?.url",
    }}
)
# Column type auto-promotes from "text" to "formula" after successful PATCH
```

### Formula Syntax — What Clay Actually Supports

Clay formulas use a **limited expression evaluator**, NOT full JavaScript. Key rules:

**Works:**
- Ternary expressions: `condition ? "yes" : "no"`
- Nested ternaries: `a ? "x" : b ? "y" : "z"`
- String methods: `.toLowerCase()`, `.split()`, `.join()`, `.slice()`, `parseInt()`, `String()`
- Regex `.test()`: `/pattern/i.test(String({{f_id}}) || "")` — **preferred for matching**
- Simple regex in `.match()`: `hcRaw.match(/[0-9]+/)`
- `let` declarations (but only the LAST expression returns — variables from earlier `let` lines are NOT accessible)
- Null coalescing: `({{f_id}} || "")`
- Optional chaining: `{{f_id}}?.key`

**Does NOT work:**
- IIFE: `(function() { ... })()` — parses but doesn't execute correctly
- Arrow functions with block bodies: `(x => { return x; })(val)` — block body ignored
- `.includes()`, `.indexOf()` — may cause "Error evaluating formula" on some Clay versions
- `.some()`, `.filter()`, `.map()`, `.find()` — parse error
- `REGEXMATCH()`, `REGEXEXTRACT()`, `LOWER()` — these are spreadsheet functions, NOT available in Clay
- Regex word boundaries `\b` — causes parse error
- Multi-statement `let` with semicolons — only last expression returns, earlier variables lost

**Pattern for complex formulas:** Use pure nested ternaries with inline expressions. Repeat the field reference rather than trying to store in a variable:

```python
# ✅ CORRECT — pure nested ternary, inline everything
formula = (
    '!(loc_check_expression)'
    ' ? "No - Location"'
    ' : hc_check === "" ? "No - HC"'
    ' : parseInt(hc_expr, 10) < 11 ? "Too small"'
    ' : parseInt(hc_expr, 10) > 200 ? "Too large"'
    ' : "Yes"'
)
# Where loc_check_expression and hc_expr are inlined field references,
# NOT variables. The field ref repeats each time it's used.

# Example: location check with 30 countries — use .test() with regex
countries = "united states|usa|canada|united kingdom|uk|germany|france|netherlands|poland|spain|italy"
formula = f'/{countries}/i.test(String({{{{f_location_id}}}}) || "") ? "QUALIFIED" : "SKIP"'
# Much cleaner than repeating .indexOf() 30 times
```

**PATCH formula requires `formulaType`:** Without it, the formulaText is silently dropped:
```python
# ❌ WRONG — formulaText silently dropped
clay.patch(f"/tables/{tid}/fields/{fid}", {
    "typeSettings": {"formulaText": "...", "dataTypeSettings": {"type": "text"}}
})

# ✅ CORRECT — include formulaType
clay.patch(f"/tables/{tid}/fields/{fid}", {
    "typeSettings": {
        "formulaText": "...",
        "formulaType": "text",        # ← REQUIRED
        "dataTypeSettings": {"type": "text"}
    }
})
```

---

## Running Columns — Rate Limits

**`runRecords` is required** — omitting it returns a 400 error:
```python
# ❌ 400 Bad Request: "Field runRecords - Required"
{"fieldIds": [...], "callerName": "clay-client"}

# ✅ Correct
{"fieldIds": [...], "callerName": "clay-client", "runRecords": {"recordIds": [record_id]}}
# OR for all records in a view:
{"fieldIds": [...], "callerName": "clay-client", "runRecords": {"viewId": view_id}}
```

**`runRecords: {"viewId": ...}` uses the UI row limit:** If the Clay UI view is set to show only 10 rows, the run endpoint will only trigger 10 records. Set the view to show all rows before running via API.

**`ERROR_TOO_MANY_RUNS`** — Clay rate-limits columns triggered too frequently:
- Status in cell: `{"metadata": {"status": "ERROR_TOO_MANY_RUNS"}}`
- The run API still returns 200 but execution is rejected
- Fix: wait ~3 minutes before re-running the column
- Affects testing heavily — don't trigger the same column more than 3-4 times in quick succession

**`isPreview: true`** — normal for API-triggered runs:
- `{"metadata": {"status": "SUCCESS", "isPreview": true}}`
- This is NOT an error — downstream formula columns CAN access preview data
- Enrichment data is usable even with `isPreview: true`

---

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "No model found with name 'gemini-2.0-flash'" | Deprecated model | Use `"gemini-2.5-flash"` |
| systemPrompt shows empty in Clay UI | `"value"` key silently dropped | Use `"formulaText"` with `'"quoted string"'` |
| systemPrompt causes "Invalid formula" | String too long or contains markdown | Keep under ~1,000 chars, no `**`, `#`, backticks |
| Column mapping empty in UI | Wrong input name (e.g. `url` instead of `company_identifier`) | Check exact input names by inspecting a working column via `clay.get_records()` or the HAR approach |
| Column mapping empty in UI | Using `{{Column Name}}` reference | Use `{{field_id}}` (field IDs only) |
| Gemini account not connecting | `authAccountId` in `inputsBinding` | Move `authAccountId` to top-level `typeSettings` |
| Formula column has no formula after create | Used `"type": "formula"` on create | Create as `text` type, then PATCH `typeSettings.formulaText` |
| formulaText not saving on any column | Missing `formulaType: "text"` in PATCH | Always include `formulaType: "text"` — it's the gatekeeper (url/number dataTypes work fine) |
| `get_schema()` returns empty fields | Wrong viewId or schema has no typeSettings | Use `table["fields"]` from `get_table()` for full column data |
| Record creation 400: "records Required" | Wrong body format | Use `{"records": [{"cells": {...}}]}` not `{"fieldValues": {...}}` |
| Column creation 400: "Missing data type settings" | Text column missing typeSettings | Always include `"typeSettings": {"dataTypeSettings": {"type": "text"}}` for text columns |
| Run rejected: "Field runRecords - Required" | Missing runRecords | Always include `"runRecords": {"recordIds": [...]}` or `{"viewId": ...}` |
| `ERROR_TOO_MANY_RUNS` | Column triggered too many times in short window | Wait ~3 minutes, then retry |
| http-api-v2 queryString/headers broken (chars 0,1,2,3...) | Used `formulaText` with JSON object | Use `formulaMap` with per-key formulas |
| Claygent "Unable to parse output schema" | `answerSchemaType` + `_metadata` missing, or `jsonSchema` single-encoded | Add both inputs with `formulaMap`. `jsonSchema` must be double-encoded: `json.dumps(json.dumps(schema))`. `_metadata` must have `modelSource: '"user"'` (inner quotes). |
| Formula "Error evaluating formula" | Used `.indexOf()`, `.includes()`, `REGEXMATCH()`, or `LOWER()` | Use `/pattern/i.test(String({{f_id}}) \|\| "")` for matching. See Formula Syntax section. |
| Webhook columns blank despite data in source | Extraction columns are plain text, not formulas | PATCH with `formulaText: "{{source_field}}?.key"`, `formulaType: "text"`, `dataTypeSettings: {"type": "text"}` |
| 404 "NoMatchingURL" on `/views/{view_id}/records` | Endpoint does not exist | Use 2-step: `/views/{view_id}/records/ids` then `bulk-fetch-records` |
| `bulk-fetch-records` 400 error | Empty or missing `recordIds` | Always pass a non-empty `recordIds` array |
| Enrich Company `ERROR_INVALID_INPUT` | Company name used instead of LinkedIn URL | Use LinkedIn company URL as `company_identifier` input |
| `mappedResultPath` formula returns empty | Missing `mappedResultPath` array for nested data | Add `"mappedResultPath": ["experience", "0", "url"]` to typeSettings |
| `POST /sources` returns "Invalid subscriptions" | Wrong endpoint for people/company sources | Use `POST /sources/create-cpj-table` instead |

---

## LinkedIn Posts (social-posts action)

```python
{
    "type": "action",
    "name": "LinkedIn Posts",
    "typeSettings": {
        "actionKey": "social-posts-get-post-activity-posts-and-shares",
        "actionPackageId": "b210a16b-cdaf-4cbd-ad9b-42d762cd165f",
        "dataTypeSettings": {"type": "text"},
        "inputsBinding": [
            # ⚠️ Input name is "socialUrl" — NOT linkedin_url
            {"name": "socialUrl", "formulaText": ref(f_linkedin_url)},
            {"name": "num_posts", "formulaText": '"10"'}   # string, not number
        ]
    }
}
```

---

## Conditional Execution ("Only run if")

Add `conditionalRunFormulaText` to `typeSettings` to gate column execution:

```python
{
    "type": "action",
    "name": "Enrich Company",
    "typeSettings": {
        "actionKey": "enrich-company-with-mixrank-v2",
        # ... other settings ...
        "conditionalRunFormulaText": "Number({{f_employees_id}}) > 5"
    }
}
# When condition not met, cell status is ERROR_RUN_CONDITION_NOT_MET
```

---

## AI Columns — API Read Behavior

When reading AI column values via `bulk-fetch-records`, the API returns:
```json
{"value": "Response", "metadata": {"isPreview": true, "status": "SUCCESS"}}
```
The actual parsed JSON is stored internally. Formula extractors (`?.key`) CAN access the parsed JSON from AI columns even though the API shows just `"Response"`.

---

## runRecords: recordIds vs viewId

Always prefer `recordIds` when you have them:
```python
# ✅ Reliable — explicit record IDs
{"runRecords": {"recordIds": ["r_xxx", "r_yyy"]}}

# ⚠️ Less reliable — depends on view's UI settings (row limit, filters)
{"runRecords": {"viewId": "v_xxx"}}
```

---

## create-cpj-table — "Find People" / "Find Companies" Source Tables

`POST /sources/create-cpj-table` creates source tables for Clay's people/company search.
Regular `POST /sources` returns 404 "Invalid subscriptions" for these source types.

```python
r = clay.session.post(
    "https://api.clay.com/v3/sources/create-cpj-table",
    json={
        "cpjConfig": {
            "type": "people",   # or "companies"
            "typeSettings": {
                "inputs": {
                    # filters, company_identifier URLs, company_record_id list
                }
            },
            "basicFields": [...]   # auto-created formula columns using {{source}}.field_name
        },
        "tableName": "Find People - My Search",
        "workbookId": "wb_xxx"   # optional — creates new workbook if omitted
    }
)
# Response: {"tableId": "t_xxx", "viewId": "v_xxx", "workbookId": "wb_xxx",
#            "sourceId": "src_xxx", "isNewTable": true}
# Triggers search automatically on creation
```

---

## Webhook Source Tables — Extraction Columns

When you create a table with a webhook source, Clay creates a source column that stores the full JSON payload. The individual data columns (name, headline, etc.) are **NOT automatically populated** — you must create formula extractors.

**Common mistake:** Creating columns like "name", "headline" as plain text. They show up in the UI with the right names but contain NO data. All downstream columns see blanks.

```python
# After creating a webhook source table, PATCH each data column to extract from source:
raw = clay.get_table(TABLE_ID)
source_field_id = None
for f in raw['table']['fields']:
    if f['type'] == 'source':
        source_field_id = f['id']
        break

# For each extraction column:
for field_id, json_key in extraction_columns.items():
    clay.session.patch(f"{BASE}/tables/{TABLE_ID}/fields/{field_id}", json={
        "typeSettings": {
            "formulaText": f'{{{{{source_field_id}}}}}?.{json_key}',
            "formulaType": "text",
            "dataTypeSettings": {"type": "text"}    # REQUIRED for PATCH
        }
    })
    time.sleep(0.15)
```

---

## Verification (MANDATORY after every create/patch)

**Never trust a 200 status.** Clay accepts broken configs silently. After creating or patching any column:

```python
# 1. GET the column back and verify config
raw = clay.get_table(TABLE_ID)
for f in raw['table']['fields']:
    if f['id'] == field_id:
        ts = f.get('typeSettings', {})
        inputs = ts.get('inputsBinding', [])
        input_names = [i.get('name') for i in inputs]

        # For AI columns: verify answerSchemaType exists and is double-encoded
        for inp in inputs:
            if inp.get('name') == 'answerSchemaType' and 'formulaMap' in inp:
                js = inp['formulaMap'].get('jsonSchema', '')
                parsed = json.loads(js)
                assert isinstance(parsed, str), f"jsonSchema is {type(parsed)} — needs double encoding"
```

---

## Reference Files

> This repo contains the API reference and Python client only. Column definition JSON examples can be found in `clay-api-reference.md` inline. Build your own table schemas by adapting the patterns documented in the sections above.

---
