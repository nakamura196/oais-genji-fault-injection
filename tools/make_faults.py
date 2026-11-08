"""v1.0.0 の AIP の複製を壊し、故障の注入の事例を作る。コンテナ（Dockerfile）の中で動かす。

壊したあと、どこまでの記録を「辻褄が合うように」付け直すか（depth）を事例ごとに決める。
  0: 何も付け直さない（7z のファイルそのものが壊れる）
  1: 7z に詰め直し、外側の SHA-256 を付け直す
  2: 1 に加え、BagIt の一覧（manifest・tagmanifest・Payload-Oxum）を付け直す
  3: 2 に加え、METS の PREMIS の対象（techMD）の SHA-256 と大きさも付け直す
     （出来事「message digest calculation」の結果に残る SHA-256 は元のまま。premis_events.py で見つかる）
  4: 3 に加え、その出来事の結果の SHA-256 も付け直す（AIP の中の固定性の記録はすべて辻褄が合う）
Zenodo の SIP の MD5 は AIP の外にあるので、どの depth でも付け直せない。

使い方: python make_faults.py <元の AIP（7z）> <出力先 runs/> [事例名 ...]
各事例は runs/<名前>/aip.7z・aip.7z.sha256・fault.json になる。
"""
import hashlib
import json
import random
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from lxml import etree

NS = {"mets": "http://www.loc.gov/METS/", "premis": "http://www.loc.gov/premis/v3",
      "xlink": "http://www.w3.org/1999/xlink"}
SEED = 20261106


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def flip_bit(path, offset, bit=0):
    b = bytearray(Path(path).read_bytes())
    b[offset] ^= 1 << bit
    Path(path).write_bytes(bytes(b))


# --- AIP の展開と詰め直し ---------------------------------------------------

def unpack(aip, work):
    shutil.rmtree(work, ignore_errors=True)
    subprocess.run(["7z", "x", "-y", str(aip), f"-o{work}"], check=True, stdout=subprocess.DEVNULL)
    return next(Path(work).iterdir())  # bag のフォルダ


def pack(bag, out_dir):
    out = Path(out_dir) / "aip.7z"
    out.unlink(missing_ok=True)
    subprocess.run(["7z", "a", "-t7z", str(out), bag.name], cwd=bag.parent, check=True, stdout=subprocess.DEVNULL)
    (Path(out_dir) / "aip.7z.sha256").write_text(f"{sha256(out)}  aip.7z\n")


def src_zip(bag):
    return next((bag / "data" / "objects").glob("*.zip"))


def extracted_dir(bag):
    return next(p for p in (bag / "data" / "objects").iterdir() if p.is_dir() and p.name.startswith(src_zip(bag).name))


def rewrite_zip(zpath, edit):
    """zip の中のファイルを edit(name, bytes) -> bytes | None（None なら消す）で書き換える。順番と圧縮は保つ。"""
    tmp = zpath.with_suffix(".tmp")
    with zipfile.ZipFile(zpath) as zi, zipfile.ZipFile(tmp, "w") as zo:
        for info in zi.infolist():
            data = zi.read(info) if not info.is_dir() else b""
            new = edit(info.filename, data) if not info.is_dir() else data
            if new is None:
                continue
            zo.writestr(info, new, compress_type=info.compress_type)
    tmp.replace(zpath)


def edit_member(bag, rel, edit):
    """ソースの中の 1 ファイル（rel はリポジトリの根からのパス）を、zip と展開した写しの両方で書き換える。"""
    hit = []

    def f(name, data):
        if name.split("/", 1)[-1] == rel:
            hit.append(name)
            return edit(data)
        return data
    rewrite_zip(src_zip(bag), f)
    assert hit, rel
    ex = extracted_dir(bag) / hit[0]
    changed = [src_zip(bag)]
    if ex.exists():
        new = edit(ex.read_bytes())
        if new is None:
            ex.unlink()
        else:
            ex.write_bytes(new)
        changed.append(ex)
    return changed


