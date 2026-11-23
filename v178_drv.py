"""v178 驱动：口径对账——把四条老结论在「方向场」口径下重跑一遍。

## 背景

v168 起把投递从"照 `via` 一条链走"改成"账给方向、自己挑活邻居"（`RETRY=1`），
但 **v135–v156 那一批结论都是在 `RETRY=0` 下量的**，从没在新口径下复核过。
这一步不产新知识，它决定**后面所有读数用哪把尺子**。

## 对账四条（都是 `[仿真]` 级、都进过结论汇总）

1. **账有消耗**（v135/v136）：`MEM_W` 0→0.5。
2. **多星**（v155）：`NSAT` 1→2（`GWCAP=1`）。
3. **横扫**（v153）：`SWEEP` 0→1。
4. **按能力选根**（v156）：`SEL_ROOT` 0→2（0＝随机，2＝按强度）。

## 判据（先写）

- **Q1 消融**：`RETRY=0`、`MEM_W=0`、`NSAT=1`、`SWEEP=0`、`SEL_ROOT=0`、`GWCAP=0` 时，
  8 种子末态链 == v134 主表（`REF`）。这是"我没把引擎改坏"的唯一凭据。
- **Q2 主判据**：对每个旋钮，算 `Δ%` ＝ (B/A−1) 在 `RETRY=0` 与 `RETRY=1` 两个口径下各是多少。
  **符号不同就是"翻号"**——那条结论必须改写；符号相同但幅度差 >50% 的，要标注"幅度依赖口径"。
- **Q3 同报**：末态链、退出。翻号往往先出现在这两个量上。
"""
import json
import statistics

import v175

# ---- 统一配置（与 v168–v177 一致）----
for _k, _v in dict(P_LOSE=0.0025, PHI=0.30, D_BASIC=0.05, EPS=0.05, MAX_HOP=12,
                   REROUTE=20, GAMMA=0.0, P_KILL_IN=1.0, C_SKY=2.0).items():
    setattr(v175, _k, _v)
for _k in ("JOIN_CUT", "POKE", "LIT_MODE", "VISION"):
    setattr(v175, _k, 1)
for _k in ("FAIL_MEM", "MEM_V", "DEM_BURST", "ACTS", "LOOPFIX"):
    setattr(v175, _k, 0.0)
v175.EXPLORE = 0.5
v175.MEM_TTL = 10 ** 9
v175.MEM_K = 0.25
v175.REFR_N = 1
v175.LIT_LO = 0.33
v175.E_INIT = (24.0, 60.0, 200.0)
v175.DIS_R = 6
v175.P_UP = 0.50
v175.DL_ON = 0
v175.MERGE = 0

DT = 120
STEPS = int(round((3.25 + 6.0) * 3600.0 / DT))
PRE = int(round(3.25 * 3600.0 / DT))
N_NODE = 576
UNIT = N_NODE * DT / 3600.0
SEEDS = list(range(1, 13))
REF = {1: 525, 2: 550, 3: 518, 4: 546, 5: 666, 6: 534, 7: 555, 8: 493}


