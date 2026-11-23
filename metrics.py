# -*- coding: utf-8 -*-
"""metrics.py —— 指标的唯一实现（2026-11-13 立，回应系统性检查 B1／C1）

为什么要有这个文件：
  · **B1**：`UNIT = 120*576/3600` 在 17 个脚本里各写一份，其中 1 处把 576 写死。
    当前网格 24×24 所以没错；v220 跑 48×48 时是**人工**改成 `120·n/3600`——做对了，但靠人记得。
    换规模漏改会**静默差 4 倍**，所有工具都不报错。
  · **C1**：每个 `exp_*` 自己写一遍 `o2p`／`t50`／接回率。今天那个 O1 口径错误就是这么来的：
    改了一个脚本的口径，别的脚本还是旧的，而它们看起来一样。
  · **A1**：接回率把「活着没接上」与「死了」混成一个数。这里强制三分解。

**规矩**：新实验一律 `import metrics`，不许再自己写这几个式子。
**老驱动（`v*_drv.py`、`exp_v221`–`v230`）不改**——它们是历史产物，改了就不再是当初跑的那一份
（纪律 144：结论要指得到产物，产物必须保持原样）。它们与这里的差异写在下面各函数的 docstring 里。

口径（每一条都写清，免得再出现"同一个名字指两件事"）：
  · `O2p`＝灾后窗口内**累计服务**（人·小时）。分母随网格变：`dt × N / 3600`。
  · `接回率` 的分母是**固定队列**：灾前那一刻已并网（`gset0`）的全部人。
  · 接回率**必须三分解**：接回／活着没接回／死了。未接回且没死的，按窗口长度记等待。
"""

import engine

DEFAULT_DT = 120          # 与 `mainline.JOB[2]` 一致
PRE_DEFAULT = 98          # 灾前步数（打灾在第 98 步）


def unit(dt=DEFAULT_DT, n=None):
    """1 步 × N 台 ＝ 多少人·小时。**分母必须跟着网格和步长算**，不许写死 576。"""
    n = engine.N if n is None else n
    return dt * n / 3600.0


def o2p(r, pre=PRE_DEFAULT, dt=DEFAULT_DT):
    """灾后窗口内的累计服务（人·小时）。"""
    return sum(r["R_loc_s"][pre:]) * unit(dt)


def sat(r):
    """满足率 serv/dem。**不作主判据**：分子分母都随死亡变（B 档 P0 的 0.874 比 A 档 0.787 好看，而 B 档死了 493 台）。"""
    dem = float(r.get("dem", 0.0))
    return (float(r.get("serv", 0.0)) / dem) if dem > 0 else float("nan")


def recon_split(r):
    """固定队列上的三分解：对 `gset0`（灾前已并网）里的每个人，判他是哪一种。

    返回 dict：
      ok／alive_no／dead —— 三类的**人数**
      frac_ok／frac_alive_no／frac_dead —— 三类的**占比**（分母＝`gset0` 人数）
      n —— 分母

    为什么必须拆：`t_self` 对**死了的人**永远留 -1，所以"接回率"这个词同时装了
    「活着但整窗没接上」与「中途死了」。实测（3 种子／T4）：
      A 档 0.29 接回 ＋ 0.71 活着没接回 ＋ 0.00 死
      B 档 0.26 接回 ＋ 0.16 活着没接回 ＋ 0.59 死
    同一个 0.28，A 档说的是"连不上"，B 档说的是"死了"。
    """
    g = r.get("gset0_list") or []
    ts = r.get("t_self") or []
    td = r.get("t_dead")
    n = len(g)
    if n == 0:
        return dict(n=0, ok=0, alive_no=0, dead=0,
                    frac_ok=float("nan"), frac_alive_no=float("nan"), frac_dead=float("nan"))
    ok = sum(1 for i in g if ts[i] >= 0)
    if td is None:            # 老引擎没有 `t_dead`：只能给出"接回"与"其余"，dead 记 None
        return dict(n=n, ok=ok, alive_no=n - ok, dead=None,
                    frac_ok=ok / float(n), frac_alive_no=(n - ok) / float(n), frac_dead=None)
    dead = sum(1 for i in g if ts[i] < 0 and td[i] >= 0)
    alive_no = n - ok - dead
    return dict(n=n, ok=ok, alive_no=alive_no, dead=dead,
                frac_ok=ok / float(n), frac_alive_no=alive_no / float(n), frac_dead=dead / float(n))


