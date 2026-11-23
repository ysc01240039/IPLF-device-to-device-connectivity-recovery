# v193 驱动：**"料和电到底花在哪"——只加读数，不改任何判定**
#
# 为什么这一版（判断依据，先写）：
#   v192 量出的量级是：总电量 ×0.7 ⇒ `O2p` −20%、末态链 −56%、退出 ×4.4；
#   而"根给谁"只 −4.3%。⇒ **在总量上，能量比调度大一个量级**。
#   那么下一件该问的事不是"再换一种排序量"，而是"**这笔能量花在哪一笔上最值**"。
#   但模型里有两个**互不相通**的存量，不能混着说：
#     · 电量 `energy`（E_INIT）：待机 `C_IDLE`／持链 `deg*C_HOLD`／连天 `C_SKY`／转发 `C_RELAY`
#     · 料   `mat`  （MAT0）  ：建链（`link_cost`，越握越贵）／白跑（`POKE_COST`，主表＝0）／断电退料 REFUND
#   过去所有"省料"的结论（v187/v188）都只动了料的两个出口，而**没说清料在总预算里占多大**；
#   反过来说，"能量比调度大一个量级"里的"能量"到底指哪一个存量，也一直没拆开。
#
# 判据（先写，跑之前定）：
#   W1 **不变性**：本版只加计数器与输出键 ⇒ `O2p` 必须与 v192「A0 满电·不换根」**逐种子逐位相同**。
#      不逐位相同 ⇒ 我改坏了引擎，读数一概作废（不是"结果差不多"，是"应当完全相同"）。
#   W2 **记账自检（不是证据，纪律 29）**：
#      · 电量：四通道之和 = `e_split.init − e_split.now`（相对误差 < 1%）
#      · 料  ：`build − refund + poke` = `m_split.init − m_split.now`（相对误差 < 1%）
#      只为确认计数器接对了位置；它恒成立，证明不了任何结论。
#   W3 **先看分布再看效应**（本项目老坑）：四通道占比与"料的两出口占比"要先看，再谈省哪笔。
#      若某一通道占比 < 5%，那么"省它"即使有效也是零头，不许写成"不小的杠杆"。
#
# 读什么：`e_split`（4 通道 × 死者/生者）、`m_split`（建链/白跑/退料）、`O2p`、`exit`、`edges`。
# 不判什么：本版**不下"哪笔最值"的结论**——那是 v194（半价臂 × 等效总能量）的事。

import json
import statistics as st

import v193
import v178_drv as _V

DT = _V.DT
STEPS = _V.STEPS
PRE = 98
UNIT = DT * 576 / 3600.0
SEEDS = list(range(1, 13))
BASE = {  # v192「A0 满电·不换根」逐种子 o2p，用来做 W1 逐位比对
    "v192A0": None,
}


def setup():
    # 与 v192 的 A0 臂**完全相同**的配置（HET_SPENT=0, ROOT_INFO=0）
    for k, v in dict(P_LOSE=0.0025, PHI=0.30, D_BASIC=0.05, EPS=0.05, MAX_HOP=12,
                     REROUTE=20, GAMMA=0.0, P_KILL_IN=1.0, C_SKY=2.0).items():
        setattr(v193, k, v)
    for k in ("JOIN_CUT", "POKE", "LIT_MODE", "VISION", "FIRSTHIT"):
        setattr(v193, k, 1)
    for k in ("FAIL_MEM", "MEM_W", "MEM_V", "DEM_BURST", "ACTS", "LOOPFIX", "MERGE",
              "DL_ON", "RELAY_PAY"):
        setattr(v193, k, 0)
    v193.EXPLORE = 0.5
    v193.MEM_TTL = 10 ** 9
    v193.MEM_K = 0.25
    v193.REFR_N = 1
    v193.LIT_LO = 0.33
    v193.E_INIT = (24.0, 60.0, 200.0)
    v193.DIS_R = 6
    v193.P_UP = 0.50
    v193.OLD_ADV = 1.0
    v193.NBR_PRIOR = 0.8
    v193.KCHEAP = 1.0
    v193.POKE_COST = 0.0
    v193.SERVE_PAY = 1
    v193.KNOWN_MODE = 1
    v193.HET_SPENT = 0.0
    v193.HET_UNIFORM = 0
    v193.ROOT_INFO = 0
    v193.ROOT_SORT = 0


