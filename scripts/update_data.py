
import csv
import json
import re
from datetime import datetime, timezone
from html import unescape
from io import StringIO
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketWatch/1.0)"}


def get_fred(series_id):
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    r = requests.get(url, params={"id": series_id}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    rows = list(csv.DictReader(StringIO(r.text)))
    valid = []
    for row in rows:
        date = row.get("observation_date") or row.get("DATE")
        value = row.get(series_id)
        if value and value not in (".", ""):
            try:
                valid.append({"date": date, "value": float(value)})
            except (ValueError, TypeError):
                pass
    return latest_pair(valid)


def latest_pair(rows):
    if not rows:
        return {"value": None, "previous": None, "date": None}
    current = rows[-1]
    previous = rows[-2] if len(rows) > 1 else None
    return {
        "value": current["value"],
        "previous": previous["value"] if previous else None,
        "date": current["date"],
    }


def get_yahoo(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    r = requests.get(
        url,
        params={"range": "5d", "interval": "1d"},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quotes = result["indicators"]["quote"][0]["close"]
    rows = []
    for ts, close in zip(timestamps, quotes):
        if close is not None:
            date = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
            rows.append({"date": date, "value": close})
    return latest_pair(rows)


def get_credit_ratio():
    """日経225.jpのページから信用評価損益率らしき数値を抽出する。
    HTMLの構造が変わった場合は取得できないため、誤った数値を出さず空欄にする。
    """
    url = "https://nikkei225jp.com/data/sinyou.php"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    html = unescape(r.text)
    text = re.sub(r"<script\b.*?</script>|<style\b.*?</style>",
                  " ", html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    # ラベル近辺にある「-10.23%」などの値を探す
    patterns = [
        r"信用評価損益率.{0,100}?(-?\d+(?:\.\d+)?)\s*％?",
        r"評価損益率.{0,100}?(-?\d+(?:\.\d+)?)\s*％?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))
            # 通常この指標はパーセントで表記される
            return {
                "value": value,
                "previous": None,
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
    return {"value": None, "previous": None, "date": None}


def safe_fetch(name, func):
    try:
        return func()
    except Exception as exc:
        print(f"取得失敗: {name}: {exc}")
        return {"value": None, "previous": None, "date": None}


def main():
    data = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "credit": safe_fetch("信用評価損益率", get_credit_ratio),
        "dgs10": safe_fetch("米国10年金利", lambda: get_fred("DGS10")),
        "fedfunds": safe_fetch("実効FF金利", lambda: get_fred("FEDFUNDS")),
        "vix": safe_fetch("VIX", lambda: get_yahoo("%5EVIX")),
        "tqqq": safe_fetch("TQQQ", lambda: get_yahoo("TQQQ")),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
