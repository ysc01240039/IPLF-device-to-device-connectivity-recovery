# -*- coding: utf-8 -*-
"""_verify_engine.py —— 复现自检：12 个种子必须与随文发布的原始结果逐位相同。

判据（先写，后跑）：
  · 对 `data/exp_v245_main.json` 里的 `Ours` 臂，取种子 1..12 重跑一遍；
  · 六个上报量（recon / t50_cond_s / sat_all / dead / lcc_frac / energy_per_node）
    必须与存档值**完全相等**（不是近似）；任一条不等 ⇒ 打印差异并退出码 1。
  · 再跑一个"只改一个旋钮"的臂（把单次计费换成双边计费），确认输出**真的会动**——
    否则"全部相同"也可能只是自检没生效。

用法：python _verify_engine.py [--seeds 12]
约 1 分钟（每种子 2–4 秒）。
"""
import argparse
import io
import json
import os
import sys

import exp_v245 as X

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ("recon", "t50_cond_s", "sat_all", "dead", "lcc_frac", "energy_per_node")


def load_ref():
    p = os.path.join(HERE, "data", "exp_v245_main.json")
    with io.open(p, encoding="utf-8") as f:
        rows = json.load(f)
    return {r["seed"]: r for r in rows if r["arm"] == "Ours"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=12)
    a = ap.parse_args()
    ref = load_ref()

    fail = 0
    for sd in range(1, a.seeds + 1):
        if sd not in ref:
            print("  seed %d: 存档里没有这一行" % sd)
            fail += 1
            continue
        got = X.run_cell("Ours", sd)
        bad = [k for k in KEYS if got[k] != ref[sd][k]]
        if bad:
            fail += 1
            print("  seed %d: **FAIL** %s" % (sd, ", ".join(bad)))
            for k in bad:
                print("      %-16s got %r  want %r" % (k, got[k], ref[sd][k]))
    print("W1 逐位复现：%d/%d seeds" % (a.seeds - fail, a.seeds))

    # 能力检查：改一个旋钮，输出必须动
    X.ARMS["_probe"] = dict(X.ARMS["Ours"])
    X.ARMS["_probe"]["ONE_SIDE"] = 0          # 单次计费 → 双边计费
    probe = X.run_cell("_probe", 1)
    base = X.run_cell("Ours", 1)
    moved = probe["recon"] != base["recon"]
    print("W2 能力检查：ONE_SIDE 1→0 时 recon %s（%s）"
          % ("变化" if moved else "不变",
             "%.4f → %.4f" % (base["recon"], probe["recon"])))
    if not moved:
        fail += 1

    if fail:
        print("**有 %d 项不通过**" % fail)
        sys.exit(1)
    print("全部通过：重跑与存档逐位相同，且自检对旋钮敏感。")


if __name__ == "__main__":
    main()
