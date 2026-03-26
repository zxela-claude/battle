from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich import box
from battle.storage import RunManifest


def _overall(cell: dict) -> float:
    r = cell["rubric"]
    return (r["ac_completeness"] + r["code_style"] + r["code_quality"]
            + r["security"] + r["bugs"]) / 5


def print_results(manifest: RunManifest) -> None:
    console = Console()

    # Aggregate cells by (plugin_id, model) — average across run_index
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for cell in manifest.cells:
        grouped[(cell["plugin_id"], cell["model"])].append(cell)

    table = Table(
        title=f"Battle Results — {manifest.test_name} | Run {manifest.run_id}",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Plugin", style="bold cyan")
    table.add_column("Model", style="dim")
    table.add_column("Overall", justify="center")
    table.add_column("AC", justify="center")
    table.add_column("Style", justify="center")
    table.add_column("Quality", justify="center")
    table.add_column("Security", justify="center")
    table.add_column("Bugs", justify="center")
    table.add_column("ESLint Errs", justify="center")
    table.add_column("Cost $", justify="right")

    for (plugin_id, model), cells in sorted(grouped.items()):
        def avg(fn):
            return sum(fn(c) for c in cells) / len(cells)

        overall = avg(_overall)
        color = "green" if overall >= 8 else "yellow" if overall >= 6 else "red"

        table.add_row(
            plugin_id,
            model,
            f"[{color}]{overall:.1f}[/{color}]",
            f"{avg(lambda c: c['rubric']['ac_completeness']):.1f}",
            f"{avg(lambda c: c['rubric']['code_style']):.1f}",
            f"{avg(lambda c: c['rubric']['code_quality']):.1f}",
            f"{avg(lambda c: c['rubric']['security']):.1f}",
            f"{avg(lambda c: c['rubric']['bugs']):.1f}",
            str(int(avg(lambda c: c['static']['error_count']))),
            f"${avg(lambda c: c['cost_usd']):.3f}",
        )

    console.print(table)
    console.print(f"\nTotal cost: [bold]${manifest.total_cost_usd:.3f}[/bold]")
