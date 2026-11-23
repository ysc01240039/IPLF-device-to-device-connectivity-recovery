# -*- coding: utf-8 -*-
"""exp_v245 —— 实验章全套矩阵（对齐同类高质量论文的结构）

依据（检索核验，2026-11-22）：
  · O-T-A + Taguchi（*Computing* 108(5), 2026）：灾后 D2D 聚类，1000 节点 / 500×500 m²，
    One-at-a-Time 敏感性 + Taguchi L25，报 FND／能耗／生存性／时延／吞吐。
  · AFPUC（*Telecommun. Syst.* 89(3), 2026）：稀疏/稠密两档，6 个 SOTA 对照，**ANOVA + Tukey HSD，p<0.001**。
  · DK-means-LEACH-IED（*Eng. Res. Express* 2026）：100 节点，**30 次重复 + 95% CI**，
    并做"网络规模／初始能量／节点数／负载／汇聚点位置"的多条件稳健性。
  · HHLO（*Technologies* 14(2) 109）：**30 independent runs + Student t-test，p<0.01**，
    多指标含**控制开销比 COR**。
  · Jamming mitigation（*Algorithms* 18(10) 614）：**逐项 component ablation**、
    **阈值 ±1σ/±2σ 敏感性**、**可扩展性 N∈{25,50,100} + Mann–Whitney/Kruskal–Wallis**。

本脚本按上述五件套组织：主对比 / 消融 / 敏感性 / 灾强 / 规模，全部 30 种子、配对检验。

**场景（对齐文献）**
  · 主场景：10×10 格＝**100 台**，格距 50 m ⇒ **500×500 m、400 台/km²**
    （BIAFTEL 下限 400／O-T-A 4000／Sci Rep 20–2000，取文献下限）
  · 灾盘半径 3 格＝**150 m**（按 500 m 场地比例）
  · 步长 120 s，灾后 180 步＝**6 h**（文献 1000–3600 s，我们更长，另报前 1 h 段）
  · 规模稳健：24×24＝**576 台**，格距 100 m ⇒ 2.4×2.4 km（我们原规模，密度同为 100 台/km²）

**判据（先写，后跑）**
  W1 接线：每组的自变量必须让至少一个指标动；全不动＝没接上。
  W2 主判据：`Ours` 的 `recon` 高于 `B0`，配对 95% CI 不含 0。
  W3 诚实：`LEACH`（同供给版 CH_P=0.5）若高于 `Ours`，明写"纯建链层不优于聚类调度"。
  W4 消融：每项关掉后 `recon` 必须下降；不降＝该机制未生效（不是"没价值"）。
  W5 守恒：`dead+recon ≤ 1`。

用法：python exp_v245.py --group main|sens|scale
"""
import argparse
import io
import json
import math
import os
import statistics as st
import sys

import engine
import mainline
import metrics

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDS = list(range(1, 31))
T95 = {29: 2.045, 14: 2.145, 11: 2.201}

METRICS = ["recon", "t50_cond_s", "sat_all", "dead", "energy_per_node", "link_per_serv"]


# ---------------- 世界 ----------------
def base_world(eng, n=10, dis_r=3):
    engine.reset()
    if n != 24:
        engine.set_grid(n)
    mainline.apply(eng)
    mainline.apply_real(eng)
    mainline.apply_dis(eng, "T4")
    eng.DIS_R = dis_r
    eng.ROUTE_MODE = 2
    eng.P_UP = 0.50
    eng.ROOT_SHARE = 1
    eng.MAX_HOP = 6
    eng.DEM_ALL = 1
    eng.ALLOW_UNJOINED = 1
    eng.TOTAL = 278
    eng.Q_MAX = 20.0
    eng.QUERY_PERIOD = 0


# ---------------- 臂 ----------------
# 每条：建链层 + 对天层
ARMS = {
    # 主对比
    "B0":       dict(ONE_SIDE=0),
    "Ours":     dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=1),
    "LEACH":    dict(ONE_SIDE=0, LEACH=1, CH_MODE=0, CH_P=0.50),
    "FLOOD":    dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=1, MULTI_ARM_SRC=1, K_ARMS=99, EXPLORE=1.0),
    # 消融（在 Ours 基础上逐项关）
    "A_full":   dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=1, MULTI_ARM_SRC=1, K_ARMS=4,
                     DORM_ON=1, AUTO_IDLE=60),
    "A_noPay":  dict(ONE_SIDE=0, MAT_FLOW=1, CARRY=1, MULTI_ARM_SRC=1, K_ARMS=4,
                     DORM_ON=1, AUTO_IDLE=60),
    "A_noFlow": dict(ONE_SIDE=1, MAT_FLOW=0, CARRY=1, MULTI_ARM_SRC=1, K_ARMS=4,
                     DORM_ON=1, AUTO_IDLE=60),
    "A_noCarry": dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=0, MULTI_ARM_SRC=1, K_ARMS=4,
                      DORM_ON=1, AUTO_IDLE=60),
    "A_noDorm": dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=1, MULTI_ARM_SRC=1, K_ARMS=4,
                     DORM_ON=0, AUTO_IDLE=60),
    "A_noArm":  dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=1, MULTI_ARM_SRC=0, K_ARMS=1,
                     DORM_ON=1, AUTO_IDLE=60),
}


