#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""票房逆袭模拟器 piaofang-nixi(原创,纯 Python 标准库)。

玩家扮演小成本喜剧片《全村第一笑》(纯属虚构)的发行方,
在 7 天国庆档里分配每日排片占比与营销费用,靠口碑把
"档期炮灰"的标签翻转为"逆袭黑马"。

灵感来源:2026 年国庆档"票房破 7 亿""小成本喜剧逆袭"的社会现象;
片名、人物、公司均为虚构,与任何真实影片无关。
"""

import argparse
import random
import sys

# ---------------- 档期常量 ----------------
DAYS = 7
MAX_SCREEN_SHARE = 30.0    # 单日排片占比上限(%)
START_REPUTATION = 50.0    # 初始口碑(0-100)
MARKETING_BUDGET = 2000.0  # 营销总预算(万元)
PRODUCTION_COST = 4500.0   # 制作成本(万元)
REVENUE_SHARE = 0.43       # 票房分账比例(片方所得)
COMEBACK_THRESHOLD = 75.0  # 口碑达到该值即翻转标签
OVERBOOK_PENALTY = 4.0     # 排片透支(排片 > 口碑/3)的口碑惩罚

# 国庆档每日大盘(万元),7 天合计 7.15 亿
MARKET = [9000.0, 10500.0, 12000.0, 12500.0, 11000.0, 9500.0, 8000.0]

FILM_NAME = "《全村第一笑》"

# 虚构竞争对手(纯属虚构,与真实影片无关)
COMPETITORS = [
    {"name": "《星河战纪3》", "share": 40.0, "rep": 70.0},
    {"name": "《古城谍影》", "share": 30.0, "rep": 75.0},
]

LABEL_DUD = "档期炮灰"
LABEL_COMEBACK = "逆袭黑马"

# (事件名, 口碑变化下限, 上限, 描述)
EVENTS = [
    ("观众自来水安利", 10.0, 16.0, "路人看完直呼\"值回票价\",朋友圈刷屏安利"),
    ("短视频二创病毒传播", 12.0, 20.0, "二创剪辑在短视频平台播放破亿,评论区大型\"哈哈哈\"现场"),
    ("影评人长文好评", 5.0, 10.0, "知名影评人发长文:\"今年国庆档最被低估的喜剧\""),
    ("隔壁大片点映口碑爆了", -12.0, -6.0, "隔壁大制作点映满分开局,部分观众被分流"),
    ("营销翻车", -10.0, -5.0, "热搜词条没买对,评论区翻车,宣发连夜删博"),
    ("风平浪静", 0.0, 3.0, "平平无奇的一天,口碑缓慢发酵"),
]

# 5 档结局:(名称, 善意玩梗评语)
ENDINGS = [
    ("票房冠军", "从\"炮灰\"一路杀到档期第一!排片经理连夜把海报从角落挪到了 C 位。"),
    ("逆袭黑马", "口碑破圈成功!观众自来水比营销费管用,\"炮灰\"标签正式撕掉。"),
    ("勉强回本", "没亏就是赢。制片人长舒一口气,决定请全剧组吃顿好的。"),
    ("档期炮灰", "大盘很热闹,但跟你没什么关系。下次记得错峰,别硬刚大制作。"),
    ("血本无归", "营销费打了水漂。排片经理的头发,和票房一起掉了。"),
]


class IllegalMove(Exception):
    """非法操作:超排片上限 / 超营销预算 / 非法输入。"""


def clamp_rep(x):
    """口碑钳制到 [0, 100]。"""
    return max(0.0, min(100.0, x))


class GameState:
    def __init__(self):
        self.day = 0
        self.reputation = START_REPUTATION
        self.budget_left = MARKETING_BUDGET
        self.marketing_spent = 0.0
        self.total_boxoffice = 0.0          # 万元
        self.comp_totals = [0.0 for _ in COMPETITORS]
        self.flipped = False                # 是否已翻转成"逆袭黑马"
        self.label = LABEL_DUD
        self.daily_log = []


def allocate(state, screen, marketing):
    """校验并执行当日排片与营销分配;非法则抛 IllegalMove。"""
    if not isinstance(screen, (int, float)) or not isinstance(marketing, (int, float)):
        raise IllegalMove("排片占比与营销费用必须是数字")
    screen = float(screen)
    marketing = float(marketing)
    if not (0.0 <= screen <= MAX_SCREEN_SHARE):
        raise IllegalMove("排片占比 %s 超出范围 [0, %s]" % (screen, MAX_SCREEN_SHARE))
    if marketing < 0.0:
        raise IllegalMove("营销费用不能为负: %s" % marketing)
    if marketing > state.budget_left + 1e-9:
        raise IllegalMove("营销费用 %s 超出剩余预算 %.1f" % (marketing, state.budget_left))
    state.budget_left -= marketing
    state.marketing_spent += marketing
    return screen, marketing


def settle(total, comp_totals, profit, flipped):
    """按 7 天总票房/利润/是否翻转结算,返回结局下标 0-4。"""
    if total > max(comp_totals):
        return 0  # 票房冠军
    if profit > 0 and flipped:
        return 1  # 逆袭黑马
    if profit >= 0:
        return 2  # 勉强回本
    if profit > -2500.0:
        return 3  # 档期炮灰
    return 4      # 血本无归


def run_game(state, decide, rng, verbose=False):
    """跑完 7 天,返回结算 dict。decide(state) -> (排片%, 营销万元)。"""
    for day in range(DAYS):
        state.day = day
        screen, marketing = decide(state)
        allocate(state, screen, marketing)

        # 营销转化为口碑(边际递减,单日上限 15)
        gain = min(marketing * 0.02, 15.0)
        state.reputation = clamp_rep(state.reputation + gain)

        # 排片透支惩罚:排片远超口碑支撑会被观众吐槽
        overbook = screen > state.reputation / 3.0 + 1e-9
        if overbook:
            state.reputation = clamp_rep(state.reputation - OVERBOOK_PENALTY)

        # 每日随机口碑事件
        name, lo, hi, desc = rng.choice(EVENTS)
        delta = rng.uniform(lo, hi)
        state.reputation = clamp_rep(state.reputation + delta)

        # 当日票房 = 排片占比 x 口碑系数 x 大盘
        market = MARKET[day]
        player_bo = screen / 100.0 * (state.reputation / 100.0) * market
        comp_bos = [c["share"] / 100.0 * (c["rep"] / 100.0) * market
                    for c in COMPETITORS]
        state.total_boxoffice += player_bo
        for i, b in enumerate(comp_bos):
            state.comp_totals[i] += b

        # 标签翻转:口碑破阈值,或单日票房超过任一对手
        if state.reputation >= COMEBACK_THRESHOLD:
            state.flipped = True
        if player_bo > max(comp_bos):
            state.flipped = True
        state.label = LABEL_COMEBACK if state.flipped else LABEL_DUD

        state.daily_log.append({
            "day": day, "screen": screen, "marketing": marketing,
            "event": name, "event_delta": delta, "event_desc": desc,
            "overbook": overbook, "reputation": state.reputation,
            "player_bo": player_bo, "comp_bos": comp_bos,
            "label": state.label,
        })
        if verbose:
            extra = "排片过猛被吐槽!" if overbook else ""
            print("第%d天 | 排片%.1f%% 营销%.0f万 | 事件:%s(%+.1f)%s"
                  % (day + 1, screen, marketing, name, delta, extra))
            print("       口碑%.1f | 单日票房%.0f万 | 标签:%s"
                  % (state.reputation, player_bo, state.label))

    profit = (state.total_boxoffice * REVENUE_SHARE
              - PRODUCTION_COST - state.marketing_spent)
    ending = settle(state.total_boxoffice, state.comp_totals, profit, state.flipped)
    return {
        "total_boxoffice": state.total_boxoffice,
        "comp_totals": list(state.comp_totals),
        "profit": profit,
        "flipped": state.flipped,
        "ending": ending,
        "ending_name": ENDINGS[ending][0],
        "ending_comment": ENDINGS[ending][1],
        "marketing_spent": state.marketing_spent,
    }


def ai_decide(state):
    """贪心 AI:前三天重营销冲口碑,排片略激进(偶尔触发排片过猛惩罚)。"""
    if state.day < 3 and state.reputation < 72.0:
        marketing = min(state.budget_left * 0.30, 500.0)
    elif state.reputation < 60.0:
        marketing = min(state.budget_left * 0.15, 250.0)
    else:
        marketing = 0.0
    screen = min(MAX_SCREEN_SHARE, state.reputation / 3.0 + 2.0)
    return screen, round(marketing, 1)


def run_auto(games, seed, verbose=False):
    """自动演示,返回每局结算 dict 列表(同种子可复现)。"""
    results = []
    for g in range(games):
        rng = random.Random(seed + g)
        state = GameState()
        res = run_game(state, ai_decide, rng, verbose=verbose)
        results.append(res)
    return results


def print_summary(results):
    counts = [0] * len(ENDINGS)
    for r in results:
        counts[r["ending"]] += 1
    print("共 %d 局,结局分布:" % len(results))
    for i, (name, _comment) in enumerate(ENDINGS):
        if counts[i]:
            print("  %s: %d 局" % (name, counts[i]))
    avg_total = sum(r["total_boxoffice"] for r in results) / len(results)
    avg_profit = sum(r["profit"] for r in results) / len(results)
    flip_rate = sum(1 for r in results if r["flipped"]) / len(results) * 100
    print("平均总票房: %.2f 亿 | 平均利润: %.0f 万 | 翻转率: %.0f%%"
          % (avg_total / 10000.0, avg_profit, flip_rate))


def parse_float(raw):
    try:
        return float(str(raw).strip())
    except (ValueError, AttributeError):
        raise IllegalMove("输入不是数字:%r" % (raw,))


def read_number(prompt, lo, hi):
    val = parse_float(input(prompt))
    if not (lo - 1e-9 <= val <= hi + 1e-9):
        raise IllegalMove("输入 %s 超出范围 [%s, %s]" % (val, lo, hi))
    return val


def interactive_decide(state):
    print("\n—— 第 %d 天(10月%d日) ——" % (state.day + 1, state.day + 1))
    print("当前口碑 %.1f | 标签:%s | 营销剩余预算 %.0f 万"
          % (state.reputation, state.label, state.budget_left))
    screen = read_number("今日排片占比(0-%s%%): " % MAX_SCREEN_SHARE, 0.0, MAX_SCREEN_SHARE)
    marketing = read_number("今日营销费用(0-%.0f万): " % state.budget_left,
                            0.0, state.budget_left)
    return screen, marketing


def print_result(res):
    print("\n===== 7 天档期结束 =====")
    print("总票房: %.2f 亿" % (res["total_boxoffice"] / 10000.0))
    for c, t in zip(COMPETITORS, res["comp_totals"]):
        print("  %s: %.2f 亿" % (c["name"], t / 10000.0))
    print("营销总花费: %.0f 万 | 净利润: %.0f 万" % (res["marketing_spent"], res["profit"]))
    print("标签: %s" % (LABEL_COMEBACK if res["flipped"] else LABEL_DUD))
    print("结局:%s" % res["ending_name"])
    print("评语:%s" % res["ending_comment"])


def interactive():
    if not sys.stdin.isatty():
        print("当前不是交互终端,无法手动排片。请使用 --auto 进入自动演示模式。")
        return 2
    print("=== 票房逆袭模拟器 ===")
    print("你是小成本喜剧片%s(纯属虚构)的发行方,初始标签:「%s」。"
          % (FILM_NAME, LABEL_DUD))
    print("7 天国庆档:营销总预算 %.0f 万,单日排片上限 %s%%。"
          % (MARKETING_BUDGET, MAX_SCREEN_SHARE))
    print("口碑达到 %.0f 即撕掉「炮灰」标签,翻转成「%s」!"
          % (COMEBACK_THRESHOLD, LABEL_COMEBACK))
    state = GameState()
    rng = random.Random()
    try:
        res = run_game(state, interactive_decide, rng, verbose=True)
    except IllegalMove as e:
        print("非法操作:%s,游戏结束。" % e)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\n已退出。")
        return 1
    print_result(res)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="票房逆袭模拟器:7 天国庆档,从档期炮灰逆袭成黑马。")
    ap.add_argument("--auto", action="store_true", help="自动演示(AI 贪心排片)")
    ap.add_argument("--games", type=int, default=10, help="自动演示局数(默认 10)")
    ap.add_argument("--seed", type=int, default=42, help="随机种子(默认 42)")
    ap.add_argument("--verbose", action="store_true", help="打印每日战报")
    args = ap.parse_args(argv)
    if args.auto:
        if args.games < 1:
            print("--games 至少为 1")
            return 2
        results = run_auto(args.games, args.seed, args.verbose)
        print_summary(results)
        return 0
    return interactive()


if __name__ == "__main__":
    sys.exit(main())