def job(sd, retry=0, gw=0, memw=0.0, nsat=1, sweep=0, sel=0, reach=3):
    """下标注释（与 run_one 的读取一一对应，v148 的错位就是这么来的）。"""
    j = [None] * 46
    j[0] = sd
    j[1] = v175.S0
    j[2] = DT
    j[3] = STEPS
    j[4] = "v178"
    j[5] = 1                # rep
    j[6] = 1.0              # sky_scale
    j[7] = 0.35             # p_adv
    j[8] = 1.0              # e_scale
    j[9] = "thin"           # dis_mode
    j[10] = reach
    j[11] = v175.DC
    j[12] = 3.25            # pre_h
    j[13] = 1.0             # str_w
    j[14] = 1.0             # str_b
    j[15] = "mix"           # ab_mode
    j[16] = 0.0             # w_use
    j[17] = 0               # flat
    j[18] = 1               # k_arms
    j[19] = 1.0             # mat_scale
    j[20] = 0               # up_sticky
    j[21] = 1               # cov_window
    j[22] = 0.39            # VIS_FRAC
    j[23] = 0.0             # cycle
    j[24] = 0.0             # fail_mem
    j[25] = 1               # poke
    j[26] = 0.5             # explore
    j[27] = 10 ** 9         # mem_ttl
    j[28] = 1               # vision
    j[29] = 1               # lit_mode
    j[30] = 0.33            # lit_lo
    j[31] = memw            # mem_w
    j[32] = 0.0             # mem_v
    j[33] = 0.25            # mem_k
    j[34] = 1               # refr_n
    j[35] = 0.0             # dem_burst
    j[36] = 3.0             # dem_burst_h
    j[37] = 0.0             # acts
    j[38] = sweep           # sweep
    j[39] = nsat            # nsat
    j[40] = gw              # gwcap
    j[41] = sel             # sel_root
    j[42] = 0               # loopfix
    j[43] = 0               # prop
    j[44] = 0               # capfix
    j[45] = retry           # retry
    return tuple(j)


def run(cfg, seeds=None):
    rows = []
    for sd in (seeds or SEEDS):
        r = v175.run_one(job(sd, **cfg))
        rows.append(dict(seed=sd, o2p=sum(r["R_loc_s"][PRE:]) * UNIT,
                         edges=r["n_edges_end"], exit=r["n_exit"], cov=r["cov_end"]))
    return rows


def agg(rows, k):
    v = [x[k] for x in rows if x[k] is not None]
    return statistics.mean(v) if v else None


KNOBS = [("账有消耗 MEM_W", dict(memw=0.0), dict(memw=0.5), 1),
         ("多星 NSAT", dict(nsat=1), dict(nsat=2), 1),
         ("横扫 SWEEP", dict(sweep=0), dict(sweep=1), 0),
         ("按能力选根", dict(sel=0), dict(sel=2), 0)]


def main():
    out = {}
    # ---- Q1 消融 ----
    abl = run(dict(retry=0, gw=0), seeds=list(range(1, 9)))
    bad = [(r["seed"], r["edges"], REF[r["seed"]]) for r in abl if r["edges"] != REF[r["seed"]]]
    print("Q1 消融（RETRY=0, GWCAP=0, 其余基线）：%s"
          % ("成立 8/8" if not bad else "**不成立** " + str(bad)), flush=True)
    out["abl"] = abl

    print("\n=== v178 口径对账（随机 74 根，12 种子，每格两口径）===", flush=True)
    print("%-14s %-7s %9s %9s %9s %9s %8s"
          % ("旋钮", "口径", "A", "B", "Δ%", "末链Δ%", "退出Δ"), flush=True)
    for name, a, b, gw in KNOBS:
        rec = {}
        for rt in (0, 1):
            ra = run(dict(a, retry=rt, gw=gw))
            rb = run(dict(b, retry=rt, gw=gw))
            d = agg(rb, "o2p") / agg(ra, "o2p") - 1
            de = agg(rb, "edges") / agg(ra, "edges") - 1
            dx = agg(rb, "exit") / max(1e-9, agg(ra, "exit")) - 1
            rec[rt] = dict(o2p_a=agg(ra, "o2p"), o2p_b=agg(rb, "o2p"), d=d, de=de, dx=dx)
            print("%-14s %-7s %9.1f %9.1f %+8.1f%% %+8.1f%% %+8.1f%%"
                  % (name if rt == 0 else "", "RETRY=%d" % rt,
                     agg(ra, "o2p"), agg(rb, "o2p"), 100 * d, 100 * de, 100 * dx), flush=True)
        out[name] = rec
        flip = (rec[0]["d"] * rec[1]["d"] < 0)
        print("   ⇒ %s（%.1f%% vs %.1f%%）%s"
              % ("**翻号**" if flip else "同号", 100 * rec[0]["d"], 100 * rec[1]["d"],
                 "—— 该结论必须改写口径" if flip else ""), flush=True)

    json.dump(out, open("v178_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n已写 v178_result.json", flush=True)


if __name__ == "__main__":
    main()