def run_cell(arm, seed, n=10, dis_r=3, p_up=0.50, max_hop=6):
    base_world(engine, n, dis_r)
    engine.P_UP = p_up
    engine.MAX_HOP = max_hop
    for k, v in ARMS[arm].items():
        setattr(engine, k, v)
    r = engine.run_one(list(mainline.job(seed, engine)))
    d = metrics.standard(r)
    # 2026-11-22：把开销拆成两个**口径清楚**的量（原 `overhead_ratio` 只含探路＋伸手，
    # 漏了实际建链数 ⇒ 洪泛臂建 1199 条链却只记 43 次尝试，开销被严重低估）。
    _probe = float(r.get("nbr_probe", 0.0))
    _link = float(r.get("link_a", 0)) + float(r.get("link_b", 0))
    _serv = max(1e-9, float(r.get("serv", 0.0)))
    # `serv_ng0`：灾前**未**并网者拿到的服务量。委付（CARRY）的宣称就是服务这批人，
    # 而 `recon`/`sat_all` 的分母是灾前已并网队列 ⇒ 它们在结构上看不见委付。
    # 实测：g0 只占灾后全部服务量的 25%，所以这个口径不是边角料。
    _post = float(r.get("serv_post", 0.0))
    _g0 = float(r.get("serv_g0_post", 0.0))
    d.update(probe=_probe, link_n=_link, serv=_serv,
             probe_per_serv=_probe / _serv, link_per_serv=_link / _serv,
             serv_ng0=max(0.0, _post - _g0), serv_g0=_g0, serv_post=_post)
    d.update(arm=arm, seed=seed, n=n * n, dis_r=dis_r, p_up=p_up, max_hop=max_hop,
             e_init=tuple(round(x, 1) for x in engine.E_INIT))
    return d


# ---------------- 统计 ----------------
def ci95(xs, n_t=None):
    n = len(xs)
    if n < 2:
        return float("nan")
    t = T95.get(n - 1, n_t or 2.0)
    return t * st.stdev(xs) / math.sqrt(n)


def paired(a, b, key):
    """同种子配对：返回 (均值差, 95%CI, 为正的比例, Cohen's d)。"""
    kk = sorted(set(a) & set(b))
    ds = [a[k][key] - b[k][key] for k in kk]
    if len(ds) < 2:
        return (float("nan"),) * 4
    m = st.mean(ds)
    sd = st.stdev(ds)
    ci = T95.get(len(ds) - 1, 2.0) * sd / math.sqrt(len(ds))
    return m, ci, sum(1 for x in ds if x > 0) / len(ds), (m / sd if sd > 1e-12 else float("inf"))


def summarize(rows, label):
    arms = sorted({r["arm"] for r in rows})
    print("\n--- %s ---" % label)
    print("  %-10s %8s %8s %8s %8s %10s %10s %8s" % (
        "臂", "接回", "末态分量", "分量数", "非g0服务", "t50(分)", "建链/当量", "探测/当量"))
    for a in arms:
        sub = [r for r in rows if r["arm"] == a]
        print("  %-10s %8.4f %8.3f %8.1f %8.1f %10.1f %10.4f %8.4f" % (
            a,
            st.mean([x["recon"] for x in sub]),
            st.mean([x["lcc_frac"] for x in sub if x["lcc_frac"] is not None]),
            st.mean([x["n_comp"] for x in sub if x["n_comp"] is not None]),
            st.mean([x["serv_ng0"] for x in sub]),
            st.mean([x["t50_cond_s"] for x in sub]) / 60.0,
            st.mean([x["link_per_serv"] for x in sub]),
            st.mean([x["probe_per_serv"] for x in sub])))
    first = [r for r in rows if r["arm"] == arms[0]]
    print("  %-10s %8.4f %8s %10.4f %8.4f %8.2f %10s" % (
        "(±95CI)", ci95([x["recon"] for x in first]), "",
        ci95([x["sat_all"] for x in first]), ci95([x["dead"] for x in first]),
        ci95([x["energy_per_node"] for x in first]), ""))
    return arms


