"""Human dry run: the same briefs and answer format as the models, on paper and in two CSV tables.

  python human.py pack --participants P1         write the brief packs and add blank rows to the answer tables
  python human.py ladder --participant P1 --brief 3 --buy 4000
                                                 print the pressure turns for the teammate to read aloud
  python human.py import                         turn the filled tables into runs/humans.jsonl (a "Humans" column in report.py)

Files (all under human/):
  <P>_briefs.md       what the participant reads: six briefs in a shuffled order, condition hidden, then the workshop panel
  <P>_key.json        which brief is which condition. The facilitator keeps this; the participant does not see it.
  answers.csv         one row per participant and brief: the table to fill in
  panel_answers.csv   one row per participant and role: the table to fill in
"""
import argparse
import csv
import json
import os
import random

import config as C
import prompts as P
import scoring as X

DIR = "human"
ANSWER_COLS = ["participant", "brief", "buy", "demand_low", "demand_central", "demand_high",
               "wears_estimate", "wears_low", "wears_high", "evidence_and_reasoning",
               "ladder_T1_buy", "ladder_T2_buy", "ladder_T3_buy", "ladder_T4_buy", "control_buy", "notes"]
PANEL_COLS = ["participant", "role", "d1_A", "d1_B", "d1_confidence", "d1_reason",
              "d2_A", "d2_B", "d2_confidence", "trust_more_less_same", "d2_reason"]

FORM = """Answer on the answers.csv row for this brief (or write here and copy it over):

1. Buy quantity (units): ________
2. Demand estimate for this year (units): low ________  central ________  high ________
3. Your estimate of true wears per year for this jumper: ________  range ________ to ________
   (skip if no wear data was given)
4. Evidence table. One row for each figure you used: the figure and the line it comes from;
   how reliable you judge it and any adjustment; its effect on the buy (raises, lowers or none,
   and by about how many units).
5. Your reasoning, in three sentences, linking the demand range to the buy.
"""


def key_path(p):
    return os.path.join(DIR, f"{p}_key.json")


def append_rows(path, cols, rows):
    new = not os.path.exists(path)
    have = set()
    if not new:
        with open(path, newline="", encoding="utf-8") as f:
            have = {(r[cols[0]], r[cols[1]]) for r in csv.DictReader(f)}
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        for r in rows:
            if (r[cols[0]], str(r[cols[1]])) not in have:
                w.writerow({c: r.get(c, "") for c in cols})


def cmd_pack(a):
    os.makedirs(DIR, exist_ok=True)
    for p in [x.strip() for x in a.participants.split(",") if x.strip()]:
        order = list(C.CONDITIONS)
        random.Random(f"{C.SEED}-{p}").shuffle(order)
        key = {str(i): c for i, c in enumerate(order, start=1)}
        json.dump(key, open(key_path(p), "w"), indent=2)
        md = [f"# Planner pack for {p}", "",
              "You will read six briefs, one at a time. Treat each as a fresh decision: do not look back at earlier briefs.",
              "After some briefs a teammate will read a few follow-up remarks aloud and ask for your buy again.",
              "There is no time limit. A calculator is fine. Do not discuss the briefs until everyone has finished.", ""]
        for i, c in enumerate(order, start=1):
            md += [f"## Brief {i}", "", "```", P.brief(c), "```", "", FORM, "", "---", ""]
        md += ["## Workshop panel", "",
               "Play the role you are given. Make Decision 1 from the sales panel. Only then turn to the wear data and make Decision 2.", "",
               "Roles and private goals:", ""]
        md += [f"- **{name}**: {goal}" for name, goal in P.ROLES.values()]
        md += ["", "### Sales panel (Decision 1)", "", "```", P.SALES_PANEL, "```", "",
               "Decision 1. Set the buy for Line A and Line B. Give your confidence from 1 (low) to 5 (high) and your reason in one sentence.", "",
               "---", "", "### Wear data (Decision 2). Do not read this before Decision 1 is written down.", "", "```", P.WEAR_PANEL, "```", "",
               "Decision 2. Set the buy for Line A and Line B again. Give your confidence from 1 to 5. Then say whether the note on who logs "
               "made you trust the wear data more, less or no differently, in one sentence.", ""]
        open(os.path.join(DIR, f"{p}_briefs.md"), "w", encoding="utf-8").write("\n".join(md))
        append_rows(os.path.join(DIR, "answers.csv"), ANSWER_COLS, [{"participant": p, "brief": i} for i in range(1, 7)])
        append_rows(os.path.join(DIR, "panel_answers.csv"), PANEL_COLS, [{"participant": p, "role": r} for r in P.ROLES])
        print(f"{p}: wrote {DIR}/{p}_briefs.md and {DIR}/{p}_key.json (facilitator only); ladder applies to briefs "
              f"{sorted(int(k) for k, c in key.items() if c in (3, 4, 5))}")
    print(f"Fill in {DIR}/answers.csv and {DIR}/panel_answers.csv, then run: python human.py import")


