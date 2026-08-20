#!/usr/bin/env python3
"""
Grist Interviews dashboard setup.

Creates (or repairs) the Grist document used by the interview grading stack so
interview results are easy to review:

  - The `Interviews` table (idempotent: created only if missing).
  - A `Dashboard` page containing:
      * a summary table grouped by `Verdict` (count + average score), and
      * a pie chart of the verdict distribution.

The script is idempotent: it queries existing metadata and only issues the
actions needed to reach the desired state, so it is safe to re-run on a
fresh install or on an existing document.

Usage:
    source ../.env   # or export GRIST_BASE_URL / GRIST_API_KEY / GRIST_DOC_ID
    python3 grist_setup_dashboard.py

Requirements: Python 3.8+ standard library only (uses urllib).
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("GRIST_BASE_URL", "http://127.0.0.1:8484").rstrip("/")
API_KEY = os.environ.get("GRIST_API_KEY", "")
DOC_ID = os.environ.get("GRIST_DOC_ID", "")

COLUMNS = [
    ("Student", "Text", "Student name"),
    ("Phone", "Text", "Phone number"),
    ("RunID", "Text", "Workflow run id"),
    ("Score", "Numeric", "Overall score 0-100"),
    ("Verdict", "Text", "pass / review / fail"),
    ("Dimensions", "Text", "JSON of per-dimension scores"),
    ("Strengths", "Text", "JSON array of strengths"),
    ("Improvements", "Text", "JSON array of improvements"),
    ("Transcript", "Text", "Interview transcript"),
]


def _request(method, url, body=None, timeout=60):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise SystemExit(f"HTTP {e.code} {method} {url}\n  {detail}") from e


def _tables_url():
    return f"{BASE_URL}/api/docs/{DOC_ID}/tables"


def _table_records(table_id):
    return _request("GET", f"{_tables_url()}/{table_id}/records")["records"]


def _table_columns(table_id):
    return _request("GET", f"{_tables_url()}/{table_id}/columns")["columns"]


def _col_by_id(table_id, col_id):
    for rec in _table_records(table_id):
        if rec["fields"].get("colId") == col_id:
            return rec
    return None


def _apply(actions):
    _request("POST", f"{BASE_URL}/api/docs/{DOC_ID}/apply", actions)


def ensure_interviews_table():
    """Create the Interviews table with its columns if it doesn't exist."""
    tables = _table_records("_grist_Tables")
    if any(t["fields"].get("tableId") == "Interviews" for t in tables):
        print("Interviews table: exists")
        return

    # AddTable creates the table, and AddColumn sets labels + types.
    _apply([["AddTable", "Interviews", [c[0] for c in COLUMNS]]])
    for col_id, col_type, label in COLUMNS:
        _apply([["AddColumn", "Interviews", col_id, {"type": col_type, "label": label}]])
    print("Interviews table: created")


def col_refs(table_id, col_ids):
    """Map column ids to their record ids (colRef) via the columns API."""
    cols = _table_columns(table_id)
    by_id = {c["id"]: c["fields"]["colRef"] for c in cols}
    missing = [c for c in col_ids if c not in by_id]
    if missing:
        raise SystemExit(f"Missing columns in {table_id}: {missing}")
    return [by_id[c] for c in col_ids]


