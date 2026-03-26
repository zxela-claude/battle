# battle

Benchmark Claude Code plugins head-to-head. Run a matrix of `(plugin × model)` combinations on the same task, score each output with LLM-as-judge + static analysis, and get a terminal table, HTML report, and JSON.

## Why

Plugin selection for Claude Code feels subjective. `battle` makes it objective — same task, same model, same judge, different plugins. A no-plugin baseline is always included as a control.

## Install

```bash
pip install -e .
```

Requires Python 3.11+ and a Claude account. Uses your existing Claude Code OAuth session — no API key needed.

```bash
cp .env.example .env
# Fill in ANTHROPIC_AUTH_TOKEN (get it with: claude config get oauthToken)
source .env
```

## Quick start

```bash
# Register your plugins by pointing at their local repos
battle register superpowers /path/to/superpowers
battle register homerun /path/to/homerun

# Run a battle
battle run --plugins superpowers,homerun --models claude-sonnet-4-6 --test spa
```

This runs 3 cells: `baseline`, `superpowers`, and `homerun`, each on the `spa` test, 3 runs per cell (averaged). Results print to terminal, plus `report.html` and `report.json` in `~/.battle/runs/<run-id>/`.

## Commands

### `battle register <name> <path-or-repo>`

Register a plugin. Accepts either a local path or a `owner/repo` GitHub shorthand — battle will clone it automatically to `~/.battle/plugins/<name>/` and keep it up to date on subsequent registers.

```bash
# GitHub shorthand (auto-clone)
battle register superpowers obra/superpowers
battle register homerun zxela/claude-plugins

# Local path (pass-through)
battle register superpowers ~/repos/obra-superpowers
```

Entries are stored in `~/.battle/plugins.json`.

### `battle list`

List registered plugins and whether their paths exist on disk.

### `battle run`

Run a benchmark matrix.

| Flag | Default | Description |
|---|---|---|
| `--plugins` | required | Comma-separated plugin names or absolute paths |
| `--models` | `claude-sonnet-4-6` | Comma-separated model IDs |
| `--test` | `spa` | Task template: `spa`, `mobile`, `tooling` |
| `--runs` | `3` | Runs per cell (averaged for final scores) |
| `--judge-model` | `claude-opus-4-6` | Model used as judge |
| `--output` | `all` | Output formats: `terminal`, `html`, `json`, or `all` |

Shorthand — `--plugins` at the top level routes to `run`:

```bash
battle --plugins superpowers --models claude-sonnet-4-6,claude-opus-4-6
```

## Test templates

| Name | Description |
|---|---|
| `spa` | React + Vite + TypeScript SPA with routing, contact form, validation, API call |
| `mobile` | Expo React Native app with navigation and fetched post list |
| `tooling` | TypeScript `wordcount` CLI with stdin support and Jest tests |

## Scoring

Each cell is scored by Claude (LLM-as-judge) across 5 dimensions, each 0–10:

- **AC completeness** — does the output satisfy every acceptance criterion?
- **Code style** — idiomatic, consistent, readable?
- **Code quality** — architecture, separation of concerns, maintainability?
- **Security** — no obvious vulnerabilities?
- **Bugs** — does it actually work?

Static analysis (ESLint) runs on any generated JS/TS and reports error + warning counts.

Multiple runs per cell are averaged. The terminal table color-codes the overall score: green ≥ 8, yellow ≥ 6, red < 6.

## Artifacts

Every run is stored under `~/.battle/runs/<timestamp>-<hash>/`:

```
~/.battle/runs/1711234567-a1b2c3d4/
├── manifest.json       # scores, costs, metadata for every cell
├── report.html         # self-contained HTML report
├── report.json         # full manifest as JSON
└── artifacts/          # generated code from every cell
    ├── baseline-claude-sonnet-4-6-0/
    ├── superpowers-claude-sonnet-4-6-0/
    └── homerun-claude-sonnet-4-6-0/
```

## Architecture

```
battle/
├── src/battle/
│   ├── cli.py              # Entry point (argparse)
│   ├── config.py           # ~/.battle/plugins.json registry
│   ├── adapters/           # PluginAdapter ABC + baseline/superpowers/homerun
│   ├── runner.py           # run_cell() coroutine → CellResult
│   ├── orchestrator.py     # run_matrix() → asyncio.gather() over all cells
│   ├── tests/              # Task prompt templates (spa, mobile, tooling)
│   ├── evaluators/
│   │   ├── llm_judge.py    # Claude-as-judge → RubricScore
│   │   └── static.py       # ESLint runner → StaticResult
│   ├── storage.py          # RunStorage + RunManifest persistence
│   └── output/
│       ├── terminal.py     # Rich table
│       ├── html.py         # Self-contained HTML report
│       └── json_out.py     # JSON serialization
└── tests/                  # 47 tests
```

All cells run in parallel via `asyncio.gather()`. Each cell gets an isolated temp directory; artifacts are copied to permanent storage after the session completes.

## Development

```bash
pip install -e ".[dev]"
pytest -v
```
