"""Rule-based coding of four of the six reasoning codes, written and run by Claude (an LLM), not by human coders.

  python code_reasoning.py                 # reads results/to_code.csv, writes results/reasoning_codes_claude.csv
  python code_reasoning.py --rules-only    # the rules alone, no adjudication: writes results/reasoning_codes_rules_only.csv
  python code_reasoning.py --review        # also print the cases the rules flagged

LLM use. Read this with the LLM Usage Statement in the paper.
  The rules     are code, drafted with Claude like the rest of the repository. What they print is a script's
                output, not a language model's assertion. --rules-only gives exactly that.
  The OVERRIDES at the bottom of this file are a language model's judgement: Claude read the text a rule had
                flagged and changed the code. The default run applies them, and Table A2 of the paper reports
                the default run. The paper has to say so wherever it reports those numbers.

Codes (definitions in Table A3 of the paper) and the rule used for each:
  wear_data_used        conditions 2-6. The evidence table has a row whose figure cell holds the logged wear figure,
                        with a reliability cell and an effect cell that are both filled in.
  reliable_information  conditions 3-5. The flaw is named in the reply and the estimate moves the right way:
                        c3 favourites/selection named and wear estimate more than 10% below the logged 39.1;
                        c4 drop-off named and wear estimate more than 10% above the logged 22.9;
                        c5 stockout named and central demand above last year's 4,000 sales.
  trade_off             The reply names a cost of buying too much (markdown, write-off, surplus) and a cost of
                        buying too little (lost or missed sales, running short), outside its description of last year.
  traceable             Every number in the figure column of the evidence table appears in the brief, is simple
                        arithmetic on brief numbers, or is labelled as the planner's own assumption or estimate.
Not coded here: reproducible, uncertainty carried through. They need a person to follow the arithmetic.
results/to_code.csv is left untouched for human coders.
"""
import csv
import re
import sys

import prompts as P

csv.field_size_limit(10 ** 9)
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
RULES_ONLY = "--rules-only" in sys.argv
SRC = ARGS[0] if ARGS else "results/to_code.csv"
OUT = ARGS[1] if len(ARGS) > 1 else ("results/reasoning_codes_rules_only.csv" if RULES_ONLY else "results/reasoning_codes_claude.csv")
LOGGED = {2: "29.8", 3: "39.1", 4: "22.9", 5: "29.8", 6: "29.8"}
FLAW = {3: r"favourit|favorit|self-?select|selection|selective|4 of (their |the )?10|four of (their |the )?ten|4 in 10|subset",
        4: r"stopped logging|stop(s)? logging|drop-?off|dropp?ed out|attrition|lapsed|before week 6|truncat|censor|missing (logs|wears|data)|incomplete",
        5: r"stock-?out|stocked out|sold out|out of stock|ran out|sell-?out|sold through|censor|constrain|unavailab|size (gap|run|availab)|broken size|no stock|XS and XXL"}
OVER = r"mark(ed)?[- ]?down|write-?off|written off|writing off|clearance|left ?over|unsold|overstock|over-?buy|surplus|excess|extra stock"
UNDER = r"shortage|units? short|margin lost|lost (full-price )?(sale|margin|demand|profit)|los(e|es|ing) (full-price )?(sale|margin)|miss(ed|es|ing)? (full-price )?(sale|demand)|unmet|shortfall|short of demand|under-?buy|under-?stock|run(s|ning)? (out|short)|forgo|foregone|sacrific|stock-?out (risk|cost)|risk of (a )?stock-?out|too few|leaves? (demand|sales) "
OWN = r"\bmy\b|assum|scenario|estimat|judg|not supplied|derived|calculat|implied|implies|own |planning|rounded|=|×|x |\*|/|plus|minus|less |times"


