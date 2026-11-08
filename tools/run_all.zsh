#!/usr/bin/env zsh
# runs/ の全事例に check.sh をかけ、results.tsv にまとめる。
# 使い方: zsh run_all.zsh <作業フォルダ（orig・ref・runs のある所）>
set -u
W=${1:A}; T=${0:A:h}
for d in $W/runs/*(/); do
  n=${d:t}
  r=$(docker run --rm -v $W:/w -v $T:/tools:ro oais-fault:1 bash /tools/check.sh /w/runs/$n /w/ref 2>/dev/null | tail -1)
  print -r -- "$n	$r"
  # 展開したものは大きいので、ログと結果だけ残す
  rm -rf $d/aip $d/src
done > $W/results.tsv