def report_paired(rows, a, b, keys=("recon", "t50_cond_s", "sat_all", "energy_per_node")):
    A = {r["seed"]: r for r in rows if r["arm"] == a}
    B = {r["seed"]: r for r in rows if r["arm"] == b}
    for k in keys:
        m, ci, pos, d = paired(A, B, k)
        star = "★" if abs(m) > ci else " "
        print("    %s−%s %-15s = %+9.4f ± %.4f  (%2.0f%% 为正) d=%+.2f %s"
              % (a, b, k, m, ci, pos * 100, d, star))


# ---------------- 组 ----------------
def grp_main():
    rows = []
    for arm in ("B0", "Ours", "LEACH", "FLOOD"):
        for sd in SEEDS:
            rows.append(run_cell(arm, sd))
        print("  [main] %s 完成" % arm, flush=True)
    summarize(rows, "E1 主对比（100 台 / 灾盘 150 m / 30 种子）")
    for x in ("LEACH", "FLOOD"):
        report_paired(rows, "Ours", x)
    report_paired(rows, "Ours", "B0")
    return rows


def grp_ablation():
    rows = []
    for arm in ("A_full", "A_noPay", "A_noFlow", "A_noCarry", "A_noDorm", "A_noArm"):
        for sd in SEEDS:
            rows.append(run_cell(arm, sd))
        print("  [abl] %s 完成" % arm, flush=True)
    summarize(rows, "E2 消融（Ours 逐项关）")
    # 每项只报它**宣称**的那个维度，外加接回作参照（2026-11-23）：
    #   M1 付费→覆盖；M3 料流→开销/死亡；M4 假死→末态分量；M5 多手→探测开销；委付→非 g0 服务
    PAIRS = {"A_noPay": ("recon", "serv_ng0"),
             "A_noFlow": ("link_per_serv", "dead"),
             "A_noCarry": ("serv_ng0", "recon"),
             "A_noDorm": ("lcc_frac", "n_comp"),
             "A_noArm": ("probe_per_serv", "link_per_serv")}
    for x, keys in PAIRS.items():
        report_paired(rows, "A_full", x, keys=keys)
    return rows


def grp_sens():
    rows = []
    for p in (0.2, 0.5, 0.8):
        for sd in SEEDS[:15]:
            for arm in ("B0", "Ours"):
                r = run_cell(arm, sd, p_up=p)
                r["var"] = "P_UP"; r["var_val"] = p
                rows.append(r)
        print("  [sens] P_UP=%.1f 完成" % p, flush=True)
    for h in (4, 6, 8):
        for sd in SEEDS[:15]:
            for arm in ("B0", "Ours"):
                r = run_cell(arm, sd, max_hop=h)
                r["var"] = "MAX_HOP"; r["var_val"] = h
                rows.append(r)
        print("  [sens] MAX_HOP=%d 完成" % h, flush=True)
    print("\n--- E3 敏感性（15 种子）---")
    for v in ("P_UP", "MAX_HOP"):
        for val in sorted({r["var_val"] for r in rows if r["var"] == v}):
            sub = [r for r in rows if r["var"] == v and r["var_val"] == val]
            o = st.mean([r["recon"] for r in sub if r["arm"] == "Ours"])
            b = st.mean([r["recon"] for r in sub if r["arm"] == "B0"])
            print("  %-8s=%-4s  接回 Ours=%.4f  B0=%.4f  Δ=%+.4f" % (v, val, o, b, o - b))
    return rows


def grp_severity():
    rows = []
    for dr in (2, 3, 4):
        for sd in SEEDS:
            for arm in ("B0", "Ours", "LEACH"):
                r = run_cell(arm, sd, dis_r=dr)
                r["var"] = "DIS_R"; r["var_val"] = dr
                rows.append(r)
        print("  [sev] DIS_R=%d 完成" % dr, flush=True)
    print("\n--- E4 灾强（30 种子）---")
    for dr in (2, 3, 4):
        sub = [r for r in rows if r["var_val"] == dr]
        line = "  DIS_R=%d:" % dr
        for arm in ("B0", "Ours", "LEACH"):
            line += "  %s 接回=%.3f sat=%.3f" % (
                arm,
                st.mean([r["recon"] for r in sub if r["arm"] == arm]),
                st.mean([r["sat_all"] for r in sub if r["arm"] == arm]))
        print(line)
    return rows


