# -*- coding: utf-8 -*-
"""_check_books.py —— 信用守恒自检（覆盖“退款按实付还是标价”这类账目错）。

恒等式：init − paid + refund − lost − dead = now
  · paid 是实际扣款（_PAID），不是标价（m_build）；两者在单边计费下相差一半。
  · 断链退款、死亡带走、自然损耗都进账。
任何一项记错（例如退款栈记标价、退款下标错位），这里都会差出可观的量。
"""
import sys

import engine
import mainline

TOL = 1e-6


def run(flags, seed):
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
    engine.FREEZE_PRE = 1
    for k, v in flags.items():
        setattr(engine, k, v)
    return engine.run_one(list(mainline.job(seed, engine)))


def check(flags, label, seeds=range(1, 6)):
    worst = 0.0
    for sd in seeds:
        r = run(flags, sd)
        m = r["m_split"]
        lhs = (m["init"] + r.get("m_resup", 0.0) - m["paid"] - m.get("thick_paid", 0.0)
               + m["refund"] - m["lost"])
        diff = lhs - m["now"]
        rel = abs(diff) / max(1.0, m["init"])
        worst = max(worst, rel)
    ok = worst < TOL
    print("  %-18s 相对误差 %.2e  %s" % (label, worst, "✓" if ok else "**✗**"))
    return ok


def main():
    print("=== 信用守恒（init − paid + refund − lost − dead = now）===")
    ok = True
    ok &= check(dict(ONE_SIDE=0), "bilateral")
    ok &= check(dict(ONE_SIDE=1), "IPLF")
    ok &= check(dict(ONE_SIDE=1, MAT_FLOW=1, CARRY=1), "IPLF+transfer+del")
    ok &= check(dict(ONE_SIDE=2), "full-initiator")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
