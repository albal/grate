#!/usr/bin/env python3
"""List Gemini API models sorted by requests-per-day (RPD), highest last.

Model list comes from the Gemini API (models.list); daily limits come from
your own project's quotas via the Cloud Quotas API.

Setup:
    pip install requests google-auth
    gcloud auth application-default login
    gcloud services enable cloudquotas.googleapis.com --project <id>

Usage:
    python gemini_rpd.py --project <id> [--tier free|paid|all] [--all-models]
    python gemini_rpd.py --project <id> --dump-quotas
"""

import argparse
import os
import sys
import warnings

import google.auth
import google.auth.exceptions
import google.auth.transport.requests
import requests

MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
QUOTAS_URL = (
    "https://cloudquotas.googleapis.com/v1/projects/{project}/locations/global/"
    "services/generativelanguage.googleapis.com/quotaInfos"
)
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
UNLIMITED = float("inf")


def get_credentials(project_arg):
    # Requests send x-goog-user-project explicitly, so ADC's quota-project warning is noise.
    warnings.filterwarnings("ignore", message="Your application has authenticated using end user credentials")
    try:
        creds, adc_project = google.auth.default(scopes=SCOPES)
        creds.refresh(google.auth.transport.requests.Request())
    except google.auth.exceptions.GoogleAuthError as e:
        sys.exit(f"Auth failed: {e}\nRun: gcloud auth application-default login")
    project = project_arg or os.environ.get("GOOGLE_CLOUD_PROJECT") or adc_project
    if not project:
        sys.exit("No project ID. Pass --project or set GOOGLE_CLOUD_PROJECT.")
    return creds.token, project


def paged_get(url, key, params=None, headers=None):
    params = dict(params or {})
    while True:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        if not r.ok:
            hint = ""
            if "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in r.text and url == MODELS_URL:
                hint = ("\nHint: set GEMINI_API_KEY, or re-login with the Gemini scope:\n"
                        "  gcloud auth application-default login --scopes="
                        "https://www.googleapis.com/auth/cloud-platform,"
                        "https://www.googleapis.com/auth/generative-language.retriever")
            sys.exit(f"GET {url} failed ({r.status_code}): {r.text[:500]}{hint}")
        data = r.json()
        yield from data.get(key, [])
        token = data.get("nextPageToken")
        if not token:
            return
        params["pageToken"] = token


def fetch_models(token, project, all_models):
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    params = {"pageSize": 1000}
    if api_key:
        params["key"] = api_key
        headers = None
    else:
        headers = {"Authorization": f"Bearer {token}", "x-goog-user-project": project}

    models = []
    for m in paged_get(MODELS_URL, "models", params, headers):
        methods = m.get("supportedGenerationMethods", [])
        if not all_models and "generateContent" not in methods:
            continue
        models.append({
            "id": m["name"].removeprefix("models/"),
            "display": m.get("displayName", ""),
        })
    return models


def fetch_quota_infos(token, project):
    headers = {"Authorization": f"Bearer {token}", "x-goog-user-project": project}
    return list(paged_get(QUOTAS_URL.format(project=project), "quotaInfos",
                          {"pageSize": 1000}, headers))


def is_daily_request_quota(q):
    if q.get("refreshInterval") != "day":
        return False
    text = (q.get("metric", "") + " " + q.get("quotaId", "")).lower()
    if "token" in text or "embed" in text:
        return False
    return "request" in text and ("generate" in text or "content" in text)


def tier_of(q):
    return "free" if "freetier" in q.get("quotaId", "").lower() else "paid"


def parse_value(v):
    n = int(v)
    return UNLIMITED if n < 0 else n


def build_limits(quota_infos, tier):
    """Return {tier: {"models": {model: rpd}, "default": rpd|None}}."""
    limits = {}
    for q in quota_infos:
        if not is_daily_request_quota(q):
            continue
        t = tier_of(q)
        if tier != "all" and t != tier:
            continue
        entry = limits.setdefault(t, {"models": {}, "default": None})
        for d in q.get("dimensionsInfos", []):
            value = d.get("details", {}).get("value")
            if value is None:
                continue
            rpd = parse_value(value)
            model = d.get("dimensions", {}).get("model")
            if model:
                prev = entry["models"].get(model)
                entry["models"][model] = rpd if prev is None else min(prev, rpd)
            else:
                prev = entry["default"]
                entry["default"] = rpd if prev is None else min(prev, rpd)
    return limits


def format_rpd(rpd):
    if rpd is None:
        return "n/a"
    if rpd == UNLIMITED:
        return "unlimited"
    return f"{rpd:,}"


def sort_key(row):
    rpd = row["rpd"]
    # n/a first, then ascending, unlimited last -> most queries at the end.
    return (-1 if rpd is None else rpd, row["id"], row["tier"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", help="GCP project ID (default: GOOGLE_CLOUD_PROJECT or ADC project)")
    ap.add_argument("--tier", choices=["free", "paid", "all"], default="all")
    ap.add_argument("--all-models", action="store_true",
                    help="include models that don't support generateContent")
    ap.add_argument("--dump-quotas", action="store_true",
                    help="print the project's daily quotas and exit")
    args = ap.parse_args()

    token, project = get_credentials(args.project)
    quota_infos = fetch_quota_infos(token, project)

    if args.dump_quotas:
        for q in quota_infos:
            if q.get("refreshInterval") != "day":
                continue
            mark = "*" if is_daily_request_quota(q) else " "
            print(f"{mark} {q.get('quotaId')}  metric={q.get('metric')}")
            for d in q.get("dimensionsInfos", []):
                print(f"      {d.get('dimensions', {})} -> {d.get('details', {}).get('value')}")
        print("\n* = counted as a requests-per-day quota")
        return

    models = fetch_models(token, project, args.all_models)
    limits = build_limits(quota_infos, args.tier)
    tiers = sorted(limits) or [args.tier if args.tier != "all" else "-"]

    rows = []
    for m in models:
        for t in tiers:
            entry = limits.get(t, {"models": {}, "default": None})
            rpd = entry["models"].get(m["id"], entry["default"])
            rows.append({**m, "tier": t, "rpd": rpd})
    rows.sort(key=sort_key)

    show_tier = args.tier == "all"
    header = ["RPD"] + (["TIER"] if show_tier else []) + ["MODEL", "DISPLAY NAME"]
    table = [[format_rpd(r["rpd"])] + ([r["tier"]] if show_tier else []) + [r["id"], r["display"]]
             for r in rows]
    widths = [max(len(str(c)) for c in col) for col in zip(header, *table)]
    for i, line in enumerate([header] + table):
        cells = [line[0].rjust(widths[0])] + [c.ljust(w) for c, w in zip(line[1:], widths[1:])]
        print("  ".join(cells).rstrip())
        if i == 0:
            print("  ".join("-" * w for w in widths))


if __name__ == "__main__":
    main()
