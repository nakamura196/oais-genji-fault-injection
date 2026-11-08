"""DIP（公開物）を、ネットの外に出られない状態で開き、どの頁が動くかを数える。

DIP を手元の HTTP サーバで配り、各頁を Chromium（Playwright）で 2 回開く。
  online : そのまま（外の CDN・フォント・API にも行ける）
  offline: 手元のサーバ（127.0.0.1）以外への要求をすべて止める
2 回の結果を比べ、頁に出た文字の量・図や表の要素の数・スクリプトのエラーを記録する。
offline で文字の量と要素の数が online の 9 割以上あり、新しいスクリプトのエラーが無ければ「動く」とする。
公開サイトの URL（kouigenjimonogatari.github.io）への要求も「外」として止める
（DIP だけで閉じているかを見るため）。

使い方: python offline_dip.py <DIP を展開したフォルダ> <出力 TSV>
"""
import csv
import functools
import http.server
import sys
import threading
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

PORT = 8765
MEASURE = """() => ({
  text: document.body ? document.body.innerText.trim().length : 0,
  elems: document.querySelectorAll('img,svg,canvas,table tr,li,iframe,video').length,
})"""


def serve(root):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    s = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def visit(browser, url, offline):
    # 既定の en-US だとトップ頁（index.html）が seo-redirect.js で英語版に飛ぶので、ja-JP で開く
    ctx = browser.new_context(locale="ja-JP")
    blocked, errors = Counter(), []
    if offline:
        def route(r):
            if urlparse(r.request.url).hostname in ("127.0.0.1", "localhost"):
                r.continue_()
            else:
                blocked[r.request.resource_type] += 1
                r.abort()
        ctx.route("**/*", route)
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)[:120]))
    try:
        page.goto(url, wait_until="load", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        m = page.evaluate(MEASURE)
    except Exception as e:
        m = {"text": 0, "elems": 0}
        errors.append("goto: " + str(e)[:100])
    ctx.close()
    return m, blocked, errors


def group(rel):
    if rel.startswith("snorql/") and rel != "snorql/index.html":
        return "snorql-docs"  # 同梱の CodeMirror の説明・見本（サイトの頁ではない）
    if rel.startswith("google") and rel.endswith(".html"):
        return "verification"
    return rel.split("/")[0] if "/" in rel else rel


def main(root, out):
    root = Path(root)
    pages = sorted(p.relative_to(root).as_posix() for p in root.rglob("*.html"))
    serve(root)
    rows = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for rel in pages:
            url = f"http://127.0.0.1:{PORT}/{rel}"
            on, _, e_on = visit(b, url, False)
            off, blocked, e_off = visit(b, url, True)
            new_err = [e for e in e_off if e not in e_on]
            ok = (off["text"] >= 0.9 * on["text"] and off["elems"] >= 0.9 * on["elems"] and not new_err)
            rows.append({"page": rel, "group": group(rel), "works_offline": int(ok),
                         "text_on": on["text"], "text_off": off["text"], "elems_on": on["elems"], "elems_off": off["elems"],
                         "blocked": ";".join(f"{k}:{v}" for k, v in sorted(blocked.items())),
                         "new_errors": " | ".join(new_err)[:300]})
            print(rel, ok, on, off, dict(blocked), flush=True)
        b.close()
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
