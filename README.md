# Fault injection for an OAIS-style release workflow

Tools and results for testing what integrity checks detect when an Archival
Information Package (AIP) is altered. Each case alters a copy of the v1.0.0 AIP of
[Kōi Genji Monogatari](https://github.com/kouigenjimonogatari/kouigenjimonogatari.github.io/releases/tag/v1.0.0)
and, in many cases, also updates the records that would otherwise reveal the change.

## Results

`results/summary.tsv` lists all 15 cases. Each check column gives the number of
runs that the check stopped, out of the number of runs. F1 was repeated 10 times
and counts as one case.

| Check | What it does |
|---|---|
| A | SHA-256 of the attached file, 7z extraction, BagIt validation, zip extraction, build from the AIP |
| B | Check A, plus comparison of the source zip in the AIP with the zip on Zenodo |
| C | MD5 of the whole AIP against the value held outside the AIP |

For the two controls, F0 and F0r, a stop is not a detection. F0r holds the same
content, but repacking changes the bytes, so Check C stops it.

Check C was computed by comparing the MD5 of each altered AIP with the MD5 of the
original (`tools/summarize.py`). **The workflow itself was not run with faults for
Check C.** Because any byte change alters the digest, detecting every case follows
from how the check works and is not evidence of its strength.

Other files in `results/`:

| File | Content |
|---|---|
| `checks-by-layer.tsv` | Per-run result of layers L1 to L8 (`tools/check.sh`) |
| `workflow-steps.tsv` | Per-run result of each step of the release workflow's DIP stage (`tools/run_ci_steps.py`) |
| `premis-events.tsv` | Comparison of PREMIS object digests with PREMIS event digests. F1-01 is the only F1 run compared; F2 cannot be unpacked and shows the error. |

## Offline and JavaScript measurements

`tools/offline_dip.py` opens each page of a DIP in Chromium, with and without
network access beyond the local server. `tools/nojs_dip.py` opens each page with
JavaScript on and off. A page meets the criterion when at least 90% of its text and
elements remain; the offline test also requires no new script errors.

| File | Content |
|---|---|
| `results/offline-v1.1.0.tsv`, `results/nojs-v1.1.0.tsv` | DIP of v1.1.0, with libraries bundled in the source |
| `results/offline-v1.0.0.tsv`, `results/nojs-v1.0.0.tsv` | DIP of v1.0.0, with libraries loaded from their distributors |

The article reports 119 pages for v1.1.0. It excludes one site-ownership verification
page and four `*-en.html` redirect pages from the 124 HTML files. For v1.0.0 it
reports 66 pages; `offline-v1.0.0.tsv` also lists the 182 pages of `snorql-docs`.
These two scripts need Playwright with Chromium on the host:
`python offline_dip.py <extracted DIP> <output TSV>`.

## Re-running

Docker and zsh are required. Comments in the scripts are in Japanese.

1. Build the images: `docker build -t oais-fault:1 -t oais-fault:2 tools`
2. Make a working folder containing:
   - `orig/`: `kouigenjimonogatari.github.io-v1.0.0-aip.7z` from the release above
     (SHA-256 `182149432e381fd5a4cdf3ec0b67d536349776fa3406c835f78b0685e046bdec`)
   - `ref/dip/`: the extracted v1.0.0 DIP from the same release
   - `ref/tools/`: the TEI validation tools (Jing, Saxon, SchXslt2, TEI XSL,
     `p5subset.xml`, `tei_odds.rng`)
3. Create the cases inside the container: `python make_faults.py <original AIP> <runs/>`.
   The random seed is fixed in the script (20261106).
4. Run the checks: `zsh tools/run_all.zsh <working folder>`
5. Run the workflow steps: `zsh tools/run_ci_all.zsh <working folder> tools/release-tested.yml`.
   This step reads the GitHub and Zenodo APIs and uses the token from `gh auth token`.
6. Summarize: `python3 tools/summarize.py <working folder> results`

`tools/release-tested.yml` is the workflow version these runs used. The current
workflow of the site repository differs: it publishes the AIP to Zenodo first and
compares the digest of the whole AIP.

## Licence

Code: MIT (see `LICENSE`). Files in `results/`: CC BY 4.0.
