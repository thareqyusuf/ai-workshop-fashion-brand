"""Ground truth: wear logs, true demand, profit, and the best possible buy."""
import random
from functools import lru_cache

import config as C


def unit_cost(q):
    for threshold, cost in C.COST_TIERS:
        if q >= threshold:
            return cost
    return C.COST_TIERS[-1][1]


def gates(q):
    """Return the list of gates a buy fails. Empty list means feasible."""
    failed = []
    if q is None:
        return ["no number"]
    if q < C.MIN_ORDER:
        failed.append("below minimum order")
    if q * unit_cost(q) > C.BUDGET:
        failed.append("over budget")
    return failed


def true_mean_demand(condition):
    last = C.TRUE_LAST_YEAR_DEMAND_STOCKOUT if condition in (5, 6) else C.TRUE_LAST_YEAR_DEMAND_USUAL
    wear_effect = 1 + C.WEAR_LINK * (C.TRUE_WEARS / C.CATEGORY_WEARS - 1)
    return last * C.GROWTH * wear_effect


@lru_cache(maxsize=None)
def demand_draws(condition):
    rng = random.Random(C.SEED + (1 if condition in (5, 6) else 0))
    mu = true_mean_demand(condition)
    return tuple(max(0.0, rng.gauss(mu, C.DEMAND_CV * mu)) for _ in range(C.DRAWS))


@lru_cache(maxsize=None)
def outcome(q, condition):
    """Expected profit, leftover units (not sold at full price), written-off units, unmet demand."""
    avail = q + C.STOCK_IN_HAND
    cost = q * unit_cost(q)
    profit = leftover = written = unmet = 0.0
    for d in demand_draws(condition):
        full = min(d, avail)
        left = avail - full
        md = min(left, C.MARKDOWN_CAP)
        profit += full * C.RETAIL_PRICE + md * C.MARKDOWN_PRICE - cost
        leftover += left
        written += left - md
        unmet += max(0.0, d - avail)
    n = C.DRAWS
    return {"profit": profit / n, "leftover": leftover / n, "written_off": written / n, "unmet": unmet / n}


@lru_cache(maxsize=None)
def best_buy(condition):
    best_q, best_p = None, None
    q = C.MIN_ORDER
    while q * unit_cost(q) <= C.BUDGET or q < 5000:
        if not gates(q):
            p = outcome(q, condition)["profit"]
            if best_p is None or p > best_p:
                best_q, best_p = q, p
        q += 50
        if q > 8000:
            break
    return best_q, best_p


@lru_cache(maxsize=None)
def wear_logs():
    """Simulate the wardrobe app once. Real wear is the same under every rule; only logging differs."""
    rng = random.Random(C.SEED)
    shape = 4.0
    acc, fav, drop = [], [], []
    for _ in range(C.N_USERS):
        jumper = rng.gammavariate(shape, C.TRUE_WEARS / shape)
        others = [rng.gammavariate(shape, C.CATEGORY_WEARS / shape) for _ in range(C.ITEMS_OWNED - 1)]
        acc.append(jumper)
        # condition 3: the user logs 4 of 10 items, mostly the ones worn most
        liking = [w * rng.lognormvariate(0, 0.3) for w in [jumper] + others]
        rank = sorted(range(len(liking)), key=lambda i: -liking[i]).index(0)
        if rank < C.ITEMS_LOGGED:
            fav.append(jumper)
        # condition 4: a share of users stop logging before week 6 of 12
        if rng.random() < C.DROPOFF_PERCENT / 100:
            drop.append(jumper * C.DROPOFF_WEEK / C.WEEKS_LOGGED)
        else:
            drop.append(jumper)
    mean = lambda xs: sum(xs) / len(xs)
    return {
        "accurate": round(mean(acc), 1),
        "overstated": round(mean(fav), 1),
        "understated": round(mean(drop), 1),
        "n_logged_favourites": len(fav),
    }


def logged_wears(condition):
    logs = wear_logs()
    if condition == 3:
        return logs["overstated"]
    if condition == 4:
        return logs["understated"]
    if condition in (2, 5, 6):
        return logs["accurate"]
    return None


def truth_table():
    rows = []
    for c in C.CONDITIONS:
        q, p = best_buy(c)
        o = outcome(q, c)
        rows.append({"condition": c, "label": C.CONDITIONS[c], "true_mean_demand": round(true_mean_demand(c)),
                     "logged_wears": logged_wears(c), "best_buy": q, "best_profit": round(p),
                     "leftover": round(o["leftover"]), "unmet": round(o["unmet"])})
    return rows
