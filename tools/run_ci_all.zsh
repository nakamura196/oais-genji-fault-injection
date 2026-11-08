#!/usr/bin/env zsh
# 直した release.yml の DIP 段を、runs/ の各事例に流し、ci-results.tsv にまとめる。
# 使い方: zsh run_ci_all.zsh <作業フォルダ（runs/ がある）> <release.yml> [事例名 ...]
# ROUTE=github を付けると、Zenodo に版が無いときの経路（GitHub のソース zip と照らす）で流す
set -euo pipefail
W=${1:A}; WF=${2:A}; shift 2
T=${0:A:h}
cases=(${@:-$(ls $W/runs)})
export GH_TOKEN=$(gh auth token)
export ROUTE=${ROUTE:-zenodo}
res=ci-result.json; [[ $ROUTE == github ]] && res=ci-result-github.json
for c in $cases; do
  docker run --rm -e GH_TOKEN -e ROUTE -v "$W/runs:/runs" -v "$T:/tools:ro" -v "$WF:/wf/release.yml:ro" oais-fault:2 python /tools/run_ci_steps.py /wf/release.yml /runs/$c >/dev/null 2>&1 || true
  print -r -- "$c	$(cat $W/runs/$c/$res)"
done | tee "$W/ci-results-partial-$ROUTE.tsv"
unset GH_TOKEN