def job(sd):
    jj = (sd, v193.S0, DT, STEPS, "v193", 1, 1.0, 0.35, 1.0, "thin", 3, v193.DC,
          3.25, 1.0, 1.0, "mix", 0.0, 0, 1, 1.0, 0, 1, 0.39, 0.0, 0.0, 1, 0.5,
          10 ** 9, 1, 1, 0.33, 0.0, 0.0, 0.25, 1, 0.0, 3.0, 0.0, 0, 1, 1,
          0, 0, 0, 0, 1)
    assert len(jj) == 46, len(jj)
    assert jj[2] == DT and jj[40] == 1 and jj[45] == 1
    return jj


def run(seeds=None):
    out = []
    for sd in (seeds or SEEDS):
        r = v193.run_one(job(sd))
        assert r["kn_g"][0] >= 0.0, ("灾没发生", sd)
        e = r["e_split"]
        m = r["m_split"]
        out.append(dict(
            seed=sd,
            o2p=sum(r["R_loc_s"][PRE:]) * UNIT,
            edges=r["n_edges_end"], exit=r["n_exit"], alive=r["n_alive"],
            first=[(st.median(r["first_g%d" % g]) if r["first_g%d" % g] else None)
                   for g in range(3)],
            e_all=e["all_"], e_dead=e["dead"], e_init=e["init"], e_now=e["now"],
            e_post=e["post"], m_post=(m["post_build"], m["post_refund"], m["post_poke"]),
            m_init=m["init"], m_now=m["now"], m_build=m["build"],
            m_refund=m["refund"], m_poke=m["poke"],
            poke_n=r["poke"]["n"], poke_hit=r["poke"]["hit"], poke_miss=r["poke"]["miss"],
            poor=m["poor"], root_steps=e["root_steps"],
        ))
    return out


def rel(a, b):
    return abs(a - b) / max(1e-9, abs(b))


