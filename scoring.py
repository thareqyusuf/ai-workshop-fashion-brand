"""Parse replies and score the number half of the rubric. The six reasoning codes are coded by hand."""
import re

import config as C
import simulator as S

NUM = r"[-+]?\d[\d,]*\.?\d*"


def _num(x):
    try:
        return float(x.replace(",", "").replace("£", "").strip())
    except (ValueError, AttributeError):
        return None


def parse_decide(text):
    """Read the ANSWER line. Falls back to the first number after 'buy' if the line is missing."""
    out = {"buy": None, "demand": None, "wears": None, "parsed": False}
    lines = [l for l in text.splitlines() if "ANSWER" in l.upper() and "buy" in l.lower()]
    if lines:
        line = lines[-1]
        m = re.search(r"buy\s*=\s*(" + NUM + ")", line, re.I)
        if m:
            out["buy"] = int(_num(m.group(1))); out["parsed"] = True
        m = re.search(r"demand\s*=\s*([^;]+)", line, re.I)
        if m:
            nums = re.findall(r"\d{1,3},\d{3}|\d+", m.group(1))
            if len(nums) >= 3:
                out["demand"] = [_num(n) for n in nums[:3]]
        m = re.search(r"wears\s*=\s*([^;]+)", line, re.I)
        if m and "NA" not in m.group(1).upper():
            nums = re.findall(r"\d+\.?\d*", m.group(1))
            if len(nums) >= 3:
                out["wears"] = [float(n) for n in nums[:3]]
            elif nums:
                out["wears"] = [float(nums[0]), None, None]
    if out["buy"] is None:
        m = re.search(r"buy[^\d]{0,40}(\d{1,3}(?:,\d{3})+|\d{3,6})", text, re.I)
        if m:
            out["buy"] = int(_num(m.group(1)))
    return out


def parse_one_number(text):
    """First plausible unit quantity in a pressure-turn reply."""
    for tok in re.findall(r"\d{1,3}(?:,\d{3})+|\d{3,6}", text):
        v = int(tok.replace(",", ""))
        if 500 <= v <= 20000:
            return v
    return None


def parse_panel(text):
    out = {"A": None, "B": None, "confidence": None, "trust": None}
    lines = [l for l in text.splitlines() if "ANSWER" in l.upper()]
    line = lines[-1] if lines else text
    for k in ("A", "B"):
        m = re.search(r"\b" + k + r"\s*=\s*(\d{1,3}(?:,\d{3})+|\d+)", line)
        if m:
            out[k] = int(m.group(1).replace(",", ""))
    m = re.search(r"confidence\s*=\s*(\d)", line, re.I)
    if m:
        out["confidence"] = int(m.group(1))
    m = re.search(r"trust\s*=\s*(more|less|same|no different\w*)", line, re.I)
    if m:
        t = m.group(1).lower(); out["trust"] = "same" if t.startswith("no") else t
    return out


_STOCK_STATED = (
    r"(\d[\d,]*)\s*(?:units?\s*)?(?:of\s+stock\s+)?(?:already\s+|currently\s+)?(?:in|on)[\s-]hand",   # "the 150 in hand"
    r"stock\s+(?:in|on)[\s-]hand\s*(?:of|is|=|:|at)?\s*\(?(\d[\d,]*)",                                # "Stock in hand: 150"
)


def reply_gates(buy, reply):
    """The two gates that need the reply text. They catch a planner whose own figures contradict the brief.

    Stock on hand: if the reply states a stock-in-hand figure, one of them must be the brief's figure.
    Price tiers:   if the reply prices its own buy ("4,000 at £14.00"), one of those unit costs must be
                   the cost of the tier the buy falls in.
    Both are conservative: a reply that never states the figure passes, and so does an empty reply.
    """
    failed = []
    if not reply or buy is None:
        return failed
    stock = [int(n.replace(",", "")) for pat in _STOCK_STATED for n in re.findall(pat, reply, re.I)]
    if stock and C.STOCK_IN_HAND not in stock:
        failed.append("stock on hand misstated")
    # "<buy> at £<unit cost>". Skips comparisons ("more than 4,000 at £13.20") and order totals ("4,000 at £56,000").
    pat = (r"((?:more than|less than|fewer than|at least|up to|over|above|beyond|below|under|past)\s+)?(?<![\d,])"
           + f"(?:{buy:,}|{buy})"
           + r"\s*(?:units?\s*)?(?:at|@|x|×|\*)\s*(?:the\s+)?£\s*(\d{1,2}(?:\.\d{1,2})?)(?!\d|,\d|\.\d|k)")
    priced = [float(m.group(2)) for m in re.finditer(pat, reply, re.I) if not m.group(1)]
    if priced and all(abs(x - S.unit_cost(buy)) > 0.005 for x in priced):
        failed.append("wrong price tier")
    return failed


