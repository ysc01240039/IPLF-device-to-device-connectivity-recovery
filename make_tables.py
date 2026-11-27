# -*- coding: utf-8 -*-
"""make_tables.py —— 把 data/exp_v245_*.json 导出成论文用的 csv。

论文里每张图都从 csv 读（pgfplots `\\addplot table`），图与数之间只隔一层；
正文里出现的每个数也都能顺着 csv 回到 json 的某一行。

用法：python make_tables.py      （读 data/*.json，写 data/*.csv）
"""
import io
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "data") if os.path.isdir(os.path.join(HERE, "data")) else HERE
OUT = SRC
os.makedirs(OUT, exist_ok=True)

ARMS7 = ["下限", "本方法", "LEACH@0.10", "CFACHS@0.05", "AFPUC-k@0.05",
         "AER-DM@0.02", "AFPUC-loc@0.10"]
SHORT = {"下限": "lower", "本方法": "ours", "LEACH@0.10": "leach", "CFACHS@0.05": "cfachs",
         "AFPUC-k@0.05": "afpuck", "AER-DM@0.02": "aerdm", "AFPUC-loc@0.10": "afpucloc"}
SH = ["lower", "ours", "leach", "cfachs", "afpuck", "aerdm", "afpucloc"]
MODE = [("leach", 0), ("cfachs", 1), ("afpuck", 2), ("aerdm", 3), ("afpucloc", 4)]
CHPS = [0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 0.85, 0.95]


def load(name):
    with io.open(os.path.join(SRC, "exp_v245_%s.json" % name), encoding="utf-8") as f:
        return json.load(f)


def write(fn, header, rows):
    p = os.path.join(OUT, fn)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")
    print("  %-18s %3d 行" % (fn, len(rows)))


def mean(rows, key, **cond):
    sub = [r for r in rows if all(r.get(k) == v for k, v in cond.items())]
    vals = [r[key] for r in sub if r.get(key) is not None]
    return st.mean(vals) if vals else float("nan")


def sd_of(rows, key, **cond):
    sub = [r for r in rows if all(r.get(k) == v for k, v in cond.items())]
    vals = [r[key] for r in sub if r.get(key) is not None]
    return st.stdev(vals) if len(vals) > 1 else 0.0


