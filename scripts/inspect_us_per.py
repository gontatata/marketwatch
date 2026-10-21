"""日経225.jp「米国株PER」ページのDOM構造を調べる診断用スクリプト。
使い方: python scripts/inspect_us_per.py
"""
from playwright.sync_api import sync_playwright

URL = "https://nikkei225jp.com/data/us_per.php"
UA = "Mozilla/5.0 (compatible; MarketMonitor/1.0)"

JS_RADIOS = """
els => els.map(e => ({
  id: e.id, name: e.name, value: e.value, checked: e.checked,
  label: (e.labels && e.labels[0]) ? e.labels[0].innerText.trim()
         : (e.parentElement ? e.parentElement.innerText.trim().slice(0, 20) : "")
}))
"""

JS_TABLES = """
ts => ts.map(t => ({
  id: t.id,
  tbodyIds: [...t.querySelectorAll('tbody')].map(b => b.id),
  rows: t.rows.length,
  firstRows: [...t.rows].slice(0, 5).map(r =>
    [...r.cells].map(c => c.innerText.replace(/\\s+/g, ' ').trim()))
}))
"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    try:
        page = browser.new_page(user_agent=UA)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)  # JSの描画待ち

        print("=== radio ===")
        for r in page.eval_on_selector_all("input[type=radio]", JS_RADIOS):
            print(r)

        print("\n=== tables (rows>=10) ===")
        for t in page.eval_on_selector_all("table", JS_TABLES):
            if t["rows"] < 10:
                continue
            print(f"\n[table id={t['id']!r} tbody={t['tbodyIds']} rows={t['rows']}]")
            for row in t["firstRows"]:
                print(len(row), row)
    finally:
        browser.close()