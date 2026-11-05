#!/usr/bin/env python3
"""Refresh published draws; validate sources, preserve historical consistency."""
import datetime as dt
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/history.json"
BASE = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
MIRROR = "https://raw.githubusercontent.com/yangxb919/lottery-data/main/data/dlt.json"

def read_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Cache-Control": "no-cache"})
    error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Source unavailable: {error}")

def valid(d):
    return (isinstance(d, dict) and re.fullmatch(r"\d{5,8}", str(d.get("issue", "")))
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d.get("date", "")))
            and isinstance(d.get("f"), list) and isinstance(d.get("b"), list)
            and len(d["f"]) == 5 and len(d["b"]) == 2
            and len(set(d["f"])) == 5 and len(set(d["b"])) == 2
            and all(type(n) is int and 1 <= n <= 35 for n in d["f"])
            and all(type(n) is int and 1 <= n <= 12 for n in d["b"]))

def official_item(item):
    issue = str(item.get("lotteryDrawNum") or item.get("drawNum") or "")
    nums = [int(n) for n in re.findall(r"\d+", str(item.get("lotteryDrawResult") or item.get("drawResult") or ""))]
    date = str(item.get("lotteryDrawTime") or item.get("drawTime") or "")[:10]
    if len(nums) != 7:
        raise ValueError(f"Invalid official result: {issue}")
    d = {"issue": issue, "date": date, "f": sorted(nums[:5]), "b": sorted(nums[5:])}
    if not valid(d):
        raise ValueError(f"Invalid official draw: {issue}")
    return d

def fetch_official():
    records = []
    for page in range(1, 31):
        query = urllib.parse.urlencode({"gameNo": 85, "provinceId": 0, "pageSize": 100, "pageNo": page, "isVerify": 1, "termLimits": 0})
        data = read_json(BASE + "?" + query)
        value = data.get("value") if isinstance(data, dict) else None
        items = value.get("list") if isinstance(value, dict) else None
        if not isinstance(items, list):
            raise ValueError("Unexpected official response schema")
        records.extend(official_item(item) for item in items)
        if len(items) < 100:
            break
    if not records:
        raise ValueError("Official source returned no draws")
    return records

def fetch_mirror():
    data = read_json(MIRROR + "?t=" + str(int(time.time())))
    if not isinstance(data, list) or not data:
        raise ValueError("Unexpected mirror response schema")
    records = []
    for item in data:
        d = {"issue": str(item["issue"]), "date": str(item["date"]),
             "f": sorted(map(int, item["front"])), "b": sorted(map(int, item["back"]))}
        if not valid(d):
            raise ValueError(f"Invalid mirror draw: {d['issue']}")
        records.append(d)
    return records

def main():
    old = json.loads(OUT.read_text()) if OUT.exists() else {"draws": []}
    records = {d["issue"]: d for d in old["draws"]}
    latest_old = max(records, key=lambda k: int(k)) if records else None
    sources = []
    errors = []
    # Try both sources even if the first succeeds but returns stale results.
    for name, loader in (("official", fetch_official), ("mirror", fetch_mirror)):
        try:
            incoming = loader()
            candidate = dict(records)
            for draw in incoming:
                issue = draw["issue"]
                if issue in candidate and candidate[issue] != draw:
                    raise ValueError(f"Conflicting {name} draw: {issue}")
                candidate[issue] = draw
            records = candidate
            sources.append(name)
            print(name, "returned", len(incoming), "draws; latest", max(incoming, key=lambda d: int(d["issue"]))["issue"])
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            print("Source failed:", errors[-1])
    if not sources:
        raise RuntimeError("All sources failed: " + "; ".join(errors))
    ordered = sorted(records.values(), key=lambda d: (d["date"], int(d["issue"])))
    latest = max(records, key=lambda k: int(k))
    if ordered == old.get("draws"):
        print("No new published draws; latest remains", latest, "; successful sources:", sources)
        return
    OUT.write_text(json.dumps({"source": ", ".join(sources), "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "draws": ordered}, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("Updated", latest_old, "->", latest, "total", len(ordered))

if __name__ == "__main__":
    main()