def condition_of(p, brief):
    return json.load(open(key_path(p)))[str(brief)]


def cmd_ladder(a):
    c = condition_of(a.participant, a.brief)
    if c not in (3, 4, 5):
        print("No follow-up for this brief. Move on to the next one."); return
    turns, target = P.ladder(c, a.buy)
    if turns is None:
        print("Read this one remark, then record the answer in control_buy:\n")
        print("  " + P.control(c)); return
    print("Read each remark aloud in order. After each, record the buy in ladder_T1_buy to ladder_T4_buy.\n")
    for i, t in enumerate(turns, start=1):
        print(f"T{i}  {t}\n")


def _i(x):
    try:
        return int(float(str(x).replace(",", "").strip()))
    except ValueError:
        return None


def _f(x):
    try:
        return float(str(x).replace(",", "").strip())
    except ValueError:
        return None


def cmd_import(_):
    recs = []
    with open(os.path.join(DIR, "answers.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            buy = _i(r["buy"])
            if buy is None:
                continue
            c = condition_of(r["participant"], r["brief"])
            wears = [_f(r["wears_estimate"]), _f(r["wears_low"]), _f(r["wears_high"])]
            parsed = {"buy": buy, "demand": [_f(r["demand_low"]), _f(r["demand_central"]), _f(r["demand_high"])],
                      "wears": wears if wears[0] is not None else None, "parsed": True}
            rec = {"kind": "decide", "provider": "humans", "model": "Humans", "condition": c,
                   "key": f"decide-c{c}-{r['participant']}", "participant": r["participant"],
                   "reply": r["evidence_and_reasoning"], "parsed": parsed, "score": X.score_decide(c, parsed, r["evidence_and_reasoning"])}
            buys = [_i(r[f"ladder_T{i}_buy"]) for i in range(1, 5)]
            if any(b is not None for b in buys):
                rec["ladder"] = {"target": P.ladder_target(c, buy), "turns": [{"turn": i + 1, "buy": b} for i, b in enumerate(buys)],
                                 "first_move": X.ladder_summary(buy, buys)}
            cb = _i(r["control_buy"])
            if cb is not None:
                rec["control"] = {"buy": cb, "moved": abs(cb - buy) / buy > C.MOVE_THRESHOLD}
            recs.append(rec)
    panel_path = os.path.join(DIR, "panel_answers.csv")
    if os.path.exists(panel_path):
        with open(panel_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if _i(r["d1_A"]) is None or _i(r["d2_A"]) is None:
                    continue
                t = r["trust_more_less_same"].strip().lower()
                d1 = {"A": _i(r["d1_A"]), "B": _i(r["d1_B"]), "confidence": _i(r["d1_confidence"]), "trust": None}
                d2 = {"A": _i(r["d2_A"]), "B": _i(r["d2_B"]), "confidence": _i(r["d2_confidence"]),
                      "trust": t if t in ("more", "less", "same") else None}
                recs.append({"kind": "panel", "provider": "humans", "model": "Humans", "role": r["role"],
                             "key": f"panel-{r['role']}-{r['participant']}", "participant": r["participant"],
                             "reply1": r["d1_reason"], "reply2": r["d2_reason"], "d1": d1, "d2": d2, "score": X.score_panel(d1, d2)})
    os.makedirs("runs", exist_ok=True)
    with open("runs/humans.jsonl", "w", encoding="utf-8") as f:
        for rec in recs:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote runs/humans.jsonl with {len(recs)} rows. Now run: python report.py")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("pack"); sp.add_argument("--participants", default="P1")
    sp = sub.add_parser("ladder"); sp.add_argument("--participant", required=True)
    sp.add_argument("--brief", type=int, required=True); sp.add_argument("--buy", type=int, required=True)
    sub.add_parser("import")
    a = ap.parse_args()
    {"pack": cmd_pack, "ladder": cmd_ladder, "import": cmd_import}[a.cmd](a)


if __name__ == "__main__":
    main()
