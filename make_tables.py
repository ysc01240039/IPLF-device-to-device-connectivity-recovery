# -*- coding: utf-8 -*-
"""make_data.py —— 把实验产物（exp_v245_*.json）导出成论文用的 csv。

为什么单独一步：
  论文里的每张图都从 csv 读，图与数之间只隔一层 `\addplot table`，
  改数据不用改正文；反过来，正文里出现的每个数都能顺着 csv 回到 json 的某一行。

用法：python make_data.py
"""
import io
import json
import os
import statistics as st

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                   "..", "..", "自用原创_光球与光网_20261024",
                                   "前置实验", "生长模型"))
OUT = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT, exist_ok=True)

ARMS7 = ["下限", "本方法", "LEACH@0.70", "CFACHS@0.70", "AFPUC-k@0.50",
         "AER-DM@0.05", "AFPUC-loc@0.10"]
SHORT = {"下限": "lower", "本方法": "ours", "LEACH@0.70": "leach", "CFACHS@0.70": "cfachs",
         "AFPUC-k@0.50": "afpuck", "AER-DM@0.05": "aerdm", "AFPUC-loc@0.10": "afpucloc"}


def load(name):
    return json.load(io.open(os.path.join(SRC, "exp_v245_%s.json" % name), encoding="utf-8"))


def write(fn, header, rows):
    p = os.path.join(OUT, fn)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")
    print("  %-18s %3d 行" % (fn, len(rows)))


def mean(rows, key, **cond):
    sub = [r for r in rows if all(r[k] == v for k, v in cond.items())]
    vals = [r[key] for r in sub if r.get(key) is not None]
    return st.mean(vals) if vals else float("nan")


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

    # ---- 调参网格 ----
    t1, t2 = load("tune"), load("tune2")
    rows = []
    for nm, mode in (("leach", 0), ("cfachs", 1), ("afpuck", 2), ("aerdm", 3), ("afpucloc", 4)):
        for chp in (0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70):
            rows.append([nm, chp, round(mean(t1, "recon", mode=mode, chp=chp), 4)])
        for chp in (0.70, 0.85, 0.95):
            rows.append([nm, chp, round(mean(t2, "recon", mode=mode, chp=chp), 4)])
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

    # ---- 宽表（供 pgfplots 直接画线：每个方法一列，含 ±1 std 误差棒）----
    def sd_of(rows, key, **cond):
        sub = [r for r in rows if all(r[k] == v for k, v in cond.items())]
        vals = [r[key] for r in sub if r.get(key) is not None]
        return st.stdev(vals) if len(vals) > 1 else 0.0

    def wide(fn, xs, keys, getter, sgetter=None):
        hdr = list(keys)
        if sgetter is not None:
            for k in keys[1:]:
                hdr.append("e" + k)
        with io.open(os.path.join(OUT, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(",".join(hdr) + "\n")
            for x in xs:
                row = [str(x)] + [("%.4f" % getter(x, k)) for k in keys[1:]]
                if sgetter is not None:
                    row += [("%.4f" % sgetter(x, k)) for k in keys[1:]]
                f.write(",".join(row) + "\n")
        print("  %-18s %3d 行%s" % (fn, len(xs), " (+std)" if sgetter else ""))

    SH = ["lower", "ours", "leach", "cfachs", "afpuck", "aerdm", "afpucloc"]
    REV = {v: k for k, v in SHORT.items()}

    wide("sev_wide.csv", [2, 3, 4], ["disr"] + SH,
         lambda x, k: 0.0 if k == "disr" else mean(sv, "recon", dim_val=x, arm=REV[k]),
         lambda x, k: 0.0 if k == "disr" else sd_of(sv, "recon", dim_val=x, arm=REV[k]))
    wide("sup_wide.csv", [0.2, 0.5, 0.8], ["pup"] + SH,
         lambda x, k: 0.0 if k == "pup" else mean(sp, "recon", dim_val=x, arm=REV[k]),
         lambda x, k: 0.0 if k == "pup" else sd_of(sp, "recon", dim_val=x, arm=REV[k]))
    wide("scale_wide.csv", [100, 576], ["nodes"] + SH,
         lambda x, k: 0.0 if k == "nodes" else mean(sc, "recon", n=x, arm=REV[k]),
         lambda x, k: 0.0 if k == "nodes" else sd_of(sc, "recon", n=x, arm=REV[k]))
    wide("robust_wide.csv", [0.0, 0.10, 0.20], ["hitp"] + SH,
         lambda x, k: 0.0 if k == "hitp" else mean(rb, "recon", hit_p=x, arm=REV[k]),
         lambda x, k: 0.0 if k == "hitp" else sd_of(rb, "recon", hit_p=x, arm=REV[k]))
    wide("robustlcc_wide.csv", [0.0, 0.10, 0.20], ["hitp"] + SH,
         lambda x, k: 0.0 if k == "hitp" else mean(rb, "lcc_frac", hit_p=x, arm=REV[k]),
         lambda x, k: 0.0 if k == "hitp" else sd_of(rb, "lcc_frac", hit_p=x, arm=REV[k]))


    print("完成 →", OUT)


if __name__ == "__main__":
    main()
