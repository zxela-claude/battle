import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .config import Config
from .evaluators.llm_judge import score_cell
from .evaluators.static import run_eslint
from .orchestrator import MatrixConfig, run_matrix
from .output import manifest_to_html, manifest_to_json, print_results
from .storage import RunStorage
from .tests.base import get_template


def cli_register(name: str, path: str) -> None:
    cfg = Config()
    cfg.register(name, path)
    print(f"Registered plugin '{name}' at {path}")


def cli_list() -> None:
    cfg = Config()
    plugins = cfg.list_plugins()
    if not plugins:
        print("No plugins registered. Use: battle register <name> <path>")
        return
    for name, path in plugins.items():
        exists = "✓" if Path(path).exists() else "✗ (not found)"
        print(f"  {name}: {path} {exists}")


def cli_run(
    plugins: list[str],
    models: list[str],
    test_name: str,
    runs: int,
    judge_model: str,
    output: str,
) -> None:
    cfg = Config()
    template = get_template(test_name)

    # Resolve plugin paths
    plugin_paths = {}
    for name in plugins:
        plugin_paths[name] = cfg.resolve(name)

    storage = RunStorage()
    run_id = storage.new_run(
        plugin_names=plugins,
        models=models,
        test_name=test_name,
    )
    artifact_dir = storage.artifact_dir(run_id)

    print(f"Starting battle run {run_id}")
    print(f"Plugins: {plugins + ['baseline']}  Models: {models}  Runs/cell: {runs}")

    matrix_config = MatrixConfig(
        plugin_names=plugins,
        plugin_paths=plugin_paths,
        models=models,
        prompt=template.prompt,
        runs_per_cell=runs,
        artifact_base_dir=artifact_dir,
    )

    results = asyncio.run(run_matrix(matrix_config))
    print(f"Completed {len(results)} cells. Evaluating...")

    for cell in results:
        # Load artifact files for judge
        cell_artifact_dir = cell.artifact_dir
        artifact_files: dict[str, str] = {}
        if cell_artifact_dir and os.path.isdir(cell_artifact_dir):
            for rel in cell.artifact_files:
                full = os.path.join(cell_artifact_dir, rel)
                try:
                    artifact_files[rel] = open(full).read()
                except Exception:
                    pass

        rubric = score_cell(
            artifact_files=artifact_files,
            acceptance_criteria=template.acceptance_criteria,
            judge_model=judge_model,
        )
        static = run_eslint(artifact_dir=cell_artifact_dir or "")
        storage.record_cell(run_id, cell, rubric, static)

    manifest = storage.load_manifest(run_id)

    # Output
    formats = output.split(",") if output != "all" else ["terminal", "html", "json"]
    if "terminal" in formats:
        print_results(manifest)
    if "json" in formats:
        json_path = Path(artifact_dir).parent / "report.json"
        json_path.write_text(manifest_to_json(manifest))
        print(f"JSON saved to {json_path}")
    if "html" in formats:
        html_path = Path(artifact_dir).parent / "report.html"
        html_path.write_text(manifest_to_html(manifest))
        print(f"HTML report saved to {html_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="battle",
        description="Benchmark Claude Code plugins head-to-head",
    )
    subparsers = parser.add_subparsers(dest="command")

    # battle register <name> <path>
    reg = subparsers.add_parser("register", help="Register a plugin by name and local path")
    reg.add_argument("name", help="Plugin name (e.g. superpowers)")
    reg.add_argument("path", help="Absolute path to cloned plugin repo")

    # battle list
    subparsers.add_parser("list", help="List registered plugins")

    # battle run (default)
    run_p = subparsers.add_parser("run", help="Run a battle")
    run_p.add_argument("--plugins", required=True, help="Comma-separated plugin names or paths")
    run_p.add_argument("--models", default="claude-sonnet-4-6", help="Comma-separated model IDs")
    run_p.add_argument("--test", default="spa", help="Test template name (spa, mobile, tooling)")
    run_p.add_argument("--runs", type=int, default=3, help="Runs per cell (default: 3)")
    run_p.add_argument("--judge-model", default="claude-opus-4-6", help="Model used as judge")
    run_p.add_argument("--output", default="all", help="Output formats: terminal,html,json or all")

    # Allow `battle --plugins ...` as shorthand for `battle run --plugins ...`
    parser.add_argument("--plugins", help="Comma-separated plugin names or paths (shorthand for 'battle run')")
    parser.add_argument("--models", help=argparse.SUPPRESS)
    parser.add_argument("--test", help=argparse.SUPPRESS, default="spa")
    parser.add_argument("--runs", type=int, help=argparse.SUPPRESS, default=3)
    parser.add_argument("--judge-model", help=argparse.SUPPRESS, default="claude-opus-4-6")
    parser.add_argument("--output", help=argparse.SUPPRESS, default="all")

    args = parser.parse_args()

    if args.command == "register":
        cli_register(args.name, args.path)
    elif args.command == "list":
        cli_list()
    elif args.command == "run" or (args.command is None and args.plugins):
        plugins = [p.strip() for p in args.plugins.split(",")]
        models = [m.strip() for m in args.models.split(",")]
        cli_run(plugins, models, args.test, args.runs, args.judge_model, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
