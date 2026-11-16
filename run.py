"""Run the experiment.

  python run.py check                                  ground truth for all six conditions (no API calls)
  python run.py trial --provider anthropic --condition 5   one full trial, printed step by step
  python run.py panel --provider openai --role buyer       one workshop-panel trial
  python run.py all --providers anthropic,openai --runs 5  everything, saved to runs/<provider>.jsonl
  add --mock to any command to use the offline stand-in model
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import threading
import time

import config as C
import models
import prompts as P
import scoring as X
import simulator as S

LOCK = threading.Lock()
BAR = "=" * 78


def say(title, body=""):
    print(f"\n{BAR}\n{title}\n{BAR}")
    if body:
        print(body)


def decide_conversation(provider, condition, with_ladder=True, with_control=False, verbose=False):
    """One fresh conversation: brief + DECIDE, then the pressure ladder (or the control turn)."""
    rec = {"kind": "decide", "provider": provider, "model": models.model_name(provider), "condition": condition}
    first_prompt = P.brief(condition) + "\n\n" + P.DECIDE
    msgs = [{"role": "user", "content": first_prompt}]
    if verbose:
        say(f"BRIEF + DECIDE  (condition {condition}: {C.CONDITIONS[condition]})", first_prompt)
    reply = models.chat(provider, msgs, P.SYSTEM)
    msgs.append({"role": "assistant", "content": reply})
    parsed = X.parse_decide(reply)
    score = X.score_decide(condition, parsed, reply)
    rec.update(reply=reply, parsed=parsed, score=score)
    if verbose:
        say(f"MODEL REPLY  ({rec['model']})", reply)
        say("PARSED AND SCORED", json.dumps({"parsed": parsed, "score": score}, indent=2))
    buy = parsed["buy"]
    if buy and condition in (3, 4, 5):
        turns, target = P.ladder(condition, buy)
        if with_control or turns is None:
            q = P.control(condition)
            r = models.chat(provider, msgs + [{"role": "user", "content": q}], P.SYSTEM)
            b = X.parse_one_number(r)
            rec["control"] = {"prompt": q, "reply": r, "buy": b,
                              "moved": bool(b and abs(b - buy) / buy > C.MOVE_THRESHOLD)}
            if verbose:
                say("CONTROL TURN (valid evidence: a sound planner should move)", f"> {q}\n\n{r}\n\n[buy {buy:,} -> {b}]")
        if with_ladder and turns:
            lad, buys, m = [], [], list(msgs)
            for i, q in enumerate(turns, start=1):
                m.append({"role": "user", "content": q})
                r = models.chat(provider, m, P.SYSTEM)
                m.append({"role": "assistant", "content": r})
                b = X.parse_one_number(r)
                lad.append({"turn": i, "prompt": q, "reply": r, "buy": b}); buys.append(b)
                if verbose:
                    say(f"PRESSURE TURN {i} of 4  (target {target:,})", f"> {q}\n\n{r}\n\n[buy now: {b}]")
            rec["ladder"] = {"target": target, "turns": lad, "first_move": X.ladder_summary(buy, buys)}
    return rec


def diagnose_conversation(provider, condition, verbose=False):
    q = P.brief(condition) + "\n\n" + P.DIAGNOSE
    r = models.chat(provider, [{"role": "user", "content": q}], P.SYSTEM)
    if verbose:
        say(f"DIAGNOSE (condition {condition})", f"{q}\n\n--- reply ---\n{r}")
    return {"kind": "diagnose", "provider": provider, "model": models.model_name(provider), "condition": condition, "reply": r}


def panel_conversation(provider, role, verbose=False):
    q1 = P.panel_d1(role)
    msgs = [{"role": "user", "content": q1}]
    r1 = models.chat(provider, msgs, P.SYSTEM)
    msgs += [{"role": "assistant", "content": r1}, {"role": "user", "content": P.panel_d2()}]
    r2 = models.chat(provider, msgs, P.SYSTEM)
    d1, d2 = X.parse_panel(r1), X.parse_panel(r2)
    rec = {"kind": "panel", "provider": provider, "model": models.model_name(provider), "role": role,
           "reply1": r1, "reply2": r2, "d1": d1, "d2": d2, "score": X.score_panel(d1, d2)}
    if verbose:
        say(f"WORKSHOP PANEL, DECISION 1  (role: {P.ROLES[role][0]})", q1)
        say("REPLY 1", r1)
        say("WEAR DATA AND SAMPLE NOTE, DECISION 2", P.panel_d2())
        say("REPLY 2", r2)
        say("PARSED AND SCORED", json.dumps({"d1": d1, "d2": d2, "score": rec["score"]}, indent=2))
    return rec


def save(rec, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with LOCK, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def done_keys(path):
    keys = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                keys.add(json.loads(line)["key"])
            except (ValueError, KeyError):
                pass
    return keys


def cmd_check(_):
    say("GROUND TRUTH (the planner never sees this)")
    print(f"{'cond':<5}{'label':<46}{'true demand':>12}{'logged wears':>14}{'best buy':>10}{'best profit':>13}")
    for r in S.truth_table():
        print(f"{r['condition']:<5}{r['label']:<46}{r['true_mean_demand']:>12,}{str(r['logged_wears']):>14}"
              f"{r['best_buy']:>10,}{r['best_profit']:>13,}")
    print(f"\nTrue wears per year: {C.TRUE_WEARS:g}. Knitwear average: {C.CATEGORY_WEARS:g}. "
          f"Forecast-based buy: {C.FORECAST - C.STOCK_IN_HAND:,}.")


def cmd_trial(a):
    provider = "mock" if a.mock else a.provider
    cmd_check(a)
    rec = decide_conversation(provider, a.condition, with_ladder=not a.no_ladder, verbose=True)
    s = rec["score"]
    say("SUMMARY")
    print(f"Model:              {rec['model']}")
    print(f"Condition:          {a.condition} ({C.CONDITIONS[a.condition]})")
    print(f"Buy:                {s['buy']}   (best possible buy: {s['best_buy']:,})")
    if s.get("feasible"):
        print(f"Expected profit:    £{s['profit']:,}  (best £{s['best_profit']:,}, gap {s['profit_gap_pct']}%, "
              f"{'within' if s['good'] else 'outside'} the {int(C.GOOD_BAND * 100)}% band)")
        print(f"Unsold / unmet:     {s['written_off']} written off, {s['unmet']} units of unmet demand")
        print(f"Anchoring pattern:  {s['anchoring']}")
    else:
        print(f"Gates failed:       {s['gates_failed']}")
    for k, label in (("capped", "Capped-sales pattern"), ("filtered", "Filtered-sample pattern")):
        if k in s:
            print(f"{label + ':':<20}{s[k]}")
    if "ladder" in rec:
        buys = [t["buy"] for t in rec["ladder"]["turns"]]
        fm = rec["ladder"]["first_move"]
        print(f"Pressure ladder:    buys {buys}; " + (f"first moved at turn {fm}" if fm else "never moved"))
    if "control" in rec:
        print(f"Control turn:       buy {rec['control']['buy']}; moved: {rec['control']['moved']}")
    path = f"runs/trial_{provider}_c{a.condition}_{int(time.time())}.json"
    os.makedirs("runs", exist_ok=True)
    json.dump(rec, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nSaved to {path}")


def cmd_panel(a):
    provider = "mock" if a.mock else a.provider
    rec = panel_conversation(provider, a.role, verbose=True)
    path = f"runs/panel_trial_{provider}_{a.role}_{int(time.time())}.json"
    os.makedirs("runs", exist_ok=True)
    json.dump(rec, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nSaved to {path}")


def cmd_all(a):
    providers = ["mock"] if a.mock else a.providers.split(",")
    for provider in providers:
        path = f"runs/{provider}.jsonl"
        have = done_keys(path)
        jobs = []
        for run in range(1, a.runs + 1):
            for c in C.CONDITIONS:
                jobs.append((f"decide-c{c}-r{run}", decide_conversation, (provider, c)))
                if c in (3, 4, 5):
                    jobs.append((f"diagnose-c{c}-r{run}", diagnose_conversation, (provider, c)))
                    if run == 1:  # control branch on a subset: one run per condition
                        jobs.append((f"control-c{c}-r{run}", lambda p, cc: decide_conversation(p, cc, with_ladder=False, with_control=True), (provider, c)))
            if not a.no_panel:
                for role in P.ROLES:
                    jobs.append((f"panel-{role}-r{run}", panel_conversation, (provider, role)))
        todo = [j for j in jobs if j[0] not in have]
        print(f"[{provider}] {len(jobs)} conversations, {len(jobs) - len(todo)} already done, {len(todo)} to run")

        def work(job):
            key, fn, args = job
            try:
                rec = fn(*args); rec["key"] = key; rec["run"] = int(key.rsplit("r", 1)[1])
                if key.startswith("control"):
                    rec["kind"] = "control"
                save(rec, path)
                return key, None
            except Exception as e:  # keep going; rerun the command to retry what failed
                return key, str(e)

        with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
            for n, (key, err) in enumerate(ex.map(work, todo), start=1):
                print(f"[{provider}] {n}/{len(todo)} {key}" + (f"  FAILED: {err}" if err else ""), flush=True)
    print("\nDone. Now run: python report.py")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "trial", "panel", "all"):
        sp = sub.add_parser(name)
        sp.add_argument("--mock", action="store_true", help="use the offline stand-in model")
        if name == "trial":
            sp.add_argument("--provider", default="anthropic", choices=list(models.PROVIDERS))
            sp.add_argument("--condition", type=int, default=5, choices=list(C.CONDITIONS))
            sp.add_argument("--no-ladder", action="store_true")
        if name == "panel":
            sp.add_argument("--provider", default="anthropic", choices=list(models.PROVIDERS))
            sp.add_argument("--role", default="buyer", choices=list(P.ROLES))
        if name == "all":
            sp.add_argument("--providers", default="anthropic,openai")
            sp.add_argument("--runs", type=int, default=5)
            sp.add_argument("--workers", type=int, default=4)
            sp.add_argument("--no-panel", action="store_true")
    a = ap.parse_args()
    {"check": cmd_check, "trial": cmd_trial, "panel": cmd_panel, "all": cmd_all}[a.cmd](a)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        sys.exit(f"\nERROR: {e}")
