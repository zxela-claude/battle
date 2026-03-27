from abc import ABC, abstractmethod
import shutil
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

# System prompt injected into all plugin cells.
# Superpowers' brainstorming skill has a HARD-GATE requiring user approval
# before proceeding. In an automated benchmark there is no human to respond,
# so Claude should act as both architect and approver: run through the full
# brainstorm/plan workflow autonomously, approve its own design, then implement.
BENCHMARK_SYSTEM = (
    "You are running in an automated benchmark evaluation with no human present. "
    "When a skill or workflow requires user approval, confirmation, or clarification, "
    "proceed autonomously — act as both the designer and the approver. "
    "Complete any brainstorming or planning steps yourself, approve your own plan, "
    "then implement immediately without waiting for external input."
)


def load_plugin_claude_md(plugin_path: str) -> str:
    """Read CLAUDE.md from the plugin root, if present."""
    claude_md = Path(plugin_path) / "CLAUDE.md"
    if claude_md.exists():
        return claude_md.read_text()
    return ""


def build_system_prompt(plugin_path: str | None) -> str:
    """Combine a plugin's CLAUDE.md with the benchmark system prompt."""
    parts = []
    if plugin_path:
        md = load_plugin_claude_md(plugin_path)
        if md:
            parts.append(md)
    parts.append(BENCHMARK_SYSTEM)
    return "\n\n".join(parts)


def install_plugin_settings(plugin_path: str, cwd: str) -> None:
    """Copy the plugin's .claude/settings.json into cwd so hooks are discovered.

    Claude Code finds settings by scanning up from the cwd. Writing the plugin's
    settings here mirrors how hooks work during a real interactive session.
    Skills are handled separately via ClaudeAgentOptions.plugins.
    """
    src = Path(plugin_path) / ".claude" / "settings.json"
    if not src.exists():
        return
    dest_dir = Path(cwd) / ".claude"
    dest_dir.mkdir(exist_ok=True)
    shutil.copy2(src, dest_dir / "settings.json")


class PluginAdapter(ABC):
    """Base class for all plugin adapters."""

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Short identifier, e.g. 'superpowers', 'homerun', 'baseline'."""

    @property
    def plugin_path(self) -> str | None:
        """Filesystem path to the installed plugin root, or None for baseline."""
        return None

    @property
    def trigger_command(self) -> str | None:
        """Optional slash command that activates this plugin, e.g. '/homerun'.

        When set, the runner will prepend this to the task prompt so the plugin
        activates as intended rather than receiving the raw task text.
        """
        return None

    def wrap_prompt(self, prompt: str) -> str:
        """Wrap the task prompt with the plugin's trigger command if needed."""
        if self.trigger_command:
            return f"{self.trigger_command} {prompt}"
        return prompt

    @abstractmethod
    def get_options(self, model: str, cwd: str) -> ClaudeAgentOptions:
        """Return ClaudeAgentOptions for a single cell run."""


_ADAPTER_REGISTRY: dict[str, type[PluginAdapter]] = {}


def register_adapter(cls: type[PluginAdapter]) -> type[PluginAdapter]:
    """Class decorator to register an adapter.

    Instantiates with no args to extract plugin_id for the lookup table.
    """
    try:
        instance = cls()
        _ADAPTER_REGISTRY[instance.plugin_id] = cls
    except Exception as exc:
        import warnings
        warnings.warn(f"Failed to register adapter {cls.__name__}: {exc}")
    return cls


class GenericPluginAdapter(PluginAdapter):
    """Adapter for any plugin not covered by a dedicated adapter class."""

    def __init__(self, name: str, plugin_path: str):
        self._name = name
        self._path = plugin_path

    @property
    def plugin_id(self) -> str:
        return self._name

    @property
    def plugin_path(self) -> str | None:
        return self._path or None

    def get_options(self, model: str, cwd: str) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            cwd=cwd,
            model=model,
            system_prompt=build_system_prompt(self._path),
            plugins=[{"type": "local", "path": self._path}],
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill"],
        )


def get_adapter(name: str, plugin_path: str | None) -> PluginAdapter:
    """Resolve adapter by plugin_id name.

    Falls back to GenericPluginAdapter for any name not covered by a registered
    adapter, as long as a plugin_path is provided.
    """
    if name in _ADAPTER_REGISTRY:
        cls = _ADAPTER_REGISTRY[name]
        if plugin_path is not None:
            return cls(plugin_path=plugin_path)
        return cls()

    # Fall back to generic adapter when a path is available
    if plugin_path is not None:
        return GenericPluginAdapter(name=name, plugin_path=plugin_path)

    raise ValueError(
        f"Unknown adapter '{name}' and no plugin_path provided. "
        f"Registered: {list(_ADAPTER_REGISTRY)}"
    )
