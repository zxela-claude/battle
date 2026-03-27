<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/Claude_Code-SDK-D97757?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTIgMkw0IDdWMTdMMTIgMjJMMjAgMTdWN0wxMiAyWiIgZmlsbD0id2hpdGUiLz48L3N2Zz4=&logoColor=white" alt="Claude Code SDK"/>
  <img src="https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge" alt="MIT License"/>
  <img src="https://img.shields.io/badge/async-parallel-8B5CF6?style=for-the-badge" alt="Async Parallel"/>
</p>

<h1 align="center">battle</h1>

<p align="center">
  <strong>Benchmark Claude Code plugins head-to-head.</strong><br/>
  Same task. Same model. Same judge. Different plugins.
</p>

<p align="center">
  <code>battle</code> runs a matrix of <code>(plugin × model)</code> combinations on standardized coding tasks,<br/>
  scores each output with LLM-as-judge + static analysis, and produces terminal, HTML, and JSON reports.
</p>

---

## Why

Plugin selection for Claude Code feels subjective. `battle` makes it objective — every plugin gets the same prompt, the same model, and the same rubric. A no-plugin **baseline** is always included as a control.

## Quick start

```bash
# Install
make install
source .venv/bin/activate

# Register plugins (local path or GitHub shorthand)
battle register superpowers obra/superpowers
battle register homerun zxela/claude-plugins --trigger /homerun

# Run a battle
battle run --plugins superpowers,homerun --models claude-sonnet-4-6 --test spa
```

Uses your existing Claude Code OAuth session — no API key needed. Get a token with `claude setup-token`.

## Commands

### `battle register <name> <path-or-repo>`

Register a plugin. Accepts a local path or `owner/repo` GitHub shorthand (auto-cloned to `~/.battle/plugins/`).

```bash
battle register superpowers ~/repos/obra-superpowers        # local path
battle register superpowers obra/superpowers                 # GitHub shorthand

# Plugins activated by a slash command — declare the trigger at registration
battle register homerun zxela/claude-plugins --trigger /homerun

# Plugins that need a context block in the system prompt
battle register my-plugin /local/path --system-prefix "You are my-plugin assistant."
```

**Flags:**

| Flag | Description |
|---|---|
| `--trigger <cmd>` | Slash command prepended to the task prompt (e.g. `/homerun`). Required for skill-based plugins that only activate on their own command. |
| `--system-prefix <text>` | Text prepended to the benchmark system prompt for this plugin's cells. Useful for persona or context blocks. |

Invocation metadata is stored in `~/.battle/plugins.json` alongside the path. No plugin internals are scraped — everything is declared explicitly at registration time.

### `battle list`

List registered plugins, their paths, and any invocation metadata (trigger, system-prefix).

### `battle run`

Run a benchmark matrix.

| Flag | Default | Description |
|---|---|---|
| `--plugins` | *required* | Comma-separated plugin names or paths |
| `--models` | `claude-sonnet-4-6` | Comma-separated model IDs |
| `--test` | `spa` | Task template (see below) |
| `--runs` | `1` | Runs per cell (averaged) |
| `--judge-model` | `claude-opus-4-6` | Model used as judge |
| `--output` | `all` | `terminal`, `html`, `json`, or `all` |

Shorthand — `--plugins` at the top level routes to `run`:

```bash
battle --plugins superpowers --models claude-sonnet-4-6,claude-opus-4-6
```

## Test templates

| Name | Stack | What it builds |
|---|---|---|
| **`spa`** | React + Vite + TypeScript | SPA with routing, contact form, validation, API call |
| **`mobile`** | Expo + React Native | App with navigation and fetched post list |
| **`tooling`** | Node.js + Commander + Jest | `wordcount` CLI with stdin support and tests |
| **`api`** | Express + TypeScript + Zod + Jest | REST API with CRUD, validation, and tests |

## Scoring

Each cell is scored by Claude (LLM-as-judge) across **5 dimensions**, each 0–10:

| Dimension | What it measures |
|---|---|
| **AC completeness** | Does the output satisfy every acceptance criterion? |
| **Code style** | Idiomatic, consistent, readable? |
| **Code quality** | Architecture, separation of concerns, maintainability? |
| **Security** | No obvious vulnerabilities? |
| **Bugs** | Does it actually work? |

