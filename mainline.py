# mainline.py —— 主表的**唯一出处**（2026-11-11 立；**2026-11-12 补全**）
#
# 为什么这一版要重写（2026-11-12 审计查出来的真缺陷）：
#   立这个文件时只声明了 `E_INIT`／`REFUND` **两项**，而"主表"实际是 ~40 个属性 + 46 槽 job 元组。
#   于是三道防线其实只建成了一小半：
#     · `E_INIT` 个人档 24→36 在文档里改了三天，代码没跟（H22 第二例）；
#     · `RETRY=1` 从 v182 起一直在主表里跑，而基线一次都没登记（H23）；
#     · `job()` 是**手写的 46 元组字面量**，改一处忘一处，没有任何东西能发现。
#   ⇒ 本文件改为：**全部属性 + 全部 job 槽位**集中声明，并给出**漂移探测器**。
#
# 规矩（纪律 138）：改这里 = 改基线，必须①在基线 §15.2b 登记；②跑 `python param_audit.py`；
#   ③在结论汇总写清"哪些结论要重算"。
# 驱动一律：`setup(); mainline.apply(引擎)`（顺序不能反）。

# ---- 一、模块属性（与 `v193_drv.setup()` 逐项对齐；值以主表为准）----
ATTRS = {
    # 世界与行为
    "P_LOSE": 0.0025, "PHI": 0.30, "D_BASIC": 0.05, "EPS": 0.05,
    "ALLOW_UNJOINED": 0,   # 2026-11-22：默认 0＝旧行为；实验时显式设 1（画面：活着就能伸）
    # `DEM_ALL`（2026-11-22 补登）：1＝所有活着的球都产生需求（画面“活着就亮”）；0＝只对已接入者。
    #   此前它只在 `engine.BASELINE`/模块默认里，**不在本表** ⇒ `apply()` 不设它、`param_audit` 看不见它，
    #   成了“有引用、无声明”的半个旋钮（与 2026-11-13 修过的 POKE/RETRY 同族）。它不进 `JOB`（走模块全局）。
    "DEM_ALL": 0,
    "MAX_HOP": 12, "REROUTE": 20, "GAMMA": 0.0, "P_KILL_IN": 1.0,
    "DIS_R": 6, "P_UP": 0.50, "C_SKY": 2.0,
    # 开关（开）
    "JOIN_CUT": 1, "POKE": 1, "LIT_MODE": 1, "VISION": 1, "FIRSTHIT": 1,
    "KNOWN_MODE": 1, "SERVE_PAY": 1,
    # **2026-11-12 补登**：这两项从 v155/v182 起就一直在主表里跑，而模块常量是旧值 0
    #   （`job[N] if len(job)>N else MODCONST` 的兜底分支永不执行 ⇒ 读代码读到的是"关"）。
    #   单一化时对齐成 1 ⇒ 从此"读代码=跑的东西"。见 engine_audit.py 与 `_jobfallback` 判据。
    "GWCAP": 1, "RETRY": 1,
    # 补给（v214/v216 新增；**默认关**＝"无补给"基线）。四项必须在表里，否则又是 H23：
    #   模块有常量、job 不传、文档不登记 ⇒ 下一版不知道基线跑的是哪一档。
    "RESUP": 0.0, "RESUP_T": 1, "RESUP_ALL": 0, "RESUP_PRE": 0,
    # 乘客档（v218）：`PASS_MAT=0` ⇒ 门槛恒不成立 ⇒ 与 v217 基线逐位相同（默认关）。
    "PASS_MAT": 0.0, "PAS_ACT": 1,
    # 开关（关）
    "FAIL_MEM": 0, "MEM_W": 0, "MEM_V": 0, "DEM_BURST": 0, "DEM_BURST_H": 3.0, "ACTS": 0,
    "LOOPFIX": 0, "MERGE": 0, "DL_ON": 0, "RELAY_PAY": 0,
    "HET_UNIFORM": 0, "ROOT_INFO": 0, "ROOT_SORT": 0,
    # 数值
    "EXPLORE": 0.5, "MEM_TTL": 10 ** 9, "MEM_K": 0.25, "REFR_N": 1, "K_ARMS": 1, "MAT_SCALE": 1.0, "E_SCALE": 1.0,
    "LIT_LO": 0.33, "OLD_ADV": 1.0, "NBR_PRIOR": 0.8, "KCHEAP": 1.0,
    "POKE_COST": 0.0, "HET_SPENT": 0.0,
    # **与驱动 `setup()` 不同的两项**（驱动是旧值 24／1.0；主表已落地新值）
    "E_INIT": (104.4, 174.0, 580.0),   # A 档：36/60/200 h ×2.9 当量/小时（P68 校准）
    "REFUND": 0.5,
    "TOTAL": 278,
    "REACH_MAX": 3,
    "CAPFIX": 0,      # 2026-11-21 接入：原来只在 JOB 里当字面值，改引擎无效（第五次同样的坑）     # 链的射程（格）。2026-11-19 接成旋钮：原来只在 JOB 里当字面值，改 engine 无效
}

