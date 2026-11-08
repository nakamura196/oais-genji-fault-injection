"""Combine the per-layer results and the AIP digests into results/summary.tsv.

Usage: python summarize.py <workdir with orig/ and runs/> <results dir>

Check A: SHA-256, 7z, BagIt, zip extraction, build (L1, L2, L3, L7).
Check B: Check A plus comparison of the source zip with the zip on Zenodo (L5).
Check C: MD5 of the whole AIP against the MD5 of the original AIP. It is computed
here from the files; the workflow itself was not run with faults.
"""
import hashlib
import json
import sys
from pathlib import Path

DEPTH = {0: "none", 1: "7z, SHA-256", 2: "7z, SHA-256, BagIt manifests",
         3: "7z, SHA-256, BagIt manifests, PREMIS objects",
         4: "7z, SHA-256, BagIt manifests, PREMIS objects, PREMIS events"}
CASES = [
    ("F0", "No change (control)", 0, True),
    ("F0r", "No change; 7z repacked (control)", 3, True),
    ("F1", "Flip 1 random bit of the 7z (10 repeats)", 0, True),
    ("F2", "Cut the last 1 MB of the 7z", 0, False),
    ("F3", "Flip 1 bit of the source zip inside the AIP", 1, True),
    ("F4", "F3 with BagIt manifests updated", 2, False),
    ("F5", "Flip 1 bit of a TEI file in the extracted copy (zip intact)", 1, False),
    ("F6", "Change 1 character of the TEI text (still schema-valid)", 3, True),
    ("F7", "Delete 1 TEI file (1 chapter)", 3, True),
    ("F8", "Delete an XSLT file required by the build", 3, False),
    ("F9", "Make a TEI file schema-invalid (seg to sgg)", 3, False),
    ("F10", "Change 1 character of TEI in the extracted copy only (zip intact)", 3, True),
    ("F11", "Delete all PREMIS events", 3, True),
    ("F12", "F6 with PREMIS event digests updated", 4, False),
    ("F13", "F10 with PREMIS event digests updated", 4, False),
]


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def main(work, out):
    work, out = Path(work), Path(out)
    layers = {}
    for line in (out / "checks-by-layer.tsv").read_text().splitlines():
        name, data = line.split("\t", 1)
        layers[name] = json.loads(data)
    orig = md5(next((work / "orig").glob("*-aip.7z")))
    rows = ["case\tchange\trecords_updated\tcheck_A\tcheck_B\tcheck_C\tcheck_B_L5_zip_only\tin_table_3"]
    for case, change, depth, table in CASES:
        runs = [n for n in layers if n == case or n.startswith(case + "-")]
        a = sum(any(layers[n][k] == "FAIL" for k in ("L1", "L2", "L3", "L7")) for n in runs)
        l5 = sum(layers[n]["L5"] == "FAIL" for n in runs)
        b = sum(any(layers[n][k] == "FAIL" for k in ("L1", "L2", "L3", "L5", "L7")) for n in runs)
        c = sum(md5(work / "runs" / n / "aip.7z") != orig for n in runs)
        total = len(runs)
        rows.append("\t".join([case, change, DEPTH[depth], f"{a}/{total}", f"{b}/{total}", f"{c}/{total}",
                               f"{l5}/{total}", "yes" if table else "no"]))
    (out / "summary.tsv").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
