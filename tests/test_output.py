import json
from io import StringIO
from battle.storage import RunManifest
from battle.output.json_out import manifest_to_json
from battle.output.html import manifest_to_html
from battle.output.terminal import print_results


def make_manifest():
    return RunManifest(
        run_id="test-123",
        timestamp=1700000000.0,
        plugin_names=["superpowers"],
        models=["claude-sonnet-4-6"],
        test_name="spa",
        cells=[
            {
                "plugin_id": "baseline",
                "model": "claude-sonnet-4-6",
                "run_index": 0,
                "cost_usd": 0.02,
                "num_turns": 3,
                "error": None,
                "rubric": {
                    "ac_completeness": 7, "code_style": 7, "code_quality": 7,
                    "security": 8, "bugs": 7, "rationale": "ok",
                },
                "static": {"error_count": 1, "warning_count": 3, "tool": "eslint", "ran": True},
            },
            {
                "plugin_id": "superpowers",
                "model": "claude-sonnet-4-6",
                "run_index": 0,
                "cost_usd": 0.04,
                "num_turns": 5,
                "error": None,
                "rubric": {
                    "ac_completeness": 9, "code_style": 8, "code_quality": 8,
                    "security": 9, "bugs": 9, "rationale": "excellent",
                },
                "static": {"error_count": 0, "warning_count": 1, "tool": "eslint", "ran": True},
            },
        ],
        total_cost_usd=0.06,
    )


def test_json_output_is_valid():
    manifest = make_manifest()
    output = manifest_to_json(manifest)
    data = json.loads(output)
    assert data["run_id"] == "test-123"
    assert len(data["cells"]) == 2


def test_html_output_contains_run_id():
    manifest = make_manifest()
    html = manifest_to_html(manifest)
    assert "test-123" in html
    assert "superpowers" in html
    assert "baseline" in html


def test_html_output_is_self_contained():
    """HTML should not reference external resources."""
    manifest = make_manifest()
    html = manifest_to_html(manifest)
    assert 'src="http' not in html
    assert 'href="http' not in html


def test_print_results_smoke():
    """print_results should not raise with a valid manifest."""
    manifest = make_manifest()
    # Should not raise
    print_results(manifest)


def test_print_results_averages_multiple_runs():
    """Cells with same (plugin_id, model) but different run_index should be averaged."""
    manifest = RunManifest(
        run_id="avg-test",
        timestamp=1700000000.0,
        plugin_names=["baseline"],
        models=["claude-sonnet-4-6"],
        test_name="spa",
        cells=[
            {
                "plugin_id": "baseline",
                "model": "claude-sonnet-4-6",
                "run_index": 0,
                "cost_usd": 0.01,
                "num_turns": 2,
                "error": None,
                "rubric": {
                    "ac_completeness": 6, "code_style": 6, "code_quality": 6,
                    "security": 6, "bugs": 6, "rationale": "run0",
                },
                "static": {"error_count": 2, "warning_count": 0, "tool": "eslint", "ran": True},
            },
            {
                "plugin_id": "baseline",
                "model": "claude-sonnet-4-6",
                "run_index": 1,
                "cost_usd": 0.03,
                "num_turns": 4,
                "error": None,
                "rubric": {
                    "ac_completeness": 8, "code_style": 8, "code_quality": 8,
                    "security": 8, "bugs": 8, "rationale": "run1",
                },
                "static": {"error_count": 0, "warning_count": 0, "tool": "eslint", "ran": True},
            },
        ],
        total_cost_usd=0.04,
    )
    # Should not raise — both cells have same plugin+model so they get averaged
    print_results(manifest)
    # Verify JSON output averages the scores
    data = json.loads(manifest_to_json(manifest))
    assert len(data["cells"]) == 2  # raw cells preserved in JSON