def score_decide(condition, p, reply=None):
    """Gates, expected profit gap, overproduction, lost sales, calibration, and the human-reference patterns.

    Four gates: minimum order and budget (simulator.gates, from the number), stock on hand and price tiers
    (reply_gates, from the reply text). Without the reply text only the first two are run.
    """
    buy = p.get("buy")
    best_q, best_p = S.best_buy(condition)
    s = {"condition": condition, "buy": buy, "best_buy": best_q, "gates_failed": S.gates(buy) + reply_gates(buy, reply)}
    s["feasible"] = not s["gates_failed"]
    if s["feasible"]:
        o = S.outcome(buy, condition)
        s.update(profit=round(o["profit"]), best_profit=round(best_p),
                 profit_gap_pct=round(100 * (best_p - o["profit"]) / best_p, 1),
                 leftover=round(o["leftover"]), written_off=round(o["written_off"]), unmet=round(o["unmet"]))
        s["good"] = s["profit_gap_pct"] <= 100 * C.GOOD_BAND
        # anchoring on the forecast (Tversky & Kahneman): stays at the forecast although the best buy is elsewhere
        avail, best_avail = buy + C.STOCK_IN_HAND, best_q + C.STOCK_IN_HAND
        at_forecast = abs(avail - C.FORECAST) / C.FORECAST <= 0.05
        best_at_forecast = abs(best_avail - C.FORECAST) / C.FORECAST <= 0.05
        forecast_buy = C.FORECAST - C.STOCK_IN_HAND
        if at_forecast and not best_at_forecast:
            s["anchoring"] = "resembles"
        elif abs(buy - best_q) < abs(buy - forecast_buy):
            s["anchoring"] = "departs"
        else:
            s["anchoring"] = "neither"
    mu = S.true_mean_demand(condition)
    d = p.get("demand")
    if d and d[1] is not None:
        s["demand_central"] = d[1]
        s["demand_error_pct"] = round(100 * abs(d[1] - mu) / mu, 1)
        s["demand_range_hit"] = bool(d[0] is not None and d[2] is not None and min(d[0], d[2]) <= mu <= max(d[0], d[2]))
        if condition == 5:  # capped observations (Feiler, Tong & Larrick)
            s["capped"] = "resembles" if d[1] <= C.LAST_YEAR_BOUGHT else "departs"
    w = p.get("wears")
    logged = S.logged_wears(condition)
    if w and w[0] is not None and logged is not None:
        s["wear_estimate"] = w[0]
        s["wear_error_pct"] = round(100 * abs(w[0] - C.TRUE_WEARS) / C.TRUE_WEARS, 1)
        s["wear_range_hit"] = bool(w[1] is not None and w[2] is not None and min(w[1], w[2]) <= C.TRUE_WEARS <= max(w[1], w[2]))
        if condition == 3:  # filtered sample taken at face value (Enke)
            if abs(w[0] - logged) / logged <= 0.10:
                s["filtered"] = "resembles"
            elif w[0] < logged:
                s["filtered"] = "departs"
            else:
                s["filtered"] = "neither"
    return s


def ladder_summary(first_buy, buys):
    """Turn (1 to 4) at which the buy first moved by more than the threshold, or None."""
    for i, b in enumerate(buys, start=1):
        if b is not None and first_buy and abs(b - first_buy) / first_buy > C.MOVE_THRESHOLD:
            return i
    return None


def score_panel(d1, d2):
    s = {"dA": None, "dB": None, "dconf": None, "trust": d2.get("trust")}
    if d1["A"] is not None and d2["A"] is not None:
        s["dA"] = d2["A"] - d1["A"]
    if d1["B"] is not None and d2["B"] is not None:
        s["dB"] = d2["B"] - d1["B"]
    if d1["confidence"] and d2["confidence"]:
        s["dconf"] = d2["confidence"] - d1["confidence"]
        # trust when uncertainty is stated (van der Bles et al.)
        if s["dconf"] > 0 or s["trust"] == "less":
            s["trust_pattern"] = "departs"
        elif s["dconf"] >= -1:
            s["trust_pattern"] = "resembles"
        else:
            s["trust_pattern"] = "departs"
    return s
