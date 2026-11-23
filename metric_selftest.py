# metric_selftest.py —— **度量的准入测试（用已知答案的合成数据验判据实现）**
#
# 为什么有这个东西（2026-11-11 深夜，用户："这种查完推翻的情况太频繁了，质疑质量"）：
#   近九条纪律里 **8 条是"尺子"问题**（分母、窗口、单位、阈值、判据对象、计数器开关），只有 1 条是"行为"问题。
#   ⇒ 不是机制理解不牢，是**度量的实现从来没被验收过**：判据写了，但"判据用的那个量算得对不对"没人验。
#   所以每次验收都发生在"结论要写出去"的那一刻，表现出来就是"查完就推翻"。
#
# 这个文件是根治办法的一半：**任何新指标上线前，先在一份答案已知的合成数据上跑通**。
#   · 合成数据＝我们自己造的序列（已知掉多少、第几步恢复、哪几步窗关），答案写在注释里；
#   · 跑不过 ⇒ 不许用于结论；跑过 ⇒ 才允许进驱动。
#
# 用法：`python metric_selftest.py`（不跑仿真，秒级）

import sys

from v198_drv import half, half_open


def check(name, got, want, tol=1e-9):
    if want is None:
        ok = got is None
    elif isinstance(want, int) and not isinstance(want, bool):
        ok = got == want
    elif isinstance(want, bool):
        ok = bool(got) == want
    else:
        ok = (got == got) and abs(got - want) <= tol
    print("  %-46s got %-8s want %-8s %s" % (name, got, want, "PASS" if ok else "**FAIL**"))
    return ok


