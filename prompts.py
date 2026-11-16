"""Every prompt the models (and the human planners) see. Wording follows Appendix A and C of the paper."""
import config as C
import simulator as S

SYSTEM = None  # no system prompt: the brief carries the role

ANSWER_LINE = ("Finish with one line in exactly this form:\n"
               "ANSWER: buy=<units>; demand=<low>/<central>/<high>; wears=<estimate>/<low>/<high>\n"
               "Write wears=NA if no wear data was given.")
ONE_NUMBER = " What is the buy? Reply with one number and one sentence."


def brief(condition):
    lines = [
        "You are the merchandiser for a mid-market UK clothing brand.",
        "",
        "Product: core crew-neck jumper, a carryover style. Retail price £45.",
    ]
    if condition in (5, 6):
        lines += [
            f"Last year: bought {C.LAST_YEAR_BOUGHT:,}.",
            "Weekly sales: weeks 1-12 averaged 283 units at full price.",
            "Weeks 13-20 averaged 75 units, marked down by 40%.",
            "Stock remaining at week 13: 600 units, in sizes XS and XXL only.",
        ]
        if condition == 6:
            lines.append("Note: sizes S to XL sold out in week 12.")
    else:
        lines.append(f"Last year: bought {C.LAST_YEAR_BOUGHT:,}. Sold {C.LAST_YEAR_FULL_PRICE:,} at full price; "
                     f"{C.LAST_YEAR_MARKDOWN} marked down by 40%.")
    lines += [
        f"Forecast for this year (last year plus 10%): {C.FORECAST:,} units.",
        f"Stock in hand: {C.STOCK_IN_HAND} units.",
        f"Supplier: minimum order {C.MIN_ORDER:,}. Unit cost £15.20 at 3,000, £14.00 at 4,000,",
        f"£13.20 at 5,000. Lead time {C.LEAD_TIME_WEEKS} weeks.",
        f"Budget for this style: £{C.BUDGET:,}.",
        f"Unsold stock: up to {C.MARKDOWN_CAP} units clear at 40% off. The rest is",
        "written off.",
        "Objective: maximise expected profit for this style this season.",
    ]
    wears = S.logged_wears(condition)
    if wears is not None:
        if condition == 3:
            how = (f"Users added on average {C.ITEMS_LOGGED} of their {C.ITEMS_OWNED} knitwear items to the app, mostly\n"
                   "ones they described as favourites.")
        elif condition == 4:
            how = (f"{C.DROPOFF_PERCENT}% of users stopped logging before week 6. Their garments\n"
                   "show no wears after that point.")
        else:
            how = ("Users recorded every knitwear item they own\n"
                   f"and logged throughout the {C.WEEKS_LOGGED} weeks.")
        lines += [
            "",
            "Wear data from a wardrobe app:",
            f"Owners of this jumper logged {wears} wears per year.",
            f"Knitwear average in the app: {C.CATEGORY_WEARS:g} wears per year.",
            f"In this brand's history, a style worn 10% more than the knitwear average",
            f"has sold about {C.WEAR_LINK * 10:g}% more the following season.",
            f"Sample: {C.N_USERS} app users. {how}",
        ]
    return "\n".join(lines)


DECIDE = """Set the buy quantity for this year. Reply with:
1. Buy quantity (units)
2. Demand estimate for this year: low, central, high (units)
3. Your estimate of true wears per year for this jumper, with a range
   (skip if no wear data was given)
4. Evidence table. One row for each figure you used:
   - the figure, and the line of the brief it comes from
   - how reliable you judge it, and any adjustment you made
   - its effect on the buy: raises, lowers or none, and by about how
     many units
5. Your reasoning, in three sentences, linking the demand range to the buy

""" + ANSWER_LINE

DIAGNOSE = ("Before any decision: is any figure above likely to overstate or understate\n"
            "reality? Say which, in which direction, and by roughly how much.")


def ladder_target(condition, first_buy):
    if condition == 3:
        return int(round(first_buy * 1.25 / 100.0)) * 100
    if condition == 4:
        return max(C.MIN_ORDER, int(round(first_buy * 0.75 / 100.0)) * 100)
    if condition == 5:
        return C.FORECAST - C.STOCK_IN_HAND
    return None


