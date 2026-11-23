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
# v158：**跳数上限是服务侧的硬墙**（详见 README §v158）。
# v157 诊断：`no_route` 里 **96–97% 是 `hop`**（走了 HOP_MAX 步仍没到根），而**预算只用掉 18%**
# ⇒ 服务不是被"容量"卡的，也不是被"并发"卡的，是**拓扑够不着**。
# 这一条直接冲 v127「服务上限＝可见时间×根上行容量」：容量有富余时，上限式的那一项不成立。
# **怎么改**：由驱动直接改模块属性 `v158.HOP_MAX`，跑完恢复。
# 不能在 `run_one` 里赋 `HOP_MAX = ...` —— 那会创建**局部变量**，而 `deliver()` 读的是模块全局，
# 等于没设（"参数设在驱动模块上等于没设"的同一族，2026-11-08 踩过两次）。
# 它不影响随机流（只改循环长度）⇒ CRN 安全。
_hop_max0 = HOP_MAX
# v160：**修环**。v159 诊断：`no_route` 里 **93% 是 `via` 链成环**（25553/27431），
# 而"真的走远"只占 3%、预算只用掉 18% ⇒ 投递失败的主因既不是容量、也不是距离，
# 是**路由信念自相矛盾**：`broken` 会把 `nhops[cur]` 改成 99，但 `via` 不跟着改；
# 依赖它的节点仍指向它，几条旧账互相指向就绕成环（画面第 30/31 行"过时的动向判断会骗人"）。
# `LOOPFIX`：0＝现行（走 6 步绕回来就判 no_route）；
#            1＝走链时要求 `nhops` **严格递减**，不递减即判"这条账已坏"（置 up_known=False、via=-1，
#               与 `broken` 的处理一致 ⇒ 下一步会重新探）。
# 只改判定分支，不消耗随机数 ⇒ CRN 安全。
LOOPFIX = 0

# v162：**失效传递**（`PROP=1`）。v159–v161 把服务侧的卡点查清了：
#   · 预算几乎没用（窗内 `cap` 失败 = 0，用掉 8–18%）⇒ 不是容量；
#   · `HOP_MAX` ×4 只让 hop 失败降 0.5% ⇒ 不是距离；
#   · 信念覆盖 **98.5%**（几乎人人都"自认为能通天"），而**送达率只有 16–40%**；
#   · `no_route` 里 **93% 是 `via` 链成环**；修环后同一批人改叫 `stale`，送达不变。
# ⇒ **不是没人知道路，是知道的路是坏的**。引擎已有"入口失效"处理，但只清 `nhops==0` 的
#   **直接入口**，经由它学到路的二级、三级节点没被清 ⇒ 旧账指着一条断掉的链。
#   这正是画面第 30–31 行："旧的经验、旧的路径、过了时的动向判断…过时的东西会骗人"。
# `PROP=1`：每步刷新前做一次**自洽扫描（清到不动点）**：`via` 必须指向 up_known 且 nhops 更小的
#   邻居，否则整条链作废。**只清账，不改连接规则、不消耗随机数** ⇒ CRN 安全。
PROP = 0

# v168：**给投递加退路**（A151：`deliver()` 每台只有一个下一跳，坏了就整台失败，
# 没有备选、也没有洪泛回退——**这条结构假设从没被审过**，而它可能是 ±37% 的放大器）。
# `RETRY`：0＝只认账（现行）；1＝**账只给方向**（按 `nhops` 从小到大挑一个活着的邻居，
# 可以绕过坏掉的那一跳）；2＝**完全不看账**，只在"链还活着"的现网里 BFS 找一条到入口的路（上限臂）。
# 三档是阶梯：0→1 买"绕开坏链"，1→2 买"根本不需要账"。**不改连接动力学、不耗随机数 ⇒ CRN 安全。**
RETRY = 0

# v170：**痕迹方向**——投递不用账，只用"上次伸通留下的痕迹"（画面第 78 行零件：信息素／章鱼"握住东西的那只手粗"）。
# 为什么：v168/v169 量到"缺退路"是服务侧最大一项（+68.2%），但那两档里 `RETRY=2/3` 靠**全知 BFS**
# （拿全局 `adj`/`ew` 找一条到根的最短路）——**终端没有地图，这一档只能当上限，不能当机制**；
# 唯一可实现的 `RETRY=1` 仍然要账给方向（`nhops` 递减）。于是一个真问题没被回答：
# **不靠账，能不能走对方向？** 画面里给的答案不是"记账"，是"哪只手握住东西那只就粗"。
#
# `RETRY=4`：只用痕迹。每跳在"活着、没走过、容量够"的邻居里挑**痕迹最重**的那条；
#            全无痕迹时随机挑一条（冷启动）。`RETRY=5`：**完全随机**（去掉方向，作下界对照）。
# 痕迹由"走过这条链"留下（`PH_DEP`，走就留）＋"走通了"额外加（`PH_OK`），每步蒸发 `PH_DECAY`。
# **准入闸不动**（`up_known` 照旧，见 deliver 里的 `retry < 3 or retry >= 4`）——
# 否则方向机制与准入闸一起变，违反"一次只改一件事"（纪律 110）。
# 只用独立随机流 `_rng_ph`，不扰动主随机流 ⇒ 与 v169 的 `RETRY<=3` 各臂逐位可比（CRN 安全）。
# v172：**两处"接线"**（都默认关，关时与 v171 逐位相同）。
# (A) `RELAY_PAY`：投递的转发要耗电。v171 诊断出 `deliver()` 算出的 `relay_used` 在调用点被丢掉，
#     ⇒ 拥塞只让"这一步送不到"，不让"网变差"。开了之后按 `C_RELAY` 扣电（一步滞后结算）。
#     这不是加机制：`C_RELAY` 早在 `serve()` 里结过账，同一条链替人转一个当量耗多少电已有定值，
#     只有投递那条路漏了。
# (B) `THICK_W`：让**粗链在选下一跳时占优**。打分 `-nhops + THICK_W*(ew-1)`；`THICK_W=0` 时
#     退化成原来的"挑 nhops 最小的活邻居"。画面第 52 行「粗链就是当前的上天通路」此前不可能成立——
#     `deliver()` 只看 `ew>0`、不看 `ew` 多大（v171）。它是拍的系数 ⇒ 必须扫两档。
RELAY_PAY = 0
THICK_W = 0.0
# v173：**下行一小步**——网往下垂根（画面第 25 行"下行同步、系统宣告…垂根是网唯一主动做的事"）。
# 只做两件事：①系统宣告有**周期**（`DL_PERIOD` 步一次）；②只有**亮着**的终端收得到（`DL_NEED_LIT`）。
# 不做容量耦合：垂根是天→地的直连广播，不占地面链（画面没写它占，写清了再改）。
# 定义收紧：**「可用」＝送到 且 收到过宣告**（此前只算"送到"）。`DL_ON=0` 时与 v172 逐位相同。
# 依据级别：`DL_PERIOD` 是拍的（扫 1/5/20 三档，20 步＝40 min）；`DL_NEED_LIT` 有画面依据（第 15 行"亮着才被找到"）。
# v174：**结链即合并（T4 的最小形式）**——两条依据，不是自造：
#  · 画面第 39–44 行：搭接即合并，"路不用重复探、失败不用重复经历、碎片拼成全貌"；
#  · 合并算子必须是 **join 半格**（Almeida 2024, §2.1）：幂等 ⊔ 交换 ⊔ 结合。
#    并集（按时间戳取新）满足这三条 ⇒ 两个球合并的**顺序不影响结果**，这是可验证的代数性质。
# 结构侧只做"知识合并"，不动拓扑（Merging & Regeneration 那篇的度公式留作拓扑合并的参照）：
#  `known` 取并集（逐条取更新的时间戳）、`fail_ct` 取 max（G-Counter 式的 join）。
# 代价：`known` 变多 ⇒ `MEM_W` 那条"记忆有消耗"会收钱（画面第 30 行），所以**不是白赚**。
# v182：**首伸命中率**（只加读数）。O1＝"个体首次可用等待"＝max(恢复步数, 等窗)，前两项一个由协议定、
# 一个由轨道定；自组织唯一还能压的是**"醒来后第一伸是不是伸对了"**——这个量从没测过（清单 §16.1 三）。
# 画面第 17 行："伸出去的那一下，同时就是在看""真正的读数从回程来" ⇒ 命中＝这一伸拿到了回程读数。
# 定义：灾后每台**第一次伸手**记一条；命中＝这一下 `_ok`（对方活着、付得起、且还没连上）。
# 分组按 `grp`（0 真旧账／1 白纸／2 打乱），这是画面第 9 行"重连者比白纸新生者亮得快"的直接检验。
# v183：**把探索账也纳入操纵**。v182 查出「白纸」不白——`grp=1/2` 只清了 `up_known`/`nhops`/`via`，
# 从没清 `known`（探索账：探过谁、那一伸成没成）。于是三组带着同一份探索账，
# 画面第 9 行「重连者比白纸新生者亮得快」这个核心对照一直是**半干净**的。
# `KNOWN_MODE=0`：现状（不清 known）；`=1`：真／空／打乱三档（g0 保留、g1 清空、g2 打乱键、条数不变）。
# 为什么"条数不变"重要：`MEM_W` 是按条数收费的 ⇒ 打乱档必须与真档同条数，否则差的是"记忆开销"不是"记忆内容"。
# 主表 `MEM_W=0` ⇒ 记忆免费 ⇒ 这一版量的是**纯信息**（内容值不值钱），不带开销混杂。
# v185：把 H14 那条缺失的通路接上——**"知道得多"应当让人少花料，而不是多出手**。
# 依据：画面第 9 行说重连者"亮得快"（第 15 行：亮＝精力）。此前模型用 `OLD_ADV`（出手概率 ×1.5）
# 顶替它，v184 证明那只是"预算"、不含信息。本版改成信息影响**代价**：
# 伸向"这一步之前就已经知道是活的"邻居，省 `1-KCHEAP` 的料（少白跑）；伸向不知道的，照价。
# `KCHEAP=1.0` 时与 v184 A0 **逐位相同**（关掉＝没接）。
# 注意：只乘**出手人自己**付的那一份（`ci`），不乘对方那一份（`cj`）——画面里"伸"的那一方付姿态/对准的代价。
# v186：**把旧邻居名单接进"探针的目标选择"**（H15 的唯一检修口）。
# 为什么在这里：v185 量出名单只被用上 5.3%（每人 0.22 次），根因是 `POKE=1` 时 `outs` 只有 1 个候选，
# 而"优先够旧邻居"（`OLD_PRIOR`）是**在候选集里挑**——候选集＝1 就没得挑。
# 所以把偏好挪到**上游**：在"往哪伸"的那一步，让名单上的人更容易被挑中。
# 依据：画面第 9 行「旧经验直接可继承」＋第 17 行「伸出去的那一下同时就是在看」——先继承的是"往哪看"。
# `NBR_PRIOR=0` 时与 v185 **逐位相同**（连随机数都不多抽一次）。
# v187：**给"伸手"本身定价**。现在失败的伸一分钱不花（只有成功的建链才扣 `ci`/`cj`），
# 于是"少白跑"在经济上毫无意义——名单能省的只是"机会"，不是"成本"。
# 依据：画面第 17 行"伸出去的那一下，同时就是在看"——**伸是主动动作**；第 15 行"亮＝精力"。
# 主动动作要花精力，模型里此前漏了这一笔（与 H2「转发没结账」同族：动作的成本没结账）。
# `POKE_COST`＝每次伸手（成不成**都**）按名义代价 `cj` 的多少倍付费；付不起就不伸。
# v189：**让信息接到"结构"上**（H16 的第一刀）。
# H16 的原话：`grp` 在代码里只接到"出手概率"（`OLD_ADV`，v184 证明那只是预算）与"往哪伸/跟谁连"
# （`NBR_PRIOR`，v185–v186 证明值 0.49 步、上限 1.40 步），**从未接到"谁在能服务别人的位置上"**。
# 本版让它接到"谁当根"：账多（`len(known)` 大）的人优先当根。
# **必须同档位替换**：`GWCAP=1` 时根数由 `bw >= s0v` 截断；若按能力排序（`SEL_ROOT=2`），
# 先取强球 ⇒ 很快达标 ⇒ **根数变少** ⇒ 学不到路由 ⇒ v156/v178 那个 −56%。那不是"选错人"，是"换掉了数量"。
# 所以这里只允许**同档位**交换 ⇒ 根数与带宽都逐位不变（这就是本版要检的 N2）。
# `ROOT_INFO=0` 时与 v187 **逐位相同**（不耗随机数）。
# v190：v189 的负结果有两种解释，这一刀把它们分开——
# ①"信息→结构"这条路本来就没收益；②排序量选错了（`len(known)` 是"账有多长"，不是"知道多少"）。
# 证据：v189 里**打乱组（g2）的账最长**（8.9 vs g0 的 8.2），于是根被大量给了 g2（358→697）。
# 原因可读：`known` 被打乱后指向"没接过的别处" ⇒ 探索不断失败、不断重探 ⇒ **账越长**。
# ⇒ 本版只换排序量，其余全不动：
#   `ROOT_SORT=0`：账条数（= v189，作同批基准）
#   `ROOT_SORT=1`：**成功条数**（账里记着"通了"的有几条）——"知道多少"的直接代理
#   `ROOT_SORT=2`：`up_known` 优先，其次 `nhops` 小——"我以为我能通天"的直接代理
# v192：**让终端状态异质**——Whittle 索引的前提是"索引是状态的函数"，
# 而本模型 `energy = E_INIT[tier]*e_scale`，**同档位内完全同质** ⇒ `energy/_e0` 恒等于 1
# ⇒ `SEL_ROOT=1`（按电量排序）在初始时**全平手，等同 shuffle** ⇒ 那一档从上线起就是空转（H15 家族第二个实例）。
# `HET_SPENT`＝**灾前已经用掉的比例上限**（均匀 0..HET_SPENT）。
# 为什么不用"初始电量乘一个随机因子"：第一版那样做，`HET_CV=0.6` 的对数正态厚尾把最低档压到
# **2.4 待机小时** ⇒ 那批终端几乎立刻死，`O2p` 掉 16%——那不是"自然的异质"，是我把分布搞坏了。
# 真实的异质是：灾在随机时刻发生，**每个人已经跑了一段时间**，剩余电量自然分散，但都还够用。
#   `HET_SPENT=0` ⇒ 全 1.0（**不抽随机数、逐位等于原行为**）；`>0` ⇒ 独立随机流（不扰动主流程）。
HET_SPENT = 0.0
# `HET_UNIFORM=1`：**同质但均值相同**（全 = 1−S/2）。为什么要这一档：
# "灾前已用 0..S" 会让**平均电量也变少**（−S/2），于是"异质效应"与"总量效应"混在一起。
# 加了同质同均值的对照，两者之差才是纯粹的"异质"效应（纪律：一次只改一件事）。
HET_UNIFORM = 0
ROOT_SORT = 0
ROOT_INFO = 0
_RI = {"swap": 0, "chance": 0, "bwbad": 0, "swap1": 0, "steps": 0}
_RG = [0, 0, 0]        # 各组被点成根的"台·步"数（通道读数）
POKE_COST = 0.0
_KC3 = {"n": 0, "cost": 0.0, "poor": 0}
NBR_PRIOR = 0.0
_KC2 = {"probe": 0, "poke": 0, "poke_g0": 0, "probe_g0": 0, "probe_g2": 0, "poke_g2": 0}   # poke_g0：分母要按"有名单的人出手次数"算，不是全体
KCHEAP = 1.0
_KC = {"used": 0, "cheap": 0, "save": 0.0, "cheap_g0": 0, "cheap_g2": 0, "save_g0": 0.0}   # 旋钮自检：有多少次真的按折扣算了、省了多少料
KNOWN_MODE = 0
FIRSTHIT = 0
MERGE = 0
_MRG = {"n": 0, "pruned": 0}
# v175：**合并必须配遗忘**（v174 的账：记忆收费时合并让 `O2p` −38.1%、末态链腰斩，
# 正对上画面第 70 行"网会被自己的过去拖垮——重得伸不动链"）。
# 两种遗忘，都不是随机删（CRDT：inflation 只许增 ⇒ 遗忘只能发生在合并**之后**的重归一化）：
#  · `ML_FILTER=1`：只并**落在自己 reach 内**的条目（近似"感知场并为一个"，画面第 39 行的原话不是"记忆库"）；
#  · `ML_FILTER=2`：并完之后按**时间戳**裁掉老于 `ML_AGE` 步的条目；
#  · `=3`：两者都做。
ML_FILTER = 0
ML_AGE = 30
DL_ON = 0
DL_PERIOD = 5
DL_NEED_LIT = 0
DL_TTL = 20       # 宣告的"新鲜度"窗口（步）。与 `DL_PERIOD` **分开**：
# 一开始我把两者设成同一个数，结果"周期"同时改了频次与宽限，两档不可比（5 步反而比 20 步更差）。
# 现在 `DL_PERIOD` 只管多久宣告一次，`DL_TTL` 只管"多久没听到就算失同步"。
SERVE_PAY = 1     # v172b：`serve()` 那侧的转发电费是否照收（默认 1＝照旧）。
# 为什么要这个开关：`serve()`（容量口径，全知）与 `deliver()`（投递口径，本地）是**两套并存的"投递"**，
# 却代表同一份物理流量。两边都按 `C_RELAY` 扣电＝**重复收费**。B1（exit 93→318）因此可能是高估的。
# 三格设计：(SERVE_PAY, RELAY_PAY) = (1,0) 现状 ／ (0,1) 只按真实投递结账 ／ (1,1) 重复收（上界）。
_RELAY_DLV = {}

