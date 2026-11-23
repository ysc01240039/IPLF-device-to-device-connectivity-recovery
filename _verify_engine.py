# -*- coding: utf-8 -*-
"""_verify_engine.py —— engine.py 与 v216 老路径的**逐位比对**（单一化的验收）。

老路径（v216 驱动的真实做法）：
    _D.setup()                      # v193_drv 的 setup，设一堆模块属性
    for k in dir(v193): setattr(v216, k, ...)   # 全量大写常量覆盖
    mainline.apply(v216)            # 再覆盖两项
    v216.run_one(list(_D.job(sd)))  # 手写的 46 元组
新路径：
    engine.reset()
    engine.run_one(mainline.job(sd, engine))

判据（先写，后跑）：
  · 12 个种子的 `O2p`（= Σ R_loc_s[98:] × UNIT）与 `n_edges_end` **完全相等**（不是"近似"）；
  · 整条 `R_loc_s` 序列**逐元素相等**（这才叫逐位）；
  · 任一条不等 ⇒ 打印第一个不等的位置与前后值，退出码 1。
  另跑一次"engine 里改一个旋钮"的臂，确认新路径**真的会动**——否则"逐位相同"可能只是"两条路都没生效"。
"""
import json
import statistics
import sys

import engine
import mainline
import pmap
import v193
import v193_drv as _D
import v216

UNIT = 120 * 576 / 3600.0
SEEDS = list(range(1, 13))


def _old(sd):
    _D.setup()
    for k in dir(v193):
        if k.startswith("_") or not k.isupper():
            continue
        setattr(v216, k, getattr(v193, k))
    setattr(v216, "EXPLORE", getattr(v193, "EXPLORE"))
    mainline.apply(v216)
    return v216.run_one(list(_D.job(sd)))


def _new(sd):
    engine.reset()
    return engine.run_one(mainline.job(sd, engine))


def _new_knob(sd):
    """能力自检：`P_LOSE` 0.0025→0.02（明显改变行为的一个旋钮）。"""
    engine.reset()
    engine.P_LOSE = 0.02
    return engine.run_one(mainline.job(sd, engine))


def _task(arg):
    which, sd = arg
    fn = {"old": _old, "new": _new, "knob": _new_knob}[which]
    r = fn(sd)
    return dict(which=which, seed=sd, o2p=sum(r["R_loc_s"][98:]) * UNIT,
                edges=r["n_edges_end"], exit=r["n_exit"], r=list(r["R_loc_s"]))


def main():
    tasks = [(w, sd) for w in ("old", "new", "knob") for sd in SEEDS]
    rows = pmap.pmap(_task, tasks)
    by = {}
    for r in rows:
        by.setdefault(r["which"], {})[r["seed"]] = r

    bad = 0
    print("%-4s %10s %10s %8s" % ("seed", "old O2p", "new O2p", "末链差"))
    for sd in SEEDS:
        o, n = by["old"][sd], by["new"][sd]
        d = n["o2p"] - o["o2p"]
        de = n["edges"] - o["edges"]
        seq = "序列同" if o["r"] == n["r"] else "**序列不同**"
        if abs(d) > 1e-9 or de != 0 or o["r"] != n["r"]:
            bad += 1
        print("%-4d %10.3f %10.3f %8d  %s" % (sd, o["o2p"], n["o2p"], de, seq))

    print("\nW1 逐位相同：%d/12 种子" % (12 - bad))
    if bad:
        for sd in SEEDS:
            o, n = by["old"][sd], by["new"][sd]
            if o["r"] != n["r"]:
                for i, (a, b) in enumerate(zip(o["r"], n["r"])):
                    if a != b:
                        print("  seed%d 首个不等 i=%d: old %.9f vs new %.9f" % (sd, i, a, b))
                        break
        print("**✗ 单一化改变了行为，停**")
        sys.exit(1)

    mo = statistics.mean([by["old"][sd]["o2p"] for sd in SEEDS])
    mk = statistics.mean([by["knob"][sd]["o2p"] for sd in SEEDS])
    print("W2 能力自检（防「都没生效」的假通过）：P_LOSE 0.0025→0.02 ⇒ O2p %.1f → %.1f（%+.1f%%）%s"
          % (mo, mk, 100 * (mk - mo) / mo, "✓ 会动" if abs(mk - mo) > 1 else "**✗ 不动，逐位相同不可信**"))
    print("\n✓ engine.py = v216 老路径（逐位相同，12 种子，整条 R_loc_s）")


if __name__ == "__main__":
    main()
