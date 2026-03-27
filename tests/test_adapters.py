import json
import pytest
from battle.adapters.base import GenericPluginAdapter, get_adapter, install_plugin_settings
from battle.adapters.baseline import BaselineAdapter


# --- BaselineAdapter ---

def test_baseline_adapter_id():
    assert BaselineAdapter().plugin_id == "baseline"


def test_baseline_options_has_no_plugins():
    opts = BaselineAdapter().get_options(model="claude-sonnet-4-6", cwd="/tmp")
    assert not getattr(opts, "plugins", None)


def test_baseline_options_uses_model():
    opts = BaselineAdapter().get_options(model="claude-opus-4-6", cwd="/tmp")
    assert opts.model == "claude-opus-4-6"


def test_baseline_plugin_path_is_none():
    assert BaselineAdapter().plugin_path is None


def test_baseline_no_trigger_command():
    adapter = BaselineAdapter()
    assert adapter.trigger_command is None
    assert adapter.wrap_prompt("hello") == "hello"


def test_baseline_has_setting_sources():
    opts = BaselineAdapter().get_options(model="claude-sonnet-4-6", cwd="/tmp")
    assert opts.setting_sources == ["user", "project"]


# --- GenericPluginAdapter ---

def test_generic_adapter_id(tmp_path):
    adapter = GenericPluginAdapter(name="my-plugin", plugin_path=str(tmp_path))
    assert adapter.plugin_id == "my-plugin"


def test_generic_adapter_plugin_path(tmp_path):
    adapter = GenericPluginAdapter(name="x", plugin_path=str(tmp_path))
    assert adapter.plugin_path == str(tmp_path)


def test_generic_adapter_has_plugin_in_options(tmp_path):
    adapter = GenericPluginAdapter(name="x", plugin_path=str(tmp_path))
    opts = adapter.get_options(model="claude-sonnet-4-6", cwd="/tmp")
    assert opts.plugins == [{"type": "local", "path": str(tmp_path)}]


def test_generic_adapter_has_setting_sources(tmp_path):
    adapter = GenericPluginAdapter(name="x", plugin_path=str(tmp_path))
    opts = adapter.get_options(model="claude-sonnet-4-6", cwd="/tmp")
    assert opts.setting_sources == ["user", "project"]


def test_generic_adapter_benchmark_system_always_present(tmp_path):
    adapter = GenericPluginAdapter(name="x", plugin_path=str(tmp_path))
    opts = adapter.get_options(model="claude-sonnet-4-6", cwd="/tmp")
    assert "autonomously" in opts.system_prompt.lower()


# --- trigger_command / wrap_prompt ---

def test_generic_adapter_no_trigger_by_default(tmp_path):
    adapter = GenericPluginAdapter(name="x", plugin_path=str(tmp_path))
    assert adapter.trigger_command is None
    assert adapter.wrap_prompt("do the thing") == "do the thing"


def test_generic_adapter_trigger_command(tmp_path):
    adapter = GenericPluginAdapter(name="homerun", plugin_path=str(tmp_path), trigger="/homerun")
    assert adapter.trigger_command == "/homerun"
    assert adapter.wrap_prompt("build a REST API") == "/homerun build a REST API"


def test_generic_adapter_no_system_prefix(tmp_path):
    adapter = GenericPluginAdapter(name="x", plugin_path=str(tmp_path))
    opts = adapter.get_options(model="claude-sonnet-4-6", cwd="/tmp")
    # No extra prefix — system prompt is BENCHMARK_SYSTEM only
    assert opts.system_prompt.strip().startswith("You are running in an automated benchmark")


def test_generic_adapter_system_prefix_prepended(tmp_path):
    adapter = GenericPluginAdapter(
        name="x", plugin_path=str(tmp_path),
        system_prefix="You are a wizard plugin.",
    )
    opts = adapter.get_options(model="claude-sonnet-4-6", cwd="/tmp")
    assert opts.system_prompt.startswith("You are a wizard plugin.")
    assert "autonomously" in opts.system_prompt.lower()


# --- get_adapter ---

def test_get_adapter_baseline():
    assert isinstance(get_adapter("baseline"), BaselineAdapter)


def test_get_adapter_with_path_returns_generic(tmp_path):
    adapter = get_adapter("superpowers", plugin_path=str(tmp_path))
    assert isinstance(adapter, GenericPluginAdapter)
    assert adapter.plugin_id == "superpowers"


def test_get_adapter_passes_trigger(tmp_path):
    adapter = get_adapter("homerun", plugin_path=str(tmp_path), trigger="/homerun")
    assert adapter.trigger_command == "/homerun"


def test_get_adapter_passes_system_prefix(tmp_path):
    adapter = get_adapter("myplugin", plugin_path=str(tmp_path), system_prefix="Be amazing.")
    opts = adapter.get_options(model="claude-sonnet-4-6", cwd="/tmp")
    assert opts.system_prompt.startswith("Be amazing.")


def test_get_adapter_no_path_raises():
    with pytest.raises(ValueError):
        get_adapter("unknown-plugin", plugin_path=None)


# --- install_plugin_settings ---

def test_install_plugin_settings_copies_file(tmp_path):
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    claude_dir = plugin_dir / ".claude"
    claude_dir.mkdir()
    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hook"}]}]}}
    (claude_dir / "settings.json").write_text(json.dumps(settings))

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    install_plugin_settings(str(plugin_dir), str(cwd))

    dest = cwd / ".claude" / "settings.json"
    assert dest.exists()
    assert json.loads(dest.read_text()) == settings


def test_install_plugin_settings_noop_when_missing(tmp_path):
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    install_plugin_settings(str(plugin_dir), str(cwd))
    assert not (cwd / ".claude" / "settings.json").exists()
