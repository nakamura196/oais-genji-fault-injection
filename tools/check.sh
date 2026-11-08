#!/usr/bin/env bash
# AIP 1 件を、release.yml の DIP 段と同じ手順で検査する。最初の段で落ちても止めず、
# 後ろの段まで続けて、各段の結果を result.json に書く。コンテナ（Dockerfile）の中で動かす。
#
# 使い方: check.sh <case_dir> <ref_dir>
#   case_dir: aip.7z と aip.7z.sha256 を置いたフォルダ（壊したもの）
#   ref_dir:  元の DIP を展開したもの（dip/）と、組み立ての道具（tools/、TEI 検証用）を置いたフォルダ
#
# 段（L1〜L3・L7 は今の release.yml が行う。L4〜L6・L8 は足した検査）
#   L1 sha256   添付の SHA-256 で AIP 全体を照合
#   L2 7z       7z の展開（中の CRC を確かめる）
#   L3 bagit    BagIt の一覧と照合
#   L4 premis   METS の PREMIS に記録した SHA-256 と照合
#   L5 sip_md5  AIP の中の zip の MD5 を、Zenodo の SIP の MD5 と照合
#   L6 tei      AIP の中のソースで TEI を検証（RELAX NG・Schematron）
#   L7 build    AIP の中のソースから DIP を組み立てる
#   L8 dip      組み立てた DIP を、公開済みの DIP と照合（build-info.json を除く）
set -u
C=$1; R=$2
ZENODO_MD5=97f1c7670bb9bf9d97d1049a0efb9b11
cd "$C"; rm -rf aip src result.json log; mkdir -p log
declare -A res
put() { res[$1]=$2; }

if sha256sum -c aip.7z.sha256 >log/L1 2>&1; then put L1 pass; else put L1 FAIL; fi
# 添付の .sha256 は元のファイル名を指すので、壊したものに名前をそろえてある（make_faults.py）

if 7z x -y aip.7z -oaip >log/L2 2>&1; then put L2 pass; else put L2 FAIL; fi
BAG=$(ls -d aip/*/ 2>/dev/null | head -1)
if [ -z "$BAG" ]; then
  for l in L3 L4 L5 L6 L7 L8; do put $l na; done
else
  if python -m bagit --validate "$BAG" >log/L3 2>&1; then put L3 pass; else put L3 FAIL; fi
  if python /tools/premis_fixity.py "$BAG" >log/L4 2>&1; then put L4 pass; else put L4 FAIL; fi
  Z=$(ls "$BAG"data/objects/*.zip 2>/dev/null | head -1)
  if [ -n "$Z" ] && [ "$(md5sum "$Z" | cut -d' ' -f1)" = "$ZENODO_MD5" ]; then put L5 pass; else put L5 FAIL; fi
  if [ -n "$Z" ] && mkdir src && unzip -q "$Z" -d src >log/unzip 2>&1; then
    S=$(ls -d "$PWD"/src/*/ | head -1)
    # TEI の検証。道具（jing・Schematron の XSLT 化）は毎回取りに行かず、元の AIP で用意したものを写す
    # 組み立て（L7）に影響しないよう、写しの上で行う。ODD から作り直したスキーマが同梱のものと一致するかも見る（validate.yml と同じ）
    T6=$PWD/src6; rm -rf "$T6"; cp -R "$S" "$T6"; mkdir -p "$T6/tools"; cp -R "$R/tools/." "$T6/tools/"
    if (cd "$T6" && zsh scripts/build-schema.zsh && diff -r "$S/docs/schema" docs/schema && zsh scripts/validate.zsh) >log/L6 2>&1; then put L6 pass; else put L6 FAIL; fi
    rm -rf "$T6"
    if (cd "$S" && python3 scripts/prebuild.py tei xsl waka stats api epub) >log/L7 2>&1; then
      put L7 pass
      if python /tools/compare_dip.py "$S/docs" "$R/dip" >log/L8 2>&1; then put L8 pass; else put L8 FAIL; fi
    else
      put L7 FAIL; put L8 na
    fi
  else
    put L6 na; put L7 FAIL; put L8 na
  fi
fi
{
  printf '{'
  sep=''
  for l in L1 L2 L3 L4 L5 L6 L7 L8; do printf '%s"%s":"%s"' "$sep" $l "${res[$l]}"; sep=','; done
  printf '}\n'
} > result.json
cat result.json