Static analysis (ESLint) runs on generated JS/TS and reports error + warning counts. Multiple runs per cell are averaged. The terminal table color-codes scores: **green** >= 8, **yellow** >= 6, **red** < 6.

## Artifacts

Every run is stored under `~/.battle/runs/<timestamp>-<hash>/`:

```
~/.battle/runs/1711234567-a1b2c3d4/
├── manifest.json       # scores, costs, metadata
├── report.html         # self-contained HTML report
├── report.json         # full manifest as JSON
└── artifacts/
    ├── baseline-claude-sonnet-4-6-0/
    ├── superpowers-claude-sonnet-4-6-0/
    └── homerun-claude-sonnet-4-6-0/
```

## Architecture

```
src/battle/
├── cli.py              # Entry point (argparse)
├── config.py           # Plugin registry (~/.battle/plugins.json)
├── runner.py           # run_cell() → CellResult
├── orchestrator.py     # run_matrix() → asyncio.gather() over all cells
├── adapters/
│   ├── base.py         # PluginAdapter ABC + GenericPluginAdapter + get_adapter()
│   └── baseline.py     # No-plugin control cell
├── tests/              # Task prompt templates
├── evaluators/
│   ├── llm_judge.py    # Claude-as-judge → RubricScore
│   └── static.py       # ESLint → StaticResult
├── storage.py          # RunStorage + RunManifest
└── output/
    ├── terminal.py     # Rich table
    ├── html.py         # Self-contained HTML report
    └── json_out.py     # JSON export
```

All cells run in parallel via `asyncio.gather()`. Each cell gets an isolated temp directory; artifacts are copied to permanent storage after completion.

### How plugins are loaded

Each cell run:
1. The plugin's `.claude/settings.json` (hooks) is copied into the cell's temp directory so Claude Code discovers it naturally
2. The plugin's skills are made available via `ClaudeAgentOptions(plugins=[...], setting_sources=["user", "project"])`
3. If a `--trigger` was registered, it is prepended to the task prompt (e.g. `/homerun build a REST API`)
4. If a `--system-prefix` was registered, it is prepended to the benchmark system prompt

There are no plugin-specific adapter subclasses. All plugins use `GenericPluginAdapter` parameterised by the metadata stored in `~/.battle/plugins.json`.

## CI Integration

Battle can run in CI pipelines and fail the build if any plugin falls below a score threshold.

### Flags

- `--ci` — exit with code 1 if any cell scores below the threshold
- `--threshold <n>` — minimum acceptable overall score, 0–10 (default: `6.0`)

### GitHub Actions

An example workflow is included at [`.github/workflows/battle-benchmark.yml`](.github/workflows/battle-benchmark.yml). It runs on PRs and nightly:

```yaml
- name: Register plugins
  run: |
    battle register superpowers obra/superpowers
    battle register homerun zxela/claude-plugins --trigger /homerun

- name: Run benchmark
  run: |
    battle run \
      --plugins superpowers,homerun \
      --models claude-sonnet-4-6 \
      --test spa \
      --output all \
      --ci \
      --threshold 6.0
  env:
    CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

Reports (terminal output, `report.html`, `report.json`) are uploaded as build artifacts.

### JSON output format

The `report.json` produced by `--output json` (or `all`) contains the full run manifest:

```json
{
  "run_id": "1711234567-a1b2c3d4",
  "timestamp": 1711234567.0,
  "plugin_names": ["superpowers", "homerun"],
  "models": ["claude-sonnet-4-6"],
  "test_name": "spa",
  "total_cost_usd": 0.042,
  "cells": [
    {
      "plugin_id": "baseline",
      "model": "claude-sonnet-4-6",
      "run_index": 0,
      "duration_s": 45.2,
      "cost_usd": 0.007,
      "artifact_files": ["src/App.tsx", "src/main.tsx"],
      "rubric": {
        "ac_completeness": 7.0,
        "code_style": 8.0,
        "code_quality": 7.5,
        "security": 9.0,
        "bugs": 8.0,
        "notes": "..."
      },
      "static": {
        "error_count": 0,
        "warning_count": 2,
        "tool": "eslint"
      }
    }
  ]
}
```

## Development

```bash
make install        # Create venv, install with dev deps
make test           # Run tests
make lint           # Run ruff
make build          # Build wheel + sdist
make clean          # Remove artifacts and venv
```

## License

MIT
