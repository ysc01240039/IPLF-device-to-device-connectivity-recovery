# -*- coding: utf-8 -*-
"""_verify_exp.py —— 论文里每个表/关键数字 vs 原始 JSON 的逐个核对。

用法：python _verify_exp.py            （退出码 0 = 全部对上，1 = 有对不上）
每个检查项给出：论文值、重算值、容差（0.05 = 四舍五入到一位小数）。

注意：这里只核对**能由 JSON 重算**的量；绘图、图注里的定性描述不在范围内。
"""
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

FAIL = []
NCHECK = [0]


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def mean(rows, key, **cond):
    xs = [r[key] for r in rows
          if all(r.get(k) == v for k, v in cond.items()) and r.get(key) is not None]
    return st.mean(xs) if xs else float("nan")


def chk(label, paper, got, tol=0.05):
    NCHECK[0] += 1
    ok = abs(paper - got) <= tol
    if not ok:
        FAIL.append((label, paper, round(got, 4)))
    return ok


def pair(rows, a, b, key="recon", **cond):
    def vals(arm):
        return [r[key] for r in rows if r["arm"] == arm
                and all(r.get(k) == v for k, v in cond.items()) and r.get(key) is not None]
    d = [x - y for x, y in zip(vals(a), vals(b))]
    return st.mean(d), sum(1 for x in d if x > 0), len(d)


# ---------------- 表 II：主对比（多场景 dim=3） ----------------
sv = load("exp_v245_multi_sev.json")
TAB2 = [  # 论文表 II：(臂, recon%, t50min, sat%, dead%)
    ("下限", 41.7, 31.4, 75.9, 22.5),
    ("本方法", 72.9, 23.8, 83.1, 10.9),
    ("LEACH@0.10", 44.1, 25.5, 27.7, 9.9),
    ("CFACHS@0.05", 43.4, 33.9, 4.1, 10.1),
    ("AFPUC-k@0.05", 44.5, 32.9, 7.9, 7.9),
    ("AER-DM@0.02", 42.0, 31.0, 6.7, 8.8),
    ("AFPUC-loc@0.10", 43.4, 32.7, 4.4, 9.6),
]
for arm, rc, t50, sat, dead in TAB2:
    chk("表II %s recon" % arm, rc, 100 * mean(sv, "recon", arm=arm, dim_val=3))
    chk("表II %s t50" % arm, t50, mean(sv, "t50_cond_s", arm=arm, dim_val=3) / 60)
    chk("表II %s sat" % arm, sat, 100 * mean(sv, "sat_all", arm=arm, dim_val=3))
    chk("表II %s dead" % arm, dead, 100 * mean(sv, "dead", arm=arm, dim_val=3))
# 正文：+28.5 点、CI ±4.7、d=2.29、29/30
m, pos, n = pair(sv, "本方法", "AFPUC-k@0.05", dim_val=3)
chk("正文 +28.5 点", 28.5, 100 * m)
chk("正文 29/30 为正", 29, pos, tol=0)

# 表 II 上行终端数
for arm, up in (("下限", 40.8), ("本方法", 40.2), ("LEACH@0.10", 4.8), ("CFACHS@0.05", 0.8),
                ("AFPUC-k@0.05", 2.1), ("AER-DM@0.02", 0.6), ("AFPUC-loc@0.10", 0.9)):
    chk("表II %s uplinks" % arm, up, mean(sv, "n_up", arm=arm, dim_val=3), tol=0.06)

# ---------------- 表 III：计费分解（冻结重跑） ----------------
wp = load("who_pays_1x_frozen.json")["arms"]
TAB3 = [("iplf", 72.9, 3.45), ("rpp", 67.7, 3.44), ("split", 65.9, 3.46),
        ("iplf_full", 29.9, 4.01), ("balanced_full", 38.8, 3.99), ("bilateral", 48.0, 4.04)]
for arm, rc, cl in TAB3:
    chk("表III %s recon" % arm, rc, 100 * st.mean(wp[arm]["recon"]))
    chk("表III %s credit/link" % arm, cl,
        st.mean([p / max(1, q) for p, q in zip(wp[arm]["paid"], wp[arm]["paid_n"])]), tol=0.02)

# 3× / 0.3× 信用档
for fn, single, double in (("who_pays_3x_frozen.json", (99.4, 99.8), (86.7, 97.0)),
                           ("who_pays_03x_frozen.json", (13.5, 15.4), (5.4, 11.4))):
    a = load(fn)["arms"]
    for arm in ("iplf", "rpp", "split"):
        v = 100 * st.mean(a[arm]["recon"])
        chk("%s %s 在 99.4–99.8 / 13.5–15.4 区间" % (fn, arm),
            1 if single[0] - 1.0 <= v <= single[1] + 1.0 else 0, 1, tol=0)
    for arm in ("iplf_full", "balanced_full", "bilateral"):
        v = 100 * st.mean(a[arm]["recon"])
        chk("%s %s 在 86.7–97.0 / 5.4–11.4 区间" % (fn, arm),
            1 if double[0] - 1.0 <= v <= double[1] + 1.0 else 0, 1, tol=0)

