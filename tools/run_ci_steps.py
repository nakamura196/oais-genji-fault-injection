"""release.yml の DIP 段の手順を、書いてあるとおりに 1 件の AIP に対して流す（直したワークフローの検査）。

check.sh は段ごとに検査を作り直したもの。こちらは release.yml の run: をそのまま取り出して動かすので、
ワークフローの文面そのものを試せる。GitHub の外では動かない手順（gh での取得・添付、setup-* の action、
道具の取得、出所の記録、添付）は飛ばし、そのかわりに同じ状態を用意する。
コンテナ（Dockerfile）の中で動かす。GitHub の API と Zenodo の API に問い合わせる（ネットが要る）。

使い方: python run_ci_steps.py <release.yml> <case_dir>
  環境変数 ROUTE=github で、Zenodo に版が無いときの経路（GitHub のソース zip と照らす）を試す（結果は ci-result-github.json）
  case_dir の aip.7z・aip.7z.sha256 を使い、case_dir/ci/ に作業し、ci-result.json に、
  各手順の成否と、最初に落ちた手順を書く。落ちても後ろの手順まで流す（どの手順が見つけるかを見るため）
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = "kouigenjimonogatari/kouigenjimonogatari.github.io"
TAG = "v1.0.0"
NAME = f"{REPO.split('/')[1]}-{TAG}"
RUN = [
    "Unpack and validate the bag",
    "Check the SIP in the AIP against copies outside the AIP",
    "Generate DIP from the AIP (tei, xsl, waka, stats, api, epub)",
    "Check that the DIP covers all 54 chapters",
]


def main(wf, case):
    case = Path(case).resolve()
    d = yaml.safe_load(open(wf))
    steps = {s["name"]: s for s in d["jobs"]["dip"]["steps"]}
    w = case / "ci"
    shutil.rmtree(w, ignore_errors=True)
    w.mkdir()
    shutil.copy(case / "aip.7z", w / f"{NAME}-aip.7z")
    (w / f"{NAME}-aip.7z.sha256").write_text((case / "aip.7z.sha256").read_text().replace("aip.7z", f"{NAME}-aip.7z"))
    for jar in ("saxon-he", "xmlresolver"):  # 「Download Saxon-HE and xmlresolver」の代わり（イメージに入っている）
        Path(f"/tmp/{jar}.jar").unlink(missing_ok=True)
        os.symlink(f"/opt/{jar}.jar", f"/tmp/{jar}.jar")
    env = {**os.environ, **{k: str(v) for k, v in d["env"].items() if "${{" not in str(v)},
           "TAG": TAG, "NAME": NAME, "GITHUB_REPOSITORY": REPO,
           "GITHUB_ENV": str(w / "github_env"), "GITHUB_STEP_SUMMARY": str(w / "summary.md")}
    if os.environ.get("ROUTE") == "github":  # Zenodo にまだ無い版の経路（GitHub のソース zip と照らす）を試す
        env["ZENODO_CONCEPT_ID"] = "0"
    Path(env["GITHUB_ENV"]).touch()
    res = {}
    # 「Retrieve AIP from the release」の検査の部分（取得は上で済ませた）
    r = subprocess.run(["sha256sum", "-c", f"{NAME}-aip.7z.sha256"], cwd=w, capture_output=True)
    res["Retrieve AIP (sha256sum -c)"] = "pass" if r.returncode == 0 else "FAIL"
    for name in RUN:
        s = steps[name]
        for line in Path(env["GITHUB_ENV"]).read_text().splitlines():  # 前の手順が GITHUB_ENV に書いた値
            k, _, v = line.partition("=")
            env[k] = v
        senv = {**env, **{k: v for k, v in (s.get("env") or {}).items()}}
        log = w / (name.split(" (")[0].replace(" ", "_") + ".log")
        with open(log, "w") as f:
            r = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", s["run"]],
                               cwd=w, env=senv, stdout=f, stderr=subprocess.STDOUT)
        res[name] = "pass" if r.returncode == 0 else "FAIL"
    first = next((k for k, v in res.items() if v == "FAIL"), None)
    out = {"steps": res, "first_fail": first}
    (case / ("ci-result-github.json" if os.environ.get("ROUTE") == "github" else "ci-result.json")).write_text(json.dumps(out, ensure_ascii=False))
    print(json.dumps(out, ensure_ascii=False))
    for p in ("aip", "src", "github-src.zip", f"{NAME}-aip.7z"):  # 大きいものは消す（ログと summary は残す）
        q = w / p
        shutil.rmtree(q, ignore_errors=True) if q.is_dir() else q.unlink(missing_ok=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
