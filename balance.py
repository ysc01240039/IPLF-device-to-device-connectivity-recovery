# -*- coding: utf-8 -*-
"""balance.py —— 守恒恒等式：注入 = 服务 + 被拒 + 积压 + 溢出（P43）

为什么要这个工具：前面所有的账都是**逐站审**（九个站点、三问），那只能发现"我想到的那几处"。
真正的守卫是**一条恒等式**——差一点就是错，不需要知道错在哪。

口径（写死，别再换）：
  注入(排队) = (dem − rej) + retry_q      ；dem 只记「人的需求」，rej 是被准入闸挡掉的，
                                          retry_q 是重试里**真正进队**的那部分（不是 retry_add）
  流出      = serv + backlog + overflow  ；overflow 是被 `Q_MAX` 挡在队外的
  恒等式    = 注入 − 流出  ≈ 0

`backlog_dead` 单列：死掉的终端留下的积压不算"流出"，它在 backlog 里，但永远不会被服务。
"""
import sys

import engine
import mainline
import metrics

CASES = [
    ("基准", dict()),
    ("ADMIT=0.2", dict(ADMIT=0.2)),
    ("RETRY=0.6", dict(RETRY_P=0.6)),
    ("Q_MAX 收紧", dict(Q_MAX=1.0)),
    ("B 档", dict(_real=True)),
    ("B+限呼+重试", dict(_real=True, ADMIT=0.2, RETRY_P=0.6)),
]


def one(over, seed=1):
    real = over.pop("_real", False)
    engine.reset()
    mainline.apply(engine)
    if real:
        mainline.apply_real(engine)
    mainline.apply_dis(engine, "T4")
    for k, v in over.items():
        setattr(engine, k, v)
    r = engine.run_one(list(mainline.job(seed, engine)))
    inj = (r["dem"] - r["rej"]) + r["retry_add"]   # 呈递量：含被队列上限挡掉的那部分
    out = r["serv"] + r["backlog"] + r["overflow"]  # 溢出单独列
    return inj, out, r


def main():
    bad = 0
    print("=== 守恒检验：注入 = 服务 + 被拒 + 积压 + 溢出 ===")
    for lab, over in CASES:
        inj, out, r = one(dict(over))
        d = inj - out
        rel = d / max(1.0, inj)
        flag = "✓" if abs(rel) < 1e-6 else "**差 %.3f（%.4f%%）**" % (d, 100 * rel)
        print("  %-14s 注入 %9.1f ｜ 流出 %9.1f ｜ %s" % (lab, inj, out, flag))
        print("                  serv %9.1f ｜ 积压 %8.1f（其中死终端 %8.1f）｜ 溢出 %8.1f ｜ 被拒 %8.1f"
              % (r["serv"], r["backlog"], r["backlog_dead"], r["overflow"], r["rej"]))
        if abs(rel) >= 1e-6:
            bad += 1
    print("")
    if bad:
        print("**%d 个工况对不上**：说明还有一处抽出/注入没记账。" % bad)
        return 1
    print("全部对上（容差 1e-6 相对）。**这一条比九个站点更硬：它不需要知道错在哪，差一点就是错。**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
