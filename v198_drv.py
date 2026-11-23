# v196 驱动：**恢复为什么只有 3 步？——拆灾的三条损毁通道**
#
# 为什么做（承接 v195）：
#   v195 量到：灾民当场掉 42%，但半衰只要 3 步。为什么这么快？查代码看到两个"太宽松"的地方：
#     ①灾剪链**把料全额退回**（`REFUND=1.0`，基线里标的是"拍"）⇒ 重建几乎是免费的；
#     ②灾**不伤电**（只断链）⇒ 终端还是满状态，伸的资格一点没少。
#   而"伸"花的是**料**、持链花的是**电**（v193 已拆开），所以"恢复快"很可能不是"地网自愈强"，
#   而是**灾本身没摧毁任何东西**。
#
# 做法：把灾拆成三条独立通道，各加一档"重"，看哪一条能把灾民半衰从 3 步拉起来。
#   A0 现灾（断链；退料 100%）          ← 基线，应与 v195 逐位相同
#   A1 断链 + **不退料**（`DIS_REFUND=0`）
#   A2 断链 + **电量骤降 50%**（`DIS_E_LOSS=0.5`）
#   A3 断链 + **料骤降 50%**（`DIS_M_LOSS=0.5`）
#   C  无灾对照（`P_KILL_IN=0`）        ← 反事实基线，所有半衰都以它为参照
#
# 判据（先写）：
#   W1 不变性：A0 的 `O2p` 必须与 v195 有灾臂**逐位相同**（830.3）⇒ 三个新旋钮默认值没改行为。
#   W2 旋钮自检（**读数，不是结果量**）：A1 的 `m_refund` 应≈0（灾那一笔不退）；A2 的 `e_lost`>0 且≈圆盘内电量×0.5；
#      A3 的 `m_lost`>0。任何一项不动 ⇒ 旋钮没接上，读数作废（纪律 98）。
#   W3 记账：`init − now = 四通道 + 灾损失`（电量）／`init − now = 建链 − 退料 + 白跑 + 灾损失`（料），误差应≈0。
#   W4 **主指标**：灾民半衰（步，口径见基线 §15.3b）。判据：
#      · 若三条通道**任一**能把半衰拉到 **≥10 步** ⇒ 恢复有厚度，且知道是哪个资源在起作用，这条线值得做；
#      · 若三条都拉不到 10 步 ⇒ "恢复快"是结构性的（链断了两三步就能重搭），**"恢复"这条线整体降级**。

import json
import statistics as st

import v198
import v193
import v193_drv as _D
import v178_drv as _V

DT = _V.DT
STEPS = _V.STEPS
PRE = _D.PRE
N = 576
UNIT = DT * N / 3600.0
SEEDS = list(range(1, 13))

ARMS = [
    ("A0 现灾", dict(kill=1.0, refund=1.0, el=0.0, ml=0.0)),
    ("A1 不退料", dict(kill=1.0, refund=0.0, el=0.0, ml=0.0)),
    ("A2 电-50%", dict(kill=1.0, refund=1.0, el=0.5, ml=0.0)),
    ("A3 料-50%", dict(kill=1.0, refund=1.0, el=0.0, ml=0.5)),
    ("C  无灾", dict(kill=0.0, refund=1.0, el=0.0, ml=0.0)),
]


def setup():
    _D.setup()
    for k in dir(v193):
        if k.startswith("_") or not k.isupper():
            continue
        setattr(v198, k, getattr(v193, k))
    setattr(v198, "EXPLORE", getattr(v193, "EXPLORE"))


def per_step(x, k=3):
    n = len(x) - len(x) % k
    return [sum(x[i:i + k]) / float(k) for i in range(0, n, k)]