# 驱动 `setup()` 里本来就过时的两项：不报"不一致"，因为这是**有意的覆盖**
INTENTIONAL_OVERRIDE = {"E_INIT", "REFUND"}

# 兼容旧接口（只含"与引擎默认不同"的项）；新代码请用 ATTRS
MAIN = {"E_INIT": ATTRS["E_INIT"], "REFUND": ATTRS["REFUND"]}
PENDING = {}

# ---- 二、job 的 46 个槽位 ----
# `"ENGINE"` ＝ 取引擎模块自己的值（S0／DC 是引擎常量，驱动从不改）
JOB = [
    ("seed", "SEED"),        # 0
    ("s0", "ENGINE"),        # 1  星上上行总量
    ("dt", 120),             # 2
    ("total", 278),          # 3
    ("tag", "main"),         # 4
    ("rep", 1),              # 5
    ("sky_scale", 1.0),      # 6  每根带宽倍数（注意它同时改 GWCAP 允许的根数）
    ("p_adv", 0.35),         # 7
    ("e_scale", 1.0),        # 8
    ("dis_mode", "thin"),    # 9
    ("reach", 3),            # 10
    ("dc", "ENGINE"),        # 11
    ("pre_h", 3.25),         # 12
    ("str_w", 1.0),          # 13
    ("str_b", 1.0),          # 14
    ("ab_mode", "mix"),      # 15
    ("w_use", 0.0),          # 16
    ("flat", 0),             # 17
    ("k_arms", 1),           # 18
    ("mat_scale", 1.0),      # 19
    ("up_sticky", 0),        # 20
    ("cov_window", 1),       # 21
    ("vis_frac", 0.39),      # 22
    ("cycle", 0.0),          # 23
    ("fail_mem", 0.0),       # 24
    ("poke", 1),             # 25
    ("explore", 0.5),        # 26
    ("mem_ttl", 10 ** 9),    # 27
    ("vision", 1),           # 28
    ("lit_mode", 1),         # 29
    ("lit_lo", 0.33),        # 30
    ("mem_w", 0.0),          # 31
    ("mem_v", 0.0),          # 32
    ("mem_k", 0.25),         # 33
    ("refr_n", 1),           # 34
    ("dem_burst", 0.0),      # 35  灾后需求倍数（>1.0 才触发）
    ("dem_burst_h", 3.0),    # 36  脉冲持续小时数
    ("acts", 0.0),           # 37
    ("sweep", 0),            # 38
    ("nsat", 1),             # 39
    ("gwcap", 1),            # 40
    ("sel_root", 0),         # 41
    ("loopfix", 0),          # 42
    ("prop", 0),             # 43
    ("capfix", 0),           # 44
    ("retry", 1),            # 45
]

DEAD_SLOTS = ()        # 2026-11-13 清空：槽 35/36 不是死槽，是我判错了两次（见下）
# **槽 35/36 的两次误判**：
#   ①第一次写「引擎从不读」——错，`run_one` 第 1333 行确实读了 `dem_burst = job[35]`。
#   ②第二次改成「设了没用」，依据是「job[35] 取 0.3／1.0 读数不变（逐位 738.856）」。
#     而门控是 `if dem_burst > 1.0 and dis_done and (t - t_dis) <= dem_burst_h*3600`
#     ⇒ **我用的两个值（0.3、1.0）都在门外**，测的是「门关着的时候」，不是「这个槽没用」。
#   实测（exp_v222）：job[35] 取 5／24／50 ⇒ 累计需求 7116→27793→125999→260444。
#   ⇒ 教训：①判「某槽无用」必须先找出它的**门控条件**再取值（纪律 154 同族）；
#          ②`DEAD_SLOTS` 这种「清单式否定」最容易被自己的取值方式骗，宁可留空。


# ---- 双基线（2026-11-13 立，用户允许"两版"）----
# A 档 ＝ **协议基线**（`ATTRS`，`E_INIT=(36,60,200)`）：回答"**协议能做什么**"——电池足够时的机制比较。
# B 档 ＝ **现实基线**（下表，`E_INIT=(10,24,200)`）：回答"**现实里瓶颈是什么**"——电池按真实续航折算。
# 为什么两档都要留：把它们混在一起会丢信息——A 档才能比出"机制之间的差"，B 档才能看出"电把一切压平"。
# 依据（基线 §15.3c）：手机灾后持续搜网＋通话 **3–6 实际小时**，实际耗电是待机的 1.5–2 倍
#   ⇒ 折 **5–12 待机小时**，取 10；对讲机 8–24 实际小时 ⇒ 折 12–36，取 24；车载靠发动机，200 保留。
ATTRS_REAL = {
    "E_INIT": (29.0, 69.6, 580.0),      # B 档：10/24/200 h ×2.9 当量/小时（P68 校准）
}


