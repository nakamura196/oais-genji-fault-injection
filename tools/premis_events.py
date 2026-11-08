"""METS の中で、PREMIS の対象（techMD）の SHA-256 と、同じファイルの出来事「message digest calculation」の
結果（eventOutcomeDetailNote）に残る SHA-256 が合っているかを確かめる（AIP の中だけでできる照合）。

make_faults.py の depth 3 は techMD の値と大きさだけを付け直し、出来事の記録は付け直さない。
そのため、この照合は depth 3 の書き換えを AIP の中だけで見つけられるかを測る。
出来事まで付け直す depth 4 には効かない。出来事の記録が無いファイルがあっても落とす（来歴の欠け）。

使い方: python premis_events.py <AIP の 7z>   （7z を展開して調べる。コンテナの中で動かす）
結果は 1 行の JSON: {"checked": n, "mismatch": n, "no_event": n}
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from lxml import etree

NS = {"mets": "http://www.loc.gov/METS/", "premis": "http://www.loc.gov/premis/v3"}


def main(aip):
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["7z", "x", "-y", aip, f"-o{td}", "*/data/METS.*.xml", "-r"], check=True,
                       stdout=subprocess.DEVNULL)
        mets = next(Path(td).rglob("METS.*.xml"))
        tree = etree.parse(str(mets))
    checked = mismatch = no_event = 0
    for amd in tree.iterfind(".//mets:amdSec", NS):
        d = amd.find("mets:techMD//premis:messageDigest", NS)
        if d is None:
            continue
        notes = [e.findtext(".//premis:eventOutcomeDetailNote", default="", namespaces=NS).strip()
                 for e in amd.iterfind("mets:digiprovMD//premis:event", NS)
                 if e.findtext("premis:eventType", namespaces=NS) == "message digest calculation"]
        if not notes:
            no_event += 1
            continue
        checked += 1
        if d.text.strip() not in notes:
            mismatch += 1
    print(json.dumps({"checked": checked, "mismatch": mismatch, "no_event": no_event}))
    return 1 if mismatch or no_event else 0  # 出来事が無いのも、来歴が欠けているので落とす


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