# --- 記録の付け直し --------------------------------------------------------

def update_bagit(bag):
    import bagit
    bagit.Bag(str(bag)).save(manifests=True)


def update_premis(bag, events=False):
    data = bag / "data"
    mets = next(data.glob("METS.*.xml"))
    tree = etree.parse(str(mets))
    amd = {a.get("ID"): a for a in tree.iterfind(".//mets:amdSec", NS)}
    for f in list(tree.iterfind(".//mets:fileSec//mets:file", NS)):
        href = f.find("mets:FLocat", NS).get(f"{{{NS['xlink']}}}href")
        p = data / href
        a = next((amd[x] for x in (f.get("ADMID") or "").split() if x in amd), None)
        if a is None:
            continue
        if not p.is_file():
            f.getparent().remove(f)  # 消したファイルは、METS からも消す
            continue
        d = a.find("mets:techMD//premis:messageDigest", NS)
        s = a.find("mets:techMD//premis:size", NS)
        if d is not None:
            old, d.text = d.text, sha256(p)
            if events:
                for e in a.iterfind("mets:digiprovMD//premis:event", NS):
                    n = e.find(".//premis:eventOutcomeDetailNote", NS)
                    if e.findtext("premis:eventType", namespaces=NS) == "message digest calculation" and n is not None \
                            and (n.text or "").strip() == old.strip():
                        n.text = d.text
        if s is not None:
            s.text = str(p.stat().st_size)
    tree.write(str(mets), xml_declaration=True, encoding="UTF-8")


def finish(bag, out_dir, depth):
    if depth >= 3:
        update_premis(bag, events=depth >= 4)
    if depth >= 2:
        update_bagit(bag)
    pack(bag, out_dir)


# --- 事例 -----------------------------------------------------------------

TEI = "xml/master/12.xml"  # 須磨
XSL = "xsl/mirador.xsl"    # 本文の頁を作る XSLT


def tei_one_char(data):
    s = data.decode()
    old = "世中いとわつらはしく"
    assert old in s
    return s.replace(old, "世中いとわつらはしき", 1).encode()  # スキーマには合う 1 字の書き換え


def tei_invalid(data):
    s = data.decode()
    i = s.index("<seg ")
    j = s.index("</seg>", i)
    return (s[:i] + "<sgg " + s[i + 5:j] + "</sgg>" + s[j + 6:]).encode()  # スキーマに無い要素


def case_bitflip_7z(aip, out, rng):
    shutil.copy(aip, out / "aip.7z")
    (out / "aip.7z.sha256").write_text(f"{sha256(aip)}  aip.7z\n")
    size = (out / "aip.7z").stat().st_size
    off = rng.randrange(size)
    flip_bit(out / "aip.7z", off, rng.randrange(8))
    return {"offset": off}


def case_truncate(aip, out, rng):
    b = Path(aip).read_bytes()
    (out / "aip.7z").write_bytes(b[: len(b) - 1_000_000])
    (out / "aip.7z.sha256").write_text(f"{sha256(aip)}  aip.7z\n")
    return {"removed_bytes": 1_000_000}


def case_payload(depth, mutate):
    def run(aip, out, rng):
        bag = unpack(aip, out / "work")
        info = mutate(bag, rng)
        finish(bag, out, depth)
        shutil.rmtree(out / "work")
        return info
    return run


