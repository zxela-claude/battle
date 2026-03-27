from claude_agent_sdk import ClaudeAgentOptions
from .base import BENCHMARK_SYSTEM, PluginAdapter


class BaselineAdapter(PluginAdapter):
    """No-plugin control cell — vanilla Claude with no skills or hooks."""

    @property
    def plugin_id(self) -> str:
        return "baseline"

    def get_options(self, model: str, cwd: str) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            cwd=cwd,
            model=model,
            system_prompt=BENCHMARK_SYSTEM,
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            setting_sources=["user", "project"],
        )