def run_arm(a, seeds):
    v198.P_KILL_IN = a["kill"]
    v198.DIS_REFUND = a["refund"]
    v198.DIS_E_LOSS = a["el"]
    v198.DIS_M_LOSS = a["ml"]
    out = []
    for sd in seeds:
        r = v198.run_one(_D.job(sd))
        out.append(dict(seed=sd, Rin=per_step(r["R_in_s"]), Rout=per_step(r["R_out_s"]),
                        Rcoh=per_step(r["R_coh_s"]), n_coh=r["n_coh"],
                        cap=per_step(r["cap_s"]),
                        n_in=r["n_in"], o2p=sum(r["R_loc_s"][PRE:]) * UNIT,
                        exit=r["n_exit"], edges=r["n_edges_end"], alive=r["n_alive"],
                        n_rec=r["n_rec"], e_lost=r["e_lost"], m_lost=r["m_lost"],
                        m_refund=r["m_split"]["refund"], m_build=r["m_split"]["build"],
                        e_split=r["e_split"], m_split=r["m_split"]))
    return out


def half_open(series, base, cap):
    """只在**两臂都窗开**的步上算缺口与半衰（纪律 97：间歇系统必须先按开/关分期）。

    为什么必须这幺做：窗关时两臂的 R 都是 0 ⇒ 差也是 0 ⇒ 旧的 `half()` 会把它当成"已经恢复"，
    半衰因此被压到 2–3 步（那其实是"下一个窗关步"的位置）。v194–v196 都踩了这个坑。
    """
    idx = [i for i in range(min(len(series), len(base), len(cap))) if cap[i] > 0]
    if len(idx) < 3:
        return None, float("nan"), float("nan"), 0
    g = [base[i] - series[i] for i in idx]
    if g[0] <= 0:
        return None, g[0], sum(g), len(idx)
    hl = next((k for k, x in enumerate(g) if x <= 0.5 * g[0]), None)
    return hl, g[0], sum(g), len(idx)


def half(series, base):
    """灾民半衰：从灾后第 0 步的落差回落到一半所需的步数；没有落差则 None。"""
    g = [b - a for a, b in zip(series, base)]
    if not g or g[0] <= 0:
        return None, (g[0] if g else float("nan")), sum(g)
    hl = next((i for i, x in enumerate(g) if x <= 0.5 * g[0]), None)
    return hl, g[0], sum(g)