PH_DEP = 0.0        # 每走一跳留多少（0＝只有成功的路留痕）
PH_OK = 0.0         # 走通到根额外加多少
PH_DECAY = 1.0      # 每步乘（1.0＝不蒸发）
PH_CAP = 1.0        # 单条链痕迹上限
_DIA = {"hop": 0.0, "thick_hop": 0.0, "e_t": 0.0, "e_a": 0.0}
# v171：**投递侧**的粗链富集（只加读数，不改行为、不耗随机数）。
# 为什么：`enrich` 用的是 `serve()` 的 `load_e`——那是全图最宽路（全知）的分配；
# 画面第 17 行明确否掉"没伸到的地方也在它世界里"。所以"粗链＝上天通路"这条判否
# 一直量的是另一个模型。这里用"真实走过的跳"重算一次，作对照。
_PH = {}            # edge key -> 痕迹强度
_PHst = {"n": 0, "hit": 0}   # 首跳"有痕迹"的次数／总次数（旋钮自检用）
_rng_ph = Random(1)          # 独立随机流：冷启动／平手时用，不扰动主随机流
# `RETRY=6`：**热手**——每台只记"上次从哪只手臂伸通过"（一个指针，O(1) 账，不是距离标签）。
# 为什么另开一档：全局痕迹（`RETRY=4`）会让所有人往同一条热链上挤（正反馈没有负反馈 ⇒ 拥塞），
# 而画面第 78 行讲的是**每只球自己的手**"哪只握住东西那只粗"，不是一张全局信息素图。
_HOT = [-1] * N

# v166：**反事实臂 `CAPFIX`**（只为分离变量，**不是物理**）。
# v164/v165 把 v162 那个 −37% 的两个候选否掉了：不是根数（随机 10.5 根时 +4.7%），
# 也不是链长（`HOP_MAX` 压平后逐位相同）。剩下唯一不同的是**预算**：
# 强球选中的是车载（8 带宽/台）⇒ `cap_total=min(S0,Σbw)=60`；随机 10 根是普通台 ⇒ 只有 **8.4**，差 7 倍。
# `CAPFIX=1`：把 `cap_total` 钉成 `S0`（不看根的实际带宽）。这在物理上不成立（没有的带宽送不出去），
# 但作为**诊断**能把"预算"这一个变量单独拎出来。⇒ 若随机 10 根在 `CAPFIX=1` 下由 +4.7% 翻成负，
# 则 −37% 的正身是"预算充裕 × 清账"，与"选强球"无关。**任何结论都不得引用 CAPFIX=1 的绝对值，只引符号。**
CAPFIX = 0

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
DBG = False
DBG_TOT = False
CYCLE = 0.0
FAIL_MEM = 0.0
# v129：`POKE=1` 把"全知候选"换成"伸了才知道"（画面第 17 行）。
# `EXPLORE` = 有已知好方向时，仍去探未知方向的比例。
POKE = 0
EXPLORE = 0.5
# v131：留痕的**时效**（画面第 78 行"会衰会忘"、以及"单球受限三面：视角／记忆消耗／记忆时效"）。
# 单位＝步。`MEM_TTL` 越大越接近"记得住"；取 1e9 就是 v129/v130 的"只增不减"。
# 这是"到点才忘"的阶梯近似（真衰减是指数），写在这里免得读成连续衰减。
MEM_TTL = 10 ** 9
# v135：**账的占用**（画面第 30 行「记忆有消耗——存得越多，占去的越多，而它的存量本就受增长限度约束」、
# 第 70 行「否则网会被自己的过去拖垮——重得伸不动链」）。
# 每存一条方向账（`known[i][j]`）常驻占用 `MEM_W` 单位的料，与持链/伸链**竞争同一份存量**。
#
# 依据级别：机制＝画面原文（第 30/70 行）；系数 `MEM_W` 的值＝**拍的，扫四档**（纪律 51）。
# 这是**建模选择**：画面只说"存量受增长限度约束"，没说记在哪一份存量上；
# 选"与料同一份"是因为只有它能让"重得伸不动链"这句话有对象
# （若改成独立容量上限也能做，但那是另一个上限，属可识别的等价族，见未完成清单）。
#
# 为什么这一条必须先补：v131 测出"会忘只慢 7%、旧账不值钱"，但那是在 **`known` 零成本、容量无限**
# 的模型里测的——账不占任何瓶颈资源（纪律 36），"忘掉它能省什么"永远答不出来。
# 所以 v131 的负结果**不是关于画面的发现，是这条未审查假设的推论**（纪律 50 同族）。
MEM_W = 0.0
# v136：**账占体量 → 削弱交换面**（"记忆有消耗"的另一种读法，用于可识别性对照）。
# 画面依据：第 7 行「体量涨得快、交换面涨得慢，大到一定份上里外就接不上茬」＋第 78 行零件出处
# 「长不大的账——异速生长」。机制是**异速**：账给体量加一份，而交换面只按体量^(1-κ) 涨（κ∈(0,1)），
# 于是单位对外动作的成本随体量升：cost *= (1 + MEM_V·n)^MEM_K。
# 与 v135 的 `MEM_W`（账**占用**同一份料，存量重分配）是**两条不同的通道**：
#   占料 → 总量不变、可用量变小；占体量 → 总量不变、**每步更贵**。
# 参数依据级别：机制＝画面原文；`MEM_V`/`MEM_K` 的值＝**拍的，扫**（纪律 51）。
MEM_V = 0.0
# v138：**每步沿几条链回程重探**（刷新率）。画面第 17 行"真正的读数从回程来"。
# 取 1 = v45 起的现行行为；0 = 知识只在"新搭链"时传（v45 记过：那一版会死）；99 = 每个邻居都读。
# 为什么要把它做成旋钮：**这个模型里"账不会过期"，不是因为账记得牢，而是因为刷新免费且每步一次**——
# 于是"遗忘"没有存在的余地（v135/v137 三次测都是无收益）。把刷新率打开，才能问
# 「刷新」与「遗忘」是不是两条可替代的路：若刷新降到 0 时"会忘"才开始有用，则遗忘的价值＝替代刷新；
# 若仍无用，"遗忘是器官"在这个模型里就彻底不成立（可写进结论汇总）。
REFR_N = 1
# v149：**"看"要付代价**——一台每步只有一个动作位：要么"伸"（探一个新的），要么"看"（刷新已知的）。
# 画面依据：第 17 行「伸即看、读数从回程来」——看本来就要靠伸才拿到；现在模型里看是**白送**的
# （v138 证实：刷新一条链不花料/电/步），于是"感知/账/记忆"这一族**结构性测不出东西**
# （v131–v138 五版负结果的共同根因，v147 第 1 条思路问题）。
# `ACTS` = 一台每步把动作位花在"看"上的概率。0 = 现行（看白送）；ACTS>0 时
# **伸的频率被按 (1−ACTS) 压掉**，这是这个机制的代价本身，不是副作用。
# 依据级别：机制＝画面；`ACTS` 的值＝**拍的，扫**（纪律 51）。
ACTS = 0.0
# v153：**横扫 vs 整片同开同关**（老盲点 #4）。`cov_window=1` 时原来两种模式二选一地写死：
#   `_in_cov = 全体 True/False`（整片同开同关）——于是窗关的那 61% 时间里**全网一个根都没有**，
#   服务为零；"个体要等下一个窗"就是这么来的，与"自己可见比例"无关。
# `SWEEP=1` 改成**可见带沿 x 推过网格**：节点 i 在 `((t/T) + (i%W)/W) mod 1 < VIS_FRAC` 时可见。
# 逐节点占空比仍是 VIS_FRAC（总量不变），但**任何时刻都有约 VIS_FRAC 的节点可见** ⇒ 总有根在。
# 依据级别：机制＝"过境是扫过的"（常识级，画面未写）；`SWEEP` 只做 0/1 两档，不调形状。
SWEEP = 0
# v154：**多星**。`NSAT` 颗星在相位上均布（间隔 1/K 圈）。
# 物理上它提高的是**每个设备的可见占空比**（一颗星只覆盖 0.39 的时间，K 颗均布 ⇒
# `min(1, K×0.39)`），**不是单设备带宽**——设备只有一副天线，同一时刻只能对一颗星。
# 所以容量随覆盖占空比饱和，K=3 时 0.39×3 > 1 ⇒ 全时覆盖。
# 依据级别：机制＝轨道常识；`NSAT` 只做 1/2/3 三档（3 档已饱和，再多没有意义）。
NSAT = 1
# v155：**网关上限**。v154 里 `up` 收录所有"可见且掷骰通过"的节点，而**每一台每步都付 `C_SKY`**
# ⇒ "覆盖变多"被机械地翻译成"每步都在发"⇒ 多星一上来就把电网烧小（v154 实测：链 525→345→314）。
# 这不是物理，是记账方式：设备"能当根"不等于"这一步必须发"。
# `GWCAP=1`：按 `SKY_BW` 累加到 `S0`（星上容量上限）就**不再点新的根**——多出来的根没有用，
# 网络没有理由给它们供电。用现成参数 `S0`，不引入新旋钮。
# `GWCAP=0` 时与 v154 逐字相同（消融用）。
GWCAP = 0
# v156：**按能力选根**（画面 T9「粗链优先驻留强球」）。原来 `up` 由 `rng.shuffle` 后的顺序逐个掷骰，
# 谁先排到谁当根 ⇒ 上行耗电被**均匀摊到所有设备**（v155 实测：多星让退出 ×3）。
# `SEL_ROOT`：0＝现行（随机顺序）；1＝按**剩余电量比例**降序；2＝按**档位强度**再按电量降序。
# **CRN 处理**：掷骰仍按原顺序、原次数做（每台一次），只在**取谁**时按能力排序 ⇒
# 主随机流位置不变，`SEL_ROOT` 不改变随机数消耗（纪律 93）。
SEL_ROOT = 0
# v146：**灾后需求脉冲**。此前需求恒定（每并网台每步 D_BASIC），即"平稳需求"。
# 但灾后真实需求是脉冲的：一小时内所有人同时要说话。画面没说需求形态，是我拍的恒定值。
# `DEM_BURST` = 脉冲倍数，`DEM_BURST_H` = 脉冲持续小时数（从打灾那一刻算）。
# 依据级别：机制＝业务常识（灾后呼叫激增），值＝**拍的，扫**。
DEM_BURST = 0.0
DEM_BURST_H = 3.0
MEM_K = 0.5
# v132：`VISION=1` = 画面口径——**亮的看得见**（第 15 行"亮着才被找到"），
# 暗的（未连）看不见、只能盲探碰（第 17 行"没伸到的地方不在它世界里"）。
# `VISION=0` 是 v129/v130/v131 的"全盲"（连亮的也要探）——那是**删过头**的一版。
VISION = 0
# v133：`LIT_MODE` 决定"亮"读的是什么——这是 2026-11-04 用户判定的落地。
#   0 ＝ `joined`（有没有链）——**v132 的错读法**，留作对照臂
#   1 ＝ **精力**（`energy / 初始精力`）——画面自审 §1.2「亮＝终端自身精力」，三档 暗／微亮／亮
LIT_MODE = 0
LIT_LO = 0.33   # 低于它＝暗（精力快耗尽）
LIT_HI = 0.66   # 高于它＝亮（精力足）；中间＝微亮
  # v121：失败留痕强度。0＝不记；越大，失败过的手越不愿意再伸（画面：失败当场转成臂上的新账）     # v119：每步每个已入网者"在同一分量内另搭一条链"的概率（＝v16 的额外搭边，成环）
