# AI Participants for Supply-Chain Workshops

Code for our Apart Research AI x Epistemics sprint report. It tests whether an AI planner
recognises unreliable data in a fashion-buying task with known true demand, whether it holds
its decision under pressure, and how it responds in each role of a design workshop panel.

## Quick start

```bash
export ANTHROPIC_API_KEY=...   # or copy .env.example to .env, fill it in, then: set -a; source .env; set +a
export OPENAI_API_KEY=...

python run.py check                                      # ground truth, no API calls
python run.py trial --provider anthropic --condition 5   # one trial, printed step by step
python run.py all --providers anthropic,openai --runs 5  # full experiment
python report.py                                         # tables and Figure 1 in results/
```

Python 3.8+, no packages required (`matplotlib` is optional, for the figure). `--mock` runs any
command with an offline stand-in model. See `CLAUDE.md` for the layout, rules and open decisions.

All code in this repository was written during the sprint, with AI assistance.

## Human dry run

The same briefs and answer format as the models, filled in by people.

```
python human.py pack --participants P1                         # brief packs + blank answer tables in human/
python human.py ladder --participant P1 --brief 3 --buy 4000   # follow-up remarks to read aloud after a brief
python human.py import                                         # filled tables -> runs/humans.jsonl
python report.py                                               # adds a Humans column to Tables 4, 5, 6, 7
```

- `human/<P>_briefs.md`: what the participant reads. Six briefs in a shuffled order, then the workshop panel.
- `human/<P>_key.json`: which brief is which condition. Facilitator only.
- `human/answers.csv`: one row per participant and brief. `human/panel_answers.csv`: one row per participant and role.
- Rows with an empty `buy` (or empty `d1_A` / `d2_A`) are skipped on import.
