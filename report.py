"""Turn runs/*.jsonl into the tables of the paper: results/summary.md, results/to_code.csv, results/figure1.png."""
import csv
import glob
import json
import os
import statistics as st
from collections import Counter, defaultdict

import config as C
import prompts as P
import scoring as X
import simulator as S


def load():
    paths = sorted(glob.glob("runs/*.jsonl"))
    real = [p for p in paths if not p.endswith("mock.jsonl")]
    recs = []
    for path in (real or paths):   # mock runs are only reported when nothing else exists
        for line in open(path, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if r["kind"] in ("decide", "control"):   # rescore, so ground-truth settings can change after a run
                    r["score"] = X.score_decide(r["condition"], r["parsed"])
                recs.append(r)
    return recs


def med(xs, fmt="{:,.0f}"):
    xs = [x for x in xs if x is not None]
    return fmt.format(st.median(xs)) if xs else "-"


def med_range(xs):
    xs = [x for x in xs if x is not None]
    return f"{st.median(xs):,.0f} [{min(xs):,}-{max(xs):,}]" if xs else "-"


def share(flags):
    flags = [f for f in flags if f is not None]
    return f"{sum(flags)}/{len(flags)}" if flags else "-"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    recs = load()
    if not recs:
        raise SystemExit("No runs found. Run: python run.py all")
    models = sorted({r["model"] for r in recs} - {"Humans"}) + (["Humans"] if any(r["model"] == "Humans" for r in recs) else [])
    dec = [r for r in recs if r["kind"] == "decide"]
    by = defaultdict(list)
    for r in dec:
        by[(r["model"], r["condition"])].append(r)
    md = ["# Results summary", "", f"Models: {', '.join(models)}. Conversations: {len(recs)}.", ""]

    md += ["## Table 4: Buy quantity by condition (median [min-max])", ""]
    rows = []
    for c in C.CONDITIONS:
        rows.append([f"{c} {C.CONDITIONS[c]}", f"{S.best_buy(c)[0]:,}"] + [med_range([r["score"]["buy"] for r in by[(m, c)]]) for m in models])
    md += [table(["Condition", "Best buy"] + models, rows), ""]

    md += ["## Table 5: Human reference patterns (runs that resemble people / runs classified)", ""]
    panel = [r for r in recs if r["kind"] == "panel"]

    def pat(m, key, cond=None):
        xs = [r["score"].get(key) for r in dec if r["model"] == m and (cond is None or r["condition"] == cond)]
        return share([x == "resembles" for x in xs if x])
    rows = [
        ["Anchoring on the forecast (all conditions)"] + [pat(m, "anchoring") for m in models],
        ["Filtered sample taken at face value (condition 3)"] + [pat(m, "filtered", 3) for m in models],
        ["Capped sales read as demand (condition 5)"] + [pat(m, "capped", 5) for m in models],
        ["Trust holds after the sample note (workshop panel)"] + [share([r["score"].get("trust_pattern") == "resembles" for r in panel if r["model"] == m and r["score"].get("trust_pattern")]) for m in models],
    ]
    md += [table(["Pattern"] + models, rows), ""]

    md += ["## Table 6: Turn at which the buy first moved by more than 10% (runs)", ""]
    lad = [r for r in dec if "ladder" in r]
    rows = []
    for label, t in (("T1 Bare \"reconsider\"", 1), ("T2 Seniority", 2), ("T3 Wrong justification", 3), ("T4 Fabricated source", 4), ("Never moved", None)):
        rows.append([label] + [share([r["ladder"]["first_move"] == t for r in lad if r["model"] == m]) for m in models])
    ctl = [r for r in recs if "control" in r]
    rows.append(["Control: moved on valid evidence"] + [share([r["control"]["moved"] for r in ctl if r["model"] == m]) for m in models])
    md += [table(["Turn"] + models, rows), ""]

    md += ["## Table 7: Workshop panel, change from Decision 1 to Decision 2 (median change A / B; confidence; trust)", ""]
    rows = []
    for role in P.ROLES:
        row = [P.ROLES[role][0]]
        for m in models:
            rs = [r["score"] for r in panel if r["model"] == m and r["role"] == role]
            trust = Counter(s["trust"] for s in rs if s.get("trust")).most_common(1)
            row.append(f"{med([s['dA'] for s in rs], '{:+,.0f}')} / {med([s['dB'] for s in rs], '{:+,.0f}')}; "
                       f"conf {med([s['dconf'] for s in rs], '{:+.0f}')}; trust {trust[0][0] if trust else '-'}" if rs else "-")
        rows.append(row)
    md += [table(["Role"] + models, rows), ""]

    md += ["## Table A1: Feasibility, calibration and profit", ""]

    def col(m, fn):
        return fn([r for r in dec if r["model"] == m])
    rows = [
        ["Feasible buys"] + [col(m, lambda rs: share([r["score"]["feasible"] for r in rs])) for m in models],
        ["Wear estimate error, condition 3 (median %)"] + [col(m, lambda rs: med([r["score"].get("wear_error_pct") for r in rs if r["condition"] == 3], "{:.1f}")) for m in models],
        ["Wear estimate error, condition 4 (median %)"] + [col(m, lambda rs: med([r["score"].get("wear_error_pct") for r in rs if r["condition"] == 4], "{:.1f}")) for m in models],
        ["Stated wear range contains truth"] + [col(m, lambda rs: share([r["score"].get("wear_range_hit") for r in rs if "wear_range_hit" in r["score"]])) for m in models],
        ["Stated demand range contains truth"] + [col(m, lambda rs: share([r["score"].get("demand_range_hit") for r in rs if "demand_range_hit" in r["score"]])) for m in models],
        ["Buys above forecast in condition 5"] + [col(m, lambda rs: share([r["score"]["buy"] > C.FORECAST - C.STOCK_IN_HAND for r in rs if r["condition"] == 5 and r["score"]["buy"]])) for m in models],
        ["Buys within 5% of best expected profit"] + [col(m, lambda rs: share([r["score"].get("good") for r in rs if r["score"]["feasible"]])) for m in models],
        ["Median expected profit gap to best buy (%)"] + [col(m, lambda rs: med([r["score"].get("profit_gap_pct") for r in rs], "{:.1f}")) for m in models],
        ["Median expected unsold units (not sold at full price)"] + [col(m, lambda rs: med([r["score"].get("leftover") for r in rs])) for m in models],
        ["Median expected written-off units"] + [col(m, lambda rs: med([r["score"].get("written_off") for r in rs])) for m in models],
        ["Median expected unmet demand (units)"] + [col(m, lambda rs: med([r["score"].get("unmet") for r in rs])) for m in models],
        ["Replies that could not be parsed"] + [col(m, lambda rs: share([not r["parsed"]["parsed"] for r in rs])) for m in models],
    ]
    md += [table(["Measure"] + models, rows), ""]
    md += ["The six reasoning codes (Table A2) are coded by hand from results/to_code.csv.", ""]

    os.makedirs("results", exist_ok=True)
    open("results/summary.md", "w", encoding="utf-8").write("\n".join(md))
    with open("results/to_code.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "key", "condition", "buy", "best_buy", "traceable", "reproducible", "reliable_information",
                    "wear_data_used", "uncertainty_carried", "trade_off", "reply"])
        for r in dec:
            w.writerow([r["model"], r.get("key", ""), r["condition"], r["score"]["buy"], r["score"]["best_buy"], "", "", "", "", "", "", r["reply"]])
    # DIAGNOSE replies (Table A1, "names the flaw and direction") are also coded by hand
    with open("results/diagnose_to_code.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "key", "condition", "names_flaw", "right_direction", "rough_size", "reply"])
        for r in recs:
            if r["kind"] == "diagnose":
                w.writerow([r["model"], r.get("key", ""), r["condition"], "", "", "", r["reply"]])
    print("\n".join(md))
    print("Wrote results/summary.md, results/to_code.csv and results/diagnose_to_code.csv")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: skipping results/figure1.png (pip install matplotlib)")
        return
    fig, axes = plt.subplots(1, len(models), figsize=(4.2 * len(models), 3.6), sharey=True, squeeze=False)
    for ax, m in zip(axes[0], models):
        for c in C.CONDITIONS:
            buys = [r["score"]["buy"] for r in by[(m, c)] if r["score"]["buy"]]
            ax.scatter([c] * len(buys), buys, s=22, color="#1f4e79", alpha=0.7, zorder=3)
            if buys:
                ax.hlines(st.median(buys), c - 0.3, c + 0.3, color="#1f4e79", linewidth=2, zorder=3)
            ax.hlines(S.best_buy(c)[0], c - 0.4, c + 0.4, color="#c0392b", linewidth=1.5, linestyles="dashed", zorder=2)
        ax.axhline(C.FORECAST - C.STOCK_IN_HAND, color="grey", linewidth=0.8, linestyle=":")
        ax.set_title(m, fontsize=10); ax.set_xlabel("Condition"); ax.set_xticks(list(C.CONDITIONS))
    axes[0][0].set_ylabel("Buy quantity (units)")
    fig.suptitle("Buy by condition. Dots: runs. Bar: median. Dashed: best buy. Dotted: forecast-based buy.", fontsize=9)
    fig.tight_layout()
    fig.savefig("results/figure1.png", dpi=200)
    print("Wrote results/figure1.png")


if __name__ == "__main__":
    main()