def apply_real(eng):
    """**在 `apply()` 之后**调，把主表换成"现实电池"档（B 档）。"""
    for k, v in ATTRS_REAL.items():
        setattr(eng, k, v)
    return dict(ATTRS_REAL)


# ---- 灾害档（2026-11-13 立；exp_v227 的结论：单开任何一个"牙"都只值个位数）----
# T0 ＝ **灾只断链**（现行主表：`DIS_REFUND=1.0`、两个 `DIS_*_LOSS=0`）⇒ 现在降为**下界**；
# T4 ＝ **三牙全开**（剪链退一半 ＋ 灾时电−60% ＋ 灾时料−60%）⇒ 建议作**标准灾害配置**。
# 依据：真实灾害里设备会坏（东日本大地震"电源单元被淹"、"电池耗尽"），
#   而 `DIS_REFUND=1.0` 是旧默认、从未估过（基线 §15.3c）——它让"灾"不花资源、只花时间。
# 为什么单独立一档而不是直接改 `ATTRS`：改了 `ATTRS` 就等于**所有历史读数都换了世界**；
#   立成一档，"灾只断链"仍是可复现的下界，两者可以并报（这正是纪律"结论要带前提"的做法）。
DIS_T4 = {"DIS_REFUND": 0.5, "DIS_E_LOSS": 0.6, "DIS_M_LOSS": 0.6}


def apply_dis(eng, tier="T0"):
    """`tier="T4"` 时把三个"牙"打开；`"T0"` 时什么都不做（＝现行主表）。"""
    if tier == "T4":
        for k, v in DIS_T4.items():
            setattr(eng, k, v)
        return dict(DIS_T4)
    return {}


def apply(eng):
    """把声明写进引擎（就地 setattr）。驱动 `setup()` 之后调用，覆盖可能过期的旧值。"""
    for k, v in ATTRS.items():
        setattr(eng, k, v)
    return dict(ATTRS)


def job(seed, eng):
    """按声明生成 job 元组（长度 46）。

    **2026-11-13 修的一处结构缺陷**：原来这里对 `JOB` 里的字面值原样打包，
    于是同一个旋钮有**两个源**——`ATTRS`（文档与 `apply()` 用的那张表）和 `JOB`（真正进引擎的那一个）。
    实测：`ATTRS` 的 50 项里 **24 项改了毫无作用**（`knobscan.py` 查出来的），
    其中包括 `RETRY`／`POKE`／`GWCAP` 这些"主表里明明写着"的开关。
    ⇒ 现在凡是 `ATTRS` 里有的名字，**一律从引擎取**；`JOB` 只负责"有哪些槽、顺序如何"。
    """
    out = []
    for name, v in JOB:
        if name == "seed":
            out.append(seed)
        elif v == "ENGINE":
            out.append(getattr(eng, "S0" if name == "s0" else "DC"))
        elif name.upper() in ATTRS:
            out.append(getattr(eng, name.upper()))
        else:
            out.append(v)
    assert len(out) == 46, len(out)
    return tuple(out)


def diff_job(jj):
    """驱动手写的 job 与声明不一致的槽位 → [(下标, 名字, 声明, 实际)]。"""
    bad = []
    for i, (name, v) in enumerate(JOB):
        # `tag` 只是标签（日志里显示版本名），不影响任何计算 ⇒ 不算漂移
        if v == "ENGINE" or name in ("seed", "tag"):
            continue
        got = jj[i]
        if isinstance(v, float) or isinstance(got, float):
            ok = abs(float(got) - float(v)) < 1e-12
        else:
            ok = (got == v)
        if not ok:
            bad.append((i, name, v, got))
    return bad


def diff_driver(eng):
    """驱动 `setup()` 之后、`apply()` 之前调用：报出驱动与声明不一致的属性。

    返回 [(属性, 声明值, 驱动值, 是否属"有意覆盖")]。
    这就是 `E_INIT` 那类漂移的探测器——它会在跑实验之前就把不一致报出来。
    """
    bad = []
    for k, v in ATTRS.items():
        got = getattr(eng, k, "<缺失>")
        if isinstance(v, tuple):
            ok = (not isinstance(got, str)) and tuple(got) == tuple(v)
        elif isinstance(v, float) or isinstance(got, float):
            ok = abs(float(got) - float(v)) < 1e-12
        else:
            ok = (got == v)
        if not ok:
            bad.append((k, v, got, k in INTENTIONAL_OVERRIDE))
    return bad