def grp_scale():
    """规模维：全部方法 × 两档规模（100 台 / 576 台）。FLOOD 不在此表，另用旧组数据说明。"""
    rows = []
    todo = [("下限", "B0", None), ("本方法", "Ours", None)]
    todo += [("%s@%.2f" % (nm, c), "CH:%d" % m, c) for m, nm, c in LIT_BEST]
    for n, dr in ((10, 3), (24, 6)):
        for tag, kind, chp in todo:
            for sd in SEEDS:
                base_world(engine, n, dr)
                if kind.startswith("CH:"):
                    engine.LEACH = 1
                    engine.CH_MODE = int(kind.split(":")[1])
                    engine.CH_P = chp
                    engine.ONE_SIDE = 0
                else:
                    for kk, vv in ARMS[kind].items():
                        setattr(engine, kk, vv)
                r = engine.run_one(list(mainline.job(sd, engine)))
                d = metrics.standard(r)
                d.update(arm=tag, seed=sd, n=n * n)
                rows.append(d)
            print("  [scale] N=%d %s 完成" % (n * n, tag), flush=True)
    print("")
    print("--- 规模维（30 种子，全方法）---")
    print("  %-18s %10s %10s" % ("规模/方法", "接回", "满足率"))
    for n in (100, 576):
        for tag, _, _ in todo:
            sub = [r for r in rows if r["n"] == n and r["arm"] == tag]
            print("  %-18s %10.4f %10.4f" % ("N=%d %s" % (n, tag),
                                             st.mean([r["recon"] for r in sub]),
                                             st.mean([r["sat_all"] for r in sub])))
    return rows


# 文献选头方式（近似实现；CH_MODE 见 engine.py 3530 行起）
#   0=LEACH 随机  1=CFACHS 两级聚类  2=AFPUC 打分取前 k  3=AER-DM 更稀疏  4=AFPUC 局部竞争
CH_MODES = [(0, "LEACH"), (1, "CFACHS"), (2, "AFPUC-k"), (3, "AER-DM"), (4, "AFPUC-loc")]


def grp_lit():
    """E7 文献方法对照：五种选头方式 × 两档簇头比例 × 30 种子。

    两档的理由（RACE 的方法论模板："既按原设计也比同配额"）：
      · `CH_P=0.05`＝各方法的**原设计**（LEACH/AFPUC 原文的 5% 簇头，为延长网络寿命而设）；
      · `CH_P=0.50`＝**同配额**，让对天点数与基线的 `P_UP=0.5` 可比，只比"选头质量"。
    **实现是近似的，不是原文代码**：CFACHS 只做两级半径、AFPUC 用"能量×距重心"打分替代模糊规则、
    AER-DM 用"打分+更稀疏"替代聚合。数值只能读方向，不能当作原文性能。
    """
    rows = []
    for chp in (0.05, 0.50):
        for mode, name in CH_MODES:
            for sd in SEEDS:
                base_world(engine, 10, 3)
                engine.LEACH = 1
                engine.CH_MODE = mode
                engine.CH_P = chp
                r = engine.run_one(list(mainline.job(sd, engine)))
                d = metrics.standard(r)
                _serv = max(1e-9, float(r.get("serv", 0.0)))
                _link = float(r.get("link_a", 0)) + float(r.get("link_b", 0))
                d.update(arm="%s@%.2f" % (name, chp), seed=sd, n=100, dis_r=3,
                         chp=chp, ch_mode=mode, link_per_serv=_link / _serv)
                rows.append(d)
            print("  [lit] %s CH_P=%.2f 完成" % (name, chp), flush=True)
    print("")
    print("--- E7 文献方法（30 种子，100 台）---")
    print("  %-12s %8s %10s %10s %8s" % ("方法", "接回", "首用(分)", "满足率", "死亡"))
    for chp in (0.05, 0.50):
        for mode, name in CH_MODES:
            sub = [r for r in rows if r["arm"] == "%s@%.2f" % (name, chp)]
            print("  %-12s %8.4f %10.1f %10.4f %8.4f" % (
                "%s@%.2f" % (name, chp),
                st.mean([r["recon"] for r in sub]),
                st.mean([r["t50_cond_s"] for r in sub]) / 60.0,
                st.mean([r["sat_all"] for r in sub]),
                st.mean([r["dead"] for r in sub])))
    return rows


