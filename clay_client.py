"""
Clay Internal API Client
Authenticates using your existing Chrome session — no login required.

Usage:
    from clay_client import ClayClient
    clay = ClayClient()
    tables = clay.list_tables()
    clay.create_column(table_id, {...})
"""

import copy
import json
import os
import re
import time
import requests
from typing import Any

BASE = "https://api.clay.com/v3"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "x-clay-frontend-version": "v20260227_221530Z_165b5326da",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "referer": "https://app.clay.com/",
    "origin": "https://app.clay.com",
}


class ClayClient:
    def __init__(self, workspace_id: int = None):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._load_cookies()
        me = self.me()
        self.user_id = me["id"]
        self.workspace_id = workspace_id or self._default_workspace()
        print(f"[clay] logged in as {me.get('email')} | workspace {self.workspace_id}")

    def _load_cookies(self):
        session_file = os.path.join(os.path.dirname(__file__), "clay-session.json")
        with open(session_file) as f:
            data = json.load(f)
        self.session.cookies.set("claysession", data["claysession"], domain=".clay.com")

    def _default_workspace(self) -> int:
        res = self.get("/my-workspaces")
        ws = res.get("results", res) if isinstance(res, dict) else res
        return ws[0]["id"]

    def _url(self, path: str) -> str:
        return f"{BASE}{path}"

    def get(self, path: str, **kwargs) -> Any:
        r = self.session.get(self._url(path), **kwargs)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict = None, **kwargs) -> Any:
        r = self.session.post(self._url(path), json=body, **kwargs)
        r.raise_for_status()
        return r.json()

    def patch(self, path: str, body: dict = None, **kwargs) -> Any:
        r = self.session.patch(self._url(path), json=body, **kwargs)
        r.raise_for_status()
        return r.json()

    def delete(self, path: str, **kwargs) -> Any:
        r = self.session.delete(self._url(path), **kwargs)
        r.raise_for_status()
        return r.json()

    # ── Auth ──────────────────────────────────────────────────────────────────

    def me(self) -> dict:
        return self.get("/me")

    # ── Workspaces / Tables ───────────────────────────────────────────────────

    def list_tables(self, folder_id: str = None) -> list[dict]:
        """List all tables in the workspace, optionally filtered by folder."""
        params = {}
        if folder_id:
            params["parentFolderId"] = folder_id
        res = self.get(f"/workspaces/{self.workspace_id}/tables", params=params)
        return res.get("results", res)

    def list_folders(self) -> list[dict]:
        """List top-level folders and resources."""
        body = {"parentResource": None, "filters": {}, "isGlobalSearch": False}
        res = self.post(f"/workspaces/{self.workspace_id}/resources_v2/", body)
        return res.get("resources", [])

    def get_table(self, table_id: str) -> dict:
        return self.get(f"/tables/{table_id}")

    def create_table(self, name: str, workbook_id: str = None) -> dict:
        """Create a new workbook + table. Returns the table dict."""
        if not workbook_id:
            wb = self.post("/workbooks", {
                "name": name,
                "workspaceId": self.workspace_id,
                "settings": {"isAutoRun": True},
            })
            workbook_id = wb["id"]

        res = self.post("/tables", {
            "icon": {"emoji": "🪄"},
            "workspaceId": str(self.workspace_id),
            "type": "spreadsheet",
            "template": "basic",
            "workbookId": workbook_id,
            "callerName": "clay-client",
            "sourceSettings": {},
        })
        table = res["table"]
        table["workbookId"] = workbook_id
        return table

    # ── Fields (Columns) ──────────────────────────────────────────────────────

    def get_schema(self, table_id: str, view_id: str) -> dict:
        """Get table schema including all field definitions."""
        return self.get(f"/tables/{table_id}/views/{view_id}/table-schema-v2")

    def create_column(self, table_id: str, column_def: dict, view_id: str = None) -> dict:
        """
        Add a column to a table.
        column_def matches the Clay JSON schema format from clay-api-reference.md.

        Examples:
            # Text column
            {"type": "text", "name": "Company Name"}

            # Formula column
            {"type": "formula", "name": "Email",
             "typeSettings": {"formulaText": "{{f_abc123}}?.email", "dataTypeSettings": {"type": "email"}}}

            # Action column (enrichment)
            {"type": "action", "name": "Find Work Email",
             "typeSettings": {
               "actionKey": "leadmagic-find-work-email",
               "actionPackageId": "edb58209-a62d-42be-992a-e41b87eeacc2",
               "inputsBinding": [...],
               "authAccountId": "aa_..."
             }}
        """
        body = dict(column_def)
        if view_id:
            body["activeViewId"] = view_id
        res = self.post(f"/tables/{table_id}/fields", body)
        return res.get("field", res)

    def update_column(self, table_id: str, field_id: str, updates: dict) -> dict:
        """Rename or update a column's settings."""
        return self.patch(f"/tables/{table_id}/fields/{field_id}", updates)

    def generate_formula(self, table_id: str, prompt: str, column_name_map: dict = None) -> dict:
        """Ask Clay's AI to generate a formula from a natural language prompt."""
        body = {
            "id": self.user_id,
            "workspaceId": str(self.workspace_id),
            "userPromptInput": prompt,
            "userProvidedCorrectedExamples": [],
            "columnNamesToIds": column_name_map or {},
            "mode": "basic",
            "rawExampleTableData": [],
            "formattedExampleTableData": [],
        }
        return self.post("/ai-generation/formula", body)

    # ── Export ───────────────────────────────────────────────────────────────

    def export_csv(self, table_id: str, view_id: str = None,
                   poll_interval: float = 2.0, timeout: int = 300) -> str:
        """
        Export a table (or view) as CSV and return the S3 download URL.

        Native CSV export: action ("Response") columns export as the literal
        string "Response" — NOT the full enrichment JSON. To get full data,
        either add formula columns (JSON.stringify({{field_id}})) or use
        fetch_all_records_full() instead.

        If view_id is given, only view-filtered rows are exported.
        If view_id is omitted, ALL table rows are exported (ignores filters).

        Returns the signed S3 download URL (valid 24h).
        """
        url = f"/tables/{table_id}/views/{view_id}/export" if view_id else f"/tables/{table_id}/export"
        r = self.session.post(f"https://api.clay.com/v3{url}")
        r.raise_for_status()
        job = r.json()
        job_id = job["id"]
        total = job.get("totalRecordsInViewCount", "?")
        print(f"[clay] export job {job_id} | {total} records")

        start = time.time()
        while time.time() - start < timeout:
            time.sleep(poll_interval)
            sr = self.session.get(f"https://api.clay.com/v3/exports/{job_id}")
            sr.raise_for_status()
            data = sr.json()
            status = data.get("status")
            exported = data.get("recordsExportedCount", 0)
            if status == "FINISHED":
                print(f"[clay] export done — {exported}/{total} rows")
                return data["downloadUrl"]
            elif status == "FAILED":
                raise RuntimeError(f"Export job failed: {data}")

        raise TimeoutError(f"Export job {job_id} did not finish within {timeout}s")

    def fetch_all_records_full(self, table_id: str, view_id: str,
                               field_id: str, workers: int = 20) -> list[dict]:
        """
        Fetch the full externalContent.fullValue for an action column across
        ALL records in a view — in parallel.

        Use this when you need the raw enrichment JSON that native CSV export
        omits (action columns export as "Response" only).

        Returns list of {record_id, value} dicts. ~27ms/record with 20 workers.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        record_ids = self.get_record_ids(table_id, view_id)
        print(f"[clay] fetching full values for {len(record_ids)} records ({workers} workers)...")

        def fetch_one(rec_id):
            r = self.session.get(f"https://api.clay.com/v3/tables/{table_id}/records/{rec_id}")
            r.raise_for_status()
            cell = r.json().get("cells", {}).get(field_id, {})
            return {
                "record_id": rec_id,
                "value": cell.get("externalContent", {}).get("fullValue"),
                "status": cell.get("metadata", {}).get("status"),
            }

        results = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(fetch_one, rid): rid for rid in record_ids}
            for f in as_completed(futures):
                results.append(f.result())

        print(f"[clay] done — {len(results)} records fetched")
        return results

    # ── Records ───────────────────────────────────────────────────────────────

    def get_record_ids(self, table_id: str, view_id: str) -> list[str]:
        """
        List ALL record IDs in a table via its view.
        This is the correct endpoint — NOT /views/{id}/records (which 404s).
        Filters out the "search" placeholder entry.
        """
        res = self.get(f"/tables/{table_id}/views/{view_id}/records/ids")
        ids = res.get("results", [])
        return [rid for rid in ids if rid != "search"]

    def list_records(self, table_id: str, view_id: str, field_ids: list[str] = None) -> list[dict]:
        """
        List ALL records in a table with their cell data.
        Two-step: get IDs, then bulk-fetch.
        Optionally filter to specific field_ids for performance.
        """
        record_ids = self.get_record_ids(table_id, view_id)
        if not record_ids:
            return []
        body = {"recordIds": record_ids}
        if field_ids:
            body["fieldIds"] = field_ids
        res = self.post(f"/tables/{table_id}/bulk-fetch-records", body)
        return res.get("results", [])

    def get_records(self, table_id: str, record_ids: list[str], field_ids: list[str] = None) -> list[dict]:
        """Fetch specific records by ID. Optionally filter to specific fields."""
        body = {"recordIds": record_ids}
        if field_ids:
            body["fieldIds"] = field_ids
        res = self.post(f"/tables/{table_id}/bulk-fetch-records", body)
        return res.get("results", [])

    def create_records(self, table_id: str, cells_list: list[dict]) -> list[dict]:
        """
        Create records in a table.
        cells_list: list of {field_id: value} dicts.
        Returns list of record dicts.
        """
        records = [{"cells": cells} for cells in cells_list]
        res = self.post(f"/tables/{table_id}/records", {"records": records})
        return res.get("records", [])

    def update_record(self, table_id: str, record_id: str, field_values: dict) -> dict:
        """Set cell values. field_values = {field_id: value}"""
        return self.patch(f"/tables/{table_id}/records/{record_id}", field_values)

    def delete_records(self, table_id: str, record_ids: list[str]) -> dict:
        """Delete specific records by ID."""
        r = self.session.delete(self._url(f"/tables/{table_id}/records"), json={"recordIds": record_ids})
        r.raise_for_status()
        return r.json()

    # ── Fields (delete) ────────────────────────────────────────────────────────

    def delete_column(self, table_id: str, field_id: str) -> dict:
        """Delete a column from a table."""
        return self.delete(f"/tables/{table_id}/fields/{field_id}")

    # ── Running ───────────────────────────────────────────────────────────────

    def run_column(self, table_id: str, field_ids: list[str],
                   record_ids: list[str] = None, view_id: str = None) -> dict:
        """
        Trigger enrichment run for specific columns.
        Prefer record_ids over view_id — viewId depends on UI row limits.
        """
        body = {"fieldIds": field_ids, "callerName": "clay-client"}
        if record_ids:
            body["runRecords"] = {"recordIds": record_ids}
        elif view_id:
            body["runRecords"] = {"viewId": view_id}
        return self.patch(f"/tables/{table_id}/run", body)

    def run_and_wait(self, table_id: str, field_ids: list[str],
                     record_ids: list[str], timeout: int = 120, poll: int = 5) -> list[dict]:
        """Run columns on records and poll until done or timeout."""
        self.run_column(table_id, field_ids, record_ids=record_ids)
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(poll)
            records = self.get_records(table_id, record_ids)
            all_done = True
            for rec in records:
                for fid in field_ids:
                    cell = rec.get("cells", {}).get(fid, {})
                    status = cell.get("metadata", {}).get("status", "")
                    if status in ("QUEUED", "RUNNING", "PENDING", ""):
                        if not cell.get("value") and status != "ERROR":
                            all_done = False
                            break
                if not all_done:
                    break
            if all_done:
                return records
        return self.get_records(table_id, record_ids)

    # ── Column helpers ────────────────────────────────────────────────────────

    def create_action_column(self, table_id: str, name: str,
                             action_key: str, package_id: str,
                             inputs: dict[str, str],
                             view_id: str = None,
                             auth_account_id: str = None,
                             condition: str = None) -> dict:
        """
        Create an action column (enrichment, AI, HTTP API).

        inputs: {input_name: formula_text} e.g. {"person_identifier": "{{f_xxx}}"}
        condition: optional "Only run if" formula (conditionalRunFormulaText)

        Common action_key / package_id combos:
          enrich-person-with-mixrank-v2     / e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2
          enrich-company-with-mixrank-v2    / e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2
          use-ai                            / 67ba01e9-1898-4e7d-afe7-7ebe24819a57
          http-api-v2                       / 4299091f-3cd3-4d68-b198-0143575f471d
        """
        inputs_binding = [{"name": k, "formulaText": v} if v else {"name": k}
                          for k, v in inputs.items()]
        ts = {
            "dataTypeSettings": {"type": "json"},
            "actionKey": action_key,
            "actionVersion": 1,
            "actionPackageId": package_id,
            "inputsBinding": inputs_binding,
        }
        if auth_account_id:
            ts["authAccountId"] = auth_account_id
        if condition:
            ts["conditionalRunFormulaText"] = condition

        return self.create_column(table_id, {
            "type": "action", "name": name, "typeSettings": ts
        }, view_id=view_id)

    def create_formula_column(self, table_id: str, name: str,
                              formula_text: str, view_id: str = None,
                              data_type: str = "text",
                              mapped_result_path: list[str] = None) -> dict:
        """
        Create a formula column using the create-as-text-then-PATCH pattern.

        mapped_result_path: required for nested enrichment data.
          e.g. ["experience", "0", "url"] to extract company LinkedIn URL
          from Enrich Person > experience > 0 > url.
          Without this, nested paths return empty even with the correct formula.
        """
        # Step 1: create as text
        field = self.create_column(table_id, {
            "type": "text",
            "name": name,
            "typeSettings": {"dataTypeSettings": {"type": data_type}},
        }, view_id=view_id)
        field_id = (field.get("field") or field).get("id") or field.get("id")

        # Step 2: PATCH with formula
        patch_ts = {
            "formulaText": formula_text,
            "formulaType": "text",
            "dataTypeSettings": {"type": data_type},
        }
        if mapped_result_path:
            patch_ts["mappedResultPath"] = mapped_result_path
            patch_ts["formula"] = formula_text

        self.update_column(table_id, field_id, {"typeSettings": patch_ts})
        return {"id": field_id, "name": name}

    def set_condition(self, table_id: str, field_id: str, condition: str) -> dict:
        """
        Set "Only run if" condition on an action column.
        condition: formula expression, e.g. 'Number({{f_employees}}) > 5'
        """
        raw = self.get_table(table_id)
        table = raw.get("table", raw)
        for f in table.get("fields", []):
            if f["id"] == field_id:
                ts = f.get("typeSettings", {})
                ts["conditionalRunFormulaText"] = condition
                return self.update_column(table_id, field_id, {"typeSettings": ts})
        raise ValueError(f"Field {field_id} not found in table {table_id}")

    # ── Sources ────────────────────────────────────────────────────────────────

    def create_webhook_source(self, table_id: str, name: str = "Webhook") -> dict:
        """Create a webhook source on a table. Returns source dict with webhook URL."""
        res = self.post("/sources", {
            "workspaceId": int(self.workspace_id),
            "tableId": table_id,
            "name": name,
            "type": "webhook",
            "typeSettings": {},
        })
        source = res.get("source", res)
        return source

    # ── Enrichments / Actions ─────────────────────────────────────────────────

    def search_enrichments(self, query: str) -> list[dict]:
        """Search available enrichment actions by keyword."""
        body = {
            "userQuery": query,
            "types": ["action", "waterfall", "template", "source_action"],
        }
        res = self.post(f"/enrichment-search/{self.workspace_id}/query", body)
        return res.get("results", [])

    def list_actions(self) -> list[dict]:
        return self.get("/actions")

    def list_auth_accounts(self) -> list[dict]:
        """List all connected integration accounts (OpenAI, LeadMagic, etc.)"""
        res = self.get(f"/workspaces/{self.workspace_id}/app-accounts")
        return res if isinstance(res, list) else res.get("accounts", [])

    def list_subroutines(self) -> list[dict]:
        res = self.get(f"/workspaces/{self.workspace_id}/subroutines")
        return res.get("subroutines", res)

    # ── Portable Schema (ClayMate format) ─────────────────────────────────────

    def export_schema(self, table_id: str, column_names: list[str] = None) -> dict:
        """
        Export a table as a portable ClayMate-compatible schema.
        Field IDs are converted to {{@Column Name}} references.
        Optionally filter to specific column_names.
        """
        raw = self.get_table(table_id)
        table = raw.get("table", raw)
        fields = table.get("fields", [])

        # Determine view-based field order
        grid_views = table.get("gridViews", [])
        view = grid_views[0] if grid_views else None
        view_order = view.get("fieldOrder", []) if view else []
        ordered_ids = view_order if view_order else [f["id"] for f in fields]

        # Build ordered field list (skip system fields)
        skip = {"f_created_at", "f_updated_at"}
        ordered_fields = []
        for fid in ordered_ids:
            if fid in skip:
                continue
            fd = next((f for f in fields if f["id"] == fid), None)
            if fd:
                ordered_fields.append(fd)

        # Filter to selected columns if specified
        if column_names:
            names_set = set(column_names)
            # Include dependencies too
            id_to_name = {f["id"]: f["name"] for f in ordered_fields}
            selected = [f for f in ordered_fields if f["name"] in names_set]
            # Also include any column referenced by selected columns
            for f in selected:
                ts_str = json.dumps(f.get("typeSettings", {}))
                for ref_id in re.findall(r"\{\{(f_[a-zA-Z0-9_]+)\}\}", ts_str):
                    dep_name = id_to_name.get(ref_id)
                    if dep_name:
                        names_set.add(dep_name)
            ordered_fields = [f for f in ordered_fields if f["name"] in names_set]

        # Build ID → name maps
        id_to_name = {f["id"]: f["name"] for f in ordered_fields}
        field_order = [f["id"] for f in ordered_fields]

        # Fetch source details for source columns
        for field in ordered_fields:
            if field.get("type") == "source":
                source_ids = (field.get("typeSettings") or {}).get("sourceIds", [])
                if source_ids:
                    try:
                        field["_sourceDetails"] = [
                            self.get(f"/sources/{sid}") for sid in source_ids
                        ]
                    except Exception:
                        pass

        # Build source data ref map
        source_data_ref_to_name = {}
        for f in ordered_fields:
            for sd in f.get("_sourceDetails", []):
                if sd.get("dataFieldId"):
                    source_data_ref_to_name[sd["dataFieldId"]] = f["name"]

        # Convert to portable format
        columns = []
        for idx, field in enumerate(ordered_fields):
            col = {
                "index": idx,
                "name": field["name"],
                "type": field["type"],
            }
            if field.get("typeSettings"):
                col["typeSettings"] = _refs_to_names(
                    copy.deepcopy(field["typeSettings"]),
                    id_to_name, source_data_ref_to_name,
                )
            if field.get("_sourceDetails"):
                col["sourceDetails"] = [
                    {
                        "name": sd["name"],
                        "type": sd.get("type", "webhook"),
                        "dataFieldId": sd.get("dataFieldId"),
                        "typeSettings": _refs_to_names(
                            copy.deepcopy(sd.get("typeSettings", {})),
                            id_to_name, source_data_ref_to_name,
                        ),
                    }
                    for sd in field["_sourceDetails"]
                ]
            columns.append(col)

        schema = {
            "version": "1.0",
            "exportedAt": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "tableId": table_id,
            "columnCount": len(columns),
            "columns": columns,
        }
        print(f"[clay] exported {len(columns)} columns from {table_id}")
        return schema

    def import_schema(self, table_id: str, schema: dict, dry_run: bool = False) -> list[dict]:
        """
        Import a portable ClayMate schema into a table.
        Resolves {{@Column Name}} refs to real field IDs.
        Creates columns in dependency order. Returns list of results.
        """
        raw = self.get_table(table_id)
        table = raw.get("table", raw)
        existing = table.get("fields", [])
        views = table.get("gridViews", table.get("views", []))
        view_id = views[0]["id"] if views else table.get("firstViewId")

        # Name → ID map (existing columns)
        name_to_id = {f["name"]: f["id"] for f in existing}
        source_name_to_data_ref = {}

        columns = schema.get("columns", [])
        sorted_cols = _sort_by_deps(columns)

        if dry_run:
            print(f"[clay] DRY RUN — would create {len(sorted_cols)} columns:")
            for c in sorted_cols:
                deps = _extract_deps(c.get("typeSettings"))
                dep_str = f" (depends on: {', '.join(deps)})" if deps else ""
                print(f"  {c['type']:8s} | {c['name']}{dep_str}")
            return []

        results = []
        print(f"[clay] importing {len(sorted_cols)} columns into {table_id}...")

        for col in sorted_cols:
            col_type = col.get("type", "text")
            try:
                if col_type == "source" and col.get("sourceDetails"):
                    created_source_ids = []
                    for sd in col["sourceDetails"]:
                        ts = _names_to_refs(
                            copy.deepcopy(sd.get("typeSettings", {})),
                            name_to_id, source_name_to_data_ref,
                        )
                        src = self.post("/sources", {
                            "workspaceId": int(self.workspace_id),
                            "tableId": table_id,
                            "name": sd["name"],
                            "type": sd.get("type", "v3-action"),
                            "typeSettings": ts,
                        })
                        sid = src.get("id") or (src.get("source") or {}).get("id")
                        if sid:
                            created_source_ids.append(sid)
                            dfid = src.get("dataFieldId") or (src.get("source") or {}).get("dataFieldId")
                            if not dfid:
                                try:
                                    dfid = self.get(f"/sources/{sid}").get("dataFieldId")
                                except Exception:
                                    pass
                            if dfid:
                                source_name_to_data_ref[col["name"]] = dfid
                        time.sleep(0.15)

                    if not created_source_ids:
                        raise Exception("No sources created")

                    result = self._create_field(table_id, view_id, {
                        "name": col["name"],
                        "type": "source",
                        "typeSettings": {
                            "sourceIds": created_source_ids,
                            "canCreateRecords": (col.get("typeSettings") or {}).get("canCreateRecords", True),
                        },
                    })
                else:
                    ts = None
                    if col.get("typeSettings"):
                        ts = _names_to_refs(
                            copy.deepcopy(col["typeSettings"]),
                            name_to_id, source_name_to_data_ref,
                        )

                    field_def = {"name": col["name"], "type": col_type}
                    if ts:
                        field_def["typeSettings"] = ts

                    # Text columns need dataTypeSettings
                    if col_type == "text":
                        field_def.setdefault("typeSettings", {})
                        field_def["typeSettings"].setdefault("dataTypeSettings", {"type": "text"})

                    # Formula columns: create as text, then PATCH formulaText
                    if col_type == "formula" and ts and ts.get("formulaText"):
                        formula_ts = ts
                        field_def["type"] = "text"
                        field_def["typeSettings"] = {"dataTypeSettings": ts.get("dataTypeSettings", {"type": "text"})}
                        result = self._create_field(table_id, view_id, field_def)
                        fid = (result.get("field") or result).get("id")
                        if fid:
                            self.patch(f"/tables/{table_id}/fields/{fid}", {"typeSettings": formula_ts})
                    elif col_type == "action" and ts:
                        ts.setdefault("dataTypeSettings", {"type": "text"})
                        field_def["typeSettings"] = ts
                        result = self._create_field(table_id, view_id, field_def)
                    else:
                        result = self._create_field(table_id, view_id, field_def)

                fid = (result.get("field") or result).get("id")
                if fid:
                    name_to_id[col["name"]] = fid
                results.append({"success": True, "name": col["name"]})
                print(f"  [ok] {col['name']}")

            except Exception as e:
                results.append({"success": False, "name": col["name"], "error": str(e)})
                print(f"  [FAIL] {col['name']}: {e}")

            time.sleep(0.15)

        ok = sum(1 for r in results if r["success"])
        fail = sum(1 for r in results if not r["success"])
        print(f"[clay] done: {ok} created, {fail} failed")
        return results

    def _create_field(self, table_id: str, view_id: str, field_def: dict) -> dict:
        """Internal: create field with view context."""
        body = {**field_def, "activeViewId": view_id}
        return self.post(f"/tables/{table_id}/fields", body)


# ── Portable schema helpers ──────────────────────────────────────────────────

_FIELD_RE = re.compile(r"\{\{(f_[a-zA-Z0-9_]+)\}\}")
_NAME_RE = re.compile(r"\{\{@([^}]+)\}\}")
_SOURCE_RE = re.compile(r"\{\{@source:([^}]+)\}\}")


def _refs_to_names(obj, id_to_name: dict, source_ref_to_name: dict = None):
    """Convert {{f_xxx}} → {{@Column Name}} in any nested structure."""
    if source_ref_to_name is None:
        source_ref_to_name = {}
    if isinstance(obj, str):
        def replace(m):
            fid = m.group(1)
            name = id_to_name.get(fid)
            if name:
                return "{{@" + name + "}}"
            sname = source_ref_to_name.get(fid)
            if sname:
                return "{{@source:" + sname + "}}"
            return m.group(0)
        return _FIELD_RE.sub(replace, obj)
    if isinstance(obj, list):
        return [_refs_to_names(item, id_to_name, source_ref_to_name) for item in obj]
    if isinstance(obj, dict):
        return {k: _refs_to_names(v, id_to_name, source_ref_to_name) for k, v in obj.items()}
    return obj


def _names_to_refs(obj, name_to_id: dict, source_name_to_ref: dict = None):
    """Convert {{@Column Name}} → {{f_xxx}} in any nested structure."""
    if source_name_to_ref is None:
        source_name_to_ref = {}
    if isinstance(obj, str):
        result = _SOURCE_RE.sub(
            lambda m: "{{" + source_name_to_ref.get(m.group(1), m.group(0)) + "}}"
            if m.group(1) in source_name_to_ref else m.group(0),
            obj,
        )
        result = _NAME_RE.sub(
            lambda m: "{{" + name_to_id[m.group(1)] + "}}"
            if m.group(1) in name_to_id else m.group(0),
            result,
        )
        return result
    if isinstance(obj, list):
        return [_names_to_refs(item, name_to_id, source_name_to_ref) for item in obj]
    if isinstance(obj, dict):
        return {k: _names_to_refs(v, name_to_id, source_name_to_ref) for k, v in obj.items()}
    return obj


def _extract_deps(type_settings) -> list[str]:
    """Extract column names referenced via {{@Name}} in typeSettings."""
    if not type_settings:
        return []
    deps = set()
    s = json.dumps(type_settings)
    for m in _SOURCE_RE.finditer(s):
        deps.add(m.group(1))
    for m in _NAME_RE.finditer(s):
        if not m.group(1).startswith("source:"):
            deps.add(m.group(1))
    return list(deps)


def _sort_by_deps(columns: list[dict]) -> list[dict]:
    """Topological sort: sources first, then by dependency order."""
    by_name = {c["name"]: c for c in columns}
    dep_map = {c["name"]: _extract_deps(c.get("typeSettings")) for c in columns}

    result = []
    visited = set()
    visiting = set()

    def visit(name):
        if name in visited or name not in by_name:
            return
        if name in visiting:
            return  # cycle — skip
        visiting.add(name)
        for dep in dep_map.get(name, []):
            visit(dep)
        visiting.discard(name)
        visited.add(name)
        result.append(by_name[name])

    # Sources first
    for c in columns:
        if c.get("type") == "source":
            visit(c["name"])
    for c in columns:
        visit(c["name"])

    return result


# ── CLI quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    clay = ClayClient()

    print("\n--- Tables ---")
    tables = clay.list_tables()
    for t in tables[:10]:
        rtype = t.get("resourceType", "")
        name = t.get("name", "?")
        rid = t.get("id", "")
        print(f"  [{rtype}] {name} ({rid})")

    print("\n--- Auth Accounts ---")
    accounts = clay.list_auth_accounts()
    if isinstance(accounts, list):
        for a in accounts[:10]:
            print(f"  {a.get('name', a.get('displayName', '?'))} ({a.get('id')})")

    print("\n--- Formula generation test ---")
    # Use a real table id from the list above to test
    tables_only = [t for t in tables if t.get("resourceType") == "TABLE"]
    if tables_only:
        tid = tables_only[0]["id"]
        result = clay.generate_formula(tid, "If company name is empty, output 'Unknown'")
        print(f"  Prompt: 'If company name is empty, output Unknown'")
        print(f"  Formula: {result.get('formula')}")