def t50_fixed(r, pre=PRE_DEFAULT):
    """**固定队列**的中位等待：`gset0` 全部人，窗口内没接回的按窗口长度记。

    这是 O1 的主口径。它不需要"最终接通"这个条件，所以不会因为方案变好而把难户吸进分母。
    """
    g = r.get("gset0_list") or []
    if not g:
        return float("nan")
    ts = r["t_self"]
    ttl = float(len(r["R_loc_s"])) - pre
    vals = sorted((ts[i] if ts[i] >= 0 else ttl) for i in g)
    m = len(vals)
    return float(vals[m // 2]) if m % 2 else 0.5 * (vals[m // 2 - 1] + vals[m // 2])


def t50_cond(r):
    """**条件中位数**：只统计最终接通的人。

    **只作辅助**，且报的时候必须写明"分母＝最终接通者"。
    它会被方案本身筛选：方案越好，原本接不上的难户也被纳进来，中位等待反而变长
    （实测 A 档 P0 38/118 人接回、t50=13；P4 114/114 人接回、t50=40）。
    """
    vals = sorted(x for x in (r.get("t_self") or []) if x >= 0)
    if not vals:
        return float("nan")
    m = len(vals)
    return float(vals[m // 2]) if m % 2 else 0.5 * (vals[m // 2 - 1] + vals[m // 2])


def row(r, pre=PRE_DEFAULT, dt=DEFAULT_DT):
    """一次取齐：新实验的返回行就用它，免得每个脚本各写一遍。"""
    s = recon_split(r)
    return dict(o2p=o2p(r, pre, dt), sat=sat(r),
                recon=s["frac_ok"], alive_no=s["frac_alive_no"], dead=s["frac_dead"],
                n_g0=s["n"],
                t50_fix=t50_fixed(r, pre), t50_cond=t50_cond(r),
                edges=r["n_edges_end"], exit_n=r["n_exit"],
                m_resup=float(r.get("m_resup", 0.0)))

def pre_idx(pre=PRE_DEFAULT):
    """灾前最后一步在逐步曲线里的下标（**由 `pre` 推导，不写字面量**）。

    2026-11-15（P36）：`exp_v237` 原来直接写 `serv_s[97]`，`PRE_H` 一改就悄悄算错，而且不会报错。
    约定：`serv_s[k]` 是第 k+1 步结束时的累计值；灾前 `pre` 步 ⇒ 最后一步下标 `pre-1`。
    """
    return int(pre) - 1


def vol_after(r, pre=PRE_DEFAULT):
    """灾后累计送达当量（**不是 `O2p`**：`O2p` 是人·小时）。"""
    ss = r.get("serv_s") or []
    i = pre_idx(pre)
    assert len(ss) > i, "窗口比灾前还短：len(serv_s)=%d, pre=%d" % (len(ss), pre)
    return float(ss[-1] - ss[i])


def sat_after(r, pre=PRE_DEFAULT):
    """**灾后**满足率（P35）。需要 `dem_s`；老结果文件没有这个字段，会返回 nan。"""
    ss = r.get("serv_s") or []
    ds = r.get("dem_s") or []
    if not ds or len(ds) != len(ss):
        return float("nan")
    i = pre_idx(pre)
    d = float(ds[-1] - ds[i])
    return (float(ss[-1] - ss[i]) / d) if d > 0 else float("nan")


def peak_k(points):
    """points＝[(负载, 值)]。返回 (峰值负载, 峰值, 降到峰值一半的负载 k50)。

    `k50` 用 2 的对数插值（负载是 2 倍步长）；若整段都没降到一半，k50 记 None（＝窗口不够长）。
    """
    import math
    ks = [p[0] for p in points]
    vs = [p[1] for p in points]
    j = max(range(len(vs)), key=lambda i: vs[i])
    pk = vs[j]
    for t in range(j + 1, len(vs)):
        if vs[t] <= 0.5 * pk:
            y0, y1 = vs[t - 1], vs[t]
            r = (y0 - 0.5 * pk) / (y0 - y1) if y0 != y1 else 0.0
            k50 = 2 ** (math.log2(ks[t - 1]) + r * (math.log2(ks[t]) - math.log2(ks[t - 1])))
            return ks[j], pk, k50
    return ks[j], pk, None


def standard(r, pre=PRE_DEFAULT, dt=DEFAULT_DT):
    """**对比用的标准出口**（2026-11-16，为与论文并排）。

    为什么要它：不同论文报不同的数，而「谁更好」最容易错在**分母不同**。
    这里把五个量固定成一套，并且**每个量都带分母**：

      sat            = serv / dem              （人·当量／人·当量；分母＝**呈递的需求**）
      serv_per_node  = serv / N                （当量／台；分母＝**网格台数**）
      energy_per_node= e_spent / N             （待机小时／台；分母同上）
      recon          = 三分分解里的「接回」     （分母＝**灾前已并网的固定队列**）
      dead           = 三分分解里的「死了」     （同上）
      t50_fixed      = 固定队列中位首用时刻     （秒；分母同上）

    换任何一档、任何一臂，都用这五个数对外；**别的口径要另起名字**（纪律 163）。
    """
    d = row(r, pre=pre, dt=dt)
    n = float(engine.N)
    return {
        # 2026-11-16：`sat` 的分子含「重试被服务的量」，分母只记人的需求 ⇒ **重试一开就被抬高**。
        # 这是分母混用的一处（自查发现），所以另给一个「按尝试算」的率，两个名字分开写。
        "sat": d["sat"],
        "sat_att": float(r.get("serv", 0.0)) / max(1e-9, (r.get("dem", 0.0) - r.get("rej", 0.0) + r.get("retry_add", 0.0))),
        # P52（2026-11-16）：**固定队列口径**——分子分母都只算「灾前已并网的那批人」，
        # 死了的人照计需求、服务为 0。这是**唯一能跨死亡程度比较**的满足率。
        "sat_all": float(r.get("serv_g0_post", 0.0)) / max(1e-9, float(r.get("dem_fixed", 0.0))),
        # `row()` 里没有 serv，只有比率；用原始量算，别从别处借
        "serv_per_node": float(r.get("serv", 0.0)) / n,
        "energy_per_node": float(r.get("e_spent", 0.0)) / n,
        "recon": d["recon"],
        "dead": d["dead"],
        # **单位修正（2026-11-18）**：`t50_*` 原本是**步**（dt=120 s/步），文档却写“秒” ⇒ 差 120 倍。
        # 这里同时给出“步”和“秒”，表里只用 `*_s`。
        # 韧性三角三量（Bruneau 2003）+ FND（2026-11-18）
        # 碎片化（文献标准：LCC 占比 / 分量数；见 §13.21）
        # 查询式业务（画面“伸即看”，2026-11-19）
        # 首用拆分（2026-11-20）：等窗口 vs 窗内接上
        "sos_rate_nodes": (r.get("sos_ok_nodes",0) / r.get("sos_try_nodes",1)) if r.get("sos_try_nodes") else float("nan"),
        "sos_rate": (r.get("q_ok", 0) / r.get("q_try", 1)) if r.get("q_try") else float("nan"),
        "sos_by60": (r.get("q_by60", 0) / r.get("q_try", 1)) if r.get("q_try") else float("nan"),
        "t_wait_min": (r.get("t_wait_med", -1) * 2.0) if r.get("t_wait_med", -1) >= 0 else float("nan"),
        "t_conn_min": (r.get("t_conn_med", -1) * 2.0) if r.get("t_conn_med", -1) >= 0 else float("nan"),
        "q_succ": (r.get("q_ok", 0) / float(r.get("q_try", 0))) if r.get("q_try") else float("nan"),
        "q_lat_min": (r.get("q_lat_med", -1) * 2.0) if r.get("q_lat_med", -1) >= 0 else float("nan"),
        "lcc_frac": r.get("lcc_frac"),
        "n_comp": r.get("n_comp"),
        "lcc_g0_frac": r.get("lcc_g0_frac"),
        "res_depth": r.get("res_depth"),
        "res_width": r.get("res_width"),
        "res_area": r.get("res_area"),
        "fnd_step": r.get("fnd_step"),
        "t50_fixed": d["t50_fix"],
        "t50_fixed_s": d["t50_fix"] * float(r.get("dt", 120)),
        "t50_cond_s": d["t50_cond"] * float(r.get("dt", 120)),
        # 条件中位（分母＝**已接回者**）：不会饱和，但**单独看会奖励「只接回少数快的人」**
        "t50_cond": d["t50_cond"],
        # 开销比（对手口径）：每送达 1 单位当量，要花多少次尝试（探路＋建链）
        # `try_link` 是**按组的三元素列表**（g0/g1/g2），要合计，不能直接 float
        # 通天通路侧（P57）：换手率与平均深度——粗细那一节只有这两条能看见
        "tu_sw_rate": float(r.get("tu_sw_rate", 0.0)),
        "hop_mean": float(r.get("hop_mean", 0.0)),
        "overhead_ratio": (float(r.get("nbr_probe", 0.0)) + float(sum(r.get("try_link", [0]))))
                          / max(1e-9, float(r.get("serv", 0.0))),
        "o2p": d["o2p"],
    }


DENOMS = {
    "sat": "serv / dem（**分母不含重试**；且只含**还活着的并网者**的需求 ⇒ 死亡越多它越高，**禁止跨死亡程度比较**）",
    "sat_att": "serv / (dem−rej+retry_add)（按**尝试**算，含重试）",
    "sat_all": "固定队列口径：g0 成员灾后被服务到的量 / g0 成员本应发出的需求（**可跨死亡比较**）",
    "serv_per_node": "serv / N（台数）",
    "energy_per_node": "e_spent / N（台数）",
    "recon": "**并入主网率**（gset0 中 t_self≥0 的比例；t_self 判据＝所在分量并入 core，见 H46——不是“发出成功”，也≠“在网”）",
    "dead": "退出（同一固定队列；与 recon 的分母相同）",
    "q_succ": "**查询成功率**：拿到回读的查询数 ÷ 发起的查询数（画面“伸即看”）",
    "q_lat_min": "查询时延中位（分钟；步×2）",
    "lcc_frac": "**最大连通分量占比**（LCC/全网节点；文献 standard，碎片化主读数）",
    "n_comp": "连通分量个数（NCC；越大越碎）",
    "lcc_g0_frac": "受灾队列中落在最大分量的比例",
    "res_depth": "**不可用（H45）**：韧性三角深度在本模型饱和为 1（灾后有连续静默步）",
    "res_width": "**不可用（H45）**：宽度随基准选择在 0 与 ∞ 之间跳",
    "res_area": "**不可用（H45）**：面积随基准变号（灾前基准下为负）",
    "fnd_step": "首个节点死亡的步（−1 表示整窗无死亡）",
    "t50_fixed": "固定队列中位首用（**步**；饱和在窗口上限＝180 步＝6 小时）",
    "t50_fixed_s": "同上，换算成秒（×dt）",
    "t50_cond_s": "条件首用（已接回者）换算成秒",
    "t50_cond": "已接回者的中位首用（秒；分母＝**已接回者**，与 `recon` 成对读）",
    "overhead_ratio": "(探路次数＋建链次数) / 送达当量（对手的 overhead ratio 的同类量）",
    "tu_sw_rate": "通天通路每次重评的换手比例（分母＝重评次数；低＝稳定）",
    "hop_mean": "已通天节点的平均跳数（分母＝已通天节点数）",
    "o2p": "灾后累计服务 × dt·N/3600（人·小时）",
}
