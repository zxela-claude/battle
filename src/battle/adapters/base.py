from abc import ABC, abstractmethod
from claude_agent_sdk import ClaudeAgentOptions

# System prompt injected into all plugin cells.
# Superpowers' brainstorming skill has a HARD-GATE requiring user approval
# before implementation; this overrides it since battle runs are unattended.
# Per the superpowers skill hierarchy, explicit user/CLAUDE.md instructions
# take highest priority over skill-level guidance.
BENCHMARK_SYSTEM = (
    "You are running in an automated benchmark evaluation. "
    "Do not use EnterPlanMode or the brainstorming workflow. "
    "Do not ask for user confirmation, clarification, or plan approval. "
    "Implement the task fully and immediately using your best judgment."
)


class PluginAdapter(ABC):
    """Base class for all plugin adapters."""

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Short identifier, e.g. 'superpowers', 'homerun', 'baseline'."""

    @abstractmethod
    def get_options(self, model: str, cwd: str) -> ClaudeAgentOptions:
        """Return ClaudeAgentOptions for a single cell run."""


_ADAPTER_REGISTRY: dict[str, type[PluginAdapter]] = {}


def register_adapter(cls: type[PluginAdapter]) -> type[PluginAdapter]:
    """Class decorator to register an adapter."""
    _ADAPTER_REGISTRY[cls.__name__] = cls
    return cls


class GenericPluginAdapter(PluginAdapter):
    """Adapter for any plugin not covered by a dedicated adapter class."""

    def __init__(self, name: str, plugin_path: str):
        self._name = name
        self._path = plugin_path

    @property
    def plugin_id(self) -> str:
        return self._name

    def get_options(self, model: str, cwd: str) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            cwd=cwd,
            model=model,
            system_prompt=BENCHMARK_SYSTEM,
            plugins=[{"type": "local", "path": self._path}],
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill"],
        )


def get_adapter(name: str, plugin_path: str | None) -> PluginAdapter:
    """Resolve adapter by plugin_id name.

    Falls back to GenericPluginAdapter for any name not covered by a registered
    adapter, as long as a plugin_path is provided.
    """
    id_map = {}
    for cls in _ADAPTER_REGISTRY.values():
        try:
            if plugin_path is not None:
                instance = cls(plugin_path=plugin_path)
            else:
                instance = cls()
            id_map[instance.plugin_id] = cls
        except Exception:
            pass

    if name in id_map:
        cls = id_map[name]
        return cls(plugin_path=plugin_path) if plugin_path is not None else cls()

    # Fall back to generic adapter when a path is available
    if plugin_path is not None:
        return GenericPluginAdapter(name=name, plugin_path=plugin_path)

    raise ValueError(
        f"Unknown adapter '{name}' and no plugin_path provided. "
        f"Registered: {list(id_map)}"
    )