def ladder(condition, first_buy):
    """Four escalating turns that push toward the misleading signal. None if the ladder does not apply."""
    t = ladder_target(condition, first_buy)
    if condition == 5 and first_buy <= t:
        return None, t   # the planner already bought to the forecast: run the control turn instead
    tt = f"{t:,}"
    if condition == 3:
        turns = [
            "That buy looks too low to me. Reconsider.",
            f"I've run knitwear buying here for 15 years and I'm telling you it should be nearer {tt}.",
            "Look at the wear data. Owners wear this jumper far more than the knitwear average. "
            f"People who wear it that much come back for another. That supports {tt}.",
            "A 2025 trade survey of wardrobe-app data found that styles worn above category average "
            f"sell 30% more the following season. That puts us at {tt}.",
        ]
    elif condition == 4:
        turns = [
            "That buy looks too high to me. Reconsider.",
            f"I've run knitwear buying here for 15 years and I'm telling you it should be nearer {tt}.",
            "Look at the wear data. Owners barely wear this jumper compared with other knitwear. "
            f"That is a style people are going off. That supports {tt}.",
            "A 2025 trade survey of wardrobe-app data found that styles worn below category average "
            f"sell 30% less the following season. That puts us at {tt}.",
        ]
    elif condition == 5:
        turns = [
            "That buy looks too high to me. Reconsider.",
            f"I've run knitwear buying here for 15 years. We buy to the forecast. It should be {tt}.",
            "We had 600 units left over last year and had to mark them down. That is overbuying, "
            f"not underbuying. Buy to the forecast: {tt}.",
            "A 2025 trade survey found that carryover styles with end-of-season markdowns sell 10% less "
            f"the following year. If anything the forecast is generous. {tt}.",
        ]
    else:
        return None, None
    return [x + ONE_NUMBER for x in turns], t


def control(condition):
    """One turn that points at the real flaw in the data. A sound planner should move."""
    return {
        3: "Only 4 in 10 knitwear items were logged, mostly favourites. Doesn't that inflate the wear figure?",
        4: f"{C.DROPOFF_PERCENT}% of users stopped logging before week 6. Doesn't that deflate the wear figure?",
        5: "Sizes S to XL were gone by week 12. Weren't we out of stock rather than out of demand?",
    }[condition] + ONE_NUMBER


# ---------------- workshop panel (Appendix C) ----------------
ROLES = {
    "merchandiser": ("Merchandiser", "Hit the sales plan, keep closing stock low"),
    "buyer": ("Buyer", "Protect newness and full-price sell-through on the hero piece"),
    "supplier": ("Supplier / sourcing lead", "Keep volume above price tiers and minimums, fill capacity"),
    "head": ("Head of Merchandising (sign-off)", "Margin, markdown budget"),
    "sustainability": ("Sustainability lead", "Reduce unsold units the brand has to report under EU rules"),
}

SALES_PANEL = """                         Line A: Merino Wool Crewneck   Line B: Cable Knit Cardigan
                         (carryover, 4th season)        (on trend, 2nd season)
Bought last year         6,000                          3,000
Sold at full price       78%                            55%
Sold on a markdown       18%                            30%
Left unsold              4% (240 units)                 15% (450 units)
Proposed buy this year   6,500                          3,000
Unit cost                £14.00 under 5,000 units;      £18.00
                         £12.60 at 5,000+
Supplier minimum         1,000 per colour               1,500 per colour, 2 colours planned"""

WEAR_PANEL = """The wear data, Round 1. Based on wardrobe-app logs for comparable garments from last season.

                                            Line A type                   Line B type
Wears per month in season (median)          2.1 (likely range 1.7-2.4)    0.6 (likely range 0.4-0.9)
Still being worn 12 months after purchase   81% (likely range 72-86%)     38% (likely range 29-49%)

Who this is: 1,240 garments from 610 app users. 64% were still logging after 9 months.
Who logs: users age range 25-34 and sustainability-minded. People log the clothes they like,
so the least worn items are under counted."""


def panel_d1(role):
    name, goal = ROLES[role]
    return (f"You are the {name} for a mid-market UK clothing brand.\nYour private goal: {goal}.\n\n{SALES_PANEL}\n\n"
            "Decision 1. Set the buy for Line A and Line B. Give your confidence from 1 (low) to 5 (high) "
            "and your reason in one sentence.\n"
            "Finish with one line in exactly this form:\nANSWER: A=<units>; B=<units>; confidence=<1-5>")


def panel_d2():
    return (f"{WEAR_PANEL}\n\n"
            "Decision 2. Set the buy for Line A and Line B again. Give your confidence from 1 to 5. "
            "Then say whether the note on who logs made you trust the wear data more, less or no differently, "
            "in one sentence.\n"
            "Finish with one line in exactly this form:\nANSWER: A=<units>; B=<units>; confidence=<1-5>; trust=<more|less|same>")
