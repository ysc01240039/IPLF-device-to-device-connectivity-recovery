# -*- coding: utf-8 -*-
"""_verify_exp.py —— 实验章（实验.md）里每个数字 vs exp_v245_*.json

为什么单写一个：手写进正文的数字最容易错在"记得的是上一轮的数"。
本脚本把正文的口径重算一遍，逐项断言；任何一项超差就报错，不通过就不算写完。
判据：四舍五入到正文的位数后必须相等（容差 5e-4）。
"""
import io
import json
import statistics as st
import sys

TOL = 6e-4          # 正文按 3 位小写，四舍五入最大误差 5e-4；留一点浮点余量


def load(g):
    return json.load(io.open("exp_v245_%s.json" % g, encoding="utf-8"))


def mean(rows, arm, key):
    return st.mean([r[key] for r in rows if r["arm"] == arm])


def check(label, got, want, tol=TOL):
    ok = abs(got - want) <= tol
    print("  %-46s 正文 %.4f | 重算 %.4f  %s" % (label, want, got, "OK" if ok else "**不符**"))
    return ok


def main():
    allok = True
    m = load("main")
    print("E1 主对比")
    for arm, want in (("B0", 0.418), ("LEACH", 0.460), ("Ours", 0.954), ("FLOOD", 0.836)):
        allok &= check("接回 %s" % arm, mean(m, arm, "recon"), want)
    for arm, want in (("B0", 0.759), ("LEACH", 0.568), ("Ours", 0.730), ("FLOOD", 0.663)):
        allok &= check("满足率 %s" % arm, mean(m, arm, "sat_all"), want)
    for arm, want in (("B0", 31.1), ("LEACH", 33.2), ("Ours", 10.7), ("FLOOD", 4.2)):
        allok &= check("条件首用(分) %s" % arm, mean(m, arm, "t50_cond_s") / 60.0, want, tol=0.06)
    for arm, want in (("B0", 0.225), ("LEACH", 0.108), ("Ours", 0.024), ("FLOOD", 0.006)):
        allok &= check("死亡 %s" % arm, mean(m, arm, "dead"), want)
    for arm, want in (("B0", 0.197), ("LEACH", 0.241), ("Ours", 0.358), ("FLOOD", 0.371)):
        allok &= check("建链/当量 %s" % arm, mean(m, arm, "link_per_serv"), want)

    a = load("abl")
    print("E2 消融")
    for arm, want in (("A_full", 0.975), ("A_noPay", 0.429), ("A_noFlow", 0.969),
                      ("A_noCarry", 0.984), ("A_noDorm", 0.989), ("A_noArm", 0.956)):
        allok &= check("接回 %s" % arm, mean(a, arm, "recon"), want)
    for arm, want in (("A_full", 0.663), ("A_noPay", 0.792), ("A_noFlow", 0.709), ("A_noArm", 0.732)):
        allok &= check("满足率 %s" % arm, mean(a, arm, "sat_all"), want)

    s = load("sens")
    print("E3 敏感性（Ours−B0 接回差）")
    for var, val, want in (("P_UP", 0.2, 0.555), ("P_UP", 0.5, 0.521), ("P_UP", 0.8, 0.524),
                           ("MAX_HOP", 4, 0.522), ("MAX_HOP", 6, 0.521), ("MAX_HOP", 8, 0.543)):
        sub = [r for r in s if r["var"] == var and r["var_val"] == val]
        got = (st.mean([r["recon"] for r in sub if r["arm"] == "Ours"])
               - st.mean([r["recon"] for r in sub if r["arm"] == "B0"]))
        allok &= check("%s=%s" % (var, val), got, want)

    v = load("sev")
    print("E4 灾强")
    for dr, want in ((2, (0.563, 0.967, 0.554)), (3, (0.418, 0.954, 0.460)), (4, (0.371, 0.962, 0.353))):
        sub = [r for r in v if r["var_val"] == dr]
        for arm, w in zip(("B0", "Ours", "LEACH"), want):
            allok &= check("DIS_R=%d %s" % (dr, arm), st.mean([r["recon"] for r in sub if r["arm"] == arm]), w)

    ARMS7 = ("下限", "本方法", "LEACH@0.70", "CFACHS@0.70", "AFPUC-k@0.50",
             "AER-DM@0.05", "AFPUC-loc@0.10")

    sv = load("multi_sev")
    print("2.1 主表 / 2.2 灾强维")
    for dv, want in ((2, (0.563, 0.967, 0.595, 0.599, 0.540, 0.543, 0.529)),
                     (3, (0.418, 0.954, 0.471, 0.475, 0.436, 0.407, 0.403)),
                     (4, (0.371, 0.962, 0.353, 0.376, 0.340, 0.339, 0.339))):
        sub = [r for r in sv if r["dim_val"] == dv]
        for arm, w in zip(ARMS7, want):
            allok &= check("DIS_R=%d %s" % (dv, arm),
                           st.mean([r["recon"] for r in sub if r["arm"] == arm]), w)

    sp = load("multi_sup")
    print("2.3 供给维")
    for dv, want in ((0.2, (0.446, 0.965, 0.408, 0.440, 0.419, 0.387, 0.377)),
                     (0.5, (0.418, 0.954, 0.471, 0.475, 0.436, 0.407, 0.403)),
                     (0.8, (0.442, 0.958, 0.443, 0.412, 0.446, 0.404, 0.401))):
        sub = [r for r in sp if r["dim_val"] == dv]
        for arm, w in zip(ARMS7, want):
            allok &= check("P_UP=%.1f %s" % (dv, arm),
                           st.mean([r["recon"] for r in sub if r["arm"] == arm]), w)

    c = load("scale")
    print("2.4 规模维")
    for n, want in ((100, (0.418, 0.954, 0.471, 0.475, 0.436, 0.407, 0.403)),
                    (576, (0.262, 0.966, 0.275, 0.267, 0.262, 0.280, 0.271))):
        sub = [r for r in c if r["n"] == n]
        for arm, w in zip(ARMS7, want):
            allok &= check("N=%d %s" % (n, arm),
                           st.mean([r["recon"] for r in sub if r["arm"] == arm]), w)

    rb = load("robust")
    print("3.1 二次打击（接回）")
    for hp, want in ((0.0, (0.418, 0.954, 0.471, 0.475, 0.436, 0.407, 0.403)),
                     (0.10, (0.391, 0.952, 0.433, 0.425, 0.412, 0.392, 0.376)),
                     (0.20, (0.378, 0.950, 0.424, 0.413, 0.402, 0.365, 0.377))):
        sub = [r for r in rb if r["hit_p"] == hp]
        for arm, w in zip(ARMS7, want):
            allok &= check("p=%.2f %s" % (hp, arm),
                           st.mean([r["recon"] for r in sub if r["arm"] == arm]), w)
    print("3.1 二次打击（末态分量）")
    for hp, want in ((0.0, (0.294, 0.552, 0.322, 0.316, 0.303, 0.359, 0.375)),
                     (0.10, (0.147, 0.438, 0.140, 0.182, 0.152, 0.179, 0.183)),
                     (0.20, (0.109, 0.287, 0.110, 0.109, 0.113, 0.130, 0.116))):
        sub = [r for r in rb if r["hit_p"] == hp]
        for arm, w in zip(ARMS7, want):
            allok &= check("p=%.2f lcc %s" % (hp, arm),
                           st.mean([r["lcc_frac"] for r in sub if r["arm"] == arm]), w)

    lg = load("long")
    print("3.2 长期运行")
    for arm, w in zip(ARMS7, (0.445, 0.954, 0.504, 0.502, 0.468, 0.444, 0.440)):
        allok &= check("12h 接回 %s" % arm,
                       st.mean([r["recon"] for r in lg if r["arm"] == arm]), w)
    for arm, w in zip(ARMS7, (0.081, 0.171, 0.093, 0.093, 0.098, 0.090, 0.098)):
        allok &= check("12h 末态 %s" % arm,
                       st.mean([r["lcc_frac"] for r in lg if r["arm"] == arm]), w)

    lit = load("lit")
    print("E7 文献方法两档（附注用）")
    for tag, want in (("LEACH@0.05", 0.412), ("LEACH@0.50", 0.460), ("CFACHS@0.05", 0.400),
                      ("CFACHS@0.50", 0.445), ("AFPUC-k@0.05", 0.444), ("AFPUC-k@0.50", 0.436),
                      ("AER-DM@0.05", 0.407), ("AER-DM@0.50", 0.407),
                      ("AFPUC-loc@0.05", 0.397), ("AFPUC-loc@0.50", 0.395)):
        allok &= check(tag, mean(lit, tag, "recon"), want)

    par = load("parity")
    print("E8 同供给对照（接回）")
    for tag, want in (("6口 B0", 0.407), ("6口 Ours", 0.964), ("6口 LEACH@0.05", 0.414),
                      ("6口 LEACH@0.50", 0.428), ("43口 B0", 0.423), ("43口 Ours", 0.958),
                      ("43口 LEACH@0.05", 0.437), ("43口 LEACH@0.50", 0.422)):
        band, arm = tag.split(" ", 1)
        sub = [r for r in par if r["band"] == band and r["arm"] == arm]
        allok &= check(tag, st.mean([r["recon"] for r in sub]), want)

    fit = load("fit")
    print("E9 机制×场景（接回）")
    for sc, want in (("S1基线", (0.966, 0.972, 0.980, 0.987, 0.957)),
                     ("S2料稀缺", (0.372, 0.292, 0.369, 0.372, 0.333)),
                     ("S3低供给", (0.982, 0.970, 0.982, 0.988, 0.975)),
                     ("S4小灾", (0.993, 0.978, 0.993, 0.989, 0.989))):
        for arm, w in zip(("A_full", "A_noFlow", "A_noCarry", "A_noDorm", "A_noArm"), want):
            sub = [r for r in fit if r["scene"] == sc and r["arm"] == arm]
            allok &= check("%s %s" % (sc, arm), st.mean([r["recon"] for r in sub]), w)

    print("")
    print("结论：%s" % ("全部对上" if allok else "**有数不符，必须改正文**"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
