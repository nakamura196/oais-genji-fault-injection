"""DIP（公開物）の各頁を、JavaScript を切った状態で開き、どれだけ表示されるかを数える（Endings 4.7 の点検）。

offline_dip.py と同じく DIP を 127.0.0.1 で配り、各頁を Chromium（Playwright）で 2 回開く。
  js  : JavaScript を有効にし、外への通信も許す
  nojs: JavaScript を切る（外への通信は許す。JavaScript の有無だけを比べるため）
文字の量（innerText）と要素の数が js の 9 割以上なら「JavaScript なしで機能する」とする。
同梱の CodeMirror の説明（snorql/ の下）と所有確認のファイルは数えない（サイトの頁ではない）。

使い方: python nojs_dip.py <DIP を展開したフォルダ> <出力 TSV>
"""
import csv
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from offline_dip import MEASURE, PORT, group, serve  # noqa: E402


def visit(browser, url, js):
    # 既定の en-US だとトップ頁（index.html）が seo-redirect.js で英語版に飛ぶので、ja-JP で開く
    ctx = browser.new_context(java_script_enabled=js, locale="ja-JP")
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="load", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(1000)
        # JavaScript を切ると page.evaluate も動かないので、文字と要素は DOM から Python 側で数える
        text = len(page.inner_text("body").strip()) if page.query_selector("body") else 0
        elems = len(page.query_selector_all("img,svg,canvas,table tr,li,iframe,video"))
        m = {"text": text, "elems": elems}
    except Exception:
        m = {"text": 0, "elems": 0}
    ctx.close()
    return m


def main(root, out):
    root = Path(root)
    pages = sorted(p.relative_to(root).as_posix() for p in root.rglob("*.html"))
    pages = [p for p in pages if group(p) not in ("snorql-docs", "verification")]
    serve(root)
    rows = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for rel in pages:
            url = f"http://127.0.0.1:{PORT}/{rel}"
            on = visit(b, url, True)
            off = visit(b, url, False)
            ok = off["text"] >= 0.9 * on["text"] and off["elems"] >= 0.9 * on["elems"]
            rows.append({"page": rel, "group": group(rel), "works_nojs": int(ok),
                         "text_js": on["text"], "text_nojs": off["text"],
                         "elems_js": on["elems"], "elems_nojs": off["elems"]})
            print(rel, ok, on, off, flush=True)
        b.close()
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
