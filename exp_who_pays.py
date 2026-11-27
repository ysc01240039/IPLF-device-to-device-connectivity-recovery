# -*- coding: utf-8 -*-
"""exp_who_pays —— 单次计费下“这笔钱记在谁头上”：发起端 / 两端对半 / 收款端。

与 exp_cost_parity 的 2×2 配套：
  单次计费（总额 = 一个端点价）：
      ip lf      ONE_SIDE=1  发起端付自己的 c_i
      split      ONE_SIDE=3  两端各付 c_i/2
      rpp        ONE_SIDE=6  收款端付自己的 c_j（发起端免费）
  两次计费（总额 = 两端价之和）：
      bilateral  ONE_SIDE=0  各付自己那份
      balanced   ONE_SIDE=4  两端各付 (c_i+c_j)/2
      iplf_full  ONE_SIDE=2  发起端付整条链

用法：python exp_who_pays.py --credit 1 [--json out.json]
"""
import argparse
import json
import statistics as st

import engine
import mainline
import metrics

ARMS = [("bilateral", 0), ("balanced_full", 4), ("iplf_full", 2),
        ("rpp", 6), ("split", 3), ("iplf", 1)]


def run(one_side, seed, credit=1.0):
    engine.reset()
    engine.set_grid(10)
    mainline.apply(engine)
    mainline.apply_real(engine)
    mainline.apply_dis(engine, "T4")
    engine.DIS_R = 3
    engine.ROUTE_MODE = 2
    engine.P_UP = 0.5
    engine.ROOT_SHARE = 1
    engine.MAX_HOP = 6
    engine.DEM_ALL = 1
    engine.ALLOW_UNJOINED = 1
    engine.Q_MAX = 20.0
    engine.QUERY_PERIOD = 0
    engine.MAT0 = tuple(v * credit for v in engine.MAT0)
    engine.ONE_SIDE = one_side
    engine.MAT_FLOW = 1
    engine.CARRY = 1
    # 2026-11-27：与 exp_v245.base_world 对齐——灾前锁定中性配置，各臂共用同一个灾前世界，
    # 否则本脚本复现的是 11-26 那一轮的旧数（IPLF 70.6 而非论文的 72.9）。
    engine.FREEZE_PRE = 1
    r = engine.run_one(list(mainline.job(seed, engine)))
    d = metrics.standard(r)
    return dict(recon=d["recon"], sat=d["sat_all"], t50=d["t50_cond_s"],
                links=r["link_a"] + r["link_b"], paid=engine._PAID["amt"],
                paid_n=engine._PAID["n"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--credit", type=float, default=1.0)
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    seeds = list(range(1, a.seeds + 1))

    out = {}
    for name, os_ in ARMS:
        rows = [run(os_, s, a.credit) for s in seeds]
        out[name] = {k: [x[k] for x in rows] for k in ("recon", "sat", "t50", "links", "paid", "paid_n")}
        print("done " + name, flush=True)

    if a.json:
        json.dump(dict(credit=a.credit, seeds=seeds, arms=out), open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False)

    print("\ncredit x%g, %d seeds" % (a.credit, len(seeds)))
    print("%-13s %6s %5s %6s %8s %9s" % ("arm", "recon", "sd", "sat", "links", "credit/lnk"))
    for name, _ in ARMS:
        v = out[name]
        print("%-13s %5.1f%% %5.1f %5.1f %8.1f %9.2f" %
              (name, 100 * st.mean(v["recon"]), 100 * st.stdev(v["recon"]),
               100 * st.mean(v["sat"]), st.mean(v["links"]),
               st.mean([p / max(1, n) for p, n in zip(v["paid"], v["paid_n"])])))


if __name__ == "__main__":
    main()