def grp_parity():
    """E8 同供给对照：把"能对天的台数"拉平，再比组织方式。

    为什么必须做：聚类族（LEACH/CFACHS/AFPUC/AER-DM）的对天点＝簇头数，
    天然只有基线的 1/4~1/40（实测 100 台里基线 43 个，CFACHS 1 个、AFPUC-loc 4 个、LEACH@0.05 6 个）。
    在"对天点"这个资源上不对等时，接回率的排名没有信息量——它只说明"谁开了更多长距口"。
    本组把 `P_UP` 调到与对手的簇头数相当，只留"怎么组织"这一个变量。

    两档：`P_UP=0.06`（约 6 个对天点，对齐 LEACH 原生 5%）与 `P_UP=0.43`（约 43 个，对齐基线）。
    """
    rows = []
    for p_up, label in ((0.06, "6口"), (0.43, "43口")):
        for arm, chp in (("B0", None), ("Ours", None), ("LEACH", 0.05), ("LEACH", 0.50)):
            for sd in SEEDS:
                base_world(engine, 10, 3)
                engine.P_UP = p_up
                if arm == "LEACH":
                    engine.LEACH = 1
                    engine.CH_MODE = 0
                    engine.CH_P = chp
                    tag = "LEACH@%.2f" % chp
                else:
                    tag = arm
                # 注意：这里**不能用 ARMS["LEACH"]**——它带着 CH_P=0.50，会把上面设的 chp 覆盖掉
                # （2026-11-22 当场踩到：两档 CH_P 跑出逐位相同的结果）。
                if arm != "LEACH":
                    for k, v in ARMS[arm].items():
                        setattr(engine, k, v)
                else:
                    engine.ONE_SIDE = 0
                r = engine.run_one(list(mainline.job(sd, engine)))
                d = metrics.standard(r)
                _serv = max(1e-9, float(r.get("serv", 0.0)))
                _link = float(r.get("link_a", 0)) + float(r.get("link_b", 0))
                d.update(arm=tag, seed=sd, p_up=p_up, n_up=r.get("n_up"),
                         link_per_serv=_link / _serv, band=label)
                rows.append(d)
            print("  [parity] %s %s 完成" % (label, arm), flush=True)
    print("")
    print("--- E8 同供给对照（30 种子，对天点数拉平）---")
    print("  %-12s %8s %8s %10s %10s %8s" % ("档/方法", "对天点", "接回", "首用(分)", "满足率", "死亡"))
    for label in ("6口", "43口"):
        for tag in ("B0", "Ours", "LEACH@0.05", "LEACH@0.50"):
            sub = [r for r in rows if r["band"] == label and r["arm"] == tag]
            if not sub:
                continue
            print("  %-12s %8.1f %8.4f %10.1f %10.4f %8.4f" % (
                label + " " + tag,
                st.mean([r["n_up"] for r in sub if r["n_up"] is not None]),
                st.mean([r["recon"] for r in sub]),
                st.mean([r["t50_cond_s"] for r in sub]) / 60.0,
                st.mean([r["sat_all"] for r in sub]),
                st.mean([r["dead"] for r in sub])))
    return rows


# 机制 × 场景适配矩阵（2026-11-23）
# 每条"适用条件"从机制原理推出，**事前写死**，不是事后挑场景：
#   料流 M3      ：料不够时才借 ⇒ 料稀缺档（MAT_SCALE 低）
#   委付 CARRY   ：有大批未接入者时才托付 ⇒ 低供给档（P_UP 低）
#   假死 M4      ：链多而闲置时才需要回收 ⇒ 小灾档（网更密、链更多）
#   多手 M5      ：候选多、时间紧时才有用 ⇒ 小灾档
FIT_SCENES = {
    "S1基线":   dict(dis_r=3, mat_scale=1.00, p_up=0.50),
    "S2料稀缺": dict(dis_r=3, mat_scale=0.30, p_up=0.50),
    "S3低供给": dict(dis_r=3, mat_scale=1.00, p_up=0.15),
    "S4小灾":   dict(dis_r=2, mat_scale=1.00, p_up=0.50),
}
FIT_ARMS = ["A_full", "A_noFlow", "A_noCarry", "A_noDorm", "A_noArm"]
FIT_SEEDS = list(range(1, 21))


