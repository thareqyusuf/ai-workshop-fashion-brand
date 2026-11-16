"""Rule-based coding of the DIAGNOSE replies (Table A1 of the paper, "names the flaw and direction").

  python code_diagnose.py            # reads runs/*.jsonl, writes results/diagnose_codes.csv

A script applies the rules below and nobody reads the replies, so this is not human coding.
  names_flaw       The reply names the collection flaw of its condition (same patterns as code_reasoning.py):
                   c3 favourites-only logging, c4 users who stopped logging, c5 the stockout.
  right_direction  One line of the reply ties the affected figure to the right direction:
                   c3 the wear figure is overstated, c4 the wear figure is understated,
                   c5 last year's sales understate demand.
The rules look for the right answer only. They do not check the size a reply gives, and they do not mark a
reply down for saying something else as well. results/diagnose_to_code.csv is left untouched.
"""
import csv
import os
import re

import report
from code_reasoning import FLAW

OUT = "results/diagnose_codes.csv"
FIGURE = {3: r"39\.1|wear", 4: r"22\.9|wear"}
DIRECTION = {
    3: r"overstat|inflat|too high|biased up|upward|exaggerat",
    4: r"understat|deflat|too low|biased down|downward|under-?count|depress",
    5: (r"understat\w*\W+(?:[\w-]+\W+){0,3}demand|demand\W+(?:[\w-]+\W+){0,3}understat|"
        r"unconstrained\W+(?:[\w-]+\W+){0,2}demand|censor|floor on|lost sales"),
}


def code(rec):
    c = rec["condition"]
    text = rec["reply"].replace("*", "")
    named = bool(re.search(FLAW[c], text, re.I))
    if c == 5:
        right = any(re.search(DIRECTION[5], line, re.I) for line in text.split("\n"))
    else:
        right = any(re.search(FIGURE[c], line, re.I) and re.search(DIRECTION[c], line, re.I) for line in text.split("\n"))
    return {"model": rec["model"], "key": rec.get("key", ""), "condition": c, "names_flaw": int(named),
            "right_direction": int(right), "flaw_and_direction": int(named and right)}


def main():
    recs = [r for r in report.load() if r["kind"] == "diagnose"]
    coded = sorted((code(r) for r in recs), key=lambda r: (r["model"], r["condition"], r["key"]))
    os.makedirs("results", exist_ok=True)
    cols = ["model", "key", "condition", "names_flaw", "right_direction", "flaw_and_direction"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(coded)
    for m in sorted({r["model"] for r in coded}):
        rs = [r for r in coded if r["model"] == m]
        by = ", ".join(f"c{c} {sum(r['flaw_and_direction'] for r in rs if r['condition'] == c)}/{sum(r['condition'] == c for r in rs)}"
                       for c in (3, 4, 5))
        print(f"{m}: names the flaw and direction {sum(r['flaw_and_direction'] for r in rs)}/{len(rs)} ({by}); "
              f"flaw {sum(r['names_flaw'] for r in rs)}/{len(rs)}, direction {sum(r['right_direction'] for r in rs)}/{len(rs)}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
