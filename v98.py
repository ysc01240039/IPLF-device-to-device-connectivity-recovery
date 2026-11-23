# -*- coding: utf-8 -*-
"""生长模型 v48：重测「记忆＝结构」（三臂），并查 v47 引入的隐患（粗链集中在少数车载）。

v46 查出粗链只占 0.10% —— 因为加粗候选只收 `load_e>0` 的链（我加的），而承载受容量限制，
于是"加粗要承载作证据、承载要粗链才够"闭环，网永远停在细链。
v47 按画面第 52 行改成"优先驻留强球"，承载只用来给同强弱的链排先后。

（以下为 v46 说明，保留）

原 v46：强球养粗（画面第 52 行）——容易粗 / 粗得久，两半分开测。

画面第 52 行："粗链优先驻留强球——天线好、供电足的球，链稳，容易粗、粗得久。"
  · 容易粗：加粗优先落在强球身上（此前只按承载量排序）；
  · 粗得久：强球两端的链更不容易断（此前断链只看"我有多粗"）。
设备强弱按画面第 11 行三档给，并乘剩余电量比例。

（以下为 v45 说明，保留）

原 v45：给"伸向哪"建自由度（可伸到 REACH 格内，远的更贵）。

v44 的负结果说明：只要候选只有 4 个固定邻居、且全都伸得起，任何"经验"都不值钱。
v45 把"伸向哪"变回一个真选择：REACH 格内任意终端皆可，代价随距离上升。
REACH=1 即复现 v44，作对照。

（以下为 v44 说明，保留）

原 v44：先造"灾前的网"，再让重连者背着**真实的旧链**回来；组内随机三分组。

v43 把"旧账"做成了 `via[i]=NBR[i][0]`（正上方一格）——所有重连者都指北，
这不是经验，是方向性偏差；而且模型里没有"灾前"，"旧"无从谈起。
v44 两段：灾前长到稳态 → 打灾（只断链）→ 在重连者里随机三分组：
  g0 真实旧账／g1 白纸／g2 打乱旧账，同网同刻同总体配对比较。

（以下为 v43 说明，保留）

原 v43：重连态（背旧账）与脱生态（白纸）分开：轨道形态改为"覆盖带内外扫"，去掉永久死区：轨道周期改成物理值，窗口按三个时间尺度定：材料账要守恒 + 报"多久铺满"和 R(t)——把"全局多源最宽路"换成"只知道伸出去过的那条路"。

v35 的 serve() 是一次全图 Dijkstra：每个终端都"知道"自己到最近上天点的最宽路，
而它从未伸过那条路。这正是画面第 17 行否掉的东西（"没伸到的地方，严格说不在它世界里"），
也是 v1–v11 被整批作废的同一个错，只是换了位置。

v36 的做法：
  · 每台只知道两样：**我实际握着的链**、以及**邻居回程告诉我的**（它能不能通天、几跳）；
  · 知识只沿"实际形成的链"一跳一跳传（伸一下就学一条），另有小概率重探（回程读数）；
  · 投递靠这张表逐跳走，遇到断链/挤不上就算失败，并记一笔（失败留痕用）；
  · 同一张网、同一步，**同时**算"全知"与"已探明"两套，配对比较，差额就是"全知的价钱"。

口径沿用 v35：连天分级 / R 分层 / 边际劣化 / 承载拐点。

依据（见 README §57 设计书、画面自审 §5、场景锚点 §2.6）：

  1. 连天按设备分级（画面第 11 行说的是**设备差异**，不是"只有车载能连"）
     —— `SKY_BW = (0.2, 1.0, 8.0)`，三档都能连天，带宽不同。
  2. R 按业务分层（连天一分级，单一个 R 就自相矛盾）
     —— `D_BASIC=1`（短报文）／`D_BROAD=4`（语音、低速数据），分别报。
  3. 额度 → 规模报酬递减（画面第 7 行"越过某个限度，感知、伸展、存护同时劣化"）
     —— 第 k 条链的代价 `C0*(1+k/K_SOFT)`，越握越贵，自己停下来。
     这才是"不能无限长"的机制；v34 的硬配额只有结论、没有机制。
  4. 承载加拐点（画面第 58 行"负载越过临界点，有效产出不涨反崩"）
     —— 准入按 `THETA*w*U` 判，越过临界就挤不上；另报"过火"诊断：
        若真塞到满，有效产出反而更低。
  5. 时间两层分辨率（场景锚点 §2.6）
     —— 慢层 DT=300 s 走整个窗口；快层 DT=20 s 只走关键期，比曲线形状。

不做：已探明场（留给下一版，它是"信息"的事）、能耗存量、残差概率。
"""
import json
import math
import statistics
import sys
from collections import deque
from random import Random

H = W = 24
N = H * W
SEEDS = [1, 2, 3, 4, 5, 6, 7, 8]

TIER_SHARE = (0.70, 0.25, 0.05)

# ---- 1. 连天分级：每档设备的上行带宽当量（不是布尔量） ----
SKY_BW = (0.2, 1.0, 8.0)       # 个人：窄带短报文 / 小队 / 车载：大功率定向天线

# ---- 2. 业务分层：每台终端每步的需求当量 ----
D_BASIC = 1.0                  # 保底：短报文、语音
D_BROAD = 4.0                  # 宽带：语音＋低速数据

# ---- 3. 规模报酬递减：握第 k 条链的代价 ----
C0 = 1.0                       # 第一条链的代价
K_SOFT = 3.0                   # 每多握 K_SOFT 条，代价翻一倍（拍的，扫）
MAT0 = (6.0, 14.0, 34.0)       # 每台的材料存量（拍的，扫）
# v54：断链时退还多少料。1.0 = 全额退（v38 起一直是这个口径）；0 = 料随链一起没了。
# 为什么要这个旋钮：全额退意味着**破坏不花任何资源**，只花时间；而灾后有的是时间（720 步）。
REFUND = 1.0

# ---- 4. 承载拐点 ----
THETA = 0.60                   # 一条链的可用上限占满容量的比例（过此即挤不上）
W_MAX = 12
U = 4.0

RELAY_INIT = (3.0, 8.0, 20.0)  # 每步能替别人转多少（速率，与链宽同量纲）

# ---- 能耗：存量，用完即退出（画面第 11 行"头顶是油、电"）----
# 单位：小时。耗得越多，活得越短；灾后补不上，所以是单向的。
E_INIT = (24.0, 60.0, 200.0)   # 三档的可用时长（拍的，扫）
C_HOLD = 0.5                   # 每握一条链，每小时耗
# v57：待机耗电。没有它，"不接链"的终端永不耗尽，而画面第 11 行说头顶就是油、电。
# **电量的单位由此定为"待机小时"**：1 单位 = 空载运转 1 小时。于是 E_INIT 标的小时才是小时。
C_IDLE = 1.0
C_SKY = 2.0                    # 连天，每小时耗
C_RELAY = 0.2                  # 每替别人转一个当量，耗
HOP_MAX = (6, 12, 18)

R_COVER = 4
# ---- 轨道 ----
# 依据级别：
#   · 低轨周期 90–100 分钟是**工程常数**（卫星高度 500–600 km），这里取 5400 s。
#     具体到某星座须查原文，本模型不指定星座，故只当量级用。
#   · 覆盖半径由波束角与高度共同决定；本节不引入具体型号，R_COVER=4 格是**拍的**。
#     （原注释写"（扫过）"是错的：台账一直标"否"，v94 才第一次扫 4/6/8/12。）
#     v94：R_COVER 决定"能当根的台数"，4→12 使根数 24→213、吞吐 586→831；
#     且 R_COVER(4) < DIS_R(6) 时覆盖盘会被灾盘整块吞掉 ⇒ 全网无根。
#   · 轨道形态：真实星下点不是固定半径的圆（倾角使星下点在不同纬度来回）。
#     这里用一个**慢变的半径**代表"覆盖带在内外扫"——是**简化，不是物理**。
T_ORBIT = 5400.0
OMEGA = 2.0 * math.pi / T_ORBIT
R_MID = 8.0            # 覆盖带中心的平均半径
R_AMP = 4.0            # 内外扫的幅度（0..4 → 覆盖带从中心扫到边缘）
T_DRIFT = 4.0 * T_ORBIT  # 6 小时扫一个来回
S0 = 60.0                      # 卫星侧能同时接的总量（外生场景量）

P_ADV = 0.35
P_UP = 0.50
P_LOSE = 0.0025

SEEDS_PER_CELL = 8
# ---- 重连 vs 脱生（画面第 9 行：重连＝也是刚脱生，但背着旧账；
#      "它比白纸新生者亮得快，旧经验直接可继承，但账可能过期，过期就得重做；
#       灾区里最多的其实是这一类"）----
# ---- v44 两段式：灾前 / 灾后 ----
# 灾前时长 6 h：v39 实测铺满约 1.0 h，6 h 时覆盖已 1.0、最小档 E_INIT=24 h 还剩大半，
# 所以灾前的网是健康的（不是"带病的灾前"）。
PRE_H = 6.0
# 灾半径 6 格：与 u1 的半径 7（打掉约 21% 的格）同量级。
# v42 的教训：破坏的**位置**比大小更决定损失，所以必须打在已并网处，不是网格正中。
DIS_R = 6
# 两种灾，**打断的链数相当**，只改空间相关性：
#   blast   ＝ 一个圆盘（同源受灾：你原来的邻居跟你一起坏）
#   scatter ＝ 同数量的格随机散开（失效不相关：邻居多半还完好）
# 单变量操纵：破坏量相同，只改"旧账还有没有用"。
SCATTER_FRAC = 0.20
DIS_R_S = 2             # 小洞半径（中等相关性档）
# ---- v45：伸向哪 ----
REACH_MAX = 3           # 最多伸到几格内（1 = 只够四邻，即 v44 口径）
DC = 0.5                # 距离代价：伸到第 d 格，代价 = 基础代价 x (1 + DC*(d-1))
# ---- v46：强球养粗（画面第 52 行）----
# 设备强弱：按画面第 11 行的三档给（个人小 / 小队中 / 车载大功率定向天线）。
# 这是"相对强弱"，只用于排序与断链，不作绝对量。拍的，未扫。
STR = (0.3, 0.6, 1.0)
STR_W = 1.0             # 加粗时"优先落在强球"的权重（0 = 回到 v45）
# ---- v62 响应阈值律（Theraulaz 1998 式(1)(2)(3)）----
TH0 = 1.0               # 阈值的初值（拍的）
TH_STR = 1.0            # 强球的阈值初值低多少：th0 = TH0*(1+TH_STR*(1-sk))
DELTA = 10.0            # "做到了"时阈值每小时降多少（拍的，但受一个硬约束：见下）
PHI = 0.3               # "没做到"时阈值每小时涨多少（拍的；独立的一项，不取负）
# 硬约束：阈值只涨不落的临界使用率 p* = PHI/(DELTA+PHI)。DELTA/PHI=2.5 时 p*=0.29，
# 而本模型里单步"有承载"的链只占 0.8/1030 ≈ 0.1%、30 步窗口内约 3% ⇒ 没有任何链能降下阈值。
# 取 DELTA/PHI≈33 ⇒ p*≈0.03，正好压在"常被走"与"偶尔被走"之间。
TH_MIN = 0.05
TH_MAX = 50.0
Q_MAX = 5.0             # 每台最多攒多少当量需求（攒满就不再新增；防止无限积压）
REROUTE = 1             # v77：按松紧选路的轮数（1 = 旧行为，只算一次静态容量）
# v79：一条路径最多几跳。24×24 环面上任意两点最短路 ≤12，取 12 作几何上限；
# 999 = 不限（v78 的旧行为，用来量"绕行"到底值多少）。
MAX_HOP = 999
# v88：圆内抽稀的两个旋钮
P_KILL_IN = 1.0    # 圆内每条链的基准断链概率（1.0 = 全灭 = blast）
GAMMA = 0.0        # 0 = 均匀抽稀；1 = 边缘不断（残存概率随距离上升）
EPS = 0.01              # 每步允许重排的量（＝v48 那个"额度"）
STR_B = 1.0             # 强球两端"更不容易断"的权重（0 = 回到 v45）
OLD_PRIOR = 0.80        # 重连者优先去够"旧邻居"的概率（拍的，扫）
OLD_ADV = 1.5           # 亮得快：连地尝试概率的倍数（与"经验"分开测）
K_ORDER = 3                    # 每步用几个不同顺序投递（量顺序噪声）

# ---- 5. 两层时间 ----
DT_SLOW = 120.0                # 2 分钟（一个轨道周期能分 45 步）
STEPS_SLOW = 720               # × 120 s = 24 小时（要跨过能耗特征时间 16–33 h）
DT_FAST = 20.0
STEPS_FAST = 360               # × 20 s = 2 小时

