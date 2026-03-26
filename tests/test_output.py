import json
from battle.storage import RunManifest
from battle.output.json_out import manifest_to_json
from battle.output.html import manifest_to_html


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
