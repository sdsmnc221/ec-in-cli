# Civique CLI

Terminal exam simulator for the French civics test (naturalization / CSP residency permit).

40 questions, 45-minute countdown, dynamic difficulty tracking across sessions.

https://github.com/user-attachments/assets/fb7956e7-f4cd-443b-902c-bc39430f4056

---

## Requirements

```bash
pip install rich
```

Python 3.10+. No database required. Sync with Convex is optional — `httpx` and `python-dotenv` are only needed if you enable it.

---

## Quick start

```bash
cd ec-in-cli/

# Demo mode — uses the bundled sample dataset
python -m civ --sample

# Full dataset (see Dataset section below)
python -m civ
```

---

## CLI options

| Flag                    | Default                         | Description                                                                |
| ----------------------- | ------------------------------- | -------------------------------------------------------------------------- |
| `--sample`              | off                             | Use `dataset_sample.json` (40 QA-ed questions, simulates a real exam draw) |
| `--dataset FILE` / `-d` | `unified_dataset_complete.json` | Path to a custom dataset                                                   |
| `--mode MODE` / `-m`    | interactive                     | Skip mode selection: `super-hard` or `marathon`                            |
| `--tutorial`            | off                             | Force-show the tutorial even if already seen                               |

```bash
python -m civ --sample
python -m civ --dataset ../unified_dataset_yours.json
python -m civ --mode marathon
python -m civ --sample --tutorial
```

---

## Exam modes

**super-hard** — 40 questions, 45 minutes, 80% threshold (32/40 to pass).  
**marathon** — multiple 40-question blocks back-to-back (you pick the number of blocks).

Both modes let you filter by theme before starting.

---

## Keyboard controls

| Key                  | Action                                                 |
| -------------------- | ------------------------------------------------------ |
| `↑` / `↓` or `1`–`4` | Navigate / select answer                               |
| `←` / `→`            | Previous / next question                               |
| `M`                  | Flag question for review (FLAGGED)                     |
| `Tab`                | Mark answer as low-confidence                          |
| `Enter`              | Confirm selection                                      |
| `S`                  | Submit exam (opens review loop for flagged/unanswered) |
| `Q`                  | Quit                                                   |

At submission, you can navigate flagged and unanswered questions with `←` / `→` before finalising.

---

## Dataset

### Using the full dataset

`unified_dataset_complete.json` is the default dataset and is expected inside `ec-in-cli/`. If it's missing, copy or symlink it from the project root:

```bash
ln -s ../unified_dataset_yours.json unified_dataset_complete.json
python -m civ
```

If the default dataset file is missing, the app exits with a red error and points you to `--sample`.

### Bringing your own dataset

Any JSON file that follows the schema below will work. Pass it with `--dataset`:

```json
[
  {
    "id": "conn-0001",
    "source": "connaissances",
    "theme": "Principes et valeurs de la République",
    "type": "connaissance",
    "question": "Quelle est la devise de la République française ?",
    "answers": [
      "Liberté, Égalité, Fraternité",
      "Travail, Famille, Patrie",
      "Liberté, Égalité, Solidarité",
      "Unité, Fraternité, Progrès"
    ],
    "correct_index": 0,
    "explication": "La devise officielle est gravée sur les frontons des bâtiments publics depuis la Révolution.",
    "options_generees_ia": false,
    "needs_manual_review": false,
    "qa_flag_type": null
  }
]
```

**Rules:**

- `correct_index` must be `0` — the app shuffles answers at display time.
- Each question needs exactly 4 entries in `answers`. Incomplete questions are silently skipped.
- `theme` must be one of the 5 official themes (see below) or it will be excluded from theme filtering.

### 5 official themes

1. Principes et valeurs de la République
2. Système institutionnel et politique
3. Droits et devoirs
4. Histoire, géographie et culture
5. Vivre dans la société française

---

## Difficulty tracking

After each session, per-question stats are persisted in `civ_stats.json` (created automatically):

```
score = error_rate×0.5 + speed_norm×0.3 + views×0.2
< 0.3 → standard   0.3–0.6 → hard   > 0.6 → piège
```

The startup screen shows your difficulty distribution and the last 3 sessions.

---

## Project structure

```
ec-in-cli/
├── civ/
│   ├── __main__.py     # entry point
│   ├── cli.py          # argument parsing
│   ├── loader.py       # JSON loading + validation
│   ├── menus.py        # theme / mode selection
│   ├── engine.py       # exam loop, timer, navigation
│   ├── models.py       # Question, AnswerSlot, ExamState
│   ├── ui.py           # Rich console, TRICOLOR theme, getch
│   ├── results.py      # scoring, session persistence, results screen
│   ├── stats.py        # difficulty scoring
│   └── tutorial.py     # first-launch tutorial
├── dataset_sample.json # 40 QA-ed questions (28 conn. + 12 mise-sit.) — one real exam draw
└── README.md
```