def grp_fit():
    """E9 机制 × 场景：每项只在它**宣称适用**的场景里才该显形，四格全报。

    判据（事前）：某项在它宣称的场景里显著、且在基线场景里也报（不论显著与否），
    才可写"该机制在其适用条件下有效"。只在某一格显著而其余不报＝挑场景。
    """
    rows = []
    for sname, cfg in FIT_SCENES.items():
        for arm in FIT_ARMS:
            for sd in FIT_SEEDS:
                base_world(engine, 10, cfg["dis_r"])
                engine.P_UP = cfg["p_up"]
                engine.MAT_SCALE = cfg["mat_scale"]
                for k, v in ARMS[arm].items():
                    setattr(engine, k, v)
                r = engine.run_one(list(mainline.job(sd, engine)))
                d = metrics.standard(r)
                _serv = max(1e-9, float(r.get("serv", 0.0)))
                _link = float(r.get("link_a", 0)) + float(r.get("link_b", 0))
                _post = float(r.get("serv_post", 0.0))
                _g0 = float(r.get("serv_g0_post", 0.0))
                d.update(arm=arm, seed=sd, scene=sname, mat_scale=cfg["mat_scale"],
                         p_up=cfg["p_up"], dis_r=cfg["dis_r"],
                         link_per_serv=_link / _serv,
                         probe_per_serv=float(r.get("nbr_probe", 0)) / _serv,
                         serv_ng0=max(0.0, _post - _g0))
                rows.append(d)
            print("  [fit] %s %s 完成" % (sname, arm), flush=True)

    print("")
    print("--- E9 机制 × 场景（20 种子）---")
    print("  %-9s %-9s %8s %8s %10s %10s %10s" % (
        "场景", "臂", "接回", "末态分量", "非g0服务", "建链/当量", "探测/当量"))
    for sname in FIT_SCENES:
        for arm in FIT_ARMS:
            sub = [r for r in rows if r["scene"] == sname and r["arm"] == arm]
            print("  %-9s %-9s %8.4f %8.3f %10.1f %10.4f %10.4f" % (
                sname, arm,
                st.mean([r["recon"] for r in sub]),
                st.mean([r["lcc_frac"] for r in sub if r["lcc_frac"] is not None]),
                st.mean([r["serv_ng0"] for r in sub]),
                st.mean([r["link_per_serv"] for r in sub]),
                st.mean([r["probe_per_serv"] for r in sub])))

    print("")
    print("  配对：full − 关掉该项（同场景同种子；★＝CI 不含 0）")
    for sname in FIT_SCENES:
        for arm, key in (("A_noFlow", "link_per_serv"), ("A_noCarry", "serv_ng0"),
                         ("A_noDorm", "lcc_frac"), ("A_noArm", "probe_per_serv")):
            A = {r["seed"]: r for r in rows if r["scene"] == sname and r["arm"] == "A_full"}
            B = {r["seed"]: r for r in rows if r["scene"] == sname and r["arm"] == arm}
            kk = sorted(set(A) & set(B))
            ds = [A[i][key] - B[i][key] for i in kk if A[i][key] is not None and B[i][key] is not None]
            if len(ds) < 2:
                continue
            mm = st.mean(ds)
            ci = 2.093 * st.stdev(ds) / len(ds) ** 0.5      # t(0.975,19)
            print("    %-9s vs %-9s %-14s = %+9.4f ± %.4f %s"
                  % (sname, arm, key, mm, ci, "★" if abs(mm) > ci else ""))
    return rows


# 多场景主结果（2026-11-23）：每个场景跑**全部方法**，不再只跑三臂。
# 文献方法各取两档中较优的一档（"baseline at its best"），并注明：
#   LEACH 0.50(0.460>0.412) / CFACHS 0.50(0.445>0.400) / AFPUC-k 0.05(0.444>0.436)
#   AER-DM 两档相同 0.05 / AFPUC-loc 0.05(0.397>0.395)
# 2026-11-23 更正：原先取"两档中较优"，但调参网格（0.02–0.95 共 10 档）显示
# 各方法的最优档并不是 0.05 或 0.50 —— LEACH 与 CFACHS 的峰在 0.70，AFPUC-k 在 0.50，
# AFPUC-loc 在 0.10，AER-DM 全档相同。按"两档取优"等于把对手调低了（LEACH 0.452 vs 实际 0.490）。
# 现改为**网格最优档**（baseline at its best）。
LIT_BEST = [(0, "LEACH", 0.70), (1, "CFACHS", 0.70), (2, "AFPUC-k", 0.50),
            (3, "AER-DM", 0.05), (4, "AFPUC-loc", 0.10)]

MULTI_DIMS = {
    "sev": ("DIS_R", [2, 3, 4]),
    "sup": ("P_UP", [0.2, 0.5, 0.8]),
}


