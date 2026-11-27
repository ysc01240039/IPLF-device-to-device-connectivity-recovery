# IPLF: Initiator-Pays Link Formation for Post-Disaster D2D Connectivity Recovery

Simulation code, per-seed data and figure sources for the paper *Initiator-Pays Link
Formation: Recovering Device-to-Device Connectivity after Infrastructure Failure*
(target journal: **Computer Networks**, Elsevier).

The code is a discrete-time simulator of a $500\times500$ m field of terminals that
can form short-range device-to-device links and reach a satellite only through
sky-visible uplink terminals. The single design variable under study is **who pays
for a link**: under bilateral payment both endpoints spend credit, under the IPLF
rule only the initiating side does.

Version: 2026-11-28 (frozen pre-disaster world, billing decomposition, 141-check
self-test). This supersedes the 2026-11-23 release, which predates the refund bug
fix (the old numbers, e.g. 95.4 %, do not reproduce here).

---

## What is in this repository

| Path | Contents |
|---|---|
| `engine.py` | The simulator. Single implementation; every experiment calls it. |
| `mainline.py` | Parameter tables (`ATTRS`), job construction, and the terminal decision rule. |
| `metrics.py` | Metric definitions (`unit`, `o2p`, `recon_split`, `t50_fixed`, `t50_cond`). |
| `exp_v245.py` | Entry point for every experiment reported in the paper. |
| `run_comp_ablation.py` | Behaviour-component ablation (Table VI): thickening / exploration / old-neighbour prior. |
| `exp_who_pays.py` | Billing decomposition (Table III): who pays, at three credit stocks (`--credit 0.3/1/3`). |
| `make_tables.py` | Regenerates every CSV in `data/` from the JSON results (the figures read those CSVs). |
| `data/exp_v245_*.json` | Raw per-seed results (30 paired seeds unless stated). |
| `data/who_pays_*_frozen.json` | Raw results of the billing decomposition at credit x0.3 / x1 / x3. |
| `data/*.csv` | The exact tables the paper's figures read; produced by `make_tables.py`. |
| `figures_src/` | TikZ/pgfplots sources of the data figures (Figs. 2 and 4–7 of the paper). |
| `_verify_engine.py` | Reproduction self-check: 12 seeds must match the released per-seed results exactly. |
| `_verify_exp.py` | Cross-checks every table and quoted number in the paper against the raw JSON (141 checks; exit code 1 on any mismatch). |
| `_check_books.py` | Credit-conservation check (`init + resup - paid - thick_paid + refund - lost = now`, tolerance 1e-15). |
| `balance.py` | Further conservation checks on the simulation bookkeeping. |

## Requirements

Python 3.13 (tested; 3.10 or later should also work). **No third-party packages are
required** — the simulator uses only the standard library (`argparse`, `json`,
`random`, `statistics`, `heapq`, `concurrent.futures`). Figures need a LaTeX
installation with TikZ and pgfplots.

```bash
python --version        # 3.13
python _verify_exp.py   # every number in the paper vs data/*.json
```

## Quick start

The main comparison table (Table II) is the `sev` slice of the `multi` group:

```bash
python exp_v245.py --group multi --dim sev
```

`--group main` is a *different* experiment: it runs the four-arm comparison
(lower bound, proposed, LEACH, flooding) used for the flooding arm and the energy
numbers. To regenerate every result:

```bash
python exp_v245.py --group main
python exp_v245.py --group multi --dim sev
python exp_v245.py --group multi --dim sup
python exp_v245.py --group abl
python exp_v245.py --group run_comp   # or: python run_comp_ablation.py
python exp_v245.py --group fit
python exp_v245.py --group robust
python exp_v245.py --group scale
python exp_v245.py --group parity
python exp_v245.py --group tune
python exp_v245.py --group tune2
python exp_v245.py --group long
python exp_who_pays.py --credit 1   --json data/who_pays_1x_frozen.json
python exp_who_pays.py --credit 0.3 --json data/who_pays_03x_frozen.json
python exp_who_pays.py --credit 3   --json data/who_pays_3x_frozen.json
python make_tables.py               # JSON -> CSV
```

Available groups: `main`, `abl`, `sens`, `sev`, `scale`, `lit`, `parity`, `fit`,
`multi`, `robust`, `tune`, `tune2`, `long`.

Runtime is dominated by `main`, `multi`, `robust` and `long`; a full regeneration
takes roughly **1–2 hours** on a single desktop core (one 100-terminal, 180-step
run takes about a second).

## Verifying that the code reproduces the paper

```bash
python _verify_engine.py    # 12 seeds, exact match on every reported metric
python _verify_exp.py       # 141 table/number checks against data/*.json
python _check_books.py      # credit conservation, four configurations
```

`_verify_engine.py` re-runs seeds 1–12 of the main configuration and compares six
quantities (`recon`, `t50_cond_s`, `sat_all`, `dead`, `lcc_frac`, `energy_per_node`)
against `data/exp_v245_main.json`; equality is exact, not approximate. It also runs
one perturbed arm (single billing switched to bilateral) to show that the check can
move — a "green" self-check that never changes anything would prove nothing.
Expect about one minute.

## Figures

`figures_src/` holds the sources of the data figures. They read the CSVs in
`data/` (paths are `../data/*.csv`, so build from inside `figures_src/`):

```bash
cd figures_src
pdflatex fig2_world.tex     # needs _fig2_cells.tex in the same directory
pdflatex fig4_states.tex
pdflatex fig5_tune.tex
pdflatex fig6_main.tex
pdflatex fig7_shock.tex
```

Figures 1 and 3 of the paper are block diagrams exported from the authors' drawing
tool; they are not data figures and are not part of this repository.

## Data notes

- All comparisons use **30 paired seeds**: the same seeds, field and instant are
  used across arms, so differences are paired and reported with a 95 % CI and
  Cohen's $d$. The pre-disaster phase is frozen (`FREEZE_PRE`) so every arm starts
  from the same world and the same at-risk cohort.
- Baselines (LEACH, CFACHS, AFPUC variants, ST) are **re-implementations from
  published descriptions**, not the authors' code; no source code is available for
  them. Their numbers should be read as directions, not as reproductions of the
  published performance. This is stated in the paper as well.
- `parity` holds the sky-visible fraction fixed across schemes, which separates
  "the mechanism organises a fixed resource better" from "the mechanism simply has
  more uplinks".
- The `tune` and `tune2` grids (nine cluster-head ratios, 0.02–0.95) give every
  baseline its own best setting before any comparison.
- `t50_cond` is the conditional median (reconnectors only); the fixed-cohort variant
  `t50_fixed` scores non-reconnecting terminals at the window length and is also in
  the JSON, for readers who prefer that convention.
- The grid is toroidal: opposite edges are adjacent, so no terminal sits on a
  boundary. This is stated in the paper (§III-A).

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

Gongzhe Qiao, Nanjing University of Information Science and Technology,
003969@nuist.edu.cn
