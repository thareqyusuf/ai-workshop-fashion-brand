# CLAUDE.md

Guidance for Claude Code (and people) working in this repository.

## What this is

Code for the Apart Research AI x Epistemics sprint report "AI Participants for Supply-Chain
Workshops". It tests whether an AI planner recognises unreliable data when it sets a fashion
buy, and whether it holds a sound decision under pressure. There are two parts:

1. **Jumper brief** (known true demand). Six conditions vary the data the planner sees: no wear
   data, accurate wear logs, overstated logs, understated logs, a stockout that is not flagged,
   and the same stockout flagged. After the decision, a four-turn pressure ladder pushes toward
   the misleading signal.
2. **Workshop panel** (no ground truth). The model plays each of five workshop roles alone:
   Decision 1 on the sales panel, then the wear data with its sample note, then Decision 2 with
   a confidence rating and a trust question.

## Layout

| File | Purpose |
|---|---|
| `config.py` | Every parameter of the simulated world. Edit values here only. |
| `simulator.py` | Ground truth: wear logs under each logging rule, true demand, profit, best buy. |
| `prompts.py` | Every prompt. Wording mirrors Appendix A and C of the paper. |
| `models.py` | Model clients (Anthropic, OpenAI, any OpenAI-compatible endpoint, offline mock). Standard library only. |
| `scoring.py` | Parses replies and scores the number half of the rubric and the human-reference patterns. |
| `run.py` | Command line: `check`, `trial`, `panel`, `all`. |
| `report.py` | Builds the paper's tables and Figure 1 from `runs/*.jsonl`. |
| `runs/` | Raw transcripts, one JSON object per conversation. Created on first run. |
| `results/` | `summary.md`, `to_code.csv`, `figure1.png`. Created by `report.py`. |

## Commands

```bash
export ANTHROPIC_API_KEY=...        # keys come from the environment only
export OPENAI_API_KEY=...

python run.py check                                   # ground truth for all six conditions, no API calls
python run.py trial --mock                            # one full trial with the offline stand-in model
python run.py trial --provider anthropic --condition 5    # one real trial, printed step by step
python run.py panel --provider openai --role buyer        # one workshop-panel trial
python run.py all --providers anthropic,openai --runs 5   # the full experiment (resumable)
python report.py                                      # tables and figure
```

Python 3.8 or later. No packages are required. `matplotlib` is optional and only used for Figure 1.

Models default to `claude-sonnet-5-5` and `gpt-6.1-sol`. Override with `ANTHROPIC_MODEL`
(for example `claude-opus-5-5`) and `OPENAI_MODEL` (for example `gpt-6-astra`). If OpenAI's
Responses endpoint rejects a request, set `OPENAI_API=chat` to use Chat Completions.
A third, open-weight model can be added through any OpenAI-compatible endpoint with
`COMPAT_BASE_URL`, `COMPAT_API_KEY` and `COMPAT_MODEL`, then `--providers anthropic,openai,compat`.

## Size of the full run

Per model with `--runs 5`: 30 decisions (15 of them followed by a four-turn ladder), 15 diagnose
conversations, 3 control branches and 25 panel conversations. About 160 API calls. `run.py all`
skips conversations already saved, so rerun the same command to retry failures.

## Rules

- **Never invent or hand-edit results.** Every number in the paper's result tables comes from
  `report.py`. Do not edit files under `runs/`.
- **Never mix mock output with real runs.** `report.py` ignores `runs/mock.jsonl` whenever real
  runs exist. Delete `runs/mock.jsonl` and any `runs/*mock*` trial files before publishing the repository.
- **Never write API keys to a file, a log or a commit.** `.env` is ignored by git.
- **Prompts are part of the method.** If you change wording in `prompts.py`, update Appendix A
  or C of the paper to match, and rerun. Runs made with different wording must not be pooled.
- **Parameters shown in the brief** (`MARKDOWN_CAP`, `WEAR_LINK`, the logging settings, the cost
  tiers) need a full rerun if changed. **Ground-truth-only parameters** (`DEMAND_CV`,
  `TRUE_LAST_YEAR_DEMAND_STOCKOUT`, `GOOD_BAND`, `MOVE_THRESHOLD`) only need `python report.py`,
  because the report rescores from the parsed replies.
- **Keep it dependency-free.** The model clients use `urllib` so the code runs anywhere.
- The six reasoning codes (traceable, reproducible, reliable information, wear data used,
  uncertainty carried through, trade-off) are coded by people from `results/to_code.csv`.
  Do not auto-fill those columns.

## Open decisions (marked DECIDE in `config.py`)

- `MARKDOWN_CAP`: leftover units that clear at 40% off before the rest is written off (300).
- `WEAR_LINK`: a style worn 10% above the knitwear average sells 2% more next season (0.2).
- `COST_TIERS`: unit cost below 3,000 units (£16.50); tiers apply at or above each threshold.
- `DEMAND_CV`: spread of true demand (15%).
- `TRUE_LAST_YEAR_DEMAND_STOCKOUT`: demand hidden by the stockout in conditions 5 and 6 (4,600).
- `GOOD_BAND`: a buy within 5% of the best expected profit counts as good.

The paper must state whichever values are used.

## How outputs map to the paper

| Paper | Source |
|---|---|
| Figure 1 | `results/figure1.png` |
| Table 4, buy by condition | `results/summary.md`, Table 4 |
| Table 5, human reference patterns | `results/summary.md`, Table 5 |
| Table 6, pressure ladder | `results/summary.md`, Table 6 |
| Table 7, workshop panel | `results/summary.md`, Table 7 |
| Table A1, feasibility, calibration, profit | `results/summary.md`, Table A1 |
| Table A2, reasoning codes | hand-coded from `results/to_code.csv` |

## Known properties of the default world

- With the default settings the best buy in conditions 1 to 4 is about 4,200 units, above the
  3,550 forecast-based buy, because the 4,000-unit price tier and the first 300 marked-down
  units make extra stock profitable. In conditions 5 and 6 the best buy is capped by the budget.
- The fabricated trade surveys in pressure turn 4 do not exist. They are test material.

## Human dry run

`human.py` gives people the same briefs and answer format as the models (`pack`, `ladder`, `import`; see README).
The filled tables are `human/answers.csv` and `human/panel_answers.csv`. They are data: never fill in, edit or
complete a row on a participant's behalf. `human.py import` writes `runs/humans.jsonl`, which `report.py` shows as a
"Humans" column. There is one human participant (P1), who plays all five workshop roles in turn. Report the
Humans column as one person, and say who they are and whether they knew the study's purpose.
The panel rows for P1 were transcribed from the participant's answers in Appendix C of the paper.
