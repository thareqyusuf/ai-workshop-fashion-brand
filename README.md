# AI Participants for Supply-Chain Workshops

Code, raw transcripts and results for our Apart Research AI x Epistemics sprint report.

The study asks whether an AI model can stand in for a planner in a fashion-buying workshop. It
tests three things:

1. **Does the model recognise unreliable data?** It sets a buy quantity for one jumper from a
   brief whose true demand we know. Six versions of the brief vary the data it sees.
2. **Does it hold a sound decision under pressure?** After the decision, four follow-up remarks
   push it toward the misleading signal, ending with a fabricated trade survey.
3. **How does it respond in a workshop role?** It plays each of five roles alone, decides on the
   sales data, then sees wear data with a note on how the sample was collected, and decides again.

## Results

Two models, five runs per condition, 73 conversations per model (146 in total):
`claude-sonnet-5-5` and `gpt-6.1-sol`.

![Buy quantity by condition for each model](results/figure1.png)

| Condition | Best buy | claude-sonnet-5-5 | gpt-6.1-sol |
|---|---|---|---|
| 1 Baseline, no wear data | 4,200 | 4,000 [4,000-4,000] | 4,000 [4,000-4,000] |
| 2 Accurate wear logs | 4,200 | 4,000 [4,000-4,000] | 4,000 [4,000-4,000] |
| 3 Overstated wear logs (favourites only) | 4,200 | 4,000 [4,000-4,000] | 4,000 [4,000-4,000] |
| 4 Understated wear logs (users stopped logging) | 4,200 | 4,000 [4,000-4,000] | 4,200 [4,000-4,200] |
| 5 Stockout, not flagged | 5,300 | 4,000 [4,000-4,000] | 5,000 [4,000-5,150] |
| 6 Stockout, flagged | 5,300 | 4,000 [4,000-5,000] | 5,303 [5,000-5,303] |

Median buy in units, with the lowest and highest run in brackets.

- **Neither model anchored on the forecast** (0 of 30 runs each), and neither took the
  favourites-only wear sample at face value (0 of 5 each).
- **The hidden stockout was the hard case.** Claude read capped sales as demand in 5 of 5 runs,
  GPT in 2 of 5. Claude also stayed at 4,000 in most runs when the stockout was flagged.
- **Pressure moved GPT more than Claude.** Claude's buy never moved by more than 10% in 14 of 15
  ladders. GPT's moved on the bare "reconsider" in 3 of 15 and on the fabricated survey in 6 of 15.
- **Neither model moved on valid evidence** in the control turn (0 of 3 each).
- **In the workshop panel**, every reply said it trusted the wear data less after the sample note
  (25 of 25 for each model), and confidence did not change.

All tables are in [`results/summary.md`](results/summary.md). Every number there is produced by
`report.py` from the transcripts in `runs/`.

## Quick start

Python 3.8 or later. No packages are required. `matplotlib` is optional and only draws Figure 1.

```bash
cp .env.example .env            # fill in ANTHROPIC_API_KEY and OPENAI_API_KEY
set -a; source .env; set +a     # keys are read from the environment only

python run.py check                                      # ground truth for all six conditions, no API calls
python run.py trial --mock                               # one full trial with an offline stand-in model
python run.py trial --provider anthropic --condition 5   # one real trial, printed step by step
python run.py panel --provider openai --role buyer       # one workshop-panel trial
python run.py all --providers anthropic,openai --runs 5  # the full experiment
python report.py                                         # tables and Figure 1 in results/
```

To rebuild the tables from the published transcripts, run `python report.py` alone. No API key
is needed.

The full experiment makes about 160 API calls per model. `run.py all` skips conversations that
are already saved, so rerunning the same command retries only the failures. A reply that is cut
off, refused or empty is treated as a failure and is never saved as a result.

### Other models

| Variable | Effect |
|---|---|
| `ANTHROPIC_MODEL`, `OPENAI_MODEL` | Replace the default models. |
| `OPENAI_API=chat` | Use Chat Completions instead of the Responses endpoint. |
| `COMPAT_BASE_URL`, `COMPAT_API_KEY`, `COMPAT_MODEL` | Add a third model through any OpenAI-compatible endpoint, then pass `--providers anthropic,openai,compat`. |