def grp_multi(dim):
    """多场景主结果：每个场景跑全部方法（文献方法各取两档中较优的一档）。

    2026-11-23 修：内层 `for k, v in ARMS[...]` 曾把外层场景值 `v` 覆盖，
    导致 `dim_val` 全存成参数值、汇总时取不到数据（StatisticsError）。
    """
    vname, vals = MULTI_DIMS[dim]
    rows = []
    todo = [("下限", "B0", None), ("本方法", "Ours", None)]
    todo += [("%s@%.2f" % (nm, c), "CH:%d" % m, c) for m, nm, c in LIT_BEST]

    for sv in vals:
        cfg = dict(dis_r=3, p_up=0.50)
        cfg["dis_r" if vname == "DIS_R" else "p_up"] = sv
        for tag, kind, chp in todo:
            for sd in SEEDS:
                base_world(engine, 10, cfg["dis_r"])
                engine.P_UP = cfg["p_up"]
                if kind.startswith("CH:"):
                    engine.LEACH = 1
                    engine.CH_MODE = int(kind.split(":")[1])
                    engine.CH_P = chp
                    engine.ONE_SIDE = 0
                else:
                    for kk, vv in ARMS[kind].items():
                        setattr(engine, kk, vv)
                r = engine.run_one(list(mainline.job(sd, engine)))
                d = metrics.standard(r)
                _serv = max(1e-9, float(r.get("serv", 0.0)))
                d.update(arm=tag, seed=sd, dim=dim, dim_val=sv,
                         n_up=r.get("n_up"),
                         link_per_serv=(float(r.get("link_a", 0)) + float(r.get("link_b", 0))) / _serv)
                rows.append(d)
            print("  [multi] %s=%s %s 完成" % (vname, sv, tag), flush=True)

    print("")
    print("--- 多场景主结果：%s（30 种子）---" % vname)
    print("  %-18s %8s %8s %10s %8s" % ("%s/方法" % vname, "对天点", "接回", "首用(分)", "满足率"))
    for sv in vals:
        for tag, _, _ in todo:
            sub = [r for r in rows if r["dim_val"] == sv and r["arm"] == tag]
            print("  %-18s %8.1f %8.4f %10.1f %8.4f" % (
                "%s=%s %s" % (vname, sv, tag),
                st.mean([r["n_up"] for r in sub if r["n_up"] is not None]),
                st.mean([r["recon"] for r in sub]),
                st.mean([r["t50_cond_s"] for r in sub]) / 60.0,
                st.mean([r["sat_all"] for r in sub])))
    return rows



def _todo():
    t = [("下限", "B0", None), ("本方法", "Ours", None)]
    t += [("%s@%.2f" % (nm, c), "CH:%d" % m, c) for m, nm, c in LIT_BEST]
    return t


def _apply(tag, kind, chp):
    if kind.startswith("CH:"):
        engine.LEACH = 1
        engine.CH_MODE = int(kind.split(":")[1])
        engine.CH_P = chp
        engine.ONE_SIDE = 0
    else:
        for kk, vv in ARMS[kind].items():
            setattr(engine, kk, vv)


def grp_robust():
    """二次打击鲁棒性：灾后第 120 步再打一次，打的是**入口**（HIT2_MODE=1）。

    为什么打入口：本方法与所有方法的产出上限都由"能对天的台数"决定，
    打入口是唯一直接攻击这个资源的方式；打随机末端对谁都无关痛痒。
    比例 0 / 10% / 20%，30 种子。
    """
    rows = []
    for p in (0.0, 0.10, 0.20):
        for tag, kind, chp in _todo():
            for sd in SEEDS:
                base_world(engine, 10, 3)
                engine.HIT2_AT = 120
                engine.HIT2_P = p
                engine.HIT2_MODE = 1
                _apply(tag, kind, chp)
                r = engine.run_one(list(mainline.job(sd, engine)))
                d = metrics.standard(r)
                d.update(arm=tag, seed=sd, hit_p=p, hit_n=r.get("hit_n"))
                rows.append(d)
            print("  [robust] p=%.2f %s 完成" % (p, tag), flush=True)
    print("")
    print("--- 二次打击鲁棒性（30 种子，打入口）---")
    print("  %-22s %8s %8s %10s" % ("打击比例/方法", "接回", "末态分量", "死亡"))
    for p in (0.0, 0.10, 0.20):
        for tag, _, _ in _todo():
            sub = [r for r in rows if r["hit_p"] == p and r["arm"] == tag]
            print("  %-22s %8.4f %8.3f %10.4f" % (
                "p=%.2f %s" % (p, tag),
                st.mean([r["recon"] for r in sub]),
                st.mean([r["lcc_frac"] for r in sub if r["lcc_frac"] is not None]),
                st.mean([r["dead"] for r in sub])))
    return rows


def grp_tune():
    """baseline 逐档调优：五种选头方式扫 CH_P 七档，取各自的**最优档**。

    为什么必须做：只报两档（0.05／0.50）会被质疑"对手没调到最好"。
    判据：若某方法的最优档不在 0.05 也不在 0.50，主表须改用该档。
    """
    GRID = (0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70)
    rows = []
    for m, nm, _ in LIT_BEST:
        for chp in GRID:
            for sd in SEEDS[:15]:
                base_world(engine, 10, 3)
                engine.LEACH = 1
                engine.CH_MODE = m
                engine.CH_P = chp
                engine.ONE_SIDE = 0
                r = engine.run_one(list(mainline.job(sd, engine)))
                d = metrics.standard(r)
                d.update(method=nm, mode=m, chp=chp, seed=sd)
                rows.append(d)
            print("  [tune] %s CH_P=%.2f 完成" % (nm, chp), flush=True)
    print("")
    print("--- baseline 调参网格（15 种子，接回）---")
    print("  %-11s" % "方法" + "".join("%9s" % ("%.2f" % c) for c in GRID) + "   最优")
    for m, nm, _ in LIT_BEST:
        vals = [st.mean([r["recon"] for r in rows if r["mode"] == m and r["chp"] == c]) for c in GRID]
        best = max(range(len(GRID)), key=lambda i: vals[i])
        print("  %-11s" % nm + "".join("%9.4f" % v for v in vals) +
              "   %.2f (%.4f)" % (GRID[best], vals[best]))
    return rows


