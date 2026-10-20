import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketMonitor/1.0)"
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

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


def latest_pair(rows):
    """日付順のデータから最新値と前回値を返す。"""
    if not rows:
        raise ValueError("有効なデータがありません")

    rows = sorted(rows, key=lambda row: row["date"])
    current = rows[-1]
    previous = rows[-2] if len(rows) > 1 else None

    return {
        "value": current["value"],
        "previous": previous["value"] if previous else None,
        "date": current["date"],
    }


def get_yahoo(symbol):
    """Yahoo Financeから日足データを取得する。"""
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}"
    )

    response = SESSION.get(
        url,
        params={"range": "5d", "interval": "1d"},
        timeout=(15, 45),
    )
    response.raise_for_status()

    result = response.json()["chart"]["result"]
    if not result:
        raise ValueError(f"{symbol}: Yahoo Financeの結果が空です")

    result = result[0]
    timestamps = result.get("timestamp", [])
    quotes = result["indicators"]["quote"][0]["close"]

    rows = []

    for ts, close in zip(timestamps, quotes):
        if close is None:
            continue

        date = datetime.fromtimestamp(
            ts, timezone.utc
        ).strftime("%Y-%m-%d")

        rows.append({
            "date": date,
            "value": close,
        })

    return latest_pair(rows)


def get_effr():
    """NY連銀の公式APIから実効FF金利(EFFR)の最新1件を取得する。"""
    url = (
        "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/1.json"
    )
    response = SESSION.get(url, timeout=(15, 45))
    response.raise_for_status()

    ref_rates = response.json().get("refRates", [])
    if not ref_rates:
        raise ValueError("EFFR: APIの結果が空です")

    row = ref_rates[0]
    if row.get("percentRate") is None:
        raise ValueError("EFFR: percentRateがありません")

    return {
        "value": float(row["percentRate"]),
        "previous": None,
        "date": row["effectiveDate"],
    }


def get_credit_ratio():
    """日経225.jpの信用評価損益率を、ブラウザ描画後のDOMから取得する。"""
    from playwright.sync_api import sync_playwright

    url = "https://nikkei225jp.com/data/sinyou.php"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # tbody#datatbl に行が入るまで待つ
            page.wait_for_selector("tbody#datatbl tr td", timeout=30000)
            html = page.inner_html("tbody#datatbl")
        finally:
            browser.close()

    soup = BeautifulSoup(f"<table>{html}</table>", "html.parser")
    parsed = []

    for row in soup.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 9:
            continue

        date_element = cells[0].select_one("time")
        date = (
            date_element.get_text(strip=True)
            if date_element
            else cells[0].get_text(strip=True)
        )

        raw = cells[8].get_text(strip=True)
        raw = raw.replace("%", "").replace("％", "").replace(",", "")

        try:
            value = float(raw)
        except ValueError:
            continue

        if re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            parsed.append({"date": date, "value": value})

    if not parsed:
        raise ValueError(
            "信用評価損益率: 行は取得できたが、有効な値を抽出できません"
        )

    return latest_pair(parsed)


def safe_fetch(name, func):
    """個別の取得エラーを記録し、他項目の取得を継続する。"""
    try:
        result = func()
        print(f"[成功] {name}: {result}", flush=True)
        return result
    except Exception as exc:
        print(
            f"[失敗] {name}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return {
            "value": None,
            "previous": None,
            "date": None,
        }


def main():
    data = {
        "updated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        ),
        "credit": safe_fetch(
            "信用評価損益率", get_credit_ratio
        ),
        "dgs10": safe_fetch(
            "米国10年金利", lambda: get_yahoo("%5ETNX")
        ),
        "fedfunds": safe_fetch(
            "実効FF金利", get_effr
        ),
        "vix": safe_fetch(
            "VIX", lambda: get_yahoo("%5EVIX")
        ),
        "tqqq": safe_fetch(
            "TQQQ", lambda: get_yahoo("TQQQ")
        ),
    }

    # 取得に失敗した場合は既存のdata.jsonを上書きしない
    failed = [
        name
        for name in ("credit", "dgs10", "fedfunds", "vix", "tqqq")
        if data[name]["value"] is None
    ]

    print(
        json.dumps(data, ensure_ascii=False, indent=2),
        flush=True,
    )

    if failed:
        print(
            f"取得失敗項目: {', '.join(failed)}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)

    OUT.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[保存成功] {OUT}", flush=True)


if __name__ == "__main__":
    main()