def m_flip_srczip(bag, rng):
    z = src_zip(bag)
    off = rng.randrange(z.stat().st_size // 2)  # 前半（本文の圧縮データ）
    flip_bit(z, off, rng.randrange(8))
    return {"file": "source zip", "offset": off}


def m_flip_extracted(bag, rng):
    p = extracted_dir(bag).glob("*/" + TEI)
    p = next(p)
    flip_bit(p, 2000)
    return {"file": "extracted copy of " + TEI}


def m_member(rel, edit, label):
    def m(bag, rng):
        edit_member(bag, rel, edit)
        return {"file": rel, "change": label}
    return m


def m_extracted_only(bag, rng):
    """a3m が展開した写しの TEI だけを 1 字書き換える（中のソースの zip は無傷）。設計に使っていない故障。"""
    p = next(extracted_dir(bag).glob("*/" + TEI))
    p.write_bytes(tei_one_char(p.read_bytes()))
    return {"file": "extracted copy of " + TEI, "change": "く→き"}


def m_drop_events(bag, rng):
    """METS の PREMIS の出来事（来歴: 取り込み・ウイルス検査・形式の同定など）をすべて消す。設計に使っていない故障。"""
    mets = next((bag / "data").glob("METS.*.xml"))
    tree = etree.parse(str(mets))
    ev = list(tree.iterfind(".//premis:event", NS))
    for e in ev:
        # premis:event を包む digiprovMD ごと消す（中身の無い digiprovMD を残さない）
        md = e
        while md is not None and etree.QName(md).localname != "digiprovMD":
            md = md.getparent()
        (md if md is not None else e).getparent().remove(md if md is not None else e)
    tree.write(str(mets), xml_declaration=True, encoding="UTF-8")
    return {"file": mets.name, "removed_events": len(ev)}


CASES = {
    # 名前: (説明, 作り方, depth)
    "F0r": ("対照: 壊さずに詰め直し、全部付け直す", case_payload(3, lambda bag, rng: {}), 3),
    "F1": ("7z の任意の 1 ビットを反転", case_bitflip_7z, 0),
    "F2": ("7z の末尾 1 MB を切る", case_truncate, 0),
    "F3": ("中のソースの zip の 1 ビットを反転", case_payload(1, m_flip_srczip), 1),
    "F4": ("F3 に加え BagIt の一覧も付け直す", case_payload(2, m_flip_srczip), 2),
    "F5": ("展開した写しの TEI を 1 ビット反転（zip は無傷）", case_payload(1, m_flip_extracted), 1),
    "F6": ("TEI の本文を 1 字書き換え（スキーマに合う）、全部付け直す", case_payload(3, m_member(TEI, tei_one_char, "く→き")), 3),
    "F7": ("TEI を 1 つ消し、全部付け直す", case_payload(3, m_member(TEI, lambda d: None, "delete")), 3),
    "F8": ("組み立てに要る XSLT を消し、全部付け直す", case_payload(3, m_member(XSL, lambda d: None, "delete")), 3),
    "F9": ("TEI をスキーマに反する形に（seg→sgg）、全部付け直す", case_payload(3, m_member(TEI, tei_invalid, "seg→sgg")), 3),
    # 以下は、直した後の検査を決めたあとで足した（検査の設計に使っていない）故障
    "F10": ("展開した写しの TEI だけを 1 字書き換え（zip は無傷）、全部付け直す", case_payload(3, m_extracted_only), 3),
    "F11": ("PREMIS の出来事（来歴）をすべて消し、全部付け直す", case_payload(3, m_drop_events), 3),
    "F12": ("F6 を depth 4 で（出来事の SHA-256 まで付け直す）", case_payload(4, m_member(TEI, tei_one_char, "く→き")), 4),
    "F13": ("F10 を depth 4 で（出来事の SHA-256 まで付け直す）", case_payload(4, m_extracted_only), 4),
}


def main(aip, runs, names):
    runs = Path(runs)
    rng = random.Random(SEED)
    for name in names or CASES:
        base = name.split("-")[0]  # F1-03 のように繰り返す
        desc, fn, depth = CASES[base]
        out = runs / name
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        key = "F3" if base == "F4" else name  # F3 と F4 は同じビットを反転し、付け直しの深さだけを変える
        info = fn(Path(aip), out, random.Random(f"{SEED}-{key}"))
        (out / "fault.json").write_text(json.dumps({"case": name, "desc": desc, "depth": depth, **info}, ensure_ascii=False))
        print(name, desc, info)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