# ---------------- 表 IV：同供给对照 ----------------
par = load("exp_v245_parity.json")
TAB4 = [("6口", "B0", 6.1, 40.6), ("6口", "Ours", 5.1, 66.6),
        ("6口", "LEACH@0.05", 0.3, 38.3), ("6口", "LEACH@0.50", 2.6, 37.3),
        ("43口", "B0", 35.9, 42.4), ("43口", "Ours", 34.6, 66.2),
        ("43口", "LEACH@0.05", 2.5, 45.4), ("43口", "LEACH@0.50", 16.4, 44.4)]
for band, arm, up, rc in TAB4:
    chk("表IV %s %s uplinks" % (band, arm), up, mean(par, "n_up", arm=arm, band=band), tol=0.06)
    chk("表IV %s %s recon" % (band, arm), rc, 100 * mean(par, "recon", arm=arm, band=band))

# ---------------- 表 V：五机制消融 ----------------
ab = load("exp_v245_abl.json")
TAB5 = [("A_full", 75.2, 50.9), ("A_noPay", 48.1, 30.8), ("A_noFlow", 64.9, 49.0),
        ("A_noCarry", 74.8, 53.7), ("A_noDorm", 74.9, 49.4), ("A_noArm", 72.9, 53.0)]
for arm, rc, lcc in TAB5:
    chk("表V %s recon" % arm, rc, 100 * mean(ab, "recon", arm=arm))
    chk("表V %s lcc" % arm, lcc, 100 * mean(ab, "lcc_frac", arm=arm))

# ---------------- 表 VI：行为分量（run_comp_ablation.py） ----------------
co = load("exp_v245_comp.json")
TAB6 = [("C_full", 72.9, 23.8, 83.1, 33.21, 51.6),
        ("C_noThick", 75.5, 20.5, 82.2, 34.56, 65.2),
        ("C_noExplore", 75.4, 24.3, 82.5, 33.09, 54.5),
        ("C_noOld", 73.3, 20.4, 83.0, 33.11, 51.8)]
for arm, rc, t50, sat, en, lcc in TAB6:
    chk("表VI %s recon" % arm, rc, 100 * mean(co, "recon", arm=arm))
    chk("表VI %s t50" % arm, t50, mean(co, "t50_cond_s", arm=arm) / 60)
    chk("表VI %s sat" % arm, sat, 100 * mean(co, "sat_all", arm=arm))
    chk("表VI %s energy" % arm, en, mean(co, "energy_per_node", arm=arm), tol=0.02)
    chk("表VI %s lcc" % arm, lcc, 100 * mean(co, "lcc_frac", arm=arm))

# ---------------- 表 VII：机制 × 场景（20 种子） ----------------
fit = load("exp_v245_fit.json")
SCENES = ("S1基线", "S2料稀缺", "S3低供给", "S4小灾")
EXP7 = {  # 机制 → (指标, 四个场景的论文值)
    "credit": ("recon", [11.4, 0.1, 9.5, 2.7]),
    "deleg": ("serv_ng0", [13.9, 156.9, 7.2, 13.1]),
    "demote": ("lcc_frac", [3.2, 0.0, -0.6, -0.7]),
}
for name, (key, vals) in EXP7.items():
    other = {"credit": "A_noFlow", "deleg": "A_noCarry", "demote": "A_noDorm"}[name]
    for sc, v in zip(SCENES, vals):
        got = mean(fit, key, arm="A_full", scene=sc) - mean(fit, key, arm=other, scene=sc)
        scale = 100.0 if key in ("recon", "lcc_frac") else 1.0
        chk("表VII %s %s" % (name, sc), v, scale * got, tol=0.06)

# ---------------- 表 VIII：12 小时 ----------------
lg = load("exp_v245_long.json")
TAB8 = [("下限", 44.0, 8.4, 33.9, 39.46), ("本方法", 74.2, 14.8, 13.2, 40.63),
        ("LEACH@0.10", 47.0, 10.1, 30.7, 37.91), ("CFACHS@0.05", 47.3, 9.5, 30.3, 37.40),
        ("AFPUC-k@0.05", 47.4, 9.6, 29.0, 37.55)]
for arm, rc, lcc, dead, en in TAB8:
    chk("表VIII %s recon" % arm, rc, 100 * mean(lg, "recon", arm=arm))
    chk("表VIII %s lcc" % arm, lcc, 100 * mean(lg, "lcc_frac", arm=arm))
    chk("表VIII %s dead" % arm, dead, 100 * mean(lg, "dead", arm=arm))
    chk("表VIII %s energy" % arm, en, mean(lg, "energy_per_node", arm=arm), tol=0.02)

# ---------------- 结论 ----------------
print("检查项：%d，失败：%d" % (NCHECK[0], len(FAIL)))
for label, paper, got in FAIL:
    print("  ✗ %-32s 论文 %s / 重算 %s" % (label, paper, got))
if FAIL:
    sys.exit(1)
print("全部对上（容差见各表：百分比 0.05、能耗 0.02、计数 0.06）")
