
import csv
import json
import re
from datetime import datetime, timezone
from html import unescape
from io import StringIO
from pathlib import Path

import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; MarketMonitor/1.0)"
})

retry = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)

adapter = HTTPAdapter(max_retries=retry)
SESSION.mount("https://", adapter)
SESSION.mount("http://", adapter)

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
    """日経225.jpの信用評価損益率をテーブルから取得する。"""
    from bs4 import BeautifulSoup

    url = "https://nikkei225jp.com/data/sinyou.php"
    response = SESSION.get(url, timeout=(10, 60))
    response.raise_for_status()
    

    soup = BeautifulSoup(response.text, "html.parser")

    # 信用残データのテーブルを特定
    tbody = soup.select_one("tbody#datatbl")
    if tbody is None:
        raise ValueError("信用データのテーブル tbody#datatbl が見つかりません")

    # ヘッダー以外の先頭行（最新データ）
    rows = tbody.select("tr")
    data_rows = [
        row for row in rows
        if row.select_one("time") is not None
    ]

    if not data_rows:
        raise ValueError("信用評価損益率のデータ行がありません")

    def parse_row(row):
        cells = row.find_all("td", recursive=False)

        # 日付 + 8項目。9列目が信用評価損益率
        if len(cells) < 9:
            raise ValueError("信用データの列数が不足しています")

        date = cells[0].get_text(strip=True)
        raw_value = cells[8].get_text(strip=True)
        raw_value = raw_value.replace("%", "").replace("％", "")

        value = float(raw_value)

        return {"date": date, "value": value}

    latest = parse_row(data_rows[0])
    previous = parse_row(data_rows[1]) if len(data_rows) > 1 else None

    return {
        "value": latest["value"],
        "previous": previous["value"] if previous else None,
        "date": latest["date"],
    }


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
