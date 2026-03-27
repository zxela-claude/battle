import json
import pytest
from battle.config import Config, _is_github_shorthand


def test_empty_config(tmp_battle_home):
    cfg = Config()
    assert cfg.list_plugins() == {}


def test_register_and_resolve(tmp_battle_home, tmp_path):
    plugin_dir = tmp_path / "superpowers"
    plugin_dir.mkdir()
    cfg = Config()
    cfg.register("superpowers", str(plugin_dir))
    assert cfg.resolve("superpowers") == str(plugin_dir)


def test_resolve_unknown_raises(tmp_battle_home):
    cfg = Config()
    with pytest.raises(KeyError, match="superpowers"):
        cfg.resolve("superpowers")


def test_resolve_absolute_path_passthrough(tmp_battle_home, tmp_path):
    plugin_dir = tmp_path / "myplugin"
    plugin_dir.mkdir()
    cfg = Config()
    assert cfg.resolve(str(plugin_dir)) == str(plugin_dir)


def test_github_shorthand_detection():
    assert _is_github_shorthand("obra/superpowers") is True
    assert _is_github_shorthand("zxela/claude-plugins") is True
    assert _is_github_shorthand("/usr/local/superpowers") is False
    assert _is_github_shorthand("./superpowers") is False
    assert _is_github_shorthand("superpowers") is False


def test_config_persists(tmp_battle_home, tmp_path):
    plugin_dir = tmp_path / "homerun"
    plugin_dir.mkdir()
    cfg = Config()
    cfg.register("homerun", str(plugin_dir))
    cfg2 = Config()
    assert cfg2.resolve("homerun") == str(plugin_dir)


# --- metadata ---

def test_register_stores_trigger(tmp_battle_home, tmp_path):
    plugin_dir = tmp_path / "homerun"
    plugin_dir.mkdir()
    cfg = Config()
    cfg.register("homerun", str(plugin_dir), trigger="/homerun")
    meta = cfg.get_meta("homerun")
    assert meta["trigger"] == "/homerun"
    assert meta["path"] == str(plugin_dir)


def test_register_stores_system_prefix(tmp_battle_home, tmp_path):
    plugin_dir = tmp_path / "myplugin"
    plugin_dir.mkdir()
    cfg = Config()
    cfg.register("myplugin", str(plugin_dir), system_prefix="Be helpful.")
    meta = cfg.get_meta("myplugin")
    assert meta["system_prefix"] == "Be helpful."


def test_register_no_optional_fields(tmp_battle_home, tmp_path):
    plugin_dir = tmp_path / "plain"
    plugin_dir.mkdir()
    cfg = Config()
    cfg.register("plain", str(plugin_dir))
    meta = cfg.get_meta("plain")
    assert "trigger" not in meta
    assert "system_prefix" not in meta


def test_list_plugins_returns_meta_dicts(tmp_battle_home, tmp_path):
    plugin_dir = tmp_path / "p"
    plugin_dir.mkdir()
    cfg = Config()
    cfg.register("myplugin", str(plugin_dir), trigger="/myplugin")
    plugins = cfg.list_plugins()
    assert "myplugin" in plugins
    assert plugins["myplugin"]["trigger"] == "/myplugin"


def test_get_meta_unknown_raises(tmp_battle_home):
    cfg = Config()
    with pytest.raises(KeyError):
        cfg.get_meta("nonexistent")


def test_backward_compat_string_format(tmp_battle_home, tmp_path):
    """Older plugins.json stored path as a bare string — must still load."""
    plugin_dir = tmp_path / "legacy"
    plugin_dir.mkdir()
    plugins_file = tmp_battle_home / "plugins.json"
    plugins_file.write_text(json.dumps({"legacy": str(plugin_dir)}))
    cfg = Config()
    assert cfg.resolve("legacy") == str(plugin_dir)
    meta = cfg.get_meta("legacy")
    assert meta["path"] == str(plugin_dir)
