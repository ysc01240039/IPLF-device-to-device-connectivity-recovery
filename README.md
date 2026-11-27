# IPLF: Initiator-Pays Link Formation for Post-Disaster D2D Connectivity Recovery

Simulation code and experimental data for the paper *Initiator-Pays Link Formation:
Recovering Device-to-Device Connectivity after Infrastructure Failure*
(target journal: **Computer Networks**, Elsevier).

The code is a discrete-time simulator of a $500\times500$ m field of terminals that
can form short-range device-to-device links and reach a satellite only through
sky-visible uplink terminals. The single design variable under study is **who pays
for a link**: under bilateral payment both endpoints spend credit, under the IPLF
rule only the initiating side does.

---

## What is in this repository

| Path | Contents |
|---|---|
| `engine.py` | The simulator. Single implementation; every experiment calls it. |
| `mainline.py` | Parameter tables (`ATTRS`), job construction, and the terminal decision rule. |
| `metrics.py` | Metric definitions (`unit`, `o2p`, `recon_split`, `t50_fixed`). |
| `exp_v245.py` | Entry point for every experiment reported in the paper. |
| `make_tables.py` | Converts the raw JSON results into the CSV files used by the figures. |
| `data/exp_v245_*.json` | Raw per-seed results (30 paired seeds unless stated). |
| `_verify_engine.py` | Engine self-check: 12 seeds must reproduce bit-identical trajectories. |
| `_verify_exp.py` | Cross-checks each number in the paper against the raw JSON. |
| `metric_selftest.py` | Verifies that each metric responds when its input is perturbed. |
| `balance.py` | Conservation checks on the simulation bookkeeping. |
| `v*.py`, `pmap.py` | Legacy modules the engine still imports (frozen, not maintained). |

## Requirements

Python 3.9 or later. **No third-party packages are required** — the simulator uses
only the standard library (`argparse`, `json`, `random`, `statistics`, `heapq`,
`concurrent.futures`).

```bash
python --version   # 3.9+
```

## Quick start

Reproduce the main comparison table (100 terminals, 30 paired seeds):

```bash
python exp_v245.py --group main
```

This writes `exp_v245_main.json` into the working directory and prints a conservation
check (`dead + recon <= 1`). To regenerate every figure input:

```bash
python exp_v245.py --group multi --dim sev
python exp_v245.py --group multi --dim sup
python exp_v245.py --group abl
python exp_v245.py --group robust
python exp_v245.py --group scale
python exp_v245.py --group tune
python exp_v245.py --group tune2
python exp_v245.py --group parity
python exp_v245.py --group long
python make_tables.py
```

Available groups: `main`, `abl`, `sens`, `sev`, `scale`, `lit`, `parity`, `fit`,
`multi`, `robust`, `tune`, `tune2`, `long`.

Runtime is dominated by `main`, `multi` and `long` (each runs 30 seeds of a
180-step simulation); a full regeneration takes roughly 1-2 hours on a single
desktop core.

## Verifying that the code reproduces the paper

```bash
python _verify_engine.py    # 12 seeds, bit-identical trajectories
python metric_selftest.py   # each metric responds to its inputs
cd data && python ../_verify_exp.py   # every number in the paper vs raw JSON
```

`_verify_exp.py` reads the raw JSON from the current working directory, so run it
from `data/` (where the `exp_v245_*.json` files live); from the repository root it
will report the files as missing. It prints one line per reported number and ends
with `结论：全部对上` when the manuscript matches the data.

`_verify_engine.py` prints `W1 bit-identical: 12/12 seeds` together with a
capability check: an injected perturbation must move the output (otherwise a
"green" self-check proves nothing).

## Data notes

- All comparisons use **30 paired seeds**: the same seeds, field and instant are
  used across arms, so differences are paired and reported with a 95% CI and
  Cohen's $d$.
- Baselines (LEACH, CFACHS, AFPUC variants, ST) are **re-implementations from
  published descriptions**, not the authors' code; no source code is available for
  them. Their numbers should be read as directions, not as reproductions of the
  published performance. This is stated in the paper as well.
- `parity` holds the uplink-terminal count fixed across schemes, which separates
  "the mechanism organises a fixed resource better" from "the mechanism simply has
  more uplinks".
- The `tune` and `tune2` grids give every baseline its own best cluster-head ratio
  before any comparison.

## Citation

```bibtex
@article{iplf2026,
  title  = {Initiator-Pays Link Formation: Recovering Device-to-Device
            Connectivity after Infrastructure Failure},
  author = {Shichen Yao and Gongzhe Qiao},
  journal= {Computer Networks},
  year   = {2026},
  note   = {Under review}
}
```

## License

MIT. See `LICENSE`.

## Contact

Shichen Yao, 202483290192@nuist.edu.cn
Gongzhe Qiao (corresponding author), 003969@nuist.edu.cn