def main():
    # ---- 主表（灾强维的 DIS_R=3 子集）----
    sv = load("multi_sev")
    rows = []
    for a in ARMS7:
        s = [x for x in sv if x["dim_val"] == 3 and x["arm"] == a]
        rows.append([SHORT[a],
                     round(st.mean([x["n_up"] for x in s if x["n_up"] is not None]), 1),
                     round(st.mean([x["recon"] for x in s]), 4),
                     round(st.mean([x["t50_cond_s"] for x in s]) / 60.0, 1),
                     round(st.mean([x["sat_all"] for x in s]), 4),
                     round(st.mean([x["dead"] for x in s]), 4)])
    write("main.csv", ["method", "nup", "recon", "t50min", "sat", "dead"], rows)

    # ---- 灾强 ----
    rows = []
    for dv in (2, 3, 4):
        for a in ARMS7:
            rows.append([dv, SHORT[a], round(mean(sv, "recon", dim_val=dv, arm=a), 4)])
    write("severity.csv", ["disr", "method", "recon"], rows)

    # ---- 供给 ----
    sp = load("multi_sup")
    rows = []
    for dv in (0.2, 0.5, 0.8):
        for a in ARMS7:
            rows.append([dv, SHORT[a], round(mean(sp, "recon", dim_val=dv, arm=a), 4)])
    write("supply.csv", ["pup", "method", "recon"], rows)

    # ---- 规模 ----
    sc = load("scale")
    rows = []
    for n in (100, 576):
        for a in ARMS7:
            rows.append([n, SHORT[a], round(mean(sc, "recon", n=n, arm=a), 4)])
    write("scale.csv", ["nodes", "method", "recon"], rows)

    # ---- 二次打击 ----
    rb = load("robust")
    rows = []
    for hp in (0.0, 0.10, 0.20):
        for a in ARMS7:
            s = [x for x in rb if x["hit_p"] == hp and x["arm"] == a]
            rows.append([hp, SHORT[a],
                         round(st.mean([x["recon"] for x in s]), 4),
                         round(st.mean([x["lcc_frac"] for x in s if x["lcc_frac"] is not None]), 4)])
    write("robust.csv", ["hitp", "method", "recon", "lcc"], rows)

    # ---- 长期 ----
    lg = load("long")
    rows = []
    for a in ARMS7:
        s = [x for x in lg if x["arm"] == a]
        rows.append([SHORT[a],
                     round(st.mean([x["recon"] for x in s]), 4),
                     round(st.mean([x["lcc_frac"] for x in s if x["lcc_frac"] is not None]), 4),
                     round(st.mean([x["dead"] for x in s]), 4),
                     round(st.mean([x["energy_per_node"] for x in s]), 2)])
    write("long.csv", ["method", "recon", "lcc", "dead", "energy"], rows)

    # ---- 消融（30 种子）----
    ab = load("abl")
    NAME = {"A_full": "full", "A_noPay": "noPay", "A_noFlow": "noFlow",
            "A_noCarry": "noCarry", "A_noDorm": "noDorm", "A_noArm": "noArm"}
    rows = []
    for k, v in NAME.items():
        s = [x for x in ab if x["arm"] == k]
        rows.append([v,
                     round(st.mean([x["recon"] for x in s]), 4),
                     round(st.mean([x["lcc_frac"] for x in s if x["lcc_frac"] is not None]), 4),
                     round(st.mean([x["serv_ng0"] for x in s]), 1),
                     round(st.mean([x["link_per_serv"] for x in s]), 4)])
    write("ablation.csv", ["config", "recon", "lcc", "servng0", "link"], rows)

    # ---- 机制 × 场景 ----
    ft = load("fit")
    SC = {"S1基线": "base", "S2料稀缺": "mat03", "S3低供给": "pup015", "S4小灾": "disr2"}
    rows = []
    for k, v in SC.items():
        for arm, nm in (("A_full", "full"), ("A_noFlow", "noFlow"),
                        ("A_noCarry", "noCarry"), ("A_noDorm", "noDorm"), ("A_noArm", "noArm")):
            rows.append([v, nm, round(mean(ft, "recon", scene=k, arm=arm), 4)])
    write("fit.csv", ["scene", "arm", "recon"], rows)

    # ---- 调参网格（宽表先出，窄表由宽表回导，保证都是 9 个比值、0.70 不重复）----
    t1, t2 = load("tune"), load("tune2")
    wide = []
    for c in CHPS:
        src = t1 if c <= 0.70 else t2
        wide.append([("%.2f" % c)] + ["%.4f" % mean(src, "recon", mode=m, chp=c) for _, m in MODE])
    with io.open(os.path.join(OUT, "tune_wide.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("chp," + ",".join(n for n, _ in MODE) + "\n")
        for r in wide:
            f.write(",".join(str(x) for x in r) + "\n")
    print("  %-18s %3d 行" % ("tune_wide.csv", len(wide)))

    rows = []
    for j, (nm, _m) in enumerate(MODE):
        for r in wide:
            rows.append([nm, r[0], r[1 + j]])
    write("tune.csv", ["method", "chp", "recon"], rows)

    # ---- 同供给对照 ----
    pq = load("parity")
    rows = []
    for band in ("6口", "43口"):
        for arm, nm in (("B0", "lower"), ("Ours", "ours"),
                        ("LEACH@0.05", "leach005"), ("LEACH@0.50", "leach050")):
            s = [x for x in pq if x["band"] == band and x["arm"] == arm]
            rows.append([band, nm,
                         round(st.mean([x["n_up"] for x in s if x["n_up"] is not None]), 1),
                         round(st.mean([x["recon"] for x in s]), 4),
                         round(st.mean([x["sat_all"] for x in s]), 4)])
    write("parity.csv", ["band", "method", "nup", "recon", "sat"], rows)

    # ---- 宽表（供 pgfplots 直接画线，含 ±1 std 误差棒）----
    REV = {v: k for k, v in SHORT.items()}
    FIELDS = {  # 文件名 -> (数据, 输出列名, json 里作为 x 的字段, 指标, x 取值)
        "sev_wide.csv": (sv, "disr", "dim_val", "recon", [2, 3, 4]),
        "sup_wide.csv": (sp, "pup", "dim_val", "recon", [0.2, 0.5, 0.8]),
        "scale_wide.csv": (sc, "nodes", "n", "recon", [100, 576]),
        "robust_wide.csv": (rb, "hitp", "hit_p", "recon", [0.0, 0.10, 0.20]),
        "robustlcc_wide.csv": (rb, "hitp", "hit_p", "lcc_frac", [0.0, 0.10, 0.20]),
    }
    for fn, (rows_, col, field, key, xs) in FIELDS.items():
        with io.open(os.path.join(OUT, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(",".join([col] + SH + ["e" + k for k in SH]) + "\n")
            for x in xs:
                row = [str(x)]
                row += ["%.4f" % mean(rows_, key, **{field: x}, arm=REV[k]) for k in SH]
                row += ["%.4f" % sd_of(rows_, key, **{field: x}, arm=REV[k]) for k in SH]
                f.write(",".join(row) + "\n")
        print("  %-18s %3d 行" % (fn, len(xs)))

    print("完成 →", OUT)


if __name__ == "__main__":
    main()
