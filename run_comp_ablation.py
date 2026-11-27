# -*- coding: utf-8 -*-
"""exp_v245_comp —— 行为分量消融（表 VI 的**可复现**来源）。

原来的表 VI（加粗 / 探索 / 旧邻居优先）在交付包里没有对应脚本，数字无法重算。
这里用同一套 base_world（FREEZE_PRE=1）与三机制主配置，只改一个行为开关：
  C_full      : EW_MODE=0, EXPLORE=0.5, OLD_PRIOR=0.8, NBR_PRIOR=0.8
  C_noThick   : EW_MODE=1（禁加束 = 不加粗）
  C_noExplore : EXPLORE=0
  C_noOld     : OLD_PRIOR=0, NBR_PRIOR=0

注意：每个臂都把四个开关**显式写全**，避免上一条臂的赋值漏到下一臂
（engine.reset() 不会还原模块常量）。
"""
import json
import os
import statistics as st
import sys

import exp_v245 as X

ARMS = {
    "C_full":      dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=1, EW_MODE=0, EXPLORE=0.5,
                        OLD_PRIOR=0.8, NBR_PRIOR=0.8),
    "C_noThick":   dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=1, EW_MODE=1, EXPLORE=0.5,
                        OLD_PRIOR=0.8, NBR_PRIOR=0.8),
    "C_noExplore": dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=1, EW_MODE=0, EXPLORE=0.0,
                        OLD_PRIOR=0.8, NBR_PRIOR=0.8),
    "C_noOld":     dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=1, EW_MODE=0, EXPLORE=0.5,
                        OLD_PRIOR=0.0, NBR_PRIOR=0.0),
}
X.ARMS.update(ARMS)

SEEDS = list(range(1, 31))
rows = []
for arm, kv in ARMS.items():
    for sd in SEEDS:
        d = X.run_cell(arm, sd, n=10, dis_r=3, p_up=0.5, max_hop=6)
        rows.append(d)
    print("  [comp] %s done" % arm, flush=True)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exp_v245_comp.json")
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)

print("")
print("--- 行为分量消融（30 配对种子，三机制主配置）---")
print("  %-12s %8s %8s %8s %10s %8s" % ("臂", "接回", "t50", "满意", "能耗/台", "末态分量"))
for arm in ARMS:
    sub = [r for r in rows if r["arm"] == arm]
    print("  %-12s %8.1f %8.1f %8.1f %10.2f %8.1f" % (
        arm,
        100 * st.mean([r["recon"] for r in sub]),
        st.mean([r["t50_cond_s"] for r in sub]) / 60,
        100 * st.mean([r["sat_all"] for r in sub]),
        st.mean([r["energy_per_node"] for r in sub]),
        100 * st.mean([r["lcc_frac"] for r in sub]),
    ))
print("  已落盘：%s（%d 条）" % (out, len(rows)))