def main():
    setup()
    print("=== v198：窗开掩码 + 固定队列(cohort)口径复算灾的三条通道（12 种子）===", flush=True)

    data = {}
    for name, a in ARMS:
        data[name] = run_arm(a, SEEDS)
    ctrl = data["C  无灾"]

    print("\n%-10s %8s %8s %8s %10s %12s %10s" %
          ("臂", "O2p", "末链", "退出", "半衰(旧)", "半衰(cohort)", "掉(cohort)"), flush=True)
    summ = {}
    for name, a in ARMS:
        rows = data[name]
        hl, d0, net = [], [], []
        hl_c, d0_c = [], []
        for r, c in zip(rows, ctrl):
            h, dd, nn = half(r["Rin"], c["Rin"])
            if h is not None:
                hl.append(h)
            d0.append(dd)
            net.append(nn)
            hc, dc, _, nopen = half_open(r["Rcoh"], c["Rcoh"], r["cap"])
            if hc is not None:
                hl_c.append(hc)
            d0_c.append(dc)
        summ[name] = dict(hl=hl, hl_c=hl_c, d0_c=st.mean(d0_c), d0=st.mean(d0), net=st.mean(net),
                          o2p=st.mean([r["o2p"] for r in rows]),
                          edges=st.mean([r["edges"] for r in rows]),
                          exit=st.mean([r["exit"] for r in rows]),
                          alive=st.mean([r["alive"] for r in rows]),
                          e_lost=st.mean([r["e_lost"] for r in rows]),
                          m_lost=st.mean([r["m_lost"] for r in rows]),
                          m_refund=st.mean([r["m_refund"] for r in rows]),
                          m_build=st.mean([r["m_build"] for r in rows]))
        s = summ[name]
        print("%-10s %8.1f %8.1f %8.1f %10s %12s %10.3f"
              % (name, s["o2p"], s["edges"], s["exit"],
                 ("%.1f" % st.median(hl)) if hl else "—",
                 ("%.1f" % st.median(s["hl_c"])) if s["hl_c"] else "—",
                 s["d0_c"]), flush=True)

    print("\nW1 不变性：A0 的 O2p %.1f（v195 有灾臂 830.3）⇒ %s"
          % (summ["A0 现灾"]["o2p"],
             "通过" if abs(summ["A0 现灾"]["o2p"] - 830.33) < 0.05 else "**不通过**"), flush=True)

    print("\nW2 旋钮自检（读数）", flush=True)
    print("  灾剪链退料：A0 %.0f／A1 %.0f ⇒ %s"
          % (summ["A0 现灾"]["m_refund"], summ["A1 不退料"]["m_refund"],
             "A1 已归零 ✓" if summ["A1 不退料"]["m_refund"] < 0.05 * summ["A0 现灾"]["m_refund"] else "**没接上**"), flush=True)
    print("  灾损失电：A2 %.0f（应为圆盘内电量×0.5）；灾损失料：A3 %.0f" %
          (summ["A2 电-50%"]["e_lost"], summ["A3 料-50%"]["m_lost"]), flush=True)

    print("\nW3 记账（误差应≈0）", flush=True)
    for name in ("A0 现灾", "A2 电-50%", "A3 料-50%"):
        rows = data[name]
        de = st.mean([abs(sum(r["e_split"]["all_"]) + r["e_lost"] - (r["e_split"]["init"] - r["e_split"]["now"]))
                      / max(1.0, r["e_split"]["init"] - r["e_split"]["now"]) for r in rows])
        dm = st.mean([abs(r["m_build"] - r["m_refund"] + r["m_split"]["poke"] + r["m_lost"]
                          - (r["m_split"]["init"] - r["m_split"]["now"]))
                      / max(1.0, r["m_split"]["init"] - r["m_split"]["now"]) for r in rows])
        print("  %-10s 电量相对误差 %.5f／料相对误差 %.5f" % (name, de, dm), flush=True)

    print("\nW4 主指标：灾民半衰（步）的分布", flush=True)
    for name, _ in ARMS:
        hl = summ[name]["hl_c"]
        if not hl:
            print("  %-10s 无落差（第0步不掉）" % name, flush=True)
            continue
        print("  %-10s 中位 %.1f／四分位 %s／最大 %d／有解 %d/12"
              % (name, st.median(hl), (sorted(hl)[len(hl) // 4], sorted(hl)[3 * len(hl) // 4]), max(hl), len(hl)), flush=True)

    print("\nW4b 判据：三条通道里有没有一条把半衰拉到 ≥10 步？", flush=True)
    best = max((st.median(summ[n]["hl"]) if summ[n]["hl"] else 0.0, n) for n, _ in ARMS if n != "C  无灾")
    print("  最高的是 %s（中位 %.1f 步）⇒ %s"
          % (best[1], best[0], "**恢复有厚度，值得做**" if best[0] >= 10 else "**三条都拉不到 10 步 ⇒ 恢复这条线整体降级**"), flush=True)

    print("\nW5 对照：非灾民半衰（应≈0）", flush=True)
    for name, _ in ARMS:
        hl = []
        for r, c in zip(data[name], ctrl):
            h, d0, _ = half(r["Rout"], c["Rout"])
            if d0 > 0.02 and h is not None:
                hl.append(h)
        print("  %-10s 有解 %d/12，中位 %s" % (name, len(hl), (st.median(hl) if hl else "—")), flush=True)

    out = {n: [{k: v for k, v in r.items() if k not in ("e_split", "m_split")} for r in rows]
           for n, rows in data.items()}
    json.dump(out, open("v198_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n已写 v198_result.json", flush=True)


if __name__ == "__main__":
    main()