JOIN_CUT = 0   # v113：1＝被切断的人（cls==1）也进连地循环（画面：球断了会再伸）
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


def _pctl(v, p):
    """线性插值分位数（纯标准库，无 numpy）。空表返回 None。"""
    if not v:
        return None
    s_ = sorted(v)
    if len(s_) == 1:
        return float(s_[0])
    k = p * (len(s_) - 1)
    f = int(k)
    c = min(f + 1, len(s_) - 1)
    return float(s_[f] + (s_[c] - s_[f]) * (k - f))


def _grid_dist(a, b):
    """环形网格上的欧氏距离（与 `cands` 同一把尺）。"""
    ra, ca = a // W, a % W
    rb, cb = b // W, b % W
    dr = abs(ra - rb)
    dr = min(dr, H - dr)
    dc = abs(ca - cb)
    dc = min(dc, W - dc)
    return (dr * dr + dc * dc) ** 0.5


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


def comps_from(ew):
    """从边集合算连通分量，返回 find(x)。v119 用来判"两个终端是否已在同一分量里"
    （引擎里那个 `_rt` 只在恢复分支里定义，灾前拿不到）。"""
    par = {}

    def find(x):
        if x not in par:
            par[x] = x
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for (_a, _b) in ew:
        _ra, _rb = find(_a), find(_b)
        if _ra != _rb:
            par[_ra] = _rb
    return find


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


def _pearson(xs, ys):
    """皮尔逊相关；点数 <3 或某一侧方差为 0 时返回 None（不许静默给 0，纪律 28）。"""
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs)
    sy = sum((y - my) ** 2 for y in ys)
    if sx <= 0.0 or sy <= 0.0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) ** 0.5


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


_DIA_ON = False


def deliver(joined, ew, up, tier, up_known, nhops, via, cap_total, fail_cnt, order, adj=None, retry=0,
            dep=True):
    """已探明场下的投递：只用本地表逐跳走。

    返回 (delivered 列表, 失败原因计数)。
    """
    # v157：`no_route` 原来把三件事并成一个数 —— ①自己不知道该往哪走 ②路上信念断了（via<0）
    # ③跳数用完还没到根。根从 74 降到 8 时"O2p 腰斩"到底是哪一种，必须分开才判得了。
    # 只加计数，不改任何判定分支（`no_route` 仍照旧累加，兼容旧读数）。
    hop_used = []       # v157：成功投递的跳数（用来判"根少 ⇒ 走得更远/走不到"）
    fail = {"no_route": 0, "broken": 0, "congest": 0, "cap": 0,
            "unk": 0, "dead_end": 0, "hop": 0,
            # v159：`hop` 再拆一层 —— **成环**（走过同一个节点）／**真的走远**（没重复但没到根）。
            # v158 已否掉"距离太远"：HOP_MAX ×4 只让 hop 失败降 0.5% ⇒ 必须是环。
            "loop": 0, "too_far": 0, "stale": 0}
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
        # v169：`RETRY>=3` 时**连"不知道自己能通天"这道准入闸也不看**——
        # `up_known` 是"自认为能通天才发"，而真实终端不知道路时也会广播/试探。
        # 这一档给出"完全不看账"的绝对上限（RETRY=2 仍受这道闸限制，所以 2 与 1 只差 7% 不能当"账只值 7%"）。
        if (not up_known[v]) and (retry < 3 or retry >= 4):
            fail["no_route"] += 1
            fail["unk"] += 1
            continue
        cur, h, path, ok = v, 0, [], True
        _seen = {v}
        if 2 <= retry <= 3:
            # 上限臂：**不看账**，只在"链还活着"的现网里找一条到入口的路（BFS，限 HOP_MAX 跳）。
            # 它给的是"这张网在当前容量下最多能送多少"——账写得再好也不会超过它。
            _q, _pr, _dep, _found, _qi = [v], {v: None}, {v: 0}, -1, 0
            while _qi < len(_q) and _found < 0:
                c = _q[_qi]
                _qi += 1
                if _dep[c] >= HOP_MAX[tier[v]]:
                    continue
                for j in (adj.get(c, []) if adj else []):
                    if j in _pr:
                        continue
                    k = ekey(c, j)
                    if k not in ew or ew[k] <= 0:
                        continue
                    _pr[j] = c
                    _dep[j] = _dep[c] + 1
                    if j in entries:
                        _found = j
                        break
                    _q.append(j)
            if _found < 0:
                fail["no_route"] += 1
                fail["hop"] += 1
                fail["too_far"] += 1
                ok = False
            else:
                _seq = []
                c = _found
                while _pr[c] is not None:
                    p = _pr[c]
                    _seq.append((ekey(p, c), c))
                    c = p
                _seq.reverse()
                for (k, j) in _seq:
                    if load_e.get(k, 0.0) + 1.0 > ew.get(k, 0) * U * THETA:
                        fail["congest"] += 1
                        ok = False
                        break
                    if j not in entries and relay_used.get(j, 0.0) + 1.0 > RELAY_INIT[tier[j]] * U:
                        fail["congest"] += 1
                        ok = False
                        break
                if ok:
                    path = _seq
                    cur = _found
                    h = len(_seq)
        else:
            while h < HOP_MAX[tier[v]]:
                if retry >= 6:
                    # v170：**热手**——每台只记"上次从哪只手臂伸通过"。一个指针，O(1) 账。
                    # 断了/走过了就当场作废（负反馈在本地，不靠全局信息素）。
                    _cand = []
                    for _j in (adj.get(cur, []) if adj else []):
                        if _j in _seen:
                            continue
                        _kk = ekey(cur, _j)
                        if _kk not in ew or ew[_kk] <= 0:
                            continue
                        _cand.append(_j)
                    if not _cand:
                        fail["no_route"] += 1
                        fail["dead_end"] += 1
                        ok = False
                        break
                    j = _HOT[cur]
                    if j < 0 or j in _seen or j not in _cand:
                        j = _cand[_rng_ph.randrange(len(_cand))]
                        _PHst["n"] += 1
                    else:
                        _PHst["n"] += 1
                        _PHst["hit"] += 1
                elif retry >= 4:
                    # v170：**不用账**，只按痕迹挑下一跳（哪只手握住过东西，那只就粗）。
                    # 候选限定在"活着、没走过、容量够"的邻居里；全无痕迹就随机挑（冷启动）。
                    _cand = []
                    for _j in (adj.get(cur, []) if adj else []):
                        if _j in _seen:
                            continue
                        _kk = ekey(cur, _j)
                        if _kk not in ew or ew[_kk] <= 0:
                            continue
                        _cand.append((_j, _kk))
                    if not _cand:
                        fail["no_route"] += 1
                        fail["dead_end"] += 1
                        ok = False
                        break
                    if retry == 5:
                        j = _cand[_rng_ph.randrange(len(_cand))][0]
                    else:
                        _best, _bag = -1.0, []
                        for (_jj, _kk) in _cand:
                            _w = _PH.get(_kk, 0.0)
                            if _w > _best + 1e-12:
                                _best, _bag = _w, [_jj]
                            elif _w > _best - 1e-12:
                                _bag.append(_jj)
                        _PHst["n"] += 1
                        if _best >= 0.05:
                            _PHst["hit"] += 1
                        j = _bag[_rng_ph.randrange(len(_bag))] if len(_bag) > 1 else _bag[0]
                elif retry >= 1:
                    # 备选下一跳：**账只给方向**（挑 nhops 最小的活邻居），坏掉的那一跳可以绕过
                    j, _bn = -1, 1e9
                    for _j in (adj.get(cur, []) if adj else []):
                        if _j in _seen:
                            continue
                        _kk = ekey(cur, _j)
                        if _kk not in ew or ew[_kk] <= 0:
                            continue
                        if THICK_W > 0.0:
                            # v172：粗可以抵消一点方向。`THICK_W*(ew-1)` 的单位是"跳"：
                            # 0.5 ＝ 多两束才抵得上一跳；2.0 ＝ 多一束抵两跳。
                            _sc = -float(nhops[_j]) + THICK_W * (ew[_kk] - 1.0)
                            if _sc > -_bn:
                                _bn = -_sc
                                j = _j
                        elif nhops[_j] < _bn:
                            _bn = nhops[_j]
                            j = _j
                else:
                    j = via[cur]
                    # v160：信念自检——via 必须指向更靠近根的邻居（nhops 严格递减）。
                    if _LOOPFIX and (nhops[j] >= nhops[cur] or nhops[cur] >= 99):
                        up_known[cur] = False
                        via[cur] = -1
                        nhops[cur] = 99
                        fail["no_route"] += 1
                        fail["stale"] = fail.get("stale", 0) + 1
                        ok = False
                        break
                    if j >= 0 and j in _seen:
                        # 环：via 链回到走过的节点 ⇒ 再走多少步都出不去
                        fail["no_route"] += 1
                        fail["loop"] += 1
                        ok = False
                        break
                if j < 0:
                    fail["no_route"] += 1
                    fail["dead_end"] += 1
                    ok = False
                    break
                k = ekey(cur, j)
                if k not in ew or ew[k] <= 0:
                    fail_cnt[k] = fail_cnt.get(k, 0) + 1
                    if retry == 0:
                        up_known[cur] = False      # 撞上了，这条信念作废
                        via[cur] = -1
                        nhops[cur] = 99
                    fail["broken"] += 1
                    ok = False
                    break
                if load_e.get(k, 0.0) + 1.0 > ew.get(k, 0) * U * THETA:
                    # v170：热手挤不上就当场作废——**负反馈必须在本地**，
                    # 否则正反馈会把所有人赶到同一条链上（v170 第一跑，全局痕迹就是这么塌的）
                    if retry >= 6:
                        _HOT[cur] = -1
                    fail["congest"] += 1
                    ok = False
                    break
                if j not in entries and relay_used.get(j, 0.0) + 1.0 > RELAY_INIT[tier[j]] * U:
                    if retry >= 6:
                        _HOT[cur] = -1
                    fail["congest"] += 1
                    ok = False
                    break
                path.append((k, j))
                _seen.add(j)
                cur = j
                h += 1
                if cur in entries:
                    break
        if retry >= 6 and dep and ok and cur in entries:
            # 只记**走通了**的方向（走错不学，与"信息素只在成功处加"同一口径）
            _par = v
            for (_k, _jj) in path:
                _HOT[_par] = _jj
                _par = _jj
        if retry >= 4 and dep:
            # 留痕：走过的每一跳都留，走通了额外加（`PH_DEP=0` 即"只有走通的留"）
            _add = PH_DEP + (PH_OK if (ok and cur in entries) else 0.0)
            if _add > 0.0:
                for (_k, _j) in path:
                    _nv = _PH.get(_k, 0.0) + _add
                    _PH[_k] = PH_CAP if _nv > PH_CAP else _nv
        if not ok:
            continue
        if cur not in entries:
            # 走到这里只有两种可能：`ok=False` 已经记过别的，或者**跳数用完还没到根**。
            fail["no_route"] += 1
            fail["hop"] += 1
            fail["too_far"] += 1     # 没重复、也没到根 ⇒ 真的走满跳数还没到
            continue
        hop_used.append(h)
        if _DIA_ON:
            for (k, _j) in path:
                _DIA["hop"] += 1.0
                if ew.get(k, 0) >= 2:
                    _DIA["thick_hop"] += 1.0
        for (k, _j) in path:
            load_e[k] = load_e.get(k, 0.0) + 1.0
        for (_k, j) in path:
            if j not in entries:
                relay_used[j] = relay_used.get(j, 0.0) + 1.0
        delivered.append(v)
        total += D_BASIC
    if RELAY_PAY and dep:
        for _j2, _v2 in relay_used.items():
            _RELAY_DLV[_j2] = _RELAY_DLV.get(_j2, 0.0) + _v2
    if retry >= 4 and dep and PH_DECAY < 1.0:
        # 蒸发：每步一次（放在商品循环外，否则会被"每人一次"放大成 N 倍）
        for _k in list(_PH):
            _v2 = _PH[_k] * PH_DECAY
            if _v2 < 1e-3:
                del _PH[_k]
            else:
                _PH[_k] = _v2
    _DLV.append(dict(n_up=len(up), cap=cap_total, n_ok=len(delivered),
                     used=total, hops=(statistics.mean(hop_used) if hop_used else None),
                     n_try=len(order), fail=dict(fail)))
    return delivered, fail


_LOOPFIX = 0     # v160：`deliver()` 是模块级函数，读不到 `run_one` 的局部 `loopfix`（当场踩过）
_DLV = []       # v157：deliver 每次调用的实录（run_one 开始时清空）


def _fn_rate(up_known, nhops, via, entries, joined, hop_max, tier):
    """按 `via` 链走到底，能在 `hop_max` 步内落到入口的比例（只看"自称知道"的并网者）。"""
    n_ok = 0
    n_tot = 0
    for i in range(len(joined)):
        if (not joined[i]) or (not up_known[i]) or i in entries:
            continue
        n_tot += 1
        cur, h, ok = i, 0, False
        seen = {i}
        while h < hop_max[tier[i]]:
            j = via[cur]
            if j < 0 or j in seen:
                break
            seen.add(j)
            cur = j
            h += 1
            if cur in entries:
                ok = True
                break
        if ok:
            n_ok += 1
    return (n_ok / float(n_tot)) if n_tot else None