NB = (
    [((i // W - 1) % H) * W + (i % W) for i in range(N)],
    [((i // W + 1) % H) * W + (i % W) for i in range(N)],
    [(i // W) * W + ((i % W - 1) % W) for i in range(N)],
    [(i // W) * W + ((i % W + 1) % W) for i in range(N)],
)
NBR = [[NB[0][i], NB[1][i], NB[2][i], NB[3][i]] for i in range(N)]
_D2 = {}


def _offsets(r):
    out = []
    for dr in range(-r, r + 1):
        for dc in range(-r, r + 1):
            if dr == 0 and dc == 0:
                continue
            d2 = dr * dr + dc * dc
            if d2 <= r * r:
                out.append((dr, dc, d2 ** 0.5))
    return out


OFFS = {r: _offsets(r) for r in range(1, REACH_MAX + 1)}


def cands(i, r):
    """格 i 在半径 r 内、除自己以外的所有格，带欧氏距离（环形网格）。

    v61：OFFS 原来只预计算到 REACH_MAX（3），扫 reach=5 时直接 KeyError。
    改成**按需生成并缓存**——预计算的边界不该悄悄变成"reach 的上限"。
    """
    row, col = i // W, i % W
    off = OFFS.get(r)
    if off is None:
        off = OFFS[r] = _offsets(r)
    return [(((row + dr) % H) * W + ((col + dc) % W), d) for dr, dc, d in off]


def build_adj(ew):
    """从链表重建邻接表。每步重建一次，代价 O(E)，好处是**不会漂**——
    维护增量邻接（加边/删边各改一处）很容易漏一处，漏了不报错，只是某条路走不通。"""
    adj = {}
    for (a, b) in ew:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    return adj


def ekey(a, b):
    return (a, b) if a < b else (b, a)


def dist2(a, b):
    k = a * N + b
    v = _D2.get(k)
    if v is None:
        ra, ca = divmod(a, W)
        rb, cb = divmod(b, W)
        dx = min(abs(ra - rb), H - abs(ra - rb))
        dy = min(abs(ca - cb), W - abs(ca - cb))
        v = dx * dx + dy * dy
        _D2[k] = v
    return v


def link_cost(deg):
    """第 deg+1 条链的代价：越握越贵（规模报酬递减）。"""
    return C0 * (1.0 + deg / K_SOFT)


def serve(joined, ew, up, tier, uv, cap_total, adj, flat=None, sky_scale=1.0, q=None, ts=1.0):
    """从连上天的那些格出发，按最宽**残量**路分配；整片共享 cap_total。

    v77：路由改成"按松紧"——每一轮都按**剩余容量**重算最宽路。
    原来是每步只算一次静态容量：路一旦被顶住，后面的终端就被**丢掉**（x<=0 → continue），
    而不是改走别的路。画面第 52 行「这根细了那根粗，此松彼紧」说的正是这件事。
    REROUTE=1 时等价于旧行为（消融臂，用来确认只改了这一个东西）。
    """
    import heapq
    load_e, relay_used, served = {}, {}, []
    diag = {"noq": 0, "cap": 0, "budget": 0, "link": 0, "relay": 0, "root": 0,
            "nopath": 0, "cap_total": 0.0, "served": 0.0, "n_try": 0,
            "bw": 0.0, "n_root": 0}
    hop_tot = {}      # v78：按"到根几跳"分的当量
    hop_thick = {}    # v78：其中路径上含粗链的那部分
    qq = q if q is not None else {}
    total = 0.0
    rootload = {}
    remaining = {}
    for _round in range(REROUTE):
        cap, par, root_of = {}, {}, {}
        hops = {}
        pq = []
        # v63：每个根的**上行能力是它自己的连天带宽**（SKY_BW 分级）。
        # v77：并扣掉本步已经压给它的量（残量）。
        for r in up:
            _rc = SKY_BW[tier[r]] * sky_scale - rootload.get(r, 0.0)
            if _rc <= 1e-12:
                continue
            cap[r] = _rc
            par[r] = -1
            root_of[r] = r
            hops[r] = 0
            heapq.heappush(pq, (-_rc, r))
        while pq:
            negc, u = heapq.heappop(pq)
            c = -negc
            if c < cap.get(u, 0.0) - 1e-12:
                continue
            for v in adj.get(u, ()):      # v45：按真实链走，不再按四邻走
                if not joined[v]:
                    continue
                _e = ew.get(ekey(u, v), 0)
                if _e <= 0:
                    continue
                _we = (flat if flat is not None else _e)
                _ce = _we * uv * THETA - load_e.get(ekey(u, v), 0.0)
                if _ce <= 0.0:            # 这条已经顶住了，不参与选路
                    continue
                nc = c if c < _ce else _ce
                _nh = hops.get(u, 0) + 1
                if _nh > MAX_HOP:      # v79：跳数封顶，不许绕远
                    continue
                _old = cap.get(v, 0.0)
                _better = nc > _old + 1e-12
                # 瓶颈一样时，优先少跳（否则"绕远换同样的瓶颈"也会被选中）
                _same_but_shorter = (abs(nc - _old) <= 1e-12
                                     and _nh < hops.get(v, 10 ** 6))
                if _better or _same_but_shorter:
                    cap[v] = nc
                    par[v] = u
                    root_of[v] = root_of[u]
                    hops[v] = _nh
                    heapq.heappush(pq, (-nc, v))

        order = sorted(cap.keys(), key=lambda v: -cap[v])
        moved = 0.0
        for v in order:
            if total >= cap_total - 1e-9:
                break
            if v not in remaining:
                remaining[v] = qq.get(v, D_BASIC * ts)
            _qv = remaining[v]
            if _qv <= 1e-9:
                diag["noq"] += 1
                continue
            diag["n_try"] += 1
            path, u, ok = [], v, True
            while par.get(u, -1) != -1:
                p = par[u]
                k = ekey(u, p)
                if k not in ew:
                    ok = False
                    break
                path.append((k, u, p))
                u = p
                if len(path) > 400:
                    ok = False
                    break
            if not ok:
                diag["nopath"] += 1
                continue
            x = min(_qv, cap[v], cap_total - total)
            _why = "queue" if x >= _qv - 1e-15 else ("cap" if x >= cap[v] - 1e-15 else "budget")
            for (k, _a, _b) in path:
                _wk = (flat if flat is not None else ew.get(k, 0))
                rem = _wk * uv * THETA - load_e.get(k, 0.0)
                if rem < x:
                    x = rem
                    _why = "link"
            for (_k, _a, b) in path[:-1]:
                rem = RELAY_INIT[tier[b]] * uv * ts - relay_used.get(b, 0.0)
                if rem < x:
                    x = rem
                    _why = "relay"
            _rt = root_of.get(v, v)
            rem = SKY_BW[tier[_rt]] * sky_scale - rootload.get(_rt, 0.0)
            if rem < x:
                x = rem
                _why = "root"
            if x <= 1e-9:
                if _why in diag:
                    diag[_why] += 1
                continue
            for (k, _a, _b) in path:
                load_e[k] = load_e.get(k, 0.0) + x
            for (_k, _a, b) in path[:-1]:
                relay_used[b] = relay_used.get(b, 0.0) + x
            rootload[_rt] = rootload.get(_rt, 0.0) + x
            served.append((v, x))
            # v78：这条当量走的是"直接连天"（0 跳）还是"经 k 跳地面"
            hop_tot[len(path)] = hop_tot.get(len(path), 0.0) + x
            if any(ew.get(k, 0) >= 2 for (k, _a, _b) in path):
                hop_thick[len(path)] = hop_thick.get(len(path), 0.0) + x
            remaining[v] = _qv - x
            moved += x
            total += x
        if moved <= 1e-9:      # 这一轮一点也推不动，再算也不会更好
            break
    diag["cap_total"] = cap_total
    diag["served"] = total
    diag["bw"] = float(sum(SKY_BW[tier[r]] for r in up)) * sky_scale / max(1.0, ts)
    diag["n_root"] = len(up)

    # 过火诊断：若允许塞到满（不用 THETA），有效产出 = f*(1-(f/C)^2)
    over = 0.0
    for k, f in load_e.items():
        c = (flat if flat is not None else ew.get(k, 0)) * uv
        if c > 0:
            over += 1.0 - (min(1.0, f / c) ** 2)
    return served, load_e, relay_used, over, hop_tot, hop_thick, diag


def deliver(joined, ew, up, tier, up_known, nhops, via, cap_total, fail_cnt, order):
    """已探明场下的投递：只用本地表逐跳走。

    返回 (delivered 列表, 失败原因计数)。
    """
    fail = {"no_route": 0, "broken": 0, "congest": 0, "cap": 0}
    load_e, relay_used = {}, {}
    delivered = []
    total = 0.0
    entries = set(up)
    for v in order:
        if total + D_BASIC > cap_total:
            fail["cap"] += 1
            continue
        if v in entries:
            delivered.append(v)
            total += D_BASIC
            continue
        if not up_known[v]:
            fail["no_route"] += 1
            continue
        cur, h, path, ok = v, 0, [], True
        while h < HOP_MAX[tier[v]]:
            j = via[cur]
            if j < 0:
                fail["no_route"] += 1
                ok = False
                break
            k = ekey(cur, j)
            if k not in ew or ew[k] <= 0:
                fail_cnt[k] = fail_cnt.get(k, 0) + 1
                up_known[cur] = False      # 撞上了，这条信念作废（失败留痕的雏形）
                via[cur] = -1
                nhops[cur] = 99
                fail["broken"] += 1
                ok = False
                break
            if load_e.get(k, 0.0) + 1.0 > ew.get(k, 0) * U * THETA:
                fail["congest"] += 1
                ok = False
                break
            if j not in entries and relay_used.get(j, 0.0) + 1.0 > RELAY_INIT[tier[j]] * U:
                fail["congest"] += 1
                ok = False
                break
            path.append((k, j))
            cur = j
            h += 1
            if cur in entries:
                break
        if not ok:
            continue
        if cur not in entries:
            fail["no_route"] += 1
            continue
        for (k, _j) in path:
            load_e[k] = load_e.get(k, 0.0) + 1.0
        for (_k, j) in path:
            if j not in entries:
                relay_used[j] = relay_used.get(j, 0.0) + 1.0
        delivered.append(v)
        total += D_BASIC
    return delivered, fail


def _corr(a, b):
    """Spearman 秩相关（并列取平均名次）。样本不足时返回 None。"""
    n = len(a)
    if n < 10:
        return None

    def rank(v):
        idx = sorted(range(n), key=lambda k: v[k])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[idx[j + 1]] == v[idx[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[idx[k]] = avg
            i = j + 1
        return r

    ra, rb = rank(a), rank(b)
    ma = sum(ra) / n
    mb = sum(rb) / n
    num = sum((ra[k] - ma) * (rb[k] - mb) for k in range(n))
    da = sum((ra[k] - ma) ** 2 for k in range(n)) ** 0.5
    db = sum((rb[k] - mb) ** 2 for k in range(n)) ** 0.5
    return num / (da * db) if da > 0 and db > 0 else None


def mem_test(w_mid, relay_mid, ew_now, lacc, frac=0.20):
    """「记忆＝结构」的配对检验。

    同一个中点、同一批链、同一个结果，只换**预测变量**：
      · 结构：链宽 w（记在链上）
      · 节点：累计替别人转发的当量（记在节点上）

    两个口径的结果都报：
      · still：末尾（末 1/4 窗口）还在承载 —— "这条路还是活的"
      · alive：到末尾这条链还在 —— 只问存活，不问流量
    """
    live = [k for k in w_mid if k in ew_now]
    if len(live) < 20:
        return None

    def still(k):
        return 1 if lacc.get(k, 0.0) > 0.0 else 0

    def alive(k):
        return 1 if k in ew_now else 0

    by_w = sorted(live, key=lambda k: (w_mid[k], k))
    m = max(1, int(round(frac * len(by_w))))
    lo_s, hi_s = by_w[:m], by_w[-m:]
    gap_s = (sum(still(k) for k in hi_s) / float(len(hi_s))
             - sum(still(k) for k in lo_s) / float(len(lo_s)))
    gap_s_alive = (sum(alive(k) for k in hi_s) / float(len(hi_s))
                   - sum(alive(k) for k in lo_s) / float(len(lo_s)))

    # 分不分得开：用"高分组里粗链的占比"，不用中位数。
    # 粗链只占 5–10% 时，即使高分组把它们全收进去，中位数仍然是 1（v48 第二跑就卡在这）。
    w_hi = (sum(1 for k in hi_s if w_mid[k] >= 2) / float(len(hi_s))) if hi_s else 0.0
    w_lo = (sum(1 for k in lo_s if w_mid[k] >= 2) / float(len(lo_s))) if lo_s else 0.0
    # 分不开时排序退化成**按节点序号**取两端，而序号在环形网格上带空间含义（离环心远近），
    # 于是会给出一个量级和真效应一样大的假读数（v48 首跑：旧口径 −0.263）。
    sep_s = (w_hi - w_lo) >= 0.05

    nodes = sorted(relay_mid.items(), key=lambda kv: (kv[1], kv[0]))
    mn = max(1, int(round(frac * len(nodes))))
    lo_n = set(_i for _i, _ in nodes[:mn])
    hi_n = set(_i for _i, _ in nodes[-mn:])
    hi_links = [k for k in live if k[0] in hi_n and k[1] in hi_n]
    lo_links = [k for k in live if k[0] in lo_n and k[1] in lo_n]
    if len(hi_links) < 5 or len(lo_links) < 5:
        gap_n = gap_n_alive = None
    else:
        gap_n = (sum(still(k) for k in hi_links) / float(len(hi_links))
                 - sum(still(k) for k in lo_links) / float(len(lo_links)))
        gap_n_alive = (sum(alive(k) for k in hi_links) / float(len(hi_links))
                       - sum(alive(k) for k in lo_links) / float(len(lo_links)))

    return dict(gap_s=gap_s, gap_n=gap_n, sep_s=sep_s, w_hi=w_hi, w_lo=w_lo,
                gap_s_alive=gap_s_alive, gap_n_alive=gap_n_alive,
                base=sum(still(k) for k in live) / float(len(live)),
                base_alive=sum(alive(k) for k in live) / float(len(live)),
                n_live=len(live), n_hi_s=len(hi_s), n_lo_s=len(lo_s),
                n_hi_n=len(hi_links), n_lo_n=len(lo_links))


def _pct(v, qs):
    """分位（最近秩）。v97：v96 的尾部自带这两个，这次拼驱动时漏了，补回。"""
    if not v:
        return [None] * len(qs)
    w = sorted(v)
    return [w[int(q * (len(w) - 1))] for q in qs]

def med(v):
    if not v:
        return -1.0
    w = sorted(v)
    return w[len(w) // 2]


def run_one(job):
    """job = (seed, s0, dt, total, tag[, rep])

    rep：一步之内重复几个"生长回合"。为什么要它——生长/连天是按"每步"掷骰子的，
    换 dt 就等于换了物理速率（20 s 一步和 300 s 一步，同样 0.35 的概率，
    单位时间里的尝试次数差 15 倍）。做两层对比时，必须让**单位时间的尝试次数**相等，
    否则比出来的差异是 dt 造成的，不是分辨率造成的。
    """
    seed, s0v, dt, total, tag = job[:5]
    rep = job[5] if len(job) > 5 else 1
    sky_scale = job[6] if len(job) > 6 else 1.0
    p_adv = job[7] if len(job) > 7 else P_ADV
    e_scale = job[8] if len(job) > 8 else 1.0
    dis_mode = job[9] if len(job) > 9 else "blast"   # blast / scatter / holes / scatter_m
    reach = job[10] if len(job) > 10 else 1
    dc = job[11] if len(job) > 11 else DC
    pre_h = job[12] if len(job) > 12 else PRE_H
    str_w = job[13] if len(job) > 13 else STR_W
    str_b = job[14] if len(job) > 14 else STR_B
    ab_mode = job[15] if len(job) > 15 else "strong"   # strong=按球强 / load=旧口径（只按承载）
    # w_use：加粗排序里"使用"的权重。0 = 纯球强（v48 口径）；越大越偏向"被走过多少"。
    # 归一化用**当步的累计承载最大值**，所以量纲上是 0..1。
    w_use = job[16] if len(job) > 16 else 0.0
    # flat：不为 0 时，承载能力与"这条链几束"脱钩（反事实臂）。0 = 正常口径。
    flat = (1.0 if job[17] else None) if len(job) > 17 else None
    # k_arms：一次出手用几只手臂。p_adv 管"伸不伸"，K 管"同时伸几只手"。
    k_arms = job[18] if len(job) > 18 else 1
    # v52：材料存量的整体倍数。**只改这一样**（候选/额度/劣化曲线/窗口/能耗都不动），
    # 用来把"材料到底约束了什么"单独量出来——前几版一直说"瓶颈在材料/容量"，
    # 但从没单独扫过它，那条结论只是"剩 9%"这一个读数加上三次负结果的推断。
    mat_scale = job[19] if len(job) > 19 else 1.0
    up_sticky = job[20] if len(job) > 20 else 0      # v92：1＝"能不能当根"按设备一次定死
    cov_window = job[21] if len(job) > 21 else 0     # v95：1＝覆盖按过境窗口（整片同时可见/不可见）
    VIS_FRAC = job[22] if len(job) > 22 else 0.10    # 可见相位占整周期的比例（0.10 ⇒ 9 min / 90 min）
    # 独立随机源：不消耗主随机流，所以 sticky=0 与 v91 逐数一致（这才是干净的 A/B）
    _rng_root = Random(seed * 7919 + 13)
    can_root = [(_rng_root.random() < P_UP) for _ in range(N)]
    rng = Random(seed * 9001 + 17 + int(dt))
    tier = []
    for _ in range(N):
        x = rng.random()
        tier.append(0 if x < TIER_SHARE[0] else (1 if x < sum(TIER_SHARE[:2]) else 2))

    joined = [False] * N
    # v57 修：原先没电退出后，别人搭过来会把 joined 又置 True（电量还是负的），
    # 于是下一步立刻再退出 —— 反复进出。退出必须是单向的（画面没有补给）。
    dead = [False] * N
    ew = {}
    th = {}                  # v62：每条链的响应阈值
    qq = {}                  # v64：每台的积压（当量）
    walk_cnt = {}            # v67 只做量测：每条链在窗口里被走过几次
    ub = [0, 0, 0, 0, 0]     # v76：利用率的五档计数（纯量测）
    u_thick = []             # v76：粗链的利用率样本
    u_thin = []              # v76：细链的利用率样本
    th_snap = []             # v71：每 5 步记一次粗链集合（检验"成浪"）
    wk_snap = []             # v74：同一节奏记"这一步被走过"的链（叠图用）
    sn_steps = []            # v74：快照步号（原来不记，暖机期的空集剔不掉）
    walked_any = set()       # v74：整个窗口被走过至少一次的链
    ref_links = set()        # v74：参考时刻的链集合（固定总体）
    cum_dem = 0.0            # 累计需求
    cum_serv = 0.0           # 累计服务（当量）
    first_thick = {}         # 第一次变粗的时刻（给"粗得久"用）
    last_thick = {}          # v75：最后一次仍为粗的时刻
    last_walk = {}           # v75：最后一次被走过的时刻
    thick_steps = {}         # v75：处于"粗"状态的总步数
    lsum_t = 0.0             # v75：过去 1 h 内粗链承载的当量
    lsum_a = 0.0             # v75：同期全部承载的当量
    lsum_nk = 0.0            # v75：同期「粗链条数占比」的逐步累加（富集的同期分母）
    lsum_ns = 0              # v75：同期步数
    hop_all = {}             # v78：全窗口按跳数累计的当量
    hop_thk = {}             # v78：其中含粗链的部分
    dg_sum = {"noq": 0, "cap": 0, "budget": 0, "link": 0, "relay": 0, "root": 0,
              "nopath": 0, "cap_total": 0.0, "served": 0.0, "n_try": 0,
              "bw": 0.0, "n_root": 0}
    n_up_sum = 0             # v78：每步"覆盖区内可连天的终端数"
    n_step_up = 0            # v78：步数
    # 逐束账：stk[k] = [(a 端付了多少, b 端付了多少), ...]，一束一项。
    # 上一版只记"整条链累计投入"，于是 ew 从 3 掉到 2 时**不退料**，
    # 材料在那儿静默消失；而当时的守恒检验用同一本账做分子分母，看不出来。
    stk = {}
    deg = [0] * N
    mat = [MAT0[tier[i]] * mat_scale for i in range(N)]
    energy = [E_INIT[tier[i]] * e_scale for i in range(N)]
    exit_s = []
    t_exit = []          # 每次退出的时刻（小时）：用来核"能活 E_INIT 小时"这个式子
    # 探针要放在**轨道环上**，不是网格正中：轨道环心在网格原点（环形网格），
    # 网格正中离环心 12 格，永远落不在半径 4..12 的环带里 —— 上一版就是这么判错的。
    PROBE = int(R_MID) * W + 0       # 距环心 R_MID 的一格
    hits = []
    covered_once = [False] * N
    first_t = [-1.0] * N
    for s in rng.sample(range(N), SEEDS_PER_CELL):
        joined[s] = True

    # 已探明场：每台只知道"我握着的链"与"邻居回程说的"
    up_known = [False] * N     # 我相信我能通到天（或我本身就是入口）
    nhops = [99] * N           # 我以为的跳数
    via = [-1] * N             # 下一跳
    fail_cnt = {}              # 失败留痕：哪条链试过不通
    # 旧星历：重连者一开始就"记得"一条通往天的路，但那是灾前的，多半已不通。
    # 这就是画面第 9 行"账可能过期，过期就得重做"——它先白跑一趟，撞上了才作废。
    # v44：旧账不再凭空造，在"打灾那一刻"从**真实状态**里取（见下面的灾块）。
    cls = [0] * N            # 0=脱生（从未有过链）1=重连（有过、此刻全断）2=仍在网里
    ever_link = [False] * N  # 是否曾经有过链。没有它就会把"此刻恰好零链但曾经连过"误判成脱生——
                             # v45 第一跑就是这样：reach=3 时断链更多，脱生一下从 0 变 164 台。
    grp = [-1] * N           # 重连者内部随机分组：0 真旧账／1 白纸／2 打乱
    old_nbrs = {}            # 只给 g0（真实）与 g2（打乱）
    dis_done = False
    t_dis = -1.0
    R_pre = 0.0
    cov_pre = 0.0
    links_broken = 0
    first_after = [-1.0] * N
    t_relink = [-1.0] * N    # 灾后第一次重新有链（deg>0）——纯设备行为，不受容量影响
    t_trunk = [-1.0] * N     # 灾后第一次"所在连通分量里有入口"——真正的接回主干
    ntry = [0] * N           # 灾后、接回主干之前，成功伸出过几次链（计数，不受步长量化）
    att = [0, 0, 0]          # 每组发起的连地次数（按次量，不受"被动连上"干扰）
    suc = [0, 0, 0]          # 其中落点已经在主干上的次数
    in_trunk = [False] * N   # 上一步结束时，这台是否已在主干（供本步连地判断落点质量）
    up_prev = []
    dep_prev = {}            # v92：上一步每个根所带的分量（comp, 大小, 该分量的根数）
    orphan_tot = 0           # v92：一个根消失时，连带掉出主干的人数（累计）
    orphan_n = 0             # v92：这类事件次数
    single_frac = []         # v92：单挂（所在分量只有 1 个根）的节点比例
    single_max = []          # v92：最大的"单挂分量"有多大
    jac_root = []            # v92：根集合的逐步 Jaccard（抖动）
    cut_prev = None          # v93：上一步的"被切断"集合
    win_idx = -1             # v96：灾后第几次开窗（第一次记 0）
    prev_vis = False         # v96：上一步可见吗（用来数开窗次数）
    cut0_set = set()         # v96：打灾那一刻被切断的人（分母固定）
    cut0_done = False        # v96：分母只记一次（哪怕那一刻没人被切断）
    cut0_delay = -1          # v96：从打灾到"第一次有根"隔了几步
    # ---- v97：地面自愈（不看到天）----
    # 核心 core＝圆盘外、还在握链（cls==2）的终端：它们是"活下来的那张地面网"。
    # gset0＝打灾那一刻、圆盘内、曾入网、但已不与 core 同分量的终端（固定分母）。
    # t_self[i]＝第一次与 core 同属一个地面分量，是灾后第几步。
    gcore = []
    gcore_done = False
    gset0 = set()
    gset_done = False
    g0_n = 0
    g0_in = 0
    gset_in = set()
    gcore_n = 0
    t_self = [-1] * N
    gcut_series = []
    gcut_in_series = []
    t_win = [-1] * N         # v96：每台在哪个窗口接回
    win_gain = {}            # v96：每个窗口接回多少台
    win_ready = False        # v96：下一拍才开始记接回（打灾那一步不算）
    nup_s = []               # v94：每步的根数
    ncand_s = []             # v94：每步"覆盖区内且在网里"的候选数
    ddis_s = []              # v94：每步覆盖中心到灾心的距离（格）
    rt_saved = None          # v93：**上一步**每个节点所在分量（归因要用它）
    nr_saved = None          # v93：**上一步** 分量→根数
    lost_by_k = {1: 0, 2: 0, 3: 0}   # v93：新掉出的人，按"上一步该分量的根数"分桶（3＝≥3）
    nr_hist = [0, 0, 0, 0, 0]        # v93：分量按根数加权的人数（0/1/2/3/≥4），全程
    nr_hist_w = [0, 0, 0, 0, 0]      # v93：同上，但只统计灾后前 10 步（恢复窗口）
    t_rec = None
    old_intact = [0.0, 0.0, 0.0]
    brk_soft = [0]      # 运行期内自然断裂的次数（不含灾）
    acc = [0.0, 0, 0.0, 0]   # 尾部累计：粗链负载和/条数、细链负载和/条数
    # 记忆检验：中点快照。链宽 w = "历史记在结构上"；relay_cum = "历史记在节点上"。
    # 两者预测同一个结果（末尾这条链还活不活），所以能配对比较。
    w_mid = {}
    relay_mid = {}
    relay_cum = [0.0] * N
    mid_done = False
    iso_after = -1
    # v59 新尺子：恢复曲线。打灾后每步记"仍活着但还没接回主干"的比例，末尾给 AUC 与半衰期。
    # 为什么换："恢复到九成 R"的阈值离灾幅太近，1–3 步就恒成立（台账第 12 条）。
    _den_rec = None
    cur = []
    # v89：新尺子。cut＝活着、没死、所在连通分量里没有任何入口。
    # 与 v88 的 cur 两处不同：不限 deg==0（链还在但整块没根也算）；分母固定在该灾那一刻。
    cut_den = None
    cut_cur = []
    cut_abs = []
    h0_mean = None
    h0_med = None
    h0_f1 = None
    h0_f2 = None
    h0_no = None
    h0_done = False
    # 单步 load_e 常常是空的，只取末 60 步时只有 8% 的链"仍在承载"，分组一算全是噪声。
    # 另记一本末四分之一窗口的累计，专门给记忆检验；不动 v47 那个末 60 步口径。
    _lacc_w = {}
    wstart = total - max(1, int(0.25 * total))
    cum_load = {}          # 全期累计承载：给"按使用加粗"那一臂用
    thick_events = 0
    # 多手诊断：出手次数 / 出手后一条也没搭上的次数 / 实际搭上的手臂数 / 单臂落空次数
    reach_ev = 0
    empty_hand = 0
    # 早期窗口：前 25% 步。全程平均会被"后期材料见底"主导，
    # 那样量到的是"钱花完了"，不是"手够不够用"。
    early_until = total // 4
    reach_ev_e = 0
    empty_hand_e = 0
    arms_used_e = 0
    arms_used = 0
    empty_arm = 0
    deg_cov90 = -1.0
    _lacc = {}               # 每条链在窗口内的累计承载（给 top10 排序用）
    used_old = [0, 0, 0]
    try_link = [0, 0, 0]
    dsum = [0.0, 0.0, 0.0]     # 每组的"伸出去的平均距离"
    dn = [0, 0, 0]
    far_link = 0               # 伸到 >1 格的次数
    try_all = 0                # 所有连地尝试次数（与 far_link 同一总体）
    pre_steps = int(round(pre_h * 3600.0 / dt))

    R_b, R_w, cov_s, upb_s, upn_s, deg_s = [], [], [], [], [], []
    mat0 = sum(mat)
    # 最后一个检查点必须落在仿真范围内：(STEPS-1)*DT = 604500 s。
    # 原先写 604800（正好 7 天整），比最后一步晚 300 s，永远取不到 —— 于是静默变成 0。
    # 检查点不再手写：末点必须由步数算出来。上一版手写 43200 > 末步 42900，又取不到（第二次）。
    CHECKS = [1800.0, 3600.0, 7200.0, 21600.0, (total - 1) * dt]
    R_at, cov_at, ci_ck = {}, {}, 0
    t_cov90 = None
    R_loc_s = []
    spread_s = []
    fail_tot = {"no_route": 0, "broken": 0, "congest": 0, "cap": 0}
    ever = set()
    t90 = None

    for step in range(total):
        t = step * dt
        r_now = R_MID + R_AMP * math.sin(2.0 * math.pi * t / T_DRIFT)
        if r_now < 0.0:
            r_now = 0.0
        ctr = (int(round(r_now * math.cos(OMEGA * t))) % H) * W + \
              (int(round(r_now * math.sin(OMEGA * t))) % W)

        # ---- 中点快照（记忆检验用；与灾无关，是过程的中点）----
        if (not mid_done) and step >= total // 2:
            mid_done = True
            w_mid = dict(ew)
            relay_mid = dict((_i, relay_cum[_i]) for _i in range(N))

        # ---- 灾：只断链，终端不消失（画面第 7 行"球散布在世界上"）----
        if (not dis_done) and step >= pre_steps and dis_mode != "none":
            dis_done = True
            t_dis = t
            R_pre = statistics.mean(R_b[-10:]) if len(R_b) >= 10 else (R_b[-1] if R_b else 0.0)
            w2_pre = (sum(1 for _k in ew if ew[_k] >= 2) / float(max(1, len(ew))))
            cov_pre = cov_s[-1] if cov_s else 0.0
            snap = {}
            for _i in range(N):
                snap[_i] = set(j for j in NBR[_i] if ekey(_i, j) in ew)
            # 灾心必须落在**灾前已并网**的格上（打在空地上等于没打，u1 踩过）；
            # 也不能取网格正中——轨道环心在原点，正中永远在环外（v42 踩过）。
            cand_c = [_i for _i in range(N) if joined[_i]]
            ctr_dis = cand_c[rng.randrange(len(cand_c))]
            _r2 = DIS_R * DIS_R
            if dis_mode == "thin":
                # v88：圆内抽稀。d 取两端到灾心的较小距离（与 blast 判定同口径）。
                links_hit = []
                for k in ew:
                    _d2 = min(dist2(k[0], ctr_dis), dist2(k[1], ctr_dis))
                    if _d2 > _r2:
                        continue
                    _pk = P_KILL_IN * (1.0 - GAMMA * (_d2 / _r2))
                    if _pk >= 0.999999:
                        links_hit.append(k)      # 不抽随机数，保证 p=1 时与 blast 逐数一致
                    elif _pk > 0.0 and rng.random() < _pk:
                        links_hit.append(k)
            elif dis_mode == "blast":
                # 圆盘：同源受灾。你原来的邻居跟你在同一个坑里。
                links_hit = [k for k in ew
                             if dist2(k[0], ctr_dis) <= _r2 or dist2(k[1], ctr_dis) <= _r2]
            elif dis_mode == "holes":
                # 中等相关性：若干个小洞，断链总数与圆盘档相等。
                # 洞小 → 洞边上的重连者，邻居大约一半还在（介于圆盘 0.11 与散点 0.73 之间）。
                _target = sum(1 for k in ew
                              if dist2(k[0], ctr_dis) <= _r2 or dist2(k[1], ctr_dis) <= _r2)
                _chosen = set()
                _cs = list(cand_c)
                rng.shuffle(_cs)
                _ii = 0
                _r2s = DIS_R_S * DIS_R_S
                while _ii < len(_cs):
                    _c = _cs[_ii]
                    _ii += 1
                    _chosen |= set(x for x in range(N) if dist2(x, _c) <= _r2s)
                    _n = sum(1 for k in ew if k[0] in _chosen or k[1] in _chosen)
                    if _n >= _target:
                        break
                links_hit = [k for k in ew if k[0] in _chosen or k[1] in _chosen]
            elif dis_mode == "scatter":
                # 同比例的格随机散开：相关性为零，但**断掉的链更多**
                # （散开的每个格都要断掉它所有的链，圆盘内部是共享的）
                _k = int(round(SCATTER_FRAC * len(cand_c)))
                _pick = set(rng.sample(cand_c, _k))
                links_hit = [k for k in ew if k[0] in _pick or k[1] in _pick]
            elif dis_mode == "scatter_m":
                # scatter_m：**断同样多的链**，只是随机挑 → 只把"相关性"这一个变量换掉
                _nb = sum(1 for k in ew
                          if dist2(k[0], ctr_dis) <= _r2 or dist2(k[1], ctr_dis) <= _r2)
                _all = list(ew.keys())
                rng.shuffle(_all)
                links_hit = _all[:_nb]
            else:
                # trunk：**断同样多的链，但专挑最粗的那些**。
                # v47 把加粗依据改成"球强"之后，粗链集中在少数车载身上（占全网 5%）——
                # 于是"打干线"成了一种新的单点故障。这里量它的后果。
                _nb = sum(1 for k in ew
                          if dist2(k[0], ctr_dis) <= _r2 or dist2(k[1], ctr_dis) <= _r2)
                _all = sorted(ew.keys(), key=lambda k: (-ew[k], k))
                links_hit = _all[:_nb]
            for k in links_hit:
                a_, b_ = k
                if True:
                    for _pa, _pb in stk.pop(k, []):
                        mat[a_] += REFUND * _pa
                        mat[b_] += REFUND * _pb
                    del ew[k]
                    deg[a_] -= 1     # deg 数的是"几条链"（加粗不加 deg），整条断才减 1
                    deg[b_] -= 1
                    links_broken += 1
            iso_after = sum(1 for _i in range(N) if deg[_i] == 0)
            for _i in range(N):
                if not ever_link[_i]:
                    cls[_i] = 0                  # 从来没连过 → 脱生
                elif deg[_i] == 0:
                    cls[_i] = 1                  # 以前连着、现在全断 → 重连
                    joined[_i] = False
                else:
                    cls[_i] = 2                  # 还有链，仍在网里（不参与比较）
            # 重连者随机三分组（同网同刻同总体）
            _rec = [_i for _i in range(N) if cls[_i] == 1]
            rng.shuffle(_rec)
            for _n, _i in enumerate(_rec):
                grp[_i] = _n % 3
            for _i in _rec:
                if grp[_i] == 0:
                    old_nbrs[_i] = snap[_i]                       # 真旧账
                elif grp[_i] == 2:
                    pool = [x for x in range(N) if x != _i and x not in NBR[_i]]
                    old_nbrs[_i] = set(rng.sample(pool, min(len(snap[_i]), len(pool))))
                if grp[_i] in (1, 2):
                    up_known[_i] = False      # 白纸/打乱：连"我以为天在哪"也不记得
                    nhops[_i] = 99
                    via[_i] = -1
            # 操纵是否成功的独立量：重连者的旧邻居里，还有多少是完好的
            _oi = [[], [], []]
            for _i in range(N):
                if grp[_i] >= 0 and snap[_i]:
                    _ok = sum(1 for _j in snap[_i] if cls[_j] == 2)
                    _oi[grp[_i]].append(_ok / float(len(snap[_i])))
            old_intact = [statistics.mean(x) if x else 0.0 for x in _oi]
            first_after = [-1.0] * N

        # 接回主干：并查集算连通分量，看是否与某个入口同属一块。
        # 纯物理量：不看容量配额、不看知识，只问"你和天之间有没有一条路"。
        # 放在连地之前，本步的"落点是否在主干上"才有得判（用上一步的入口，滞后一步可忽略）。
        # v96 修：原来是 `if dis_done and up_prev:`——不可见期 up_prev 为空，
        # 整个测量块被跳过，于是"没有根的时候量不到任何东西"，cut0 变成 0。
        # 现在无论有没有根都跑，_live 为空时 in_trunk 自然全 False。
        if dis_done:
            _par = list(range(N))

            def _find(x):
                while _par[x] != x:
                    _par[x] = _par[_par[x]]
                    x = _par[x]
                return x

            for (_a, _b) in ew:
                _ra, _rb = _find(_a), _find(_b)
                if _ra != _rb:
                    _par[_ra] = _rb
            _live = set(_find(_r) for _r in up_prev)
            _rt = [_find(_x) for _x in range(N)]
            in_trunk = [(_rt[_x] in _live) for _x in range(N)]

            # ---- v97：地面自愈（只用地面链，与根/覆盖无关）----
            if not gcore_done:
                gcore = [_x for _x in range(N)
                         if cls[_x] == 2 and not dead[_x]
                         and dist2(_x, ctr_dis) > DIS_R * DIS_R]
                gcore_done = True
                gcore_n = len(gcore)
            if gcore_done and gcore:
                _crt = set(_rt[_c] for _c in gcore)
                if not gset_done:
                    # v97 改：分母取**全网地面失联**（不只圆盘内）——灾会切断"一端在盘内"的链，
                    # 于是盘外也有人被连带切断。圆盘子集单独存一份，好分开读。
                    gset0 = set(_x for _x in range(N)
                                if cls[_x] in (1, 2) and not dead[_x]
                                and _rt[_x] not in _crt)
                    gset_in = set(_x for _x in gset0
                                  if dist2(_x, ctr_dis) <= DIS_R * DIS_R)
                    g0_n = len(gset0)
                    g0_in = len(gset_in)
                    gset_done = True
                _hip = 0
                _hip_in = 0
                for _x in gset0:
                    if t_self[_x] < 0 and (not dead[_x]) and (_rt[_x] in _crt):
                        t_self[_x] = step - pre_steps
                    if t_self[_x] < 0 and not dead[_x]:
                        _hip += 1
                        if _x in gset_in:
                            _hip_in += 1
                gcut_series.append(_hip)
                gcut_in_series.append(_hip_in)

            # ---- v92：单挂分量 + 根消失的连带 ----
            _sz = {}
            for _x in range(N):
                _c = _rt[_x]
                _sz[_c] = _sz.get(_c, 0) + 1
            _nr = {}
            for _r in up_prev:
                _c = _rt[_r]
                _nr[_c] = _nr.get(_c, 0) + 1
            _dep_now = {}
            for _r in up_prev:
                _c = _rt[_r]
                _dep_now[_r] = (_c, _sz.get(_c, 0), _nr.get(_c, 0))
            if dep_prev:
                for _r, (_c, _s, _n) in dep_prev.items():
                    if _r not in _dep_now and _n == 1:
                        orphan_tot += _s
                        orphan_n += 1
            dep_prev = _dep_now
            # ---- v93：新掉出主干的人，按"上一步它所在分量的根数"归因 ----
            _cut_now = set(_x for _x in range(N)
                           if cls[_x] in (1, 2) and not dead[_x] and not in_trunk[_x])
            # v96 修：分母必须取在"灾后第一次有根"的那一步——那之前两臂都是全体无根，
            # 差集恒为空。顺带记下"从灾到第一次看见天"隔了几步。
            if (not cut0_done) and up_prev:
                cut0_set = set(_cut_now)
                cut0_done = True
                cut0_delay = step - pre_steps
            if cut_prev is not None and rt_saved is not None and nr_saved is not None:
                for _x in _cut_now - cut_prev:
                    _k = nr_saved.get(rt_saved[_x], 0)
                    if _k <= 1:
                        lost_by_k[1] += 1
                    elif _k == 2:
                        lost_by_k[2] += 1
                    else:
                        lost_by_k[3] += 1
            cut_prev = _cut_now
            rt_saved = _rt
            nr_saved = _nr

            # ---- v96：窗口计数与"第几个窗口接回" ----
            if cov_window:
                _vis = ((t % T_ORBIT) / T_ORBIT) < VIS_FRAC
                if _vis and not prev_vis:
                    win_idx += 1
                prev_vis = _vis
            if win_ready:
                for _x in cut0_set:
                    if t_win[_x] < 0 and in_trunk[_x] and not dead[_x]:
                        t_win[_x] = win_idx
                        win_gain[win_idx] = win_gain.get(win_idx, 0) + 1
            win_ready = True
            # 分量按根数加权的人数
            _h = [0, 0, 0, 0, 0]
            # v93 修：没有根的分量里的人也属于 k=0（原来漏了，于是 k=0 份额结构性恒为 0）
            _h[0] += sum(1 for _x in range(N)
                         if cls[_x] in (1, 2) and not dead[_x] and not in_trunk[_x])
            for _c, _k in _nr.items():
                _n = _sz.get(_c, 0)
                if _k >= 4:
                    _h[4] += _n
                else:
                    _h[_k] += _n
            for _q in range(5):
                nr_hist[_q] += _h[_q]
            if len(cut_abs) <= 10:          # 只在恢复窗口里累加
                for _q in range(5):
                    nr_hist_w[_q] += _h[_q]

            _alive_j = sum(1 for x_ in range(N) if joined[x_] and not dead[x_])
            if _alive_j > 0:
                _one = 0
                _mx = 0
                for _c, _k in _nr.items():
                    if _k == 1 and _c in _live:
                        _one += _sz.get(_c, 0)
                        if _sz.get(_c, 0) > _mx:
                            _mx = _sz.get(_c, 0)
                single_frac.append(_one / float(_alive_j))
                single_max.append(_mx)
            for _i in range(N):
                if cls[_i] == 1 and t_trunk[_i] < 0 and in_trunk[_i]:
                    t_trunk[_i] = t - t_dis
        elif dis_done:
            in_trunk = [False] * N
        if dis_done:
            _alive_rec = 0
            _nt = 0
            for _i in range(N):
                if cls[_i] == 1 and not dead[_i]:
                    _alive_rec += 1
                    if t_trunk[_i] < 0:
                        _nt += 1
            if _den_rec is None and _alive_rec > 0:
                _den_rec = _alive_rec
            if _den_rec:
                cur.append(_nt / float(_den_rec))

            # ---- v89 新尺子 ----
            _cut = sum(1 for _i in range(N)
                       if cls[_i] in (1, 2) and not dead[_i] and not in_trunk[_i])
            cut_abs.append(_cut)
            if cut_den is None:
                cut_den = _cut
            if cut_den:
                cut_cur.append(_cut / float(cut_den))

            # 几何 h0：在「可能连」的邻居图上，从每个被切断的人往外 BFS，
            # 走到已经在主干上的人要新建几条链。一步就能碰到记作 h0=1。
            if (not h0_done) and cut_den and cut_den > 0:
                h0_done = True
                _dist = {}
                _dq = []
                for _i in range(N):
                    if in_trunk[_i] and not dead[_i]:
                        _dist[_i] = 0
                        _dq.append(_i)
                _head = 0
                while _head < len(_dq):
                    _u = _dq[_head]
                    _head += 1
                    # 走「几何可达」而不是现有链路：新链能伸 reach 格，
                    # 被切断的人之间也能互相搭（v89 第一次用 NBR=4 邻接，两个都错了）。
                    for _j, _dd in cands(_u, reach):
                        if _j in _dist:
                            continue
                        if dead[_j]:
                            continue
                        _dist[_j] = _dist[_u] + 1
                        _dq.append(_j)
                _h = []
                _no = 0
                for _i in range(N):
                    if cls[_i] in (1, 2) and not dead[_i] and not in_trunk[_i]:
                        if _i in _dist:
                            _h.append(_dist[_i])
                        else:
                            _no += 1
                if _h:
                    h0_mean = statistics.mean(_h)
                    h0_med = statistics.median(_h)
                    h0_f1 = sum(1 for _x in _h if _x <= 1) / float(len(_h))
                    h0_f2 = sum(1 for _x in _h if _x <= 2) / float(len(_h))
                h0_no = (_no / float(max(1, _no + len(_h))))

        # ---- 一、连地：不看覆盖区；两端各付"第 deg+1 条链"的代价 ----
        # 重复 rep 次：让"单位时间的尝试次数"与 dt 无关
        for _rep in range(rep):
          order = [i for i in range(N) if joined[i]]
          rng.shuffle(order)
          for i in order:
              base_i = link_cost(deg[i])
              _pa = p_adv * (OLD_ADV if grp[i] in (0, 2) else 1.0)
              if mat[i] < base_i or rng.random() >= _pa:
                  continue
              # v45：候选是半径 reach 内的任意终端；远的付得更多（姿态对准要功率）
              outs = []
              for j, dist in cands(i, reach):
                  if dead[j]:          # 没电的终端不在候选里（不能被拉回网）
                      continue
                  cj = link_cost(deg[j]) * (1.0 + dc * (dist - 1.0))
                  if mat[j] < cj:
                      continue
                  if (not joined[j]) or (ekey(i, j) not in ew):
                      outs.append((cj, j, dist))
              if not outs:
                  continue
              # 旧经验可继承：优先够"我原来连着的那几个"——它们物理上还在，名单多半有效；
              # 但也可能已经没电／没人在，所以会过期。g2 的名单是错的，走上去就白跑。
              _onb = old_nbrs.get(i)
              if grp[i] >= 0:
                  try_link[grp[i]] += 1
              reach_ev += 1
              _early = step < early_until
              if _early:
                  reach_ev_e += 1
              # ---- 多手：一次出手，最多 K 只手臂 ----
              # 各臂从**同一份候选**里挑目标（先搭后认），但**各自按当时的边际代价付费**：
              # 第 2、3 只手比第 1 只贵（link_cost 随 deg 上升），这是画面"越过限度就劣化"。
              pool = list(outs)
              got = 0
              for _arm in range(k_arms):
                  if not pool:
                      break
                  _pri = [x for x in pool if x[1] in _onb] if _onb else []
                  if _pri and rng.random() < OLD_PRIOR:
                      cj, j, dist = _pri[rng.randrange(len(_pri))]
                      pool = [x for x in pool if x[1] != j]
                      if grp[i] >= 0:
                          used_old[grp[i]] += 1
                  else:
                      cj, j, dist = pool.pop(rng.randrange(len(pool)))
                  ci = link_cost(deg[i]) * (1.0 + dc * (dist - 1.0))
                  cj = link_cost(deg[j]) * (1.0 + dc * (dist - 1.0))
                  if mat[i] < ci or mat[j] < cj:      # 远的／后伸的那只可能付不起
                      empty_arm += 1
                      continue
                  try_all += 1
                  got += 1
                  if dist > 1.0:
                      far_link += 1
                  if grp[i] >= 0:
                      dsum[grp[i]] += dist
                      dn[grp[i]] += 1
                  joined[j] = True
                  k = ekey(i, j)
                  ew[k] = ew.get(k, 0) + 1
                  a_, b_ = k
                  if a_ == i:
                      stk.setdefault(k, []).append((ci, cj))
                  else:
                      stk.setdefault(k, []).append((cj, ci))
                  mat[i] -= ci
                  mat[j] -= cj
                  deg[i] += 1
                  deg[j] += 1
                  ever_link[i] = True
                  ever_link[j] = True
                  if dis_done and cls[i] == 1 and t_trunk[i] < 0:
                      ntry[i] += 1
                  if grp[i] >= 0:
                      att[grp[i]] += 1
                      if in_trunk[j]:
                          suc[grp[i]] += 1
              arms_used += got
              if _early:
                  arms_used_e += got
              if got == 0:
                  empty_hand += 1
                  if _early:
                      empty_hand_e += 1

        # 重新连上（设备行为）：灾后第一次 deg>0。与"被服务"分开记。
        if dis_done:
            for _i in range(N):
                if cls[_i] == 1 and t_relink[_i] < 0 and deg[_i] > 0:
                    t_relink[_i] = t - t_dis

        # ---- 二、连天：三档都能连，带宽不同 ----
        # v95：覆盖可以是"一个移动小盘"，也可以是"整片同时可见/不可见"（过境窗口）。
        if cov_window:
            _vis = ((t % T_ORBIT) / T_ORBIT) < VIS_FRAC
            _in_cov = (lambda _i: True) if _vis else (lambda _i: False)
        else:
            _in_cov = (lambda _i: dist2(_i, ctr) <= R_COVER * R_COVER)
        if _in_cov(PROBE):
            hits.append(t)
        for _i in range(N):
            if not covered_once[_i] and _in_cov(_i):
                covered_once[_i] = True
        cand = [i for i in range(N) if joined[i] and _in_cov(i)]
        rng.shuffle(cand)
        up = []
        bw = 0.0
        for i in cand:
            # v92：sticky=1 时"能不能当根"由设备定（can_root），不每步重掷；
            # sticky=0 时与旧行为逐字相同（消耗同一个 rng）。
            if up_sticky:
                _ok = can_root[i]
            else:
                _ok = (rng.random() < P_UP)
            if _ok:
                up.append(i)
                bw += SKY_BW[tier[i]] * sky_scale
        if up_prev and up:
            _su, _sp = set(up), set(up_prev)
            jac_root.append(len(_su & _sp) / float(len(_su | _sp)))
        if dis_done:
            nup_s.append(len(up))
            ncand_s.append(len(cand))
            try:
                ddis_s.append(math.sqrt(dist2(ctr, ctr_dis)))
            except Exception:
                ddis_s.append(-1.0)
        # v83：速率量 × dt —— 以 dt=120 s 为基准（ts=1 时与旧行为逐数一致）
        _ts = dt / 120.0
        cap_total = min(s0v, bw) * _ts
        up_prev = up
        for i in up:
            up_known[i] = True
            nhops[i] = 0
            via[i] = -1

        # 信念有时效（画面第 31 行"星历会过期，网的结构也会过期"）：
        # 上一步还是入口、这一步已不在覆盖区里的，必须失效。否则所有人的路由
        # 都指向一个早就不通天的格，走到底也够不着——这一版第一跑就是这么错的。
        cur_entries = set(up)
        for i in range(N):
            if up_known[i] and nhops[i] == 0 and i not in cur_entries:
                up_known[i] = False
                nhops[i] = 99
                via[i] = -1

        # 回程读数：每步沿**已经握着的链**重探一次（画面第 17 行"真正的读数从回程来"）。
        # 只在"新搭链"时传知识的版本会死：网长满之后不再有新链，知识就冻在原地。
        adj = build_adj(ew)          # v45：每步重建，谁也不用维护增量
        refr = [i for i in range(N) if joined[i]]
        rng.shuffle(refr)
        for i in refr:
            nbs = adj.get(i, [])
            if not nbs:
                continue
            j = nbs[rng.randrange(len(nbs))]
            if up_known[j] and nhops[j] + 1 < nhops[i]:
                up_known[i] = True
                nhops[i] = nhops[j] + 1
                via[i] = j
            elif up_known[i] and nhops[i] + 1 < nhops[j]:
                up_known[j] = True
                nhops[j] = nhops[i] + 1
                via[j] = i

        # ---- 服务：整片共享 ----
        # v64：先把这一步的需求攒进队列（有上限，攒满就不再涨），再按当量分配。
        for _i in range(N):
            if joined[_i]:
                _q0 = qq.get(_i, 0.0) + D_BASIC * _ts
                _qm = Q_MAX * _ts
                qq[_i] = _q0 if _q0 < _qm else _qm
                cum_dem += D_BASIC * _ts
        if up and cap_total > 0:
            served, load_e, relay_used, over, hop_tot, hop_thick, _dg = serve(
                joined, ew, up, tier, U, cap_total, adj,
                sky_scale=sky_scale * _ts, q=qq, flat=flat, ts=_ts)
        else:
            served, load_e, relay_used, over, hop_tot, hop_thick = [], {}, {}, 0.0, {}, {}
            _dg = {"noq": 0, "cap": 0, "budget": 0, "link": 0, "relay": 0, "root": 0,
                   "nopath": 0, "cap_total": 0.0, "served": 0.0, "n_try": 0,
                   "bw": 0.0, "n_root": 0}

        # 承载的尾部累计：单步 load_e 常常是空的（那一步没有入口），
        # 所以"粗链承载 vs 细链承载"必须累计，不能取某一瞬间。
        for _v, _x in served:
            qq[_v] = max(0.0, qq.get(_v, 0.0) - _x)
            cum_serv += _x
        for _i, _v in relay_used.items():
            relay_cum[_i] += _v
        for _dk in dg_sum:
            dg_sum[_dk] += _dg.get(_dk, 0)
        for _h, _x in hop_tot.items():
            hop_all[_h] = hop_all.get(_h, 0.0) + _x
        for _h, _x in hop_thick.items():
            hop_thk[_h] = hop_thk.get(_h, 0.0) + _x
        n_up_sum += len(up)
        n_step_up += 1

        if load_e:
            # v76：利用率＝实际承载 / 这条链此刻的容量
            for _k, _v in load_e.items():
                _cap = THETA * ew.get(_k, 1) * U
                if _cap > 0:
                    _u = _v / _cap
                    if _u < 0.1:
                        ub[0] += 1
                    elif _u < 0.5:
                        ub[1] += 1
                    elif _u < 0.9:
                        ub[2] += 1
                    elif _u < 0.99:
                        ub[3] += 1
                    else:
                        ub[4] += 1
                    if ew.get(_k, 1) >= 2:
                        u_thick.append(_u)
                    else:
                        u_thin.append(_u)
            for _k, _v in load_e.items():
                cum_load[_k] = cum_load.get(_k, 0.0) + _v
                walk_cnt[_k] = walk_cnt.get(_k, 0) + 1
                walked_any.add(_k)
                last_walk[_k] = step
        if step >= wstart and load_e:
            for _k in ew:
                _lacc_w[_k] = _lacc_w.get(_k, 0.0) + load_e.get(_k, 0.0)

        if step >= total - 60 and load_e:
            for _k in ew:
                _lacc[_k] = _lacc.get(_k, 0.0) + load_e.get(_k, 0.0)
                lsum_a += load_e.get(_k, 0.0)
                if ew[_k] >= 2:
                    acc[0] += load_e.get(_k, 0.0)
                    acc[1] += 1
                    lsum_t += load_e.get(_k, 0.0)
                else:
                    acc[2] += load_e.get(_k, 0.0)
                    acc[3] += 1
            lsum_nk += sum(1 for _k2 in ew if ew[_k2] >= 2) / float(max(1, len(ew)))
            lsum_ns += 1

        # ---- 四、能耗：存量扣减；用完即退出（设备层的老去，与网的老去分开）----
        # 用速率×dt 扣：这是"存量"，不是"每步重置的额度"。
        dt_h = dt / 3600.0
        for i in range(N):
            if not joined[i]:
                continue
            use = (C_IDLE + deg[i] * C_HOLD) * dt_h
            if i in up:
                use += C_SKY * dt_h
            use += relay_used.get(i, 0.0) * C_RELAY
            energy[i] -= use
        # 退出：终端还在（世界上的球不会消失），但它没电了，链跟着没
        for i in range(N):
            if joined[i] and energy[i] <= 0.0:
                joined[i] = False
                up_known[i] = False
                nhops[i] = 99
                via[i] = -1
                # v45：必须删**所有**与它相连的边。原先只遍历 NBR[i]，
                # 一旦允许伸到更远，远处的边会留下来指向一个已经没电的格。
                for j in list(adj.get(i, [])):
                    k = ekey(i, j)
                    if k in ew:
                        for _pa, _pb in stk.pop(k, []):
                            mat[i] += REFUND * _pa
                            mat[j] += REFUND * _pb
                        del ew[k]
                        deg[j] -= 1
                deg[i] = 0
                dead[i] = True
                t_exit.append(t / 3600.0)

        # 同一张网、同一步，两套一起算（配对）
        # 两个臂必须数同一批人：全知那臂把入口也算作"被服务"（入口本身就在上行），
        # 本地这臂若把入口排除在候选之外，两臂的分母就不是一回事——
        # 2026-11-05 自查发现：×1 时全知的 18 个名额几乎全被入口占掉，
        # 而本地只数非入口，两者在量不同的东西，那个"差 3%"因此不成立。
        # 同一张网、同一时刻，用 K 个不同顺序各投递一次：量"先来后到"到底有多大
        order_local = [i for i in range(N) if joined[i]]
        trial = []
        failstat = None
        for _k in range(K_ORDER):
            o = order_local[:]
            rng.shuffle(o)
            loc, fs = deliver(joined, ew, up, tier, up_known, nhops, via,
                              cap_total, fail_cnt, o)
            trial.append(len(loc) / float(N))
            if failstat is None:
                failstat = fs
        R_loc = statistics.mean(trial)
        sp = (max(trial) - min(trial)) / R_loc if R_loc > 0 else 0.0

        n_join = sum(1 for i in range(N) if joined[i])
        _units = sum(_x for _v, _x in served)
        R_basic = _units / float(N)                           # v64：按当量（不再按台数）
        R_broad = min(_units, int(cap_total // D_BROAD)) / float(N)
        for _v, _x in served:
            if first_t[_v] < 0:
                first_t[_v] = t
            if dis_done and first_after[_v] < 0:
                first_after[_v] = t - t_dis
        if dis_done and t_rec is None and R_pre > 0 and R_basic >= 0.9 * R_pre:
            t_rec = (t - t_dis) / 3600.0
        R_loc_s.append(R_loc)
        spread_s.append(sp)
        R_b.append(R_basic)
        R_w.append(R_broad)
        cov_s.append(n_join / float(N))
        upb_s.append(bw)
        upn_s.append(len(up))
        deg_s.append(sum(deg) / float(max(1, sum(1 for i in range(N) if joined[i]))))
        exit_s.append(sum(1 for i in range(N) if energy[i] <= 0.0) / float(N))
        if t_cov90 is None and n_join >= 0.9 * N:
            t_cov90 = t / 3600.0
            deg_cov90 = sum(deg) / float(max(1, n_join))
        while ci_ck < len(CHECKS) and t >= CHECKS[ci_ck]:
            R_at[CHECKS[ci_ck]] = R_basic
            cov_at[CHECKS[ci_ck]] = n_join / float(N)
            ci_ck += 1
        for _k in failstat:
            fail_tot[_k] += failstat[_k]
        ever.update(_v for _v, _x in served)
        if t90 is None and R_basic >= 0.9 * max(1e-9, max(R_b)):
            pass

        # ---- 五、加粗（v62：响应阈值律，Theraulaz 1998 式(1)(2)(3)）----
        # 状态：每条链一个阈值 th[k]（"愿不愿意再加一束"）。刺激 s＝这条链**本步**的待承载量。
        # 加粗概率 T = s^2/(s^2+th^2)（原式，不改成硬阈值：分级量不做成二值）。
        # 阈值双向更新：本步成功承载 → th -= delta*dt_h；没承载（没用上或没用成）→ th += phi*dt_h。
        # 「容易粗」落在 delta 与 th 初值上，「粗得久」落在 phi 上——画面对应的就是这两处。
        for k in ew:
            if k not in th:
                _a0, _b0 = k
                _sk0 = 0.5 * (STR[tier[_a0]] * min(1.0, energy[_a0] / E_INIT[tier[_a0]])
                              + STR[tier[_b0]] * min(1.0, energy[_b0] / E_INIT[tier[_b0]]))
                th[k] = TH0 * (1.0 + TH_STR * (1.0 - _sk0))    # 强球初值更低＝容易粗
        _dt_h = dt / 3600.0
        for k in list(ew):
            _ld = load_e.get(k, 0.0)
            _a0, _b0 = k
            _sk0 = 0.5 * (STR[tier[_a0]] * min(1.0, energy[_a0] / E_INIT[tier[_a0]])
                          + STR[tier[_b0]] * min(1.0, energy[_b0] / E_INIT[tier[_b0]]))
            _dl = DELTA * (0.5 + _sk0)          # 强球学得快
            _ph = PHI * (1.5 - _sk0)            # 强球忘得慢
            if _ld > 0.0:
                th[k] = th[k] - _dl * _dt_h
            else:
                th[k] = th[k] + _ph * _dt_h
            if th[k] < TH_MIN:
                th[k] = TH_MIN
            elif th[k] > TH_MAX:
                th[k] = TH_MAX
            # v68：**取消刺激**。画面说"试稳了的链变粗"——试的是通不通，不是忙不忙。
            # 蚂蚁模型里那个 s 是任务需求，画面里没有这个量，是我借来的（清单 A49）。
            # 于是 T 只由阈值定：T = 1/(1+θ²)。θ 小（常成）→ T≈1；θ 大（久不用）→ T≈0。
            _t2 = th[k] * th[k]
            _T = 1.0 / (1.0 + _t2)
            # 加一束：概率 eps*T，且付得起
            # v84：EPS 是「每步重排概率」，单位时间的重排次数 ∝ 1/dt，必须乘 ts
            if ew.get(k, 0) < W_MAX and rng.random() < EPS * _ts * _T:
                ca, cb = link_cost(deg[_a0]), link_cost(deg[_b0])
                if mat[_a0] >= ca and mat[_b0] >= cb:
                    ew[k] += 1
                    thick_events += 1
                    stk.setdefault(k, []).append((ca, cb))
                    mat[_a0] -= ca
                    mat[_b0] -= cb
                    if ew[k] == 2 and k not in first_thick:
                        first_thick[k] = step
            # 减一束：概率 eps*(1-T)，独立的一项（系数不同、驱动量不同，不是加粗取负号）
            elif ew.get(k, 0) > 1 and rng.random() < EPS * _ts * (1.0 - _T):
                ew[k] -= 1
                _pa, _pb = stk[k].pop()
                mat[_a0] += REFUND * _pa
                mat[_b0] += REFUND * _pb

        if step == REF_STEP:
            ref_links = set(ew)
        # v75：粗的持续期要「每一步都在看」，不能只看刚加粗那一刻。
        for _k in ew:
            if ew[_k] >= 2:
                last_thick[_k] = step
                thick_steps[_k] = thick_steps.get(_k, 0) + 1
        if step % 5 == 0:
            th_snap.append(frozenset(_k for _k in ew if ew[_k] >= 2))
            wk_snap.append(frozenset(_k for _k in load_e))
            sn_steps.append(step)

        # ---- 三、断裂：只删链，终端常驻；按当初付的代价回收 ----
        # 断裂按"每秒速率"归一：p_step = 1-(1-p_20s)^(dt/20)
        p_lose = 1.0 - (1.0 - P_LOSE) ** (dt / 20.0)
        # v46：粗得久 —— 强球两端的链更稳（画面第 52 行"链稳、粗得久"）。
        # str_b=0 时退回 v45 的"只看我有多粗只"。
        _sk2 = {}
        for k in ew:
            _av, _bv = k
            _sk2[k] = 0.5 * (STR[tier[_av]] * min(1.0, energy[_av] / E_INIT[tier[_av]])
                             + STR[tier[_bv]] * min(1.0, energy[_bv] / E_INIT[tier[_bv]]))
        for k in list(ew):
            if rng.random() < p_lose / (1.0 + ew[k]) / (1.0 + str_b * _sk2.get(k, 0.0)):
                a, b = k
                if ew[k] > 1:
                    ew[k] -= 1
                    _pa, _pb = stk[k].pop()      # 掉一束，退一束的料
                    brk_soft[0] += 1
                    mat[a] += REFUND * _pa
                    mat[b] += REFUND * _pb
                else:
                    brk_soft[0] += 1
                    del ew[k]
                    for _pa, _pb in stk.pop(k, []):
                        mat[a] += REFUND * _pa
                        mat[b] += REFUND * _pb
                    deg[a] -= 1
                    deg[b] -= 1

    tail = max(1, min(60, len(R_b)))
    return {
        "seed": seed, "dt": dt, "total": total, "tag": tag, "s0": s0v,
        "sky_scale": sky_scale, "p_adv": p_adv,
        "p_kill_in": P_KILL_IN,
        "ctr_dis": (ctr_dis if dis_done else -1),
        "reach_used": reach,
        "cov_end": statistics.mean(cov_s[-tail:]),
        "R_basic": statistics.mean(R_b[-tail:]),
        "R_broad": statistics.mean(R_w[-tail:]),
        "up_bw": statistics.mean(upb_s[-tail:]),
        "up_n": statistics.mean(upn_s[-tail:]),
        "R_b_series": R_b,
        "deg_mean": statistics.mean(deg_s[-tail:]),
        "deg_cov90": deg_cov90,
        "R_local": statistics.mean(R_loc_s[-tail:]),
        "R_p10": sorted(R_b[-tail:])[max(0, int(0.10 * tail) - 1)],
        "R_p50": sorted(R_b[-tail:])[int(0.50 * tail) - 1],
        "R_p90": sorted(R_b[-tail:])[min(tail - 1, int(0.90 * tail))],
        "t_cov90_h": t_cov90 if t_cov90 is not None else -1.0,
        "R_at": {str(int(k)): v for k, v in R_at.items()},
        "cov_at": {str(int(k)): v for k, v in cov_at.items()},
        "mat_end": sum(mat) + sum(x + y for v in stk.values() for (x, y) in v),
        "stk_mismatch": sum(1 for k in ew if len(stk.get(k, [])) != ew[k]),
        "strand_total": sum(len(v) for v in stk.values()),
        "exit_frac": exit_s[-1] if exit_s else 0.0,
        "n_exit": len(t_exit),
        "t_exit_p": _pct(t_exit, (0.10, 0.50, 0.90)),
        "probe_gap_h": ((hits[-1] - hits[0]) / 3600.0 / (len(hits) - 1)) if len(hits) > 1 else -1.0,
        "probe_hits": len(hits),
        "ever_cov": sum(1 for x in covered_once if x) / float(N),
        "R_pre": R_pre, "cov_pre": cov_pre, "links_broken": links_broken,
        "n_rec": sum(1 for x in cls if x == 1),
        "n_new": sum(1 for x in cls if x == 0),
        "n_kept": sum(1 for x in cls if x == 2),
        "first_g0": [first_after[_i] for _i in range(N) if grp[_i] == 0 and first_after[_i] >= 0],
        "first_g1": [first_after[_i] for _i in range(N) if grp[_i] == 1 and first_after[_i] >= 0],
        "first_g2": [first_after[_i] for _i in range(N) if grp[_i] == 2 and first_after[_i] >= 0],
        "n_g": [sum(1 for x in grp if x == _g) for _g in (0, 1, 2)],
        "relink_g0": [t_relink[_i] for _i in range(N) if grp[_i] == 0 and t_relink[_i] >= 0],
        "relink_g1": [t_relink[_i] for _i in range(N) if grp[_i] == 1 and t_relink[_i] >= 0],
        "relink_g2": [t_relink[_i] for _i in range(N) if grp[_i] == 2 and t_relink[_i] >= 0],
        "n_relinked": sum(1 for _i in range(N) if cls[_i] == 1 and t_relink[_i] >= 0),
        "trunk_g0": [t_trunk[_i] for _i in range(N) if grp[_i] == 0 and t_trunk[_i] >= 0],
        "trunk_g1": [t_trunk[_i] for _i in range(N) if grp[_i] == 1 and t_trunk[_i] >= 0],
        "trunk_g2": [t_trunk[_i] for _i in range(N) if grp[_i] == 2 and t_trunk[_i] >= 0],
        "n_trunk": sum(1 for _i in range(N) if cls[_i] == 1 and t_trunk[_i] >= 0),
        "try_g0": [ntry[_i] for _i in range(N) if grp[_i] == 0 and t_trunk[_i] >= 0],
        "try_g1": [ntry[_i] for _i in range(N) if grp[_i] == 1 and t_trunk[_i] >= 0],
        "try_g2": [ntry[_i] for _i in range(N) if grp[_i] == 2 and t_trunk[_i] >= 0],
        "att": list(att), "suc": list(suc),
        "t_rec_h": t_rec if t_rec is not None else -1.0,
        "str_w": str_w, "str_b": str_b,
        "dis_mode": dis_mode, "reach": reach, "dc": dc,
        "w2_strong": (sum(1 for k in ew if ew[k] >= 2
                          for _x in k if tier[_x] == 2) / float(max(1, 2 * sum(1 for k in ew if ew[k] >= 2)))),
        "net_strong": sum(1 for i in range(N) if tier[i] == 2) / float(N),
        "n_w2": sum(1 for k in ew if ew[k] >= 2),
        "ab_mode": ab_mode,
        "w2_frac": sum(1 for k in ew if ew[k] >= 2) / float(max(1, len(ew))),
        "w_mean": sum(ew.values()) / float(max(1, len(ew))),
        "w_max": max(ew.values()) if ew else 0,
        # 物理合理性：粗链应当承载更多。若粗链的承载反而更低，说明"粗"建在了没人走的地方。
        # 注意：没有粗链时**不能返回 -1.0 之类的哨兵**——它会被当成一个观测值混进均值
        # （纪律 28 的同族：默认值不许伪装成观测）。这里返回 None，聚合时剔掉。
        # 尾部累计口径；无样本时给 None（不许用哨兵伪装成观测）
        "load_thick": (acc[0] / acc[1]) if acc[1] else None,
        "load_thin": (acc[2] / acc[3]) if acc[3] else None,
        "top10_thick": (sum(1 for k in sorted(ew, key=lambda x: -_lacc.get(x, 0.0))[:10]
                            if ew[k] >= 2)),
        "break_total": links_broken,
        "thick_events": thick_events,
        "thick_ever": len(first_thick),
        # 自查修正：原来只有 thick_alive＝"还在"，那不是"粗得久"。
        # 链被削回一束仍然在 ew 里，所以"还在"会把"已经不粗了"算成"粗得久"。
        "thick_alive": (sum(1 for _k in first_thick if _k in ew) / float(len(first_thick))
                        if first_thick else None),
        "thick_still": (sum(1 for _k in first_thick if ew.get(_k, 0) >= 2)
                        / float(len(first_thick)) if first_thick else None),
        "thick_ever_n": len(first_thick),
        # v75：真的"粗得久"＝从第一次变粗到最后一次还粗的时长（步）
        "thick_dur_p": _pct([last_thick.get(_k, first_thick[_k]) - first_thick[_k]
                             for _k in first_thick], (0.10, 0.50, 0.90)),
        # 停走之后还能粗多久（末态仍粗的链）
        "after_walk_p": _pct([(total - 1) - last_walk[_k]
                              for _k in ew if ew[_k] >= 2 and _k in last_walk], (0.10, 0.50)),
        # 承载份额：粗链吃了多少流量，相对其条数占比的富集
        "duty_p": _pct([thick_steps.get(_k, 0) / float(max(1, last_thick.get(_k, first_thick[_k]) - first_thick[_k] + 1))
                        for _k in first_thick], (0.10, 0.50, 0.90)),
        "share_load": (lsum_t / lsum_a) if lsum_a > 0 else None,
        # 富集＝承载份额 / 同期的条数占比（同一个 1 h 窗口，不用末态快照当分母）
        "enrich": ((lsum_t / lsum_a) / (lsum_nk / lsum_ns)
                   if lsum_a > 0 and lsum_nk > 0 and lsum_ns else None),
        "th_p": _pct([v for v in th.values()], (0.10, 0.50, 0.90)),
        "eps": EPS,
        "cut_den": cut_den,
        "cut_first": (cut_cur[0] * cut_den) if (cut_cur and cut_den) else None,
        "cut_last": (cut_abs[-1] if cut_abs else None),
        "cut_t50": (next((_k for _k, _v in enumerate(cut_cur) if _v <= 0.5), None)
                    if cut_cur and cut_cur[0] > 0 else None),
        "cut_auc": (statistics.mean(cut_cur) if cut_cur else None),
        "cut_n": len(cut_cur),
        "h0_mean": h0_mean,
        "h0_med": h0_med,
        "h0_f1": h0_f1,
        "h0_f2": h0_f2,
        "h0_no": h0_no,
        "up_sticky": up_sticky,
        "cov_window": cov_window,
        "win_n": win_idx + 1,
        "cut0_n": len(cut0_set),
        "cut0_list": sorted(cut0_set),
        "g0_n": g0_n,
        "g0_in": g0_in,
        "gset_in_list": sorted(gset_in),
        "gcut_in_series": list(gcut_in_series),
        "gcore_n": gcore_n,
        "gset0_list": sorted(gset0),
        "t_self": list(t_self),
        "gcut_series": list(gcut_series),
        "cut0_delay": cut0_delay,
        "t_win": list(t_win),
        "win_gain": dict((int(k), v) for k, v in win_gain.items()),
        "vis_frac": VIS_FRAC,
        "orphan_tot": orphan_tot,
        "orphan_n": orphan_n,
        "orphan_mean": (orphan_tot / float(orphan_n)) if orphan_n else None,
        "single_frac": (statistics.mean(single_frac) if single_frac else None),
        "single_max": (max(single_max) if single_max else None),
        "jac_root": (statistics.mean(jac_root) if jac_root else None),
        "lost_k1": lost_by_k[1],
        "lost_k2": lost_by_k[2],
        "lost_k3": lost_by_k[3],
        "nr_hist": list(nr_hist),
        "nr_hist_w": list(nr_hist_w),
        "nup_s": list(nup_s),
        "ncand_s": list(ncand_s),
        "ddis_s": list(ddis_s),
        "cut_series": list(cut_abs),
        "reroute": REROUTE,
        "max_hop": MAX_HOP,
        "n_step": total,
        "ts": _ts,
        "diag": dict(dg_sum),
        "hop_all": dict(hop_all),
        "hop_thick": dict(hop_thk),
        "up_frac": (n_up_sum / float(max(1, n_step_up))) / float(N),
        "jac": _jac(th_snap, sn_steps, 30),
        "jac_walk": _jac(wk_snap, sn_steps, 30),
        "n_snap": len(th_snap),
        "n_snap_warm": sum(1 for _t in sn_steps if _t >= 30),
        # 叠图：粗链里有多大比例"最近这一格被走过"（同期）
        "ov": [(_inter(a, b) / float(len(a)) if a else None)
               for a, b in zip(th_snap, wk_snap)],
        "w2_pre": (w2_pre if dis_done else None),
        "util_buckets": list(ub),
        "util_thick_p": _pct(u_thick, (0.10, 0.50, 0.90)),
        "util_thin_p": _pct(u_thin, (0.10, 0.50, 0.90)),
        "util_thick_n": len(u_thick),
        "util_thin_n": len(u_thin),
        "walk_p": _pct(list(walk_cnt.values()), (0.10, 0.50, 0.90, 1.00)),
        # 原口径把"建得晚、还没轮到"算进"从未被走"（分母是末态全体）。
        # 这里另给一个固定总体的读数：只问参考时刻（第 60 步）就在的链。
        "walk_zero": (sum(1 for _k in ref_links if _k not in walked_any)
                      / float(max(1, len(ref_links)))),
        "walk_zero_old": (sum(1 for _k in ew if walk_cnt.get(_k, 0) == 0) / float(max(1, len(ew)))),
        "walk_mean": (sum(walk_cnt.values()) / float(max(1, len(walk_cnt)))),
        "q_mean": (sum(qq[_i] for _i in range(N) if joined[_i]) /
                   float(max(1, sum(1 for _i in range(N) if joined[_i])))),
        "q_p90": (_pct([qq[_i] for _i in range(N) if joined[_i]], (0.90,))[0]),
        "clear_rate": (cum_serv / cum_dem if cum_dem > 0 else None),
        # 为什么加了 w_use 没变化？因为两套排序可能是同一批链。
        # 这里量"球强分"与"累计承载"在末态全部链上的秩相关：若接近 1，加权等于没加权。
        "corr_str_use": _corr(
            [0.5 * (STR[tier[_k[0]]] * min(1.0, energy[_k[0]] / E_INIT[tier[_k[0]]])
                   + STR[tier[_k[1]]] * min(1.0, energy[_k[1]] / E_INIT[tier[_k[1]]]))
             for _k in ew],
            [cum_load.get(_k, 0.0) for _k in ew]),
        "w_use": w_use,
        "k_arms": k_arms,
        "reach_ev": reach_ev,
        "empty_hand_rate": (empty_hand / float(reach_ev)) if reach_ev else None,
        "arms_per_reach": (arms_used / float(reach_ev)) if reach_ev else None,
        "empty_arm_rate": (empty_arm / float(max(1, reach_ev * k_arms))),
        "eh_early": (empty_hand_e / float(reach_ev_e)) if reach_ev_e else None,
        "arms_early": (arms_used_e / float(reach_ev_e)) if reach_ev_e else None,
        "flat": (1 if flat is not None else 0),
        # 集中度：粗链是不是堆在少数几台身上，以及上限由谁在管。
        # 不用"要不要压集中"这种问法——画面第 7 行的"越过限度就劣化"若在起作用，
        # 集中本来就有上限；这里只是把上限量出来。
        "conc_max": max([sum(1 for k in ew if ew[k] >= 2 and i in k) for i in range(N)] or [0]),
        "conc_top1": (max([sum(1 for k in ew if ew[k] >= 2 and i in k) for i in range(N)] or [0])
                      / float(max(1, sum(1 for k in ew if ew[k] >= 2)))),
        "deg_max": max(deg) if deg else 0,
        # 分布先行（纪律 41）：度数若几乎恒定，所有以它为自变量的结论都退化。
        "deg_p": _pct(deg, (0.10, 0.50, 0.90)),
        # "够不够料"与"贵不贵"是两件事：cant_afford 说多少人买不起下一条，
        # price_next 说下一条本身多贵（＝劣化曲线走到第几档）。只报前者，
        # 分不清"料不够"和"价格曲线自己把上限压住了"。
        "price_next": statistics.mean([link_cost(deg[i]) for i in range(N) if joined[i]] or [0.0]),
        "joined_frac": sum(1 for i in range(N) if joined[i]) / float(N),
        "mat_scale": mat_scale,
        # ⚠ 这里差点又写成同义反复：`sum(mat) + Σ链上投入` 恒等于 mat0，
        # 那是记账方式的另一种写法（v39 已判过，纪律 29）。要判"材料是不是卡住"，
        # 只能看**手上还剩多少**，以及**有多少台已经买不起下一条**。
        "mat_free": sum(mat) / float(max(1, mat0)),
        "cant_afford": (sum(1 for i in range(N) if joined[i] and mat[i] < link_cost(deg[i]))
                        / float(max(1, sum(1 for i in range(N) if joined[i])))),
        "iso_after": iso_after,
        # ⚠ 自查更正（v52 跑完之后才发现）：`iso_after` 是**打灾那一刻的快照**
        # （`deg==0` 的台数），它由圆盘几何在 t_dis 就定死了，之后花多少料都改不了它。
        # 拿它去问"材料是否改善灾后韧性"是判据错（指代错时点），不是对象不成立。
        # 真正的"灾后还连不上"要看**末态**：仍零链、或重连了却始终没接回主干。
        "iso_end": sum(1 for _i in range(N) if deg[_i] == 0),
        "not_trunk": sum(1 for _i in range(N) if cls[_i] == 1 and t_trunk[_i] < 0),
        # 恢复曲线：AUC（越小越快）、半衰期（步）、以及首末值
        "rec_auc": (statistics.mean(cur) if cur else None),
        "rec_first": (cur[0] if cur else None),
        "rec_last": (cur[-1] if cur else None),
        "rec_t50": (next((_k for _k, _v in enumerate(cur) if _v <= 0.5 * cur[0]), None)
                     if cur and cur[0] > 0 else None),
        "rec_n": len(cur),
        "mem": (mem_test(w_mid, relay_mid, ew, _lacc_w) if dis_mode == "none" else None),
        "brk_soft": brk_soft[0],
        "n_edges_end": len(ew),
        "n_pairs": len(ew),
        "n_bundles": sum(ew.values()),
        "n_joined": sum(1 for _i in range(N) if joined[_i]),
        "mean_dist": [(dsum[_g] / dn[_g] if dn[_g] else -1.0) for _g in (0, 1, 2)],
        "far_frac": far_link / float(try_all) if try_all else 0.0,
        "old_intact": list(old_intact),
        "used_frac": [(used_old[_g] / float(try_link[_g]) if try_link[_g] else 0.0)
                      for _g in (0, 1, 2)],
        "cov_after_end": cov_s[-1] if cov_s else 0.0,
        "e_scale": e_scale,
        "mat0": mat0,
        "spread": statistics.mean(spread_s[-tail:]),
        "fail": dict(fail_tot),
        "R_basic_win": len(ever) / float(N),
    }


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    out = []
    for g in (1, 2, 4, 8, 16, 32):
        num = 0
        den = 0
        for t in range(len(snaps) - g):
            if steps[t] < warm or steps[t + g] < warm:
                continue
            u = len(snaps[t] | snaps[t + g])
            if u == 0:
                continue
            num += len(snaps[t] & snaps[t + g])
            den += u
        out.append((num / float(den)) if den else None)
    return out


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    out = []
    for g in (1, 2, 4, 8, 16, 32):
        num = 0
        den = 0
        for t in range(len(snaps) - g):
            if steps[t] < warm or steps[t + g] < warm:
                continue
            u = len(snaps[t] | snaps[t + g])
            if u == 0:
                continue
            num += len(snaps[t] & snaps[t + g])
            den += u
        out.append((num / float(den)) if den else None)
    return out


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    out = []
    for g in (1, 2, 4, 8, 16, 32):
        num = 0
        den = 0
        for t in range(len(snaps) - g):
            if steps[t] < warm or steps[t + g] < warm:
                continue
            u = len(snaps[t] | snaps[t + g])
            if u == 0:
                continue
            num += len(snaps[t] & snaps[t + g])
            den += u
        out.append((num / float(den)) if den else None)
    return out


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    out = []
    for g in (1, 2, 4, 8, 16, 32):
        num = 0
        den = 0
        for t in range(len(snaps) - g):
            if steps[t] < warm or steps[t + g] < warm:
                continue
            u = len(snaps[t] | snaps[t + g])
            if u == 0:
                continue
            num += len(snaps[t] & snaps[t + g])
            den += u
        out.append((num / float(den)) if den else None)
    return out


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    out = []
    for g in (1, 2, 4, 8, 16, 32):
        num = 0
        den = 0
        for t in range(len(snaps) - g):
            if steps[t] < warm or steps[t + g] < warm:
                continue
            u = len(snaps[t] | snaps[t + g])
            if u == 0:
                continue
            num += len(snaps[t] & snaps[t + g])
            den += u
        out.append((num / float(den)) if den else None)
    return out


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    out = []
    for g in (1, 2, 4, 8, 16, 32):
        num = 0
        den = 0
        for t in range(len(snaps) - g):
            if steps[t] < warm or steps[t + g] < warm:
                continue
            u = len(snaps[t] | snaps[t + g])
            if u == 0:
                continue
            num += len(snaps[t] & snaps[t + g])
            den += u
        out.append((num / float(den)) if den else None)
    return out


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    return [None] * 6


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    return [None] * 6


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    return [None] * 6


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    return [None] * 6


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    return [None] * 6


REF_STEP = 60


def _inter(a, b):
    return len(a & b)


def _jac(snaps, steps, warm):
    return [None] * 6


# -*- coding: utf-8 -*-
"""v98 驱动：四块，每块只动一个量。

块 A（两段是否可加）：过境窗口下，地面自愈**全部**早于"第一根出现"吗？
  占空比 0.05（每 90 min 只开 2.25 步）vs 1.00（一直可见）。两臂 t50 一样 ⇒ 地面自愈与天无关。

块 B（reach 与系数 2.5）：原预测"多跳串联 ⇒ 所需跳数 = ceil(DIS_R/reach)"，
  即 t50(1):t50(3):t50(5) ≈ 3:1:1。**这一条是拿来被否的**：单例探针已看到 reach=1 反而更快，
  所以这里正式量，并把"离灾心多远"分档，看结构。

块 C（当根的电价）：C_SKY 0/1/2/4，退出台数是否随"当根每小时付的电"单调上升。

块 D（前沿宽度）：若机制是"前沿按 (周长 × p_adv) 逐格推进"，则
  t50 ≈ (g0/2)/(周长·p_adv) ⇒ t50 ∝ R（因为 g0 ∝ R²、周长 ∝ R）。
  预登记：t50(3):t50(6):t50(9) ≈ 1:2:3（±30%）。
"""
import json
import statistics
import sys

import v98

SEEDS = [1, 2, 3, 4, 5, 6, 7, 8]
DT = 120
PRE_H = 3.25
PA = 0.35


def mean(v):
    v = [x for x in v if x is not None]
    return statistics.mean(v) if v else None


def f1(x):
    return "%.2f" % x if x is not None else "NA"


def t_q(nodes, t_self, q):
    n = len(nodes)
    if n == 0:
        return None
    need = q * n
    done = sorted(t_self[i] for i in nodes if t_self[i] >= 0)
    if len(done) < need:
        return None
    return float(done[int(need) - 1])


def run(pi, pa, cw, vf, post_h, tag, reach=3):
    steps = int(round((PRE_H + post_h) * 3600.0 / DT))
    v98.P_KILL_IN = pi
    rows = []
    for sd in SEEDS:
        r = v98.run_one((sd, v98.S0, DT, steps, tag, 1, 1.0, pa, 1.0, "thin", reach, v98.DC,
                         PRE_H, 1.0, 1.0, "mix", 0.0, 0, 1, 1.0, 0, cw, vf))
        assert abs(r["p_adv"] - pa) < 1e-12, "p_adv 没生效"
        assert abs(r["p_kill_in"] - pi) < 1e-12, "p_kill_in 没生效"
        assert r["cov_window"] == cw, "cov_window 没生效"
        assert r["reach_used"] == reach, "reach 没生效"
        rows.append(r)
    return rows


def summ(rows):
    g0 = mean([r["g0_n"] for r in rows])
    t50 = mean([t_q(r["gset0_list"], r["t_self"], 0.5) for r in rows])
    t90 = mean([t_q(r["gset0_list"], r["t_self"], 0.9) for r in rows])
    tall = mean([max([r["t_self"][i] for i in r["gset0_list"]] or [0]) for r in rows])
    delay = mean([r["cut0_delay"] for r in rows])
    early = mean([(sum(1 for i in r["gset0_list"]
                       if 0 <= r["t_self"][i] <= r["cut0_delay"])
                   / float(max(1, len(r["gset0_list"])))) for r in rows])
    late = mean([(sum(1 for i in r["gset0_list"]
                      if r["t_self"][i] > r["cut0_delay"])
                  / float(max(1, len(r["gset0_list"])))) for r in rows])
    return dict(g0=g0, t50=t50, t90=t90, tall=tall, delay=delay,
                early=early, late=late,
                ex=mean([r["n_exit"] for r in rows]),
                ne=mean([r["n_edges_end"] for r in rows]))


def bands(rows, R):
    """按"到灾心距离"分档的中位 t_self（只用 seed 级逐点数据）。"""
    W, H = v98.W, v98.H
    acc = {}
    for r in rows:
        c = r["ctr_dis"]
        if c < 0:
            continue
        for i in r["gset0_list"]:
            t = r["t_self"][i]
            if t < 0:
                continue
            ax, ay = i % W, i // W
            bx, by = c % W, c // W
            dx = min(abs(ax - bx), W - abs(ax - bx))
            dy = min(abs(ay - by), H - abs(ay - by))
            k = int(((dx * dx + dy * dy) ** 0.5) // 2) * 2
            acc.setdefault(k, []).append(t)
    out = []
    for k in sorted(acc):
        v = sorted(acc[k])
        out.append((k, len(v), v[len(v) // 2]))
    return out


def main():
    print("[env] %s  N=%d  dt=%d s  |  灾前 %.2f h（相位 %.2f）"
          % (sys.version.split()[0], v98.N, DT, PRE_H, PRE_H * 3600.0 / v98.T_ORBIT))
    print("[v98] 四块各只动一个量：A 两段可加性 / B reach（拿来被否）/ C 当根的电价 / D 前沿宽度")
    print("")
    print("[判据准入] A 能失败：两臂 t50 差 >20% ⇒ 地面自愈其实受天影响；有人晚于第一根 ⇒ 两段不能相加。")
    print("           B 能失败：t50 与 reach 无关 ⇒ \"多跳串联\"这个解释错。")
    print("           C 能失败：退出与 C_SKY 无关 ⇒ \"当根要付电\"这个读法错。")
    print("           D 能失败：t50 不随 DIS_R 线性 ⇒ \"前沿按周长推进\"这个解释错。")
    print("           E 只改一样：每块只动一个量；等号处：D 用 1:2:3 ±30% 判。")

    v98.P_LOSE = 0.0025
    v98.PHI = 0.30
    v98.D_BASIC = 0.05
    v98.EPS = 0.05
    v98.MAX_HOP = 12
    v98.REROUTE = 20
    v98.P_UP = 0.50
    v98.GAMMA = 0.0
    R0 = v98.DIS_R
    SKY0 = v98.C_SKY
    print("[实际生效] P_LOSE=%.4f PHI=%.2f D_BASIC=%.2f EPS=%.2f C_SKY=%.1f DIS_R=%d"
          % (v98.P_LOSE, v98.PHI, v98.D_BASIC, v98.EPS, v98.C_SKY, v98.DIS_R))
    print("")

    A = {}

    # ---------------- 块 A ----------------
    print("=== 块 A：两段是否可加（灾后 2 h，p_in=1.0、reach=3）===")
    print("%-9s %7s %9s %6s %6s %10s %10s %7s"
          % ("占空比", "失联", "第一根(步)", "t50", "全愈", "早于第一根", "晚于第一根", "退出"))
    for vf in (0.05, 1.00):
        rows = run(1.0, PA, 1, vf, 2.0, "a%.2f" % vf)
        a = summ(rows)
        a["vf"] = vf
        A[("A", vf)] = a
        print("%-9s %7.0f %9.0f %6s %6s %9.0f%% %9.0f%% %7.1f"
              % ("%.2f" % vf, a["g0"], a["delay"], f1(a["t50"]), "%.0f" % a["tall"],
                 100 * (a["early"] or 0), 100 * (a["late"] or 0), a["ex"]))

    # ---------------- 块 B ----------------
    print("")
    print("=== 块 B：reach（p_in=1.0、p_adv=0.35、灾后 6 h）===")
    print("%-7s %8s %6s %6s %6s %8s %8s"
          % ("reach", "需要跳数", "失联", "t50", "全愈", "t90", "链数"))
    for rc in (1, 3, 5):
        rows = run(1.0, PA, 1, 0.10, 6.0, "b%d" % rc, reach=rc)
        a = summ(rows)
        a["reach"] = rc
        a["hops"] = -(-v98.DIS_R // rc)
        A[("B", rc)] = a
        print("%-7d %8d %6.0f %6s %6s %6s %8.0f"
              % (rc, a["hops"], a["g0"], f1(a["t50"]), "%.0f" % a["tall"], f1(a["t90"]), a["ne"]))
        if rc in (1, 3):
            bd = bands(rows, v98.DIS_R)
            print("        按到灾心距离（格）分档的中位 t_self："
                  + " ｜ ".join("%d-%d格 n=%d med=%d" % (k, k + 1, n, m) for k, n, m in bd))

    # ---------------- 块 C ----------------
    print("")
    print("=== 块 C：当根的电价（p_in=1.0、p_adv=0.35、灾后 6 h、占空比 0.10）===")
    print("%-8s %9s %8s %7s %6s"
          % ("C_SKY", "退出台数", "末态链", "失联", "t50"))
    for cs in (0.0, 1.0, 2.0, 4.0):
        v98.C_SKY = cs
        rows = run(1.0, PA, 1, 0.10, 6.0, "c%.1f" % cs)
        a = summ(rows)
        a["csky"] = cs
        A[("C", cs)] = a
        print("%-8.1f %9.1f %8.0f %7.0f %6s"
              % (cs, a["ex"], a["ne"], a["g0"], f1(a["t50"])))
    v98.C_SKY = SKY0

    # ---------------- 块 D ----------------
    print("")
    print("=== 块 D：前沿宽度（p_in=1.0、p_adv=0.35、reach=3、灾后 6 h）===")
    print("%-7s %8s %6s %6s %6s %9s"
          % ("DIS_R", "圆盘格数", "失联", "t50", "全愈", "t50/圆盘"))
    DISK = {3: 29.0, 6: 113.0, 9: 253.0}
    for R in (3, 6, 9):
        v98.DIS_R = R
        rows = run(1.0, PA, 1, 0.10, 6.0, "d%d" % R)
        a = summ(rows)
        a["R"] = R
        a["disk"] = DISK[R]
        A[("D", R)] = a
        print("%-7d %8.0f %6.0f %6s %6s %9s"
              % (R, DISK[R], a["g0"], f1(a["t50"]), "%.0f" % a["tall"],
                 f1((a["t50"] / DISK[R] * 1000) if a["t50"] else None)))
    v98.DIS_R = R0

    # ---------------- 判据 ----------------
    a5, a1 = A[("A", 0.05)], A[("A", 1.00)]
    A1 = bool(a5["t50"] and a1["t50"] and
              abs(a5["t50"] - a1["t50"]) <= 0.2 * max(a5["t50"], a1["t50"]))
    A2 = (a5["early"] or 0) >= 0.99
    b = [A[("B", r)]["t50"] for r in (1, 3, 5)]
    B1 = bool(b[1] and all(x is not None and abs(x - p) <= 0.4 * p
                           for x, p in zip(b, [3.0 * b[1], b[1], b[1]])))
    B2 = bool(b[0] and b[1] and b[0] > b[1] * 1.5)
    c = [A[("C", x)]["ex"] for x in (0.0, 1.0, 2.0, 4.0)]
    C1 = all(c[i] <= c[i + 1] + 1e-9 for i in range(3))
    d = [A[("D", r)]["t50"] for r in (3, 6, 9)]
    D1 = bool(d[0] and all(x is not None and abs(x - p) <= 0.3 * p
                           for x, p in zip(d, [d[0], 2.0 * d[0], 3.0 * d[0]])))

    print("")
    print("A1 两臂 t50 差 <20%%：%s vs %s -> %s"
          % (f1(a5["t50"]), f1(a1["t50"]), "成立" if A1 else "不成立"))
    print("A2 全部早于第一根（≥99%%）：%.0f%% -> %s"
          % (100 * (a5["early"] or 0), "成立" if A2 else "不成立"))
    print("B1 t50(1):t50(3):t50(5) ≈ 3:1:1（±40%%）：%s -> %s"
          % ("/".join(f1(x) for x in b), "成立" if B1 else "不成立"))
    print("B2 reach=1 明显更慢（>1.5 倍 reach=3）：%s vs %s -> %s"
          % (f1(b[0]), f1(b[1]), "成立" if B2 else "不成立"))
    print("C1 退出随 C_SKY 单调不减：%s -> %s"
          % ("/".join("%.0f" % x for x in c), "成立" if C1 else "不成立"))
    print("D1 t50(3):t50(6):t50(9) ≈ 1:2:3（±30%%）：%s -> %s"
          % ("/".join(f1(x) for x in d), "成立" if D1 else "不成立"))
    print("")
    print("（A 的\"第一根\"取 cut0_delay，来自\"上一步有根\"，比真实首根晚一步；"
          "B 的\"需要跳数\"＝ceil(DIS_R/reach)。）")

    out = {"params": dict(seeds=len(SEEDS), DT=DT, PRE_H=PRE_H, PA=PA, DISK=DISK),
           "arms": {"%s|%s" % k: dict(v) for k, v in A.items()},
           "verdict": dict(A1=A1, A2=A2, B1=B1, B2=B2, C1=C1, D1=D1)}
    with open("v98_result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("")
    print("结果已写入 v98_result.json")


if __name__ == "__main__":
    main()
