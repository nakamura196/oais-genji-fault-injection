"""組み立てた DIP（docs/）を、公開済みの DIP と照合する（L8）。build-info.json は除く。

EPUB は中の各ファイルの中身で比べる。組み立てのたびに zip の日時が変わり、
ファイルとしては一致しないため（v1.0.0 で 54 件すべて。中身は一致）。

違ったファイルの数と最初の数件を出す。1 件でも違えば終了コード 1。
使い方: python compare_dip.py <組み立てた docs> <公開済み DIP を展開したフォルダ>
"""
import hashlib
import sys
import zipfile
from pathlib import Path

SKIP = {"build-info.json"}


def epub_digest(p):
    h = hashlib.sha256()
    try:
        with zipfile.ZipFile(p) as z:
            for n in sorted(z.namelist()):
                h.update(n.encode() + b"\0" + z.read(n))
    except zipfile.BadZipFile:
        return "bad-zip"
    return h.hexdigest()


def digests(root):
    root = Path(root)
    out = {}
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if rel not in SKIP:
                out[rel] = epub_digest(p) if p.suffix == ".epub" else hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main(built, ref):
    a, b = digests(built), digests(ref)
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    print(f"built {len(a)} / ref {len(b)} / added {len(only_a)} / missing {len(only_b)} / changed {len(diff)}")
    for label, xs in (("added", only_a), ("missing", only_b), ("changed", diff)):
        for x in xs[:20]:
            print(f"{label}: {x}")
    return 1 if (only_a or only_b or diff) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