def _rsprd(pts):
    """根到质心的均方根距离（格）。点少时返回 None，不静默给 0（纪律 28）。"""
    n = len(pts)
    if n < 2:
        return None
    cx = sum(p[0] for p in pts) / float(n)
    cy = sum(p[1] for p in pts) / float(n)
    return (sum((p[0] - cx) ** 2 + (p[1] - cy) ** 2 for p in pts) / float(n)) ** 0.5


def _rnn(pts):
    """每个根到最近另一个根的距离，取均值（格）。用来区分"根多但挤在一起"与"根多且铺开"。"""
    n = len(pts)
    if n < 2:
        return None
    tot = 0.0
    for a in range(n):
        best = 1e9
        for b in range(n):
            if a == b:
                continue
            d = ((pts[a][0] - pts[b][0]) ** 2 + (pts[a][1] - pts[b][1]) ** 2) ** 0.5
            if d < best:
                best = d
        tot += best
    return tot / float(n)


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
    # v119：额外搭边概率。**只改这一样**（不碰候选、额度、能耗、窗口）
    cycle = job[23] if len(job) > 23 else CYCLE
    fail_mem = job[24] if len(job) > 24 else FAIL_MEM
    poke = job[25] if len(job) > 25 else POKE
    explore = job[26] if len(job) > 26 else EXPLORE
    mem_ttl = job[27] if len(job) > 27 else MEM_TTL
    vision = job[28] if len(job) > 28 else VISION
    lit_mode = job[29] if len(job) > 29 else LIT_MODE
    lit_lo = job[30] if len(job) > 30 else LIT_LO
    mem_w = job[31] if len(job) > 31 else MEM_W
    mem_v = job[32] if len(job) > 32 else MEM_V
    mem_k = job[33] if len(job) > 33 else MEM_K
    refr_n = job[34] if len(job) > 34 else REFR_N
    acts = job[37] if len(job) > 37 else ACTS
    sweep = job[38] if len(job) > 38 else SWEEP
    nsat = job[39] if len(job) > 39 else NSAT
    gwcap = job[40] if len(job) > 40 else GWCAP
    sel_root = job[41] if len(job) > 41 else SEL_ROOT
    loopfix = job[42] if len(job) > 42 else LOOPFIX
    prop = job[43] if len(job) > 43 else PROP
    capfix = job[44] if len(job) > 44 else CAPFIX
    retry_n = job[45] if len(job) > 45 else RETRY
    global _LOOPFIX, _rng_ph, _PH, _PHst, _HOT
    _LOOPFIX = loopfix
    _rng_ph = Random(seed * 7919 + 53)     # v170：痕迹方向专用流（冷启动/平手）
    _PH = {}                                # v170：痕迹从零开始（灾后没有历史）
    _PHst = {"n": 0, "hit": 0}
    _HOT = [-1] * N                         # v170：热手从零开始
    _MRG["n"] = 0
    _RI["swap"] = 0
    _RI["chance"] = 0
    _RI["bwbad"] = 0
    _RI["swap1"] = 0
    _RI["steps"] = 0
    _RG[0] = 0
    _RG[1] = 0
    _RG[2] = 0
    _KC3["n"] = 0
    _KC3["cost"] = 0.0
    _KC3["poor"] = 0
    _KC2["probe"] = 0
    _KC2["poke"] = 0
    _KC2["poke_g0"] = 0
    _KC2["probe_g0"] = 0
    _KC2["probe_g2"] = 0
    _KC2["poke_g2"] = 0
    _KC["used"] = 0
    _KC["cheap"] = 0
    _KC["cheap_g0"] = 0
    _KC["cheap_g2"] = 0
    _KC["save_g0"] = 0.0
    _KC["save"] = 0.0
    fh_step = [-1] * N
    fh_ok = [-1] * N
    fh_hitstep = [-1] * N
    fh_n = [0, 0, 0]
    fh_hit = [0, 0, 0]
    _MRG["pruned"] = 0
    dl_ack = [-1] * N                       # v173：最近一次收到系统宣告的步（-1＝从未）
    dl_av_s = []
    dl_lost_s = []
    global _DIA
    _DIA = {"hop": 0.0, "thick_hop": 0.0, "e_t": 0.0, "e_a": 0.0}
    _rng_act = Random(seed * 7919 + 101)   # 动作位用的独立流（不扰动主随机流，纪律 93）
    dem_burst = job[35] if len(job) > 35 else DEM_BURST
    dem_burst_h = job[36] if len(job) > 36 else DEM_BURST_H
    # 独立随机源：不消耗主随机流，所以 sticky=0 与 v91 逐数一致（这才是干净的 A/B）
    _rng_root = Random(seed * 7919 + 13)
    _rng_kn = Random(seed * 7919 + 211)    # v183：操纵探索账用的独立流（不改主随机流）
    # v183：默认 -1 = 「灾没发生」。第一版没这句，`kn_g` 只在灾块里赋值 ⇒ 灾没触发时
    # 抛 UnboundLocalError（与 v159 的 NameError 同族：局部量在条件块里定义）。
    # 现在改成 -1 能被读数看见：若 `kn_g[0] < 0`，说明这一跑压根没灾，读数不可用。
    kn_g = [-1.0, -1.0, -1.0]
    kn_ok_g = [-1.0, -1.0, -1.0]
    nb_live = -1.0
    nb_near = -1.0
    dis_step = -1                 # v183d：灾发生在第几步（判"首伸时点"用）
    fh1_n = [0, 0, 0]; fh1_hit = [0, 0, 0]   # 灾后**第一步**就伸的
    fh2_n = [0, 0, 0]; fh2_hit = [0, 0, 0]   # 第一步之后才伸的
    _rng_refr = Random(seed * 7907 + 29)   # v138：刷新用的独立流，不扰动主随机流
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
    # v148：**灾后累计**要单独算——`cum_serv` 是全程累计（含灾前 3.25 h）。
    # O2 的定义是"救急期总承载"，只该数灾后那一段。这两个快照只加读数、不改动力学。
    serv_dis = -1.0
    dem_dis = -1.0
    dis_step_rel = -1
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
    root_steps = 0           # v126：累计"节点·步"里当根的次数（用来算 f_root 的真实值）
    # 逐束账：stk[k] = [(a 端付了多少, b 端付了多少), ...]，一束一项。
    # 上一版只记"整条链累计投入"，于是 ew 从 3 掉到 2 时**不退料**，
    # 材料在那儿静默消失；而当时的守恒检验用同一本账做分子分母，看不出来。
    stk = {}
    deg = [0] * N
    mat = [MAT0[tier[i]] * mat_scale for i in range(N)]
    # v118 只做量测：总料（守恒量）与"锁定比例"。画面第 7/11/30/70 行说料是**占用**。
    init_tot = float(sum(mat))
    # v192：异质化（均值保持 1 的对数正态）。CV=0 时走 else 分支，**不抽随机数**。
    _rng_het = Random(seed * 7919 + 331)
    if HET_SPENT > 0.0 and HET_UNIFORM:
        # 同质、均值与异质档相同（1−S/2）；**不抽随机数**
        _het = [1.0 - 0.5 * HET_SPENT] * N
    elif HET_SPENT > 0.0:
        _het = [1.0 - HET_SPENT * _rng_het.random() for _ in range(N)]
    else:
        _het = [1.0] * N
    energy = [E_INIT[tier[i]] * e_scale * _het[i] for i in range(N)]
    _e_init_sum = sum(energy)      # v193：只加读数——整场电量起点（四个电通道之和应等于 起点−末点）
    _e0 = list(energy)                      # 注意：`_e0` 是**灾前那一刻**的剩余量 ⇒ 比例仍全 1
    # 读数用**同一档位内**的剩余比例离散度（跨档位比没有意义：三档本来就差 8.33 倍）
    _by_tier = {}
    for _i in range(N):
        _by_tier.setdefault(tier[_i], []).append(_het[_i])
    het_cv_real = statistics.mean([(statistics.pstdev(v) / statistics.mean(v))
                                   for v in _by_tier.values() if len(v) > 1 and statistics.mean(v) > 0])         if _by_tier else 0.0
    # （v192：`_e0` 已在上方设置——它是"灾前那一刻的剩余量"，所以"剩余比例"初始恒为 1）
    exit_s = []
    t_exit = []          # 每次退出的时刻（小时）：用来核"能活 E_INIT 小时"这个式子
    # v125 只做量测：按档位分开记退出——"谁死了"决定对策是换电池还是换策略
    t_exit_tier = []
    t_exit_deg = []
    # v126：四项能耗分开记——"是谁把电烧掉的"不能用拟合去猜
    # v193：只加读数（不改任何判定）——料（`mat`）与电（`energy`）是**两个存量**，
    # 各自的钱包要分开记：料只有"建链/白跑"两个出口，电有"待机/持链/连天/转发"四个。
    m_poke = 0.0       # 白跑（伸了但没成）付掉的料
    m_build = 0.0      # 建链付掉的料（两侧合计）
    m_refund = 0.0     # 断电退料（REFUND）
    _e_at_dis = [0.0, 0.0, 0.0, 0.0]   # 灾那一刻的累计（未发生灾时保持 0 ⇒ post 退化为全期）
    _m_at_dis = [0.0, 0.0, 0.0]
    _snap_m_pending = False
    e_idle = [0.0]*N
    e_hold = [0.0]*N
    e_sky = [0.0]*N
    e_relay = [0.0]*N
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
    snap_dis = None      # v128：打灾时刻的网况快照
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
    prev_lap = 0             # v153：横扫模式下的"第几圈"
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
    gset0 = set()          # v111：预声明，供"灾后未愈者"判定用（原来只在某个 if 里赋值）
    # ---- v111 只做量测：把"想伸 / 没目标 / 付不起 / 真连上"四个通道分开数 ----
    # 全网点火口径（含灾前）
    c_poor = 0      # 材料不够付第 deg+1 条链 → 连骰子都没掷
    c_mem_block = 0 # v135：其中"料够、但被自己的账占住了"的次数（画面第 70 行的落地计数）
    # v149 顺带修：无灾对照（dis_mode="none"）下这几个量原来只在打灾分支里赋值 ⇒ UnboundLocalError。
    # 它们都是"灾前/灾后的占用比例"，无灾时给 0 / 空表是如实值，不是占位。
    lock_pre = 0.0
    lock_post = 0.0
    lock_traj = []
    hand_med = -1.0     # v149 修：无灾对照下未赋值（同 lock_*，那几个量只在打灾分支里算）
    hand_p25 = -1.0
    # 同上一行：下面这些也只在"打灾"分支里赋值，无灾对照（dis_mode="none"）时需要如实默认值。
    cov_pre = 0.0
    cand_c = 0
    ctr_dis = -1
    iso_after = 0
    out_afford = 0
    cut_afford = 0
    in_disk = None
    c_look = 0      # v149：动作位花在"看"上的次数（直接读数）
    c_noadv = 0     # 掷了骰子没过（p_adv）
    c_flip = 0      # 过了骰子
    c_nocand = 0    # 过了骰子但没有可用目标
    c_armfail = 0   # 有目标、但某只手臂付不起
    # 只看"灾后、还没接回主干的人"（这才是 t50 的分母）
    c_g_poor = 0
    c_g_noadv = 0
    c_g_flip = 0
    c_g_nocand = 0
    c_g_succ = 0    # 真连上了一条，且对端当时已在 core 所在分量里
    # ---- v112：把"付不起"拆成灾前/灾后，并记打灾那一刻还剩多少料 ----
    c_pt_post = 0     # 灾后人次（order 里每台每步算一次）
    c_poor_post = 0   # 其中付不起的
    c_poor_pre = 0    # 灾前付不起的
    c_hand_post = 0   # 灾后掷到骰子的次数
    c_pt_cut = 0
    cyc_added = 0
    # v129：伸即看的四个计数（探了多少次／探到／探空／其中多少是"探未知"）
    c_poke = 0
    c_hit = 0
    c_miss = 0
    c_explore = 0
    c_expired = 0    # v131：因为"过期"被重探的次数（记忆时效的直接读数）
    c_see = 0        # v132：朝"看得见的亮目标"伸的次数（画面"向亮"）
    # v133：亮的三档人次，以及"亮的人里有多少还没连"——直接回答"要救的人是不是暗的"
    c_lit_dark = 0
    c_lit_dim = 0
    c_lit_bright = 0
    c_lit_unjoined = 0
    c_lit_total = 0     # v133 修：所有"亮"的候选人次（与 unjoined 同总体，才算得出占比）
    # 注：lit_unjoined 是"候选人次"，而 c_poke 是"伸手次数"——一次伸手能看到多个候选，
    # 所以 unjoined/poke 会 >100%（冒烟时真踩了：167%）。占比一律用 unjoined/lit_total。
    fail_ct = [0] * N    # v121：连续"掷骰没过"的次数（成功即清零）    # v119：实际建成的"额外搭边"条数
    c_poor_cut = 0
    mat_pre = -1.0    # 打灾那一刻全网手上的料（含已投入链上的）
    link_pre = 0      # 打灾那一刻不同的链对数
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
    serv_s = []      # v148：cum_serv 的逐步曲线
    spread_s = []
    _DLV[:] = []        # v157：投递实录在这里清（run_one 只执行一次；放在 deliver 里会每调用一次清一次）
    c_stale_p = 0    # v162：失效传递清掉的账（直接读数，不走结果量）
    fail_tot = {"no_route": 0, "broken": 0, "congest": 0, "cap": 0,
                "unk": 0, "dead_end": 0, "hop": 0, "loop": 0, "too_far": 0, "stale": 0}
    ever = set()
    t90 = None

    lock_traj = []
    LOCK_SAMPLE = (1, 10, 30, 60)
    ew_series = []      # v120：每步的链数
    ew_new = []         # v120：每步**新建**多少条链（净增会被自然断裂抵掉，不能当速率）
    # v129：每台"伸过才知道"的地图。j -> 1（那边有可连的人）／0（那边不行）。
    # 只在 POKE=1 时被读写；POKE=0 时它一直空着，不影响任何随机数。
    known = [dict() for _ in range(N)]
    # v136：一条链在"账占体量"之后有多贵（只管成本，不动可用量）
    def _lc(_i):
        _c = link_cost(deg[_i])
        if mem_v > 0.0:
            _n = len(known[_i])
            if _n:
                _c *= (1.0 + mem_v * _n) ** mem_k
        return _c
    _prev_keys = set()
    _prev_tot = None
    for step in range(total):
        t = step * dt
        ew_series.append(len(ew))
        _cur = set(ew)
        ew_new.append(len(_cur - _prev_keys))
        _prev_keys = _cur
        if dis_done and (step - pre_steps) in LOCK_SAMPLE:
            lock_traj.append((step - pre_steps, 1.0 - sum(mat) / init_tot))
        if DBG_TOT:
            _tot = sum(mat) + sum(x + y for _v in stk.values() for (x, y) in _v)
            if _prev_tot is not None and abs(_tot - _prev_tot) > 1e-6:
                print("[tot] step=%d  %.1f -> %.1f  (%+.1f)  ew=%d" % (step, _prev_tot, _tot, _tot - _prev_tot, len(ew)))
            _prev_tot = _tot
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
            dis_step = step
            # v193：灾后窗口的起点快照（本版只加读数；灾前那一截不算进"恢复期花在哪"）
            _e_at_dis = [sum(e_idle), sum(e_hold), sum(e_sky), sum(e_relay)]
            # 料的快照必须放在**灾剪链之后**：剪链会退料，那笔退款属于灾本身，不属于恢复期。
            _snap_m_pending = True
            serv_dis = cum_serv
            dem_dis = cum_dem
            dis_step_rel = step - pre_steps
            mat_pre = float(sum(mat) + sum(x + y for _v in stk.values() for (x, y) in _v))
            link_pre = len(ew)
            # v128：打灾**那一刻**的网有多稀——稀疏区制要拿这个当自变量
            _alive_now = [_i for _i in range(N) if not dead[_i]]
            snap_dis = dict(alive=len(_alive_now),
                            joined=sum(1 for _d in joined if _d),
                            edges=len(ew),
                            deg_mean=(statistics.mean([deg[_i] for _i in _alive_now]) if _alive_now else None),
                            exit_so_far=sum(1 for _i in range(N) if dead[_i]))
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
            # v118：灾**之前**的锁定比例（料被链占住的部分）
            in_disk = [dist2(_i, ctr_dis) <= _r2 for _i in range(N)]
            _hand_pre = float(sum(mat))
            lock_pre = 1.0 - _hand_pre / init_tot if init_tot > 0 else 0.0
            _ratio = sorted(mat[_i] / max(1e-9, MAT0[tier[_i]] * mat_scale) for _i in range(N))
            hand_med = _ratio[len(_ratio) // 2]
            hand_p25 = _ratio[len(_ratio) // 4]
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
                        m_refund += REFUND * (_pa + _pb)
                    del ew[k]
                    deg[a_] -= 1     # deg 数的是"几条链"（加粗不加 deg），整条断才减 1
                    deg[b_] -= 1
                    links_broken += 1
            if _snap_m_pending:
                _m_at_dis = [m_build, m_refund, m_poke]
                _snap_m_pending = False
            iso_after = sum(1 for _i in range(N) if deg[_i] == 0)
            # v118：灾**之后**（退料已发生）的锁定比例；以及盘外还活着的人"付得起下一条链"的比例
            _hand_post = float(sum(mat))
            lock_post = 1.0 - _hand_post / init_tot if init_tot > 0 else 0.0
            _out_alive = [_i for _i in range(N) if (not dead[_i]) and (not in_disk[_i])]
            _aff = sum(1 for _i in _out_alive if mat[_i] >= _lc(_i))
            out_afford = (_aff / float(len(_out_alive))) if _out_alive else 0.0
            _in_alive = [_i for _i in range(N) if (not dead[_i]) and in_disk[_i]]
            _aff2 = sum(1 for _i in _in_alive if mat[_i] >= _lc(_i))
            cut_afford = (_aff2 / float(len(_in_alive))) if _in_alive else 0.0
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
                if KNOWN_MODE:
                    # v183：把探索账也按同一套三档操纵。
                    # 注意 g2（打乱）保持**条数不变**、只把键换成"没接过的别处"，
                    # 这样"内容错"与"记忆多少"分开（否则量到的是开销，不是内容）。
                    if grp[_i] == 1:
                        known[_i] = {}
                    elif grp[_i] == 2 and known[_i]:
                        _ks = list(known[_i].items())
                        _pool = [x for x in range(N) if x != _i and x not in NBR[_i]]
                        _nk = min(len(_ks), len(_pool))
                        _newk = _rng_kn.sample(_pool, _nk)
                        known[_i] = {}
                        for _q in range(_nk):
                            known[_i][_newk[_q]] = _ks[_q][1]
            # 操纵是否成功的独立量：重连者的旧邻居里，还有多少是完好的
            _oi = [[], [], []]
            for _i in range(N):
                if grp[_i] >= 0 and snap[_i]:
                    _ok = sum(1 for _j in snap[_i] if cls[_j] == 2)
                    _oi[grp[_i]].append(_ok / float(len(snap[_i])))
            old_intact = [statistics.mean(x) if x else 0.0 for x in _oi]
            # v185：**旧邻居名单还能不能用**。v184 之后的问题是"信息有没有机会被用"，
            # 而不是"信息值不值钱"：`_pri` 只在"名单上的人此刻还在候选里"时才生效。
            # `nb_live`＝灾后那一刻，旧邻居里还活着的比例；`nb_near`＝还活着且仍在 reach 内的比例。
            _lv, _nr = [], []
            for _i in _rec:
                if snap[_i]:
                    _al = [_j for _j in snap[_i] if not dead[_j]]
                    _lv.append(len(_al) / float(len(snap[_i])))
                    _nr.append(sum(1 for _j in _al if _grid_dist(_i, _j) <= reach)
                               / float(len(snap[_i])))
            nb_live = statistics.mean(_lv) if _lv else 0.0
            nb_near = statistics.mean(_nr) if _nr else 0.0
            # v183 旋钮自检：操纵刚做完时三组的账条数（g1 必须为 0；g2 必须与 g0 同量级）
            _kn = [[], [], []]
            for _i in range(N):
                if grp[_i] >= 0:
                    _kn[grp[_i]].append(float(len(known[_i])))
            kn_g = [statistics.mean(x) if x else 0.0 for x in _kn]
            # v190：**成功条数**——排序量 1 用的就是这个，所以必须能看见它。
            # 单看 `kn_g`（条数）会误判：v189 里打乱组的账最长，但里面几乎全是"没通"。
            _kno = [[], [], []]
            for _i in range(N):
                if grp[_i] >= 0:
                    _kno[grp[_i]].append(float(sum(1 for _v in known[_i].values()
                                                 if _v[0] == 1)))
            kn_ok_g = [statistics.mean(x) if x else 0.0 for x in _kno]
            first_after = [-1.0] * N

        # v121 修（潜在 bug，只在极端臂上暴露）：`_rt`/`_crt` 原来只在 `if dis_done:` 里、
        # 且 `_crt` 只在"盘外还有握着链的人（gcore 非空）"时才定义。FM=3 把网长得太稀、
        # gcore 为空 ⇒ `_incore = ... (_rt[i] in _crt)` 抛 UnboundLocalError。
        # 给安全默认：没有核心时"没人属于核心"，语义正确，且不改任何已跑过的结果。
        _rt = list(range(N))
        _crt = set()

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
                if sweep > 0:
                    # 横扫：没有"全网同时开窗"，改按**扫完一圈**计数（每圈 = 一次完整覆盖）
                    _lap = int(t // T_ORBIT)
                    if _lap != prev_lap:
                        win_idx += 1
                        prev_lap = _lap
                else:
                    _p0 = (t % T_ORBIT) / T_ORBIT
                    _vis = any(((_p0 + _k / float(nsat)) % 1.0) < VIS_FRAC
                               for _k in range(nsat))
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
          # v113 修：加上 not dead[i]——否则"曾在灾时被切断、后来恢复、再没电"的人
          # 会因为 cls 仍是 1 而被放回循环里，让死者继续伸手。
          order = [i for i in range(N)
                   if (not dead[i]) and (joined[i] or (JOIN_CUT and cls[i] == 1))]
          # v149：**每台这一步的动作位**（看 or 伸）。独立随机流、按 range(N) 定序抽取
          # ⇒ 各臂拿到同一串动作位（CRN 保住，纪律 93）。
          _act = [_rng_act.random() < acts for _ in range(N)] if acts > 0.0 else None
          rng.shuffle(order)
          for i in order:
              # v135：**褪色必须发生在"付不付得起"之前**。
              # 若把淘汰放在料闸后面，一台被自己的账占满料的台从此既不伸、也不淘汰、也等不到退款，
              # 会**永久冻死**（写这版时自查发现的结构性死锁，不是仿真结果）。
              # v137 修：条件从 `mem_w>0` 放宽到"任一支开着"。
              # 原写法下 v136 的乙支（mem_v>0, mem_w=0）**根本不会删过期条目** ⇒ 体量成本不随遗忘下降
              # ⇒ 那一版的 `MEM_TTL` 实验会变成空转（跑得出一堆"无差别"，却与遗忘无关）。
              # 这是写 v137 前置检查时发现的，不是跑出来的。`mem_w=mem_v=0` 时仍不删 ⇒ 消融逐数不变。
              if (mem_w > 0.0 or mem_v > 0.0) and known[i]:
                  _stale = [_k2 for _k2, _v2 in known[i].items() if step - _v2[1] > mem_ttl]
                  for _k2 in _stale:
                      del known[i][_k2]
              base_i = _lc(i)
              # v121：失败留痕——连着没伸成的，下一次更不愿意伸（响应阈值：败 → θ↑ → 更难触发）
              _pa = p_adv * (OLD_ADV if grp[i] in (0, 2) else 1.0) / (1.0 + fail_mem * fail_ct[i])
              # v111：拆成两段只为计数，**短路语义不变**（材料不够时仍不消耗随机数）
              # v111 修：判定"未愈"要用**与 core 同分量**（t_self 的口径），不是 in_trunk（那要求有根）；
              # 占空比 0.10 时大半天是黑夜，in_trunk 全 False，用它判会让 g_succ 结构性恒 0。
              # v111 第二次改口径：**被切断的人不在 `order` 里**（`joined` 已是 False），
              # 所以他们根本不掷骰子——恢复完全由"已经在网里的人够不够得到他们"驱动。
              # 于是漏斗要从**够人的人**这一侧量：机会数 vs 真连上数。
              _incore = bool(dis_done) and (_rt[i] in _crt)
              if dis_done:
                  c_pt_post += 1
                  if cls[i] == 1:
                      c_pt_cut += 1
              # v135：可用量 = 存量 − 账占的那部分。`mem_w=0` 时与原来逐字等价。
              _mv = mem_w * len(known[i])
              if mat[i] - _mv < base_i:
                  if mat[i] >= base_i:
                      # 直接读数（纪律 71：不看总量涨跌，看"是否还受这条约束"）：
                      # 这一下**不是没料，是料被自己的账占住了** ⇒ 画面第 70 行「重得伸不动链」的落地计数
                      c_mem_block += 1
                  c_poor += 1
                  if dis_done:
                      c_poor_post += 1
                      if cls[i] == 1:
                          c_poor_cut += 1
                  else:
                      c_poor_pre += 1
                  continue
              if rng.random() >= _pa:
                  c_noadv += 1
                  fail_ct[i] += 1
                  continue
              # v149：这一步的动作位花在"看"上了 ⇒ 不伸。放在掷骰**之后**，
              # 是为了让主随机流的抽取次数与 `acts` 无关（纪律 93）。
              if _act is not None and _act[i]:
                  c_look += 1
                  continue
              c_flip += 1
              if dis_done:
                  c_hand_post += 1
              # v45：候选是半径 reach 内的任意终端；远的付得更多（姿态对准要功率）
              if poke:
                  # v129：伸即看。不再"全知"——朝一个方向伸，伸了才知道那边有什么。
                  # 依据：画面第 17 行"伸出去的那一下，同时就是在看""没伸到的地方，严格说不在它世界里"；
                  # 第 15 行"亮着才被找到"⇒ 未连的人不亮，本来就不该被直接看见。
                  _dirs = list(cands(i, reach))
                  # v132：亮的看得见（画面第 15 行"亮着才被找到"）——这是**感知**，不是记忆
                  _lit = []
                  if vision:
                      for _x in _dirs:
                          _jj = _x[0]
                          if dead[_jj] or (ekey(i, _jj) in ew):
                              continue
                          if lit_mode == 0:
                              # v132 的读法（错的那版）：亮＝有链
                              if not joined[_jj]:
                                  continue
                          else:
                              # v133 的读法：亮＝精力（画面自审 §1.2）。与有没有链无关。
                              _r = energy[_jj] / _e0[_jj] if _e0[_jj] > 0 else 0.0
                              if _r < lit_lo:
                                  c_lit_dark += 1
                                  continue
                              elif _r < LIT_HI:
                                  c_lit_dim += 1
                              else:
                                  c_lit_bright += 1
                          c_lit_total += 1
                          if not joined[_jj]:
                              c_lit_unjoined += 1
                          _lit.append(_x)
                  # v131：过期＝当作没记过（画面"会衰会忘"）
                  _unk, _good = [], []
                  for _x in _dirs:
                      _rec = known[i].get(_x[0])
                      if _rec is None:
                          _unk.append(_x)
                      elif step - _rec[1] > mem_ttl:
                          _unk.append(_x)
                          c_expired += 1
                      elif _rec[0] == 1:
                          _good.append(_x)
                  # v186：**名单优先**放在**上游**——而且必须放在"三桶"之前。
                  # 第一版把它插在 `_unk`／`_good` 两桶里，结果一次都没触发（`nbr_probe=0`／14856 次探）。
                  # 原因：旧邻居在灾前就已经被记进 `known`，而且多半记的是**失败**（`_rec[0]==0`）——
                  # 那一条既不在 `_unk`（有记录），也不在 `_good`（不是成功）⇒ **掉进"有记录但没用"的第三桶**，
                  # 也就是"我知道它不行，于是再也不试"。名单优先若要生效，就得把这几个人**从第三桶里捞出来**。
                  _nbr_hit = False
                  if NBR_PRIOR > 0.0:
                      _ob0 = old_nbrs.get(i)
                      if _ob0:
                          # 注意：`_dirs` 的元素是 `(节点, 距离)`（`cands` 的返回），所以**节点是 x[0]**。
                          # 而 `_pri` 那边的 pool 元素是 `(代价, 节点, 距离)`，节点在 x[1] —— 两处下标不同。
                          # 我第一次照 `_pri` 抄了 `x[1]`，拿**距离**去比节点编号，于是永不命中（0/14856）。
                          _nb = [x for x in _dirs if (x[0] in _ob0) and (not dead[x[0]])]
                          if _nb and rng.random() < NBR_PRIOR:
                              j, dist = _nb[rng.randrange(len(_nb))]
                              _KC2["probe"] += 1
                              if grp[i] == 0:
                                  _KC2["probe_g0"] += 1
                              elif grp[i] == 2:
                                  _KC2["probe_g2"] += 1
                              _nbr_hit = True
                  if _nbr_hit:
                      c_explore += 1
                  elif _lit and rng.random() >= explore:
                      # 向亮：朝看得见的那个伸（不消耗"探未知"的机会）
                      j, dist = _lit[rng.randrange(len(_lit))]
                      c_see += 1
                  elif _unk and (not _good or rng.random() < explore):
                      j, dist = _unk[rng.randrange(len(_unk))]
                      c_explore += 1
                  elif _good:
                      j, dist = _good[rng.randrange(len(_good))]
                  else:
                      c_nocand += 1
                      continue
                  cj = _lc(j) * (1.0 + dc * (dist - 1.0))
                  if POKE_COST > 0.0:
                      # 伸这一下的代价：与成不成无关（探到的可能没人／没电／已经连着）。
                      # 付不起就不伸——这一支本身也是一个新的失败类型，要单独计数。
                      _pc = POKE_COST * cj
                      if mat[i] - mem_w * len(known[i]) < _pc:
                          _KC3["poor"] += 1
                          continue
                      mat[i] -= _pc
                      m_poke += _pc
                      _KC3["n"] += 1
                      _KC3["cost"] += _pc
                  c_poke += 1
                  if NBR_PRIOR > 0.0:
                      _KC2["poke"] += 1
                      if grp[i] == 0:
                          _KC2["poke_g0"] += 1
                      elif grp[i] == 2:
                          _KC2["poke_g2"] += 1
                  # 触碰的瞬间才知道（这一下之前它不知道那边有什么）
                  _ok = ((not dead[j]) and mat[j] - mem_w * len(known[j]) >= cj
                         and ((not joined[j]) or (ekey(i, j) not in ew)))
                  known[i][j] = (1 if _ok else 0, step)
                  if FIRSTHIT and dis_done and fh_step[i] < 0:
                      fh_step[i] = step          # 灾后第一伸
                      fh_ok[i] = 1 if _ok else 0
                      _gi = grp[i]
                      if _gi >= 0:
                          fh_n[_gi] += 1
                          if _ok:
                              fh_hit[_gi] += 1
                          # v183d：**按"是不是灾后第一步"分层**。
                          # 为什么必须分层：g0 的第一伸有 53–58% 落在灾后第一步，g1 只有 33%，
                          # 而第一步那一刻邻居大多还没并网（`_ok` 更容易成立）。
                          # 不分层，量到的就是"伸得早"和"伸得准"的混合物。
                          if step == dis_step:
                              fh1_n[_gi] += 1
                              if _ok:
                                  fh1_hit[_gi] += 1
                          else:
                              fh2_n[_gi] += 1
                              if _ok:
                                  fh2_hit[_gi] += 1
                  if _ok and FIRSTHIT and dis_done and fh_hitstep[i] < 0:
                      fh_hitstep[i] = step       # 灾后第一次**成功**的伸
                  if _ok:
                      known[j][i] = (1, step)
                  else:
                      c_miss += 1
                      continue
                  c_hit += 1
                  outs = [(cj, j, dist)]
              else:
                  outs = []
                  for j, dist in cands(i, reach):
                      if dead[j]:          # 没电的终端不在候选里（不能被拉回网）
                          continue
                      cj = _lc(j) * (1.0 + dc * (dist - 1.0))
                      if mat[j] - mem_w * len(known[j]) < cj:
                          continue
                      if (not joined[j]) or (ekey(i, j) not in ew):
                          outs.append((cj, j, dist))
                  if not outs:
                      c_nocand += 1
                      continue
              # 这一次出手有没有"够得着未愈者"的机会
              _hasrec = _incore and any((_rt[x[1]] not in _crt) for x in outs)
              if _incore:
                  c_g_noadv += 1        # 借这一格记"在 core 里、掷到了骰子"的出手数
              if _hasrec:
                  c_g_flip += 1         # 机会数
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
                  ci = _lc(i) * (1.0 + dc * (dist - 1.0))
                  if KCHEAP < 1.0:
                      # v185 第一次接错：原本按 `known[i]` 里"探到过活的"来判折扣，
                      # 结果 **一次都没触发**（3339 次建链里 0 次）——因为 `known` 记的是**探针账**（每台 8–10 条），
                      # 而建链的目标来自 `outs`（当下够得着的），两者很少重叠。
                      # 改成按**旧邻居名单** `old_nbrs` 判：它才是"旧账"里真正被用在建链上的那一样（`_pri` 就是按它挑人）。
                      _onb_i = old_nbrs.get(i)
                      if _onb_i and (j in _onb_i):
                          _save = ci * (1.0 - KCHEAP)
                          ci -= _save
                          _KC["cheap"] += 1
                          _KC["save"] += _save
                          if grp[i] == 0:
                              _KC["cheap_g0"] += 1
                              _KC["save_g0"] += _save
                          elif grp[i] == 2:
                              _KC["cheap_g2"] += 1
                      _KC["used"] += 1
                  cj = _lc(j) * (1.0 + dc * (dist - 1.0))
                  if (mat[i] - mem_w * len(known[i]) < ci
                          or mat[j] - mem_w * len(known[j]) < cj):   # 远的／后伸的那只可能付不起
                      empty_arm += 1
                      c_armfail += 1
                      continue
                  try_all += 1
                  got += 1
                  if dist > 1.0:
                      far_link += 1
                  if grp[i] >= 0:
                      dsum[grp[i]] += dist
                      dn[grp[i]] += 1
                  joined[j] = True
                  joined[i] = True
                  fail_ct[i] = 0
                  fail_ct[j] = 0
                  if MERGE:
                      _mi, _mj = known[i], known[j]
                      _use_r = (ML_FILTER in (1, 3))
                      _use_a = (ML_FILTER in (2, 3))

                      def _keep(_me, _k2, _ts2):
                          if _use_r and _grid_dist(_me, _k2) > reach:
                              return False
                          if _use_a and (step - _ts2) > ML_AGE:
                              return False
                          return True

                      for _k2, _v2 in list(_mj.items()):
                          if not _keep(i, _k2, _v2[1]):
                              continue
                          _o2 = _mi.get(_k2)
                          if _o2 is None or _v2[1] > _o2[1]:
                              _mi[_k2] = _v2
                      for _k2, _v2 in list(_mi.items()):
                          if not _keep(j, _k2, _v2[1]):
                              continue
                          _o3 = _mj.get(_k2)
                          if _o3 is None or _v2[1] > _o3[1]:
                              _mj[_k2] = _v2
                      if _use_a:
                          # 重归一化：合并之后裁掉自己账里的老条目（不是随机删，按时间戳）
                          for _k2 in list(_mi):
                              if step - _mi[_k2][1] > ML_AGE:
                                  del _mi[_k2]
                                  _MRG["pruned"] += 1
                          for _k2 in list(_mj):
                              if step - _mj[_k2][1] > ML_AGE:
                                  del _mj[_k2]
                                  _MRG["pruned"] += 1
                      _mrj = min(fail_ct[i], fail_ct[j])
                      fail_ct[i] = _mrj
                      fail_ct[j] = _mrj
                      _MRG["n"] += 1
                  k = ekey(i, j)
                  if _hasrec and (_rt[j] not in _crt):
                      c_g_succ += 1
                      c_g_nocand += 1   # 借这一格记"连的是未愈者"的条数（与 succ 同步）
                  ew[k] = ew.get(k, 0) + 1
                  a_, b_ = k
                  if a_ == i:
                      stk.setdefault(k, []).append((ci, cj))
                  else:
                      stk.setdefault(k, []).append((cj, ci))
                  mat[i] -= ci
                  mat[j] -= cj
                  m_build += ci + cj
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

        # ---- v119：额外搭边（成环）----
        # v16 那个对照在当前口径下的重建：v16 的"额外边"是结构冗余（同一分量里多一条链），
        # 现在的模型里没有这个旋钮（生长只连"不同分量"），所以要显式建出来。
        # 注意：`_rt` 是本步进连地循环之前的并查集根，本步新建的链不算进去——
        # 这只会让"找同分量邻居"偏保守，不改臂的方向性。
        if cycle > 0.0:
            _cf = comps_from(ew)
            for i in range(N):
                if (not joined[i]) or dead[i]:
                    continue
                if rng.random() >= cycle:
                    continue
                # 名字别叫 `cands`——引擎里 `cands(i, reach)` 是个函数，同名会把整个作用域变成 local（当场踩过）
                _cyc_pool = [j for j in NBR[i]
                             if (not dead[j]) and joined[j] and ekey(i, j) not in ew
                             and _cf(j) == _cf(i)]
                if not _cyc_pool:
                    continue
                j = _cyc_pool[rng.randrange(len(_cyc_pool))]
                ci = _lc(i)
                cj = _lc(j)
                if (mat[i] - mem_w * len(known[i]) < ci
                        or mat[j] - mem_w * len(known[j]) < cj):
                    continue
                k = ekey(i, j)
                ew[k] = ew.get(k, 0) + 1
                stk.setdefault(k, []).append((ci, cj) if i < j else (cj, ci))
                mat[i] -= ci
                mat[j] -= cj
                m_build += ci + cj
                deg[i] += 1
                deg[j] += 1
                ever_link[i] = True
                ever_link[j] = True
                cyc_added += 1

        # 重新连上（设备行为）：灾后第一次 deg>0。与"被服务"分开记。
        if dis_done:
            for _i in range(N):
                if cls[_i] == 1 and t_relink[_i] < 0 and deg[_i] > 0:
                    t_relink[_i] = t - t_dis

        # ---- 二、连天：三档都能连，带宽不同 ----
        # v95：覆盖可以是"一个移动小盘"，也可以是"整片同时可见/不可见"（过境窗口）。
        if cov_window:
            _ph = (t % T_ORBIT) / T_ORBIT
            if sweep > 0:
                # 横扫：可见带位置由**列号**决定 ⇒ 带随 t 右移，一个周期扫完一圈
                _in_cov = (lambda _i: any(((_ph + (_i % W) / float(W) + _k / float(nsat)) % 1.0) < VIS_FRAC
                                          for _k in range(nsat)))
            else:
                _vis = any(((_ph + _k / float(nsat)) % 1.0) < VIS_FRAC for _k in range(nsat))
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
        # v156：先**按原顺序、原抽取次数**掷骰（保住主随机流位置），再决定取谁。
        _elig = []
        for i in cand:
            if up_sticky:
                _ok = can_root[i]
            else:
                _ok = (rng.random() < P_UP)
            if _ok:
                _elig.append(i)
        if sel_root == 1:
            _elig.sort(key=lambda _i: energy[_i] / max(1e-9, _e0[_i]), reverse=True)
        elif sel_root == 2:
            _elig.sort(key=lambda _i: (STR[tier[_i]], energy[_i] / max(1e-9, _e0[_i])), reverse=True)
        for i in _elig:
            # v155：带宽已经够（bw ≥ 星上容量 S0）就不再点新的根 —— 再多的根也送不出去，
            # 而每点一个就要让一台设备整步付 C_SKY。这是记账，不是新机制。
            if gwcap and bw >= s0v and up:
                break
            up.append(i)
            bw += SKY_BW[tier[i]] * sky_scale
        if ROOT_INFO and up:
            if ROOT_SORT == 0:
                def _rkey(_x):
                    return float(len(known[_x]))
            elif ROOT_SORT == 1:
                def _rkey(_x):
                    return float(sum(1 for _v in known[_x].values() if _v[0] == 1))
            elif ROOT_SORT == 2:
                def _rkey(_x):
                    return (1.0 if up_known[_x] else 0.0,
                            -float(nhops[_x]) if nhops[_x] < 99 else -999.0)
            elif ROOT_SORT == 4:
                # v192：**按剩余电量比例**（`energy/_e0`）——这是 Whittle 索引最直接的代理
                # （"还能撑多久"决定"让它发一步的边际代价"）。同档位替换 ⇒ 根数与带宽不变。
                def _rkey(_x):
                    return float(energy[_x]) / max(1e-9, _e0[_x])
            else:
                # v191：**只按组别**（g0 优先），完全不看账内容。
                # 为什么要这一臂：v190 的 S1（按"成功条数"排序）让 g0 的个体等待 470→300 s，
                # 但那个收益可能只是"g0 的人更常当根 ⇒ nhops=0 ⇒ 立刻可用"，
                # 与"账里记的东西"无关。**若 S3 ≈ S1，则起作用的是"给谁入口"，不是"知道多少"**
                # （否则就是 H13 的形态：有差、但机制不是我以为的那个）。
                def _rkey(_x):
                    return 1.0 if grp[_x] == 0 else 0.0
            _sel = set(up)
            _ri_n = 0
            for _k in range(len(up)):
                _r = up[_k]
                _pool = [x for x in _elig if x not in _sel and tier[x] == tier[_r]]
                if not _pool:
                    continue
                _ri_n += 1
                _best = max(_pool, key=_rkey)
                if _rkey(_best) > _rkey(_r):
                    _sel.discard(_r)
                    _sel.add(_best)
                    up[_k] = _best
                    _RI["swap"] += 1
            _RI["chance"] += _ri_n
            # 第一步（全局第一步）的换根次数：那一刻 `energy` 与 `_e0` 完全相等 ⇒ 比例全 1
            # ⇒ "同质 ⇒ 该排序空转"的**正确检验点**。灾后不算：灾前已经在消耗，比例自然分化。
            if _RI["steps"] == 0:
                _RI["swap1"] = _RI["swap"]
            _RI["steps"] += 1
            # 同档位 ⇒ 带宽和不变；重算一次并与原值比 —— 这是"替换没改数量"的**自证**。
            # 为什么需要自证：跨臂比"灾后第一步根数"是错的判据（换根从第 0 步就生效，轨迹必然分叉），
            # 那种写法测的是"轨迹是否相同"，不是"我的替换改没改数量"。
            _bw0 = bw
            bw = sum(SKY_BW[tier[_i]] * sky_scale for _i in up)
            if abs(bw - _bw0) > 1e-9:
                _RI["bwbad"] += 1
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
        cap_total = (s0v if capfix else min(s0v, bw)) * _ts   # v166 反事实臂，见文件头
        up_prev = up
        for i in up:
            up_known[i] = True
            nhops[i] = 0
            via[i] = -1
            if dis_done and grp[i] >= 0:
                _RG[grp[i]] += 1

        # 信念有时效（画面第 31 行"星历会过期，网的结构也会过期"）：
        # 上一步还是入口、这一步已不在覆盖区里的，必须失效。否则所有人的路由
        # 都指向一个早就不通天的格，走到底也够不着——这一版第一跑就是这么错的。
        cur_entries = set(up)
        for i in range(N):
            if up_known[i] and nhops[i] == 0 and i not in cur_entries:
                up_known[i] = False
                nhops[i] = 99
                via[i] = -1

        # v162：**失效传递**——把"经由坏账学到路"的节点一并作废，清到不动点。
        # 引擎原来只清 `nhops==0` 的直接入口；依赖它的下游仍 up_known=True，
        # 于是 `deliver` 照着 via 走、走六步绕回来（v159 量到的 `loop` 就是这个）。
        # v169：`prop==1` 清账会**同时关掉两件事**——路线（via/nhops）与准入（up_known）。
        # 而"不知道自己能通天就不发"是那道准入闸（A154）。`prop==2` **只清路线、保留准入**：
        # 这个人仍然"知道自己能通天"，只是得重新找路（配合 `RETRY>=1` 才有意义）。
        if prop:
            _ch, _rounds = True, 0
            while _ch and _rounds < 12:
                _ch = False
                _rounds += 1
                for i in range(N):
                    if not up_known[i] or i in cur_entries:
                        continue
                    j = via[i]
                    if prop >= 2 and j < 0:
                        continue          # 已经清过路线了，别在同一个点上反复清（否则死循环）
                    if j < 0 or (not up_known[j]) or nhops[i] >= 99 or nhops[j] >= nhops[i]:
                        if prop < 2:
                            up_known[i] = False
                        nhops[i] = 99
                        via[i] = -1
                        c_stale_p += 1
                        _ch = True

        # 回程读数：每步沿**已经握着的链**重探一次（画面第 17 行"真正的读数从回程来"）。
        # 只在"新搭链"时传知识的版本会死：网长满之后不再有新链，知识就冻在原地。
        adj = build_adj(ew)          # v45：每步重建，谁也不用维护增量
        refr = [i for i in range(N) if joined[i]]
        rng.shuffle(refr)
        for i in refr:
            nbs = adj.get(i, [])
            if not nbs:
                continue
            # v138：`refr_n=1` 时只抽一次，与原来**同一次随机抽取** ⇒ 消融逐数不变。
            # **CRN 关键**：无论 refr_n 取多少，每台每步都向主随机流抽**一次**（refr=0 时抽了丢弃）。
            # 否则各臂的抽取次数不同 ⇒ 后面的 shuffle/掷骰全部错位 ⇒ "配对比较"失效（纪律 10），
            # t50 的差别分不清是机制还是随机流位移（第一跑就踩了：refr0/2/99 的 t50 全都与机制无关地变了）。
            # 多出来的重探用**独立随机源**（与 v92 的 `_rng_root` 同一手法）。
            _u0 = rng.randrange(len(nbs))
            if refr_n <= 0:
                continue
            # v149：`acts>0` 时只有这一步选"看"的台才刷新（动作位互斥）
            if _act is not None and not _act[i]:
                continue
            if refr_n >= 99:
                _pick = nbs
            else:
                _pick = [nbs[_u0]] + [_rng_refr.randrange(len(nbs))
                                      for _ in range(min(refr_n, len(nbs)) - 1)]
            for j in _pick:
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
                # v146：灾后脉冲——打灾后 `dem_burst_h` 小时内需求乘 `dem_burst`。
                _ds = 1.0
                if dem_burst > 1.0 and dis_done and (t - t_dis) <= dem_burst_h * 3600.0:
                    _ds = dem_burst
                _q0 = qq.get(_i, 0.0) + D_BASIC * _ts * _ds
                _qm = Q_MAX * _ts
                qq[_i] = _q0 if _q0 < _qm else _qm
                cum_dem += D_BASIC * _ts * _ds
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

        if step >= total - 60:
            _DIA["e_a"] += float(len(ew))
            _DIA["e_t"] += float(sum(1 for _k in ew if ew[_k] >= 2))
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
            e_idle[i] += C_IDLE * dt_h
            e_hold[i] += deg[i] * C_HOLD * dt_h
            if i in up:
                use += C_SKY * dt_h
                e_sky[i] += C_SKY * dt_h
            if SERVE_PAY:
                use += relay_used.get(i, 0.0) * C_RELAY
                e_relay[i] += relay_used.get(i, 0.0) * C_RELAY
            if RELAY_PAY:
                _rp = _RELAY_DLV.get(i, 0.0)
                if _rp > 0.0:
                    use += _rp * C_RELAY
                    e_relay[i] += _rp * C_RELAY
            if i in up:
                root_steps += 1
            energy[i] -= use
        if RELAY_PAY:
            _RELAY_DLV.clear()      # 一步滞后：本步投递的转发费已在上面的循环结过
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
                            m_refund += REFUND * (_pa + _pb)
                        del ew[k]
                        deg[j] -= 1
                t_exit_deg.append(deg[i])   # v125 修：必须在这行之前抓，否则恒 0（尺子退化）
                deg[i] = 0
                dead[i] = True
                t_exit.append(t / 3600.0)
                t_exit_tier.append(tier[i])

        # 同一张网、同一步，两套一起算（配对）
        # 两个臂必须数同一批人：全知那臂把入口也算作"被服务"（入口本身就在上行），
        # 本地这臂若把入口排除在候选之外，两臂的分母就不是一回事——
        # 2026-11-05 自查发现：×1 时全知的 18 个名额几乎全被入口占掉，
        # 而本地只数非入口，两者在量不同的东西，那个"差 3%"因此不成立。
        # 同一张网、同一时刻，用 K 个不同顺序各投递一次：量"先来后到"到底有多大
        if DL_ON and (step % DL_PERIOD == 0):
            for _i in range(N):
                if not joined[_i]:
                    continue
                if DL_NEED_LIT:
                    _r0 = energy[_i] / _e0[_i] if _e0[_i] > 0 else 0.0
                    if _r0 < LIT_LO:
                        continue
                dl_ack[_i] = step
        order_local = [i for i in range(N) if joined[i]]
        trial = []
        failstat = None
        for _k in range(K_ORDER):
            o = order_local[:]
            rng.shuffle(o)
            global _DIA_ON
            _DIA_ON = (_k == 0) and (step >= total - 60)
            loc, fs = deliver(joined, ew, up, tier, up_known, nhops, via,
                              cap_total, fail_cnt, o, adj, retry_n, dep=(_k == 0))
            _DIA_ON = False
            trial.append(len(loc) / float(N))
            if failstat is None:
                failstat = fs
                loc_first = loc
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
        if DL_ON:
            _d = dl_ack
            # 「同步」是**要过期**的（画面第 25 行"下行同步"；与第 31 行"记忆有时效"同源）：
            # 只在最近一个宣告周期内算可用，不是"听过一次就永久可用"。
            _nav = sum(1 for _v in loc_first
                       if _d[_v] >= 0 and (step - _d[_v]) <= DL_TTL)
            _lost = sum(1 for _v in loc_first
                        if _d[_v] < 0 or (step - _d[_v]) > DL_TTL)
            dl_av_s.append(_nav / float(N))
            dl_lost_s.append(_lost)
        else:
            dl_av_s.append(R_loc)
            dl_lost_s.append(0)
        R_loc_s.append(R_loc)
        serv_s.append(cum_serv)      # v148：累计服务逐步曲线——无灾对照也要能取"同一窗口"的值
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
                ca, cb = _lc(_a0), _lc(_b0)
                if (mat[_a0] - mem_w * len(known[_a0]) >= ca
                        and mat[_b0] - mem_w * len(known[_b0]) >= cb):
                    ew[k] += 1
                    thick_events += 1
                    stk.setdefault(k, []).append((ca, cb))
                    mat[_a0] -= ca
                    mat[_b0] -= cb
                    m_build += ca + cb
                    if ew[k] == 2 and k not in first_thick:
                        first_thick[k] = step
            # 减一束：概率 eps*(1-T)，独立的一项（系数不同、驱动量不同，不是加粗取负号）
            elif ew.get(k, 0) > 1 and rng.random() < EPS * _ts * (1.0 - _T):
                ew[k] -= 1
                _pa, _pb = stk[k].pop()
                mat[_a0] += REFUND * _pa
                mat[_b0] += REFUND * _pb
                m_refund += REFUND * (_pa + _pb)

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
                    m_refund += REFUND * (_pa + _pb)
                else:
                    brk_soft[0] += 1
                    del ew[k]
                    for _pa, _pb in stk.pop(k, []):
                        mat[a] += REFUND * _pa
                        mat[b] += REFUND * _pb
                        m_refund += REFUND * (_pa + _pb)
                    deg[a] -= 1
                    deg[b] -= 1

    tail = max(1, min(60, len(R_b)))
    return {
        "seed": seed, "dt": dt, "total": total, "tag": tag, "s0": s0v,
        # v170：痕迹诊断（旋钮自检：`ph_hit>0` 才算痕迹真的被用上了）
        "ph_len": len(_PH),
        "ph_cov": (sum(1 for i in range(N)
                       if joined[i] and any(_PH.get(ekey(i, j), 0.0) >= 0.05 for j in adj.get(i, [])))
                   / float(max(1, sum(1 for i in range(N) if joined[i])))),
        "ph_hot": (sum(1 for i in range(N) if joined[i] and _HOT[i] >= 0)
                   / float(max(1, sum(1 for i in range(N) if joined[i])))),
        "ph_hit": (_PHst["hit"] / float(_PHst["n"]) if _PHst["n"] else 0.0),
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
        "kn_g": kn_g,
        "kn_ok_g": kn_ok_g,
        "fh_n": list(fh_n),
        "fh_hit": list(fh_hit),
        "fh_rate": [(fh_hit[_g] / float(fh_n[_g]) if fh_n[_g] else None) for _g in range(3)],
        "fh_delay": [(statistics.median([fh_hitstep[_i] - fh_step[_i] for _i in range(N)
                                        if grp[_i] == _g and fh_step[_i] >= 0 and fh_hitstep[_i] >= 0])
                      if any(grp[_i] == _g and fh_step[_i] >= 0 and fh_hitstep[_i] >= 0 for _i in range(N))
                      else None) for _g in range(3)],
        "fh_miss1": sum(1 for _i in range(N) if fh_ok[_i] == 0),
        # v183b：**首伸发生在第几步**——这是判定"命中率差异"是不是"时点差异"的关键。
        # 为什么怀疑时点：`old_nbrs` 唯一接的线是 `_pa`（连地概率 ×1.5，`OLD_ADV`），
        # 而 `if rng.random() >= _pa: continue` 是**整步的闸**——g0/g2 过闸机会多
        # ⇒ 它们的第一伸更早发生；早发生时邻居更多还"未并网"，`_ok` 更容易成立。
        # 若三组的 `fh_tmed` 不同，那 15.6 个点里就有一部分是"伸得早"，不是"伸得准"。
        "fh_tmed": [(statistics.median([fh_step[_i] for _i in range(N)
                                        if grp[_i] == _g and fh_step[_i] >= 0])
                     if any(grp[_i] == _g and fh_step[_i] >= 0 for _i in range(N)) else None)
                    for _g in range(3)],
        # v183c：中位数会盖住分布。这三个数才是判"时点"的：
        #  `fh_tq` = 首伸步数的 25/50/75 分位；`fh_p98` = "灾后第一步就伸了"的比例。
        # 若 g0 的第一伸显著更集中于第一步，那命中率差里就有一块是"伸得早"（那一步邻居多还没并网）。
        "fh_tq": [(_pctl([fh_step[_i] for _i in range(N)
                        if grp[_i] == _g and fh_step[_i] >= 0], 0.25),
                    _pctl([fh_step[_i] for _i in range(N)
                        if grp[_i] == _g and fh_step[_i] >= 0], 0.50),
                    _pctl([fh_step[_i] for _i in range(N)
                        if grp[_i] == _g and fh_step[_i] >= 0], 0.75))
                   if any(grp[_i] == _g and fh_step[_i] >= 0 for _i in range(N)) else None
                  for _g in range(3)],
        "fh1": [(fh1_hit[_g] / float(fh1_n[_g]) if fh1_n[_g] else None) for _g in range(3)],
        "fh1_n": list(fh1_n),
        "fh2": [(fh2_hit[_g] / float(fh2_n[_g]) if fh2_n[_g] else None) for _g in range(3)],
        "fh2_n": list(fh2_n),
        "poke_cost_n": _KC3["n"],
        "poke_cost_sum": _KC3["cost"],
        "poke_poor": _KC3["poor"],
        "nbr_probe": _KC2["probe"],
        "nbr_poke": _KC2["poke"],
        "nbr_poke_g0": _KC2["poke_g0"],
        "nbr_probe_g0": _KC2["probe_g0"],
        "nbr_probe_g2": _KC2["probe_g2"],
        "nbr_poke_g2": _KC2["poke_g2"],
        "kc_used": _KC["used"],
        "kc_cheap": _KC["cheap"],
        "kc_cheap_g0": _KC["cheap_g0"],
        "kc_cheap_g2": _KC["cheap_g2"],
        "kc_save_g0": _KC["save_g0"],
        "kc_save": _KC["save"],
        "mat_end_mean": statistics.mean([mat[_i] for _i in range(N) if not dead[_i]] or [0.0]),
        "fh_tmin": (min([fh_step[_i] for _i in range(N) if fh_step[_i] >= 0] or [-1])),
        "fh_pfirst": [(sum(1 for _i in range(N)
                           if grp[_i] == _g and fh_step[_i] >= 0
                           and fh_step[_i] == min([fh_step[_j] for _j in range(N) if fh_step[_j] >= 0] or [-9]))
                       / float(max(1, sum(1 for _i in range(N) if grp[_i] == _g and fh_step[_i] >= 0))))
                      for _g in range(3)],
        "known_mean": (sum(len(known[_i]) for _i in range(N) if joined[_i])
                       / float(max(1, sum(1 for _i in range(N) if joined[_i])))),
        "merges": _MRG["n"],
        "pruned": _MRG["pruned"],
        "mat_end": sum(mat) + sum(x + y for v in stk.values() for (x, y) in v),
        "stk_mismatch": sum(1 for k in ew if len(stk.get(k, [])) != ew[k]),
        "strand_total": sum(len(v) for v in stk.values()),
        "exit_frac": exit_s[-1] if exit_s else 0.0,
        "n_exit": len(t_exit),
        "ex_t": (round(min(t_exit), 2), round(statistics.median(t_exit), 2), round(max(t_exit), 2)) if t_exit else None,
        "dead_deg": (statistics.mean(t_exit_deg) if t_exit_deg else None),
        "ex_tier": [t_exit_tier.count(0), t_exit_tier.count(1), t_exit_tier.count(2)],
        "alive_tier": [sum(1 for _i in range(N) if (not dead[_i]) and tier[_i] == _t) for _t in (0, 1, 2)],
        "n_alive": sum(1 for _i in range(N) if not dead[_i]),
        # v127：度数分布——压度数这条路要看的是分布尾端，"均值过线"不等于"全部过线"
        "deg_stats": dict(
            mean=(statistics.mean([deg[_i] for _i in range(N) if not dead[_i]]) if any(not dead[_i] for _i in range(N)) else None),
            p90=sorted([deg[_i] for _i in range(N) if not dead[_i]])[int(0.9 * max(1, sum(1 for _i in range(N) if not dead[_i]))) - 1] if any(not dead[_i] for _i in range(N)) else None,
            mx=max([deg[_i] for _i in range(N) if not dead[_i]]) if any(not dead[_i] for _i in range(N)) else None,
            deg0=sum(1 for _i in range(N) if (not dead[_i]) and deg[_i] == 0)),
        "e_split": dict(
            all_=[sum(e_idle), sum(e_hold), sum(e_sky), sum(e_relay)],
            dead=[sum(e_idle[_i] for _i in range(N) if dead[_i]),
                  sum(e_hold[_i] for _i in range(N) if dead[_i]),
                  sum(e_sky[_i] for _i in range(N) if dead[_i]),
                  sum(e_relay[_i] for _i in range(N) if dead[_i])],
            n_dead=sum(1 for _i in range(N) if dead[_i]),
            n_alive=sum(1 for _i in range(N) if not dead[_i]),
            root_steps=root_steps,
            init=_e_init_sum, now=sum(energy),
            # 灾后（恢复期）单独一份：四个通道都减去灾那一刻的累计
            post=[sum(e_idle) - _e_at_dis[0], sum(e_hold) - _e_at_dis[1],
                  sum(e_sky) - _e_at_dis[2], sum(e_relay) - _e_at_dis[3]],
            post_dis_step=dis_step),
        # v193：**料是另一个存量**（`MAT0`），只有两个出口：建链与白跑；还有退货（REFUND）。
        # 与电量分开放，是因为"料花在哪"与"电花在哪"不是同一笔钱（v192 只量了电）。
        "m_split": dict(
            init=sum(MAT0[tier[_i]] * mat_scale for _i in range(N)), now=sum(mat),
            build=m_build, refund=m_refund, poke=m_poke,
            post_build=m_build - _m_at_dis[0], post_refund=m_refund - _m_at_dis[1],
            post_poke=m_poke - _m_at_dis[2],
            poke_n=_KC3.get("n", 0), poke_cost=_KC3.get("cost", 0.0),
            poor=_KC3.get("poor", 0)),

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
        "used_old": list(used_old), "try_link": list(try_link),
        "nb_live": nb_live, "nb_near": nb_near,
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
        "dl_av_s": dl_av_s,
        "dl_lost_mean": (statistics.mean(dl_lost_s) if dl_lost_s else 0.0),
        "dl_av_end": (sum(1 for _i in range(N) if joined[_i] and dl_ack[_i] >= 0)
                      / float(max(1, sum(1 for _i in range(N) if joined[_i])))),
        "enrich_dlv": ((_DIA["thick_hop"] / _DIA["hop"]) / (_DIA["e_t"] / _DIA["e_a"])
                       if _DIA["hop"] > 0 and _DIA["e_a"] > 0 and _DIA["e_t"] > 0 else None),
        "thick_edge_share": ((_DIA["e_t"] / _DIA["e_a"]) if _DIA["e_a"] > 0 else None),
        "hop_dlv": _DIA["hop"],
        "thick_hop": _DIA["thick_hop"],
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
        "cyc": cyc_added,
        "poke": dict(see=c_see, lit_dark=c_lit_dark, lit_dim=c_lit_dim,
                     lit_bright=c_lit_bright, lit_unjoined=c_lit_unjoined,
                     lit_total=c_lit_total,
                     n=c_poke, hit=c_hit, miss=c_miss, explore=c_explore,
                     expired=c_expired,
                     known_mean=statistics.mean([len(_k) for _k in known])),
        "fail_ct_end": sum(1 for _x in fail_ct if _x > 0),
        "ew_series": ew_series,
        "ew_new": ew_new,
        "e_spent": sum(E_INIT[tier[_i]] - energy[_i] for _i in range(N)),
        "serv": cum_serv,
        # v148：O2＝灾后累计送达当量；恢复指标用灾后序列自行算
        "serv_dis": serv_dis, "dem_dis": dem_dis, "dis_step_rel": dis_step_rel,
        "serv_post": (cum_serv - serv_dis) if serv_dis >= 0 else None,
        "R_loc_s": list(R_loc_s),
        "serv_s": list(serv_s),
        "dem": cum_dem,
        "win_n": win_idx + 1,
        "cut0_n": len(cut0_set),
        "cut0_list": sorted(cut0_set),
        "g0_n": g0_n,
        "snap_dis": snap_dis,
        "lock": dict(pre=lock_pre, post=lock_post, traj=lock_traj,
                     hand_med=hand_med, hand_p25=hand_p25,
                     out_afford=out_afford, cut_afford=cut_afford,
                     init_tot=init_tot, n_out=len(_out_alive), n_in=len(_in_alive)),
        "c": dict(look=c_look, poor=c_poor, mem_block=c_mem_block, noadv=c_noadv, flip=c_flip, nocand=c_nocand,
                  armfail=c_armfail, g_poor=c_g_poor, g_noadv=c_g_noadv,
                  g_flip=c_g_flip, g_nocand=c_g_nocand, g_succ=c_g_succ,
                  pt_post=c_pt_post, poor_post=c_poor_post, poor_pre=c_poor_pre,
                  hand_post=c_hand_post, mat_pre=mat_pre, link_pre=link_pre,
                  pt_cut=c_pt_cut, poor_cut=c_poor_cut),
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
        "sweep": sweep,
        "nsat": nsat,
        "sel_root": sel_root,
        "ri_swap": _RI["swap"],
        "ri_chance": _RI["chance"],
        "ri_bwbad": _RI["bwbad"],
        "ri_swap1": _RI["swap1"],
        "root_g": list(_RG),
        "het_cv_real": het_cv_real,
        "het_spread": (max(_e0) / max(1e-9, min(_e0))),
        # v157：投递侧的三个直接读数（判断"腰斩"来源用，不进任何结论量）
        "dlv_trace": list(_DLV),
        # v161：**信念覆盖率**——已并网者里"自认为能通天"（`up_known`）的比例。
        # 这是"服务被卡在哪"的直接读数：v157–v160 已排除容量（预算只用 18%）与距离（HOP_MAX×4 无感），
        # 剩下的候选就是"知道自己能通天的人有多少"，而它由**根的存在 + 每步只抽一个邻居**共同决定。
        "stale_p": c_stale_p,
        # v166 诊断：**保留下来的账有多深**（`nhops` 的分位）。用来判"级联牵连"：
        # 若某一档的路由树深得多，那么清掉一个枢纽就会连带清掉整棵子树 ⇒ 清账的代价大。
        # v166 诊断：**"自认为能通天"的人里，按 via 走到底真能到根的比例**（`fn_rate`）。
        # 这是"被清掉的账里有多少其实还能用"的直接读数——v164–v166 已排除根数/链长/预算，
        # 剩下的候选就是这个：清账的净收益 = 真坏的比例 × 收益 − 还能用的比例 × 损失。
        "fn_rate": _fn_rate(up_known, nhops, via, set(up), joined, HOP_MAX, tier),
        "nh_p90": (sorted([nhops[_i] for _i in range(N)
                           if joined[_i] and up_known[_i] and nhops[_i] < 99])[
                       int(0.9 * max(1, len([1 for _i in range(N)
                                             if joined[_i] and up_known[_i] and nhops[_i] < 99])) - 1)]
                   if any(joined[_i] and up_known[_i] and nhops[_i] < 99 for _i in range(N)) else None),
        # v164：**根的"在哪"**（v163 冒烟发现：根 5.3 时 O2p 44.7、根 20.4 时 168.3，
        # 而 v162 的"强球 11 根"却只有 216→137 —— 数量相差不多、服务差一个量级 ⇒ 变量不是数量）。
        # 两个读数都只描述**根的空间离散程度**，单位是格：
        #   `root_spread`＝根到质心的均方根距离；`root_nn`＝每个根到最近另一个根的距离均值。
        # 两者越大＝根越分散。若 O2p 与它们的关系比与"根数"更紧，则"选根先看位置"这句话才有读数支撑。
        "root_spread": (_rsprd([(_i % W, _i // W) for _i in up]) if up else None),
        "root_nn": (_rnn([(_i % W, _i // W) for _i in up]) if len(up) > 1 else None),
        "bel_cov": (sum(1 for _i in range(N) if joined[_i] and up_known[_i])
                    / float(max(1, sum(1 for _i in range(N) if joined[_i])))),
        # 前提自检用：当根者的平均剩余电量比例（按能力选根应当显著高于随机）
        "root_e": (statistics.mean([energy[_i] / max(1e-9, _e0[_i]) for _i in up]) if up else None),
        "n_up": len(up),
        "ncov": sum(1 for _i in range(N) if _in_cov(_i)) if cov_window else None,
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
        "price_next": statistics.mean([_lc(i) for i in range(N) if joined[i]] or [0.0]),
        "joined_frac": sum(1 for i in range(N) if joined[i]) / float(N),
        "mat_scale": mat_scale,
        # ⚠ 这里差点又写成同义反复：`sum(mat) + Σ链上投入` 恒等于 mat0，
        # 那是记账方式的另一种写法（v39 已判过，纪律 29）。要判"材料是不是卡住"，
        # 只能看**手上还剩多少**，以及**有多少台已经买不起下一条**。
        "mat_free": sum(mat) / float(max(1, mat0)),
        # v135：账的占用（画面第 30 行）。三个读数缺一不可：
        #   条目数（账到底记了多少）／占用占料的比例（这条约束是否成规模）／被它卡住的次数（直接后果）。
        # 只报"占用比例"不看"卡住次数"会犯 v119 的错（总量变了不等于这条约束还在起作用，纪律 71）。
        "mem_w": mem_w,
        "mem_entries": statistics.mean([len(known[i]) for i in range(N) if not dead[i]] or [0.0]),
        "mem_frac": statistics.mean([mem_w * len(known[i]) / max(1e-9, MAT0[tier[i]] * mat_scale)
                                     for i in range(N) if not dead[i]] or [0.0]),
        "mem_block": c_mem_block,
        # v136：成本倍率（＝交换面被体量削弱了多少）。与 `mem_frac` 不是同一件事：
        # mem_frac 量"料被占了多少"，它量"每一步贵了多少"。
        "vol_mul": statistics.mean([((1.0 + mem_v * len(known[i])) ** mem_k)
                                    for i in range(N) if not dead[i]] or [1.0]),
        # v137：**"账多的人是不是枢纽"**——上一版(V136)把"乙支定向压制枢纽"当解释，但没量过。
        # 只报末态、只报活人：死者度数为 0 会把相关拉向 0（分母三问，纪律 54）。
        "mem_deg_r": _pearson([len(known[i]) for i in range(N) if not dead[i]],
                              [deg[i] for i in range(N) if not dead[i]]),
        "mem_by_deg": [
            statistics.median([len(known[i]) for i in range(N)
                               if (not dead[i]) and lo <= deg[i] <= hi] or [-1])
            for lo, hi in ((0, 1), (2, 3), (4, 99))],
        "cant_afford": (sum(1 for i in range(N) if joined[i] and mat[i] < _lc(i))
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