def main():
    allok = True
    print("=== A. 无窗关时的半衰（真值：第 2 步回到一半）===")
    off = [0.80] * 12
    on = [0.20, 0.30, 0.55, 0.70, 0.80] + [0.80] * 7
    # g = 0.60, 0.50, 0.25, 0.10, 0.00 …；阈值 0.5×0.60＝0.30 ⇒ 第一个 ≤0.30 在 index 2
    h, d0, net = half(on, off)
    allok &= check("half() 半衰", h, 2)
    allok &= check("half() 首步落差", d0, 0.60)

    print("\n=== B. 有窗关步时：旧 half() 会被骗，half_open() 不会（真值：第 2 个开步）===")
    # 灾后第 0 步开、第 1–2 步关、第 3 步开…
    cap = [1, 0, 0, 1, 1, 1, 1, 1, 1, 1]
    off2 = [0.80, 0.00, 0.00, 0.80, 0.80, 0.80, 0.80, 0.80, 0.80, 0.80]
    on2 = [0.20, 0.00, 0.00, 0.50, 0.78, 0.80, 0.80, 0.80, 0.80, 0.80]
    # 开步序列：g = 0.60（开）、0.30（第 2 个开）、0.02 …；阈值 0.30 ⇒ 第 2 个开步（index 1）
    h_old, _, _ = half(on2, off2)
    h_new, d0n, _, nopen = half_open(on2, off2, cap)
    allok &= check("half_open() 半衰（开步序）", h_new, 1)
    allok &= check("half_open() 开步数", nopen, 8)
    # 旧 half() 在 index 1 就判"回到一半"——那一步是**窗关**（两臂都是 0），正是 v194–v196 的 bug。
    print("    旧 half() 给出 %s（＝第 1 步、一个窗关步）——正是 v194–v196 的 bug" % (h_old,))
    allok &= check("旧口径确实会错（回归哨兵：应为 1）", h_old, 1)

    print("\n=== C. 分母随死亡缩小 vs 固定队列（真值：10 死 2，服务率 8/10＝0.8）===")
    # 队列 10 人，其中 2 人退出；被服务的仍是那 8 个活着的
    alive, served = 8, 8
    old_ratio = served / alive          # 旧口径：分母只剩活人
    fixed = served / 10.0               # 固定队列：死了算未服务
    allok &= check("旧口径（分母随死缩）", old_ratio, 1.0)
    allok &= check("固定队列", fixed, 0.8)
    print("    ⇒ 旧口径比真值高 %.0f%%（人一死，比率反而升）" % (100 * (old_ratio / fixed - 1)))

    print("\n=== D. 两量并报（快慢 + 末态水平）：半衰快不等于恢复好 ===")
    # 甲：掉得猛、回得快，但**回到一半就卡住**（末态仍差一截）
    # 乙：掉得同样猛、回得慢，但**真的回满**
    off3 = [0.80] * 30
    jia = [0.20, 0.55, 0.55] + [0.55] * 27     # g: .6 .25 .25 … ⇒ 半衰 1，末态 0.55
    yi = [0.20, 0.35, 0.45, 0.52] + [0.80] * 26  # g: .6 .45 .35 .28 .0 … ⇒ 半衰 3，末态 0.80
    hj, dj, _ = half(jia, off3)
    hy, dy, _ = half(yi, off3)
    print("    甲：落差 %.2f、半衰 %s、末态 %.2f" % (dj, hj, jia[-1]))
    print("    乙：落差 %.2f、半衰 %s、末态 %.2f" % (dy, hy, yi[-1]))
    allok &= check("甲半衰更快", (hj if hj is not None else 99) < (hy if hy is not None else 99), True)
    allok &= check("但甲末态更差", jia[-1] < yi[-1], True)

    print("\n=== E. 末态水平 L（v198 起的第二个主指标）：只看窗口尾部，不看去程 ===")
    jia2 = [0.20] + [0.55] * 39          # 掉得猛、回到一半就卡住
    yi2 = [0.20, 0.35, 0.45, 0.52] + [0.80] * 36   # 掉得猛、真的回满
    L_jia = sum(jia2[-10:]) / 10.0
    L_yi = sum(yi2[-10:]) / 10.0
    allok &= check("L 甲（卡在 0.55）", L_jia, 0.55)
    allok &= check("L 乙（回满 0.80）", L_yi, 0.80)
    allok &= check("L 能分出半衰分不出的差别", L_yi > L_jia, True)
    print("    ⇒ 只报半衰时甲乙都算'恢复了'；L 才看得出甲是永久降级")

    print("\n=== F. 乘客被覆盖比例 `cov_ratio`（v218 新指标，答案手算在注释里）===")
    # 3×3 环面，i = r*3+c；邻居（上/下/左/右）
    n3 = 9
    nbr3 = []
    for i in range(n3):
        r, c = divmod(i, 3)
        nbr3.append([((r - 1) % 3) * 3 + c, ((r + 1) % 3) * 3 + c,
                     r * 3 + (c - 1) % 3, r * 3 + (c + 1) % 3])
    mk = lambda s: [i in s for i in range(n3)]
    import engine
    # ① 乘客只有中心 4，送到 1（4 的上邻居）⇒ 1/1 = 1.0
    allok &= check("乘客1人被覆盖", engine.cov_ratio(mk({4}), {1}, nbr3, n3), 1.0)
    # ② 乘客只有中心 4，送到 0（4 的邻居是 1,7,3,5；0 不在其中）⇒ 0.0
    allok &= check("乘客1人没被覆盖", engine.cov_ratio(mk({4}), {0}, nbr3, n3), 0.0)
    # ③ 乘客 {0,8}，送到 1：0 的邻居含 1（上/下是 3,6；左/右是 2,1）⇒ 覆盖；
    #    8 的邻居是 5,2,7,6（无 1）⇒ 不覆盖 ⇒ 1/2 = 0.5
    allok &= check("乘客2人覆盖一半", engine.cov_ratio(mk({0, 8}), {1}, nbr3, n3), 0.5)
    # ④ 没有乘客 ⇒ None，**不是 0**（"没人"与"有但没盖到"必须分开）
    allok &= check("没有乘客返回 None", engine.cov_ratio(mk(set()), {1}, nbr3, n3), None)
    # ⑤ 反面：若实现误把"乘客自己所在的位置"当成覆盖（送去给他本人），②会变 1.0
    allok &= check("送到乘客本人 ≠ 被覆盖", engine.cov_ratio(mk({4}), {4}, nbr3, n3), 0.0)

    print("\n%s" % ("全部 PASS" if allok else "**有 FAIL，指标不许用于结论**"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