def nums(text):
    return {re.sub(r"\.0+$", "", n.replace(",", "").rstrip(".")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def ev_table(reply):
    out, on = [], False
    for l in reply.split("\n"):
        if l.strip().startswith("|"):
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            if not on:
                on = len(cells) >= 3 and bool(re.search(r"effect", l, re.I)) and bool(re.search(r"reliab|adjust", l, re.I))
                continue
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            out.append([cells[0], " ".join(cells[1:-1]), cells[-1]])
        elif on and out and not l.strip():
            break
    return out


def answer(reply):
    m = re.search(r"ANSWER:\s*buy=([\d,]+);\s*demand=([\d,.]+)/([\d,.]+)/([\d,.]+);\s*wears=([^\s;]+)", reply)
    if not m:
        return None, None
    f = lambda x: float(x.replace(",", ""))
    w = m.group(5).split("/")
    return f(m.group(3)), (f(w[0]) if w[0].upper() != "NA" else None)


def outside_table(reply):
    return "\n".join(l for l in reply.split("\n") if not l.strip().startswith("|"))


def snippet(pat, text, width=70):
    m = re.search(pat, text, re.I)
    if not m:
        return ""
    a, b = max(0, m.start() - width), min(len(text), m.end() + width)
    return text[a:b].replace("\n", " ")


def code(row):
    c = int(row["condition"]); reply = row["reply"]; table = ev_table(reply)
    central, wears = answer(reply)
    brief = nums(P.brief(c)) | {"27", "18", "3550", "3740", "100"}
    res = {"model": row["model"], "key": row["key"], "condition": c}
    # wear data used
    if c >= 2:
        hit = [r for r in table if LOGGED[c] in r[0] or re.search(r"logged .*wears|wears .*logged|wear data|wear figure", r[0], re.I)]
        res["wear_data_used"] = int(any(len(r[1]) >= 10 and len(r[2]) >= 3 for r in hit))
    else:
        res["wear_data_used"] = ""
    # reliable information
    if c in (3, 4, 5):
        named = bool(re.search(FLAW[c], reply, re.I))
        if c == 3: right = wears is not None and wears < 39.1 * 0.9
        elif c == 4: right = wears is not None and wears > 22.9 * 1.1
        else: right = central is not None and central > 4000
        res["reliable_information"] = int(named and right)
        res["_rel"] = f"named={named} est={wears if c != 5 else central}"
    else:
        res["reliable_information"] = ""; res["_rel"] = ""
    # trade-off: looked for in the prose and the effect column, not in the description of last year's figures
    text = outside_table(reply) + "\n" + "\n".join(r[2] for r in table)
    o, u = snippet(OVER, text), snippet(UNDER, text)
    res["trade_off"] = int(bool(o) and bool(u)); res["_over"], res["_under"] = o, u
    # traceable
    bad = []
    for r in table:
        extra = nums(re.sub(r"£", "", r[0])) - brief
        if extra and not re.search(OWN, r[0], re.I):
            bad.append((sorted(extra), r[0][:110]))
    res["traceable"] = int(not bad); res["_bad"] = bad
    return res


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    coded = [code(r) for r in rows]
    changed = 0
    if not RULES_ONLY:
        for r in coded:                               # adjudications made by Claude after reading the flagged text
            for k, v in OVERRIDES.get((r["model"], r["key"]), {}).items():
                changed += int(r[k] != v)
                r[k] = v
    print("Rules only, no adjudication." if RULES_ONLY else
          f"Rules, with {changed} values changed by Claude's adjudication (an LLM). --rules-only gives the rules alone.")
    cols = ["model", "key", "condition", "traceable", "reliable_information", "wear_data_used", "trade_off"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(coded)
    for m in sorted({r["model"] for r in coded}):
        print(m)
        for k in cols[3:]:
            v = [r[k] for r in coded if r["model"] == m and r[k] != ""]
            print(f"  {k:22s} {sum(v)}/{len(v)}")
    return coded


# Adjudications made by Claude after reading the text the rules flagged. Everything else is the rule's output.
_C, _G = "claude-sonnet-5-5", "gpt-6.1-sol"
_derived = {"traceable": 1}      # flagged numbers are arithmetic on brief numbers (percentages, 283 x 12, order cost) or line references
_lastyear = {"trade_off": 0}     # "lost sales/demand" describes last year's stockout (or "missing demand probabilities"), not a cost of this buy
OVERRIDES = {
    **{(_C, f"decide-{k}"): _derived for k in ("c3-r1", "c6-r1", "c5-r1", "c2-r2", "c3-r2", "c6-r2", "c5-r2", "c2-r3", "c6-r3",
                                               "c5-r3", "c5-r4", "c6-r5", "c5-r5")},
    **{(_G, f"decide-{k}"): _derived for k in ("c1-r1", "c1-r2", "c1-r4")},
    # claude c4-r4 and c4-r5 stay 0: the figure column gives a "£22.50 net" clearance price, which needs a VAT rate the brief does not state
    (_C, "decide-c6-r5"): {**_derived, **_lastyear},
    (_G, "decide-c5-r1"): _lastyear, (_G, "decide-c6-r2"): _lastyear, (_G, "decide-c1-r4"): {**_derived, **_lastyear}, (_G, "decide-c6-r5"): _lastyear,
}

if __name__ == "__main__":
    coded = main()
    if "--review" in sys.argv:
        for r in coded:
            tag = f"{r['model'][:6]} {r['key'][7:]}"
            if r["_bad"]: print("TRACE?", tag, r["_bad"][:3])
        for r in coded:
            tag = f"{r['model'][:6]} {r['key'][7:]}"
            if r["condition"] in (3, 4, 5) and not r["reliable_information"]: print("REL0", tag, r["_rel"])
            if r["condition"] >= 2 and not r["wear_data_used"]: print("WEAR0", tag)