def main():
    setup()
    print("=== v193：料/电花在哪（只加读数；配置＝v192「A0 满电·不换根」）12 种子 ===", flush=True)
    rows = run()

    # ---- W1 不变性：与 v192 A0 逐种子比 ----
    try:
        prev = json.load(open("v192_result.json", encoding="utf-8"))["A0 满电·不换根"]
        pv = {r["seed"]: r["o2p"] for r in prev}
        diff = [abs(r["o2p"] - pv.get(r["seed"], -1)) for r in rows]
        same = all(d == 0.0 for d in diff)
        print("W1 不变性：与 v192 A0 逐种子 %s（最大差 %.3e）"
              % ("逐位相同 ✓" if same else "**不相同 ✗**", max(diff)), flush=True)
    except FileNotFoundError:
        print("W1 不变性：找不到 v192_result.json，跳过", flush=True)

    # ---- W2 记账自检 ----
    print("\nW2 记账自检（恒等式，不是证据）", flush=True)
    eb, mb = [], []
    for r in rows:
        es = sum(r["e_all"])
        eb.append(rel(es, r["e_init"] - r["e_now"]))
        nb = r["m_build"] - r["m_refund"] + r["m_poke"]
        mb.append(rel(nb, r["m_init"] - r["m_now"]))
    print("  电量：|Σ四通道 / (起点−末点) − 1| 中位 %.4f 最大 %.4f"
          % (st.median(eb), max(eb)), flush=True)
    print("  料  ：|建链−退料+白跑 / (起点−末点) − 1| 中位 %.4f 最大 %.4f"
          % (st.median(mb), max(mb)), flush=True)

    # ---- W3 分布 ----
    print("\nW3-a 电量四通道（全期，占已耗电量）", flush=True)
    names = ["待机 C_IDLE", "持链 deg*C_HOLD", "连天 C_SKY", "转发 C_RELAY"]
    tot = [st.mean([r["e_all"][i] for r in rows]) for i in range(4)]
    dead = [st.mean([r["e_dead"][i] for r in rows]) for i in range(4)]
    s_all = sum(tot)
    s_dead = sum(dead)
    print("  %-16s %10s %8s %10s %8s" % ("通道", "合计", "占比", "其中死者", "占死者"), flush=True)
    for i in range(4):
        print("  %-16s %10.1f %7.1f%% %10.1f %7.1f%%"
              % (names[i], tot[i], 100.0 * tot[i] / s_all, dead[i],
                 100.0 * dead[i] / s_dead if s_dead else 0.0), flush=True)

    print("\nW3-b 料的两个出口（全期）", flush=True)
    mb_ = st.mean([r["m_build"] for r in rows])
    mr_ = st.mean([r["m_refund"] for r in rows])
    mp_ = st.mean([r["m_poke"] for r in rows])
    mi_ = st.mean([r["m_init"] for r in rows])
    net = mb_ - mr_ + mp_
    print("  建链 %.1f（毛）／退料 %.1f（%.1f%% 返）／白跑 %.1f ⇒ 净支出 %.1f"
          % (mb_, mr_, 100.0 * mr_ / mb_ if mb_ else 0.0, mp_, net), flush=True)
    print("  期初料 %.1f ⇒ 净支出占期初 %.1f%%；期末余料 %.1f"
          % (mi_, 100.0 * net / mi_, st.mean([r["m_now"] for r in rows])), flush=True)
    pn = st.mean([r["poke_n"] for r in rows]); pm = st.mean([r["poke_miss"] for r in rows])
    print("  白跑次数 %.0f／出手 %.0f（%.1f%%；`POKE_COST=0` ⇒ 这一笔花钱 0，但次数不小）"
          % (pm, pn, 100.0 * pm / pn if pn else 0.0), flush=True)

    print("\nW3-a2 电量四通道（只算灾后恢复期，扣掉灾那一刻的累计）", flush=True)
    pt = [st.mean([r["e_post"][i] for r in rows]) for i in range(4)]
    s_pt = sum(pt)
    print("  %-16s %10s %8s" % ("通道", "灾后累计", "占比"), flush=True)
    for i in range(4):
        print("  %-16s %10.1f %7.1f%%" % (names[i], pt[i], 100.0 * pt[i] / s_pt), flush=True)

    print("\nW3-b2 料的两个出口（只算灾后）", flush=True)
    pb = st.mean([r["m_post"][0] for r in rows])
    prr = st.mean([r["m_post"][1] for r in rows])
    print("  灾后建链 %.1f（毛）／退料 %.1f（%.1f%% 返）⇒ 净 %.1f"
          % (pb, prr, 100.0 * prr / pb if pb else 0.0, pb - prr), flush=True)

    print("\nW3-c 两个存量放在同一把尺子上（都以「期初」归一）", flush=True)
    print("  电量净耗 %.1f（期初 %.1f，占 %.1f%%）"
          % (st.mean([r["e_init"] - r["e_now"] for r in rows]),
             st.mean([r["e_init"] for r in rows]),
             100.0 * st.mean([(r["e_init"] - r["e_now"]) / r["e_init"] for r in rows])), flush=True)
    print("  料净耗   %.1f（期初 %.1f，占 %.1f%%）"
          % (net, mi_, 100.0 * net / mi_), flush=True)

    print("\n主指标（对照 v192 A0：O2p 830.3／末链 698.5／退出 88.8）", flush=True)
    print("  O2p %.1f／末链 %.1f／退出 %.1f／存活 %.1f"
          % (st.mean([r["o2p"] for r in rows]), st.mean([r["edges"] for r in rows]),
             st.mean([r["exit"] for r in rows]), st.mean([r["alive"] for r in rows])), flush=True)
    print("  O1 中位（g0/g1/g2）%s"
          % [round(st.median([r["first"][g] for r in rows if r["first"][g] is not None]), 0)
             for g in range(3)], flush=True)

    json.dump(rows, open("v193_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n已写 v193_result.json", flush=True)


if __name__ == "__main__":
    main()
