"""METS の中の PREMIS に記録された SHA-256 と、bag の中のファイルを照合する（L4）。

mets:file の FLocat（ファイルの場所）と ADMID（techMD への参照）から、ファイルごとの値を引く。
食い違い・欠落が 1 件でもあれば終了コード 1。
使い方: python premis_fixity.py <bag のフォルダ>
"""
import hashlib
import sys
from pathlib import Path

from lxml import etree

NS = {"mets": "http://www.loc.gov/METS/", "premis": "http://www.loc.gov/premis/v3",
      "xlink": "http://www.w3.org/1999/xlink"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main(bag):
    data = Path(bag) / "data"
    mets_files = list(data.glob("METS.*.xml"))
    if not mets_files:
        print("METS がありません"); return 1
    try:
        tree = etree.parse(str(mets_files[0]))
    except etree.XMLSyntaxError as e:
        print(f"METS を読めません: {e}"); return 1
    tech = {}
    # mets:file の ADMID は amdSec を指し、その中の techMD に PREMIS の値がある
    for t in tree.iterfind(".//mets:amdSec", NS):
        d = t.find("mets:techMD//premis:messageDigest", NS)
        if d is not None:
            tech[t.get("ID")] = d.text
    bad = checked = 0
    for f in tree.iterfind(".//mets:fileSec//mets:file", NS):
        loc = f.find("mets:FLocat", NS)
        href = loc.get(f"{{{NS['xlink']}}}href")
        want = next((tech[a] for a in (f.get("ADMID") or "").split() if a in tech), None)
        if want is None:
            continue
        checked += 1
        p = data / href
        if not p.is_file():
            print(f"missing: {href}"); bad += 1
        elif sha256(p) != want:
            print(f"mismatch: {href}"); bad += 1
    print(f"checked {checked}, bad {bad}")
    return 1 if bad or checked == 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