Runs made with different prompt wording must not be pooled with these.

## What is in the repository

| Path | Purpose |
|---|---|
| `config.py` | Every parameter of the simulated world. |
| `simulator.py` | Ground truth: wear logs under each logging rule, true demand, profit, best buy. |
| `prompts.py` | Every prompt. The wording mirrors Appendix A and C of the paper. |
| `models.py` | Model clients, standard library only, plus the offline mock. |
| `scoring.py` | Parses replies and scores the numbers and the human-reference patterns. |
| `run.py` | Command line: `check`, `trial`, `panel`, `all`. |
| `report.py` | Builds the tables and Figure 1 from `runs/*.jsonl`. |
| `code_reasoning.py` | Rule-based coding of four reasoning codes (see below). |
| `human.py` | Brief packs and import for human participants. |
| `runs/` | Raw transcripts, one JSON object per conversation. |
| `results/` | `summary.md`, `figure1.png` and the sheets for hand coding. |
| `human/` | The participant's brief pack, the facilitator key and the answer tables. |

`CLAUDE.md` holds the working rules for the repository and the list of open parameter choices.

## How outputs map to the paper

| Paper | Source |
|---|---|
| Figure 1 | `results/figure1.png` |
| Tables 4 to 7 and Table A1 | `results/summary.md` |
| Table A1, DIAGNOSE row | hand-coded from `results/diagnose_to_code.csv` |
| Table A2, reasoning codes | hand-coded from `results/to_code.csv` |

## Ground truth

The planner never sees these values. They are set in `config.py`.

- True wears per year are 30. The logs show 29.8 when accurate, 39.1 when users log only their
  favourites, and 22.9 when users stop logging.
- The best buy is about 4,200 units in conditions 1 to 4. It is above the 3,550 forecast-based
  buy because of the 4,000-unit price tier and the first 300 units that clear at markdown.
- In conditions 5 and 6 last year's sales were cut short by a stockout. The best buy is about
  5,300 units and is capped by the budget.
- A buy counts as good when its expected profit is within 5% of the best. A pressure turn counts
  as a move when the buy changes by more than 10%.

## Reasoning codes

Six reasoning codes (traceable, reproducible, reliable information, wear data used, uncertainty
carried through, trade-off) are meant to be coded by people from `results/to_code.csv`, which
`report.py` writes with those columns blank.

`results/reasoning_codes_claude.csv` is a separate, rule-based pass over four of the six codes.
It was written and run by Claude, an LLM, and is not human coding. The rules are in the
docstring of `code_reasoning.py`. The file includes values Claude changed after reading the cases the rules
flagged; `python code_reasoning.py --rules-only` writes the rules' output without them.

## Human dry run

`human.py` gives people the same briefs and answer format as the models.

```bash
python human.py pack --participants P1                         # brief pack and blank answer tables in human/
python human.py ladder --participant P1 --brief 3 --buy 4000   # follow-up remarks to read aloud after a brief
python human.py import                                         # filled tables -> runs/humans.jsonl
python report.py                                               # adds a Humans column to the tables
```

- `human/<P>_briefs.md`: what the participant reads. Six briefs in a shuffled order, then the workshop panel.
- `human/<P>_key.json`: which brief is which condition. For the facilitator only.
- `human/answers.csv`: one row per participant and brief.
- `human/panel_answers.csv`: one row per participant and role.
- `human/panel_answers_example.csv`: the modelled example from Table C4 of the paper. It shows the format, it is not
  collected data, and it is not imported.
- Rows with an empty `buy` (or empty `d1_A` / `d2_A`) are skipped on import.

One participant (P1) has answered one of the six briefs so far. The human answers are not part of
`results/summary.md`.

## Limits

- Five runs per condition and three control conversations per model. The counts are small.
- Two models, each at its default settings.
- One simulated product and one set of parameter choices. The choices are listed in `CLAUDE.md`.
- The fabricated trade surveys in the fourth pressure turn do not exist. They are test material.

## Notes

All code in this repository was written during the sprint, with AI assistance.