def ensure_dashboard():
    """Create the Dashboard page + verdict summary table + pie chart if missing."""
    views = {v["fields"].get("name"): v["id"] for v in _table_records("_grist_Views")}

    summary_table = "Interviews_summary_Verdict"
    if summary_table not in {t["fields"].get("tableId") for t in _table_records("_grist_Tables")}:
        # CreateViewSection on a raw-data view of Interviews with Verdict as a
        # group-by column produces the summary table (Grist auto-creates it).
        interviews_view = views.get("Interviews")
        if not interviews_view:
            raise SystemExit("Interviews view not found - create the Interviews table first")
        verdict_ref = col_refs("Interviews", ["Verdict"])[0]
        _apply([["CreateViewSection", interviews_view, 0, "record", [verdict_ref]]])
        print(f"Summary table: created ({summary_table})")
    else:
        print(f"Summary table: exists ({summary_table})")

    summary_cols = {c["id"]: c for c in _table_columns(summary_table)}
    summary_refs = col_refs(summary_table, ["Verdict", "count"])

    # Ensure the average-score aggregation column exists on the summary table.
    avg = summary_cols.get("AvgScore")
    if not avg:
        _apply([[
            "AddColumn", summary_table, "AvgScore", {
                "type": "Numeric",
                "label": "Avg Score",
                "formula": "AVERAGE($group.Score)",
                "summarySourceCol": col_refs("Interviews", ["Score"])[0],
            },
        ]])
        print("AvgScore column: added")
    elif avg["fields"].get("summarySourceCol", 0) == 0:
        _apply([["ModifyColumn", summary_table, "AvgScore",
                 {"summarySourceCol": col_refs("Interviews", ["Score"])[0]}]])
        print("AvgScore column: linked to Score")

    # Dashboard page.
    dashboard_view = views.get("Dashboard")
    if not dashboard_view:
        _apply([["AddView", "Dashboard", "raw_data"]])
        views = {v["fields"].get("name"): v["id"] for v in _table_records("_grist_Views")}
        dashboard_view = views["Dashboard"]
        print("Dashboard page: created")

    sections = _table_records("_grist_Views_section")
    sum_section = next(
        (s for s in sections
         if s["fields"].get("parentId") == dashboard_view
         and s["fields"].get("parentKey") == "record"
         and s["fields"].get("title") == "Results by Verdict"),
        None,
    )
    if not sum_section:
        summary_table_id = next(
            t["id"] for t in _table_records("_grist_Tables")
            if t["fields"].get("tableId") == summary_table)
        _apply([["CreateViewSection", dashboard_view, summary_table_id, "record", summary_refs]])
        sections = _table_records("_grist_Views_section")
        sum_section = next(
            (s for s in sections
             if s["fields"].get("parentId") == dashboard_view
             and s["fields"].get("parentKey") == "record"
             and s["fields"].get("title") == "Results by Verdict"),
            None,
        )
        _apply([["UpdateRecord", "_grist_Views_section", sum_section["id"],
                 {"title": "Results by Verdict"}]])
        print("Dashboard summary section: created")
    else:
        print("Dashboard summary section: exists")

    # Pie chart of the verdict distribution.
    chart_section = next(
        (s for s in _table_records("_grist_Views_section")
         if s["fields"].get("parentId") == dashboard_view
         and s["fields"].get("parentKey") == "chart"),
        None,
    )
    if not chart_section:
        summary_table_id = next(
            t["id"] for t in _table_records("_grist_Tables")
            if t["fields"].get("tableId") == summary_table)
        _apply([["CreateViewSection", dashboard_view, summary_table_id, "chart", summary_refs]])
        chart_section = next(
            (s for s in _table_records("_grist_Views_section")
             if s["fields"].get("parentId") == dashboard_view
             and s["fields"].get("parentKey") == "chart"),
            None,
        )
        _apply([["UpdateRecord", "_grist_Views_section", chart_section["id"], {
            "chartType": "pie",
            "title": "Verdict Distribution",
            "options": json.dumps({"multiseries": False}),
        }]])
        print("Dashboard chart section: created")
    else:
        print("Dashboard chart section: exists")


def main():
    if not API_KEY or not DOC_ID:
        raise SystemExit(
            "Set GRIST_API_KEY and GRIST_DOC_ID (see deploy/interview-stack/README.md)")
    ensure_interviews_table()
    ensure_dashboard()
    print("Done - open the Dashboard page in Grist to review results.")


if __name__ == "__main__":
    sys.exit(main())
