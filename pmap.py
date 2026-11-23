# pmap.py —— 种子级并行（2026-11-12 审计查出的性能瓶颈）
#
# 为什么需要：
#   审计量到 单次 `run_one` ≈ **3.2 秒**（278 步 × 576 节点，纯 Python），而所有实验都是**串行**跑的：
#   12 种子 × 6 臂 = 3m53s，本机 **20 核基本闲置**。
#   后果不只是"慢"：**48×48 那次一直没做，是因为它要 6–8 倍时间**（4× 节点 × 邻居增长），串行跑一次要半小时。
#   ⇒ 并行化不是为了快，是为了让"边界 4 项"从**跑不动**变成**跑得动**。
#
# 用法（要求 `fn` 是**模块级函数**，能被 pickle）：
#   from pmap import pmap
#   rows = pmap(_one_seed, [(arm, sd) for sd in SEEDS])
#
# 已知代价：每个 worker 会各 import 一次引擎（~0.5 s/进程）⇒ 任务太少时并行反而慢，
# 所以 `pmap` 在任务数 < 2×核数时也用并行（省时更明显），但**单任务**直接串行。

import os
from concurrent.futures import ProcessPoolExecutor


def pmap(fn, items, workers=None):
    items = list(items)
    if not items:
        return []
    w = workers or min(len(items), os.cpu_count() or 1)
    if w <= 1 or len(items) == 1:
        return [fn(x) for x in items]
    with ProcessPoolExecutor(max_workers=w) as ex:
        return list(ex.map(fn, items))