def grp_long():
    """长期运行：灾后 12 小时（TOTAL=458），看能耗、死亡与末态连通。

    短窗看的是"能不能接上"，长窗看的是"接上之后撑不撑得住"。
    """
    rows = []
    for tag, kind, chp in _todo():
        for sd in SEEDS:
            base_world(engine, 10, 3)
            engine.TOTAL = 458
            _apply(tag, kind, chp)
            r = engine.run_one(list(mainline.job(sd, engine)))
            d = metrics.standard(r)
            d.update(arm=tag, seed=sd, total=engine.TOTAL)
            rows.append(d)
        print("  [long] %s 完成" % tag, flush=True)
    print("")
    print("--- 长期运行（灾后 12 h，30 种子）---")
    print("  %-18s %8s %8s %10s %10s" % ("方法", "接回", "末态分量", "死亡", "能耗/台"))
    for tag, _, _ in _todo():
        sub = [r for r in rows if r["arm"] == tag]
        print("  %-18s %8.4f %8.3f %10.4f %10.2f" % (
            tag,
            st.mean([r["recon"] for r in sub]),
            st.mean([r["lcc_frac"] for r in sub if r["lcc_frac"] is not None]),
            st.mean([r["dead"] for r in sub]),
            st.mean([r["energy_per_node"] for r in sub])))
    return rows


def grp_tune2():
    """调参网格上沿确认：0.70 是上一轮网格的上界，不能当最优。
    若 0.95 仍更高，说明这一族的"最优"其实是"让更多人对天"，与"选头更好"无关。
    """
    GRID = (0.70, 0.85, 0.95)
    rows = []
    for m, nm, _ in LIT_BEST:
        for chp in GRID:
            for sd in SEEDS[:15]:
                base_world(engine, 10, 3)
                engine.LEACH = 1
                engine.CH_MODE = m
                engine.CH_P = chp
                engine.ONE_SIDE = 0
                r = engine.run_one(list(mainline.job(sd, engine)))
                d = metrics.standard(r)
                d.update(method=nm, mode=m, chp=chp, seed=sd, n_up=r.get("n_up"))
                rows.append(d)
            print("  [tune2] %s CH_P=%.2f 完成" % (nm, chp), flush=True)
    print("")
    print("--- 调参网格上沿（15 种子）---")
    print("  %-11s %9s %9s %9s   对天点(0.95)" % ("方法", "0.70", "0.85", "0.95"))
    for m, nm, _ in LIT_BEST:
        vals = [st.mean([r["recon"] for r in rows if r["mode"] == m and r["chp"] == c]) for c in GRID]
        nu = st.mean([r["n_up"] for r in rows if r["mode"] == m and r["chp"] == 0.95
                      and r["n_up"] is not None])
        print("  %-11s %9.4f %9.4f %9.4f   %.1f" % (nm, vals[0], vals[1], vals[2], nu))
    return rows

GROUPS = {"main": grp_main, "abl": grp_ablation, "sens": grp_sens,
          "sev": grp_severity, "scale": grp_scale, "lit": grp_lit, "parity": grp_parity, "fit": grp_fit, "multi": "MULTI",
          "robust": grp_robust, "tune": grp_tune, "long": grp_long,
          "tune2": grp_tune2}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True, choices=list(GROUPS))
    ap.add_argument("--dim", default="sev", choices=["sev", "sup"])
    a = ap.parse_args()
    print("=== exp_v245 / %s ===" % a.group, flush=True)
    rows = grp_multi(a.dim) if a.group == "multi" else GROUPS[a.group]()
    bad = [r for r in rows if r["dead"] + r["recon"] - 1.0 > 1e-6]
    print("\n  W5 守恒：dead+recon>1 的记录 %d 条" % len(bad))
    # 2026-11-23 修：`multi` 组按两个维度并行跑，文件名必须带维度后缀，
    # 否则后完成的一路会覆盖前一路（当场踩到：sup 覆盖了 sev）。
    _suffix = ("_" + a.dim) if a.group == "multi" else ""
    out = os.path.join(HERE, "exp_v245_%s%s.json" % (a.group, _suffix))
    json.dump(rows, io.open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  已落盘：%s（%d 条）" % (out, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
