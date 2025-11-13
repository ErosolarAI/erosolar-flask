"""
Plugin Loader for Erosolar Universal Agent
===========================================
Loads Claude Code-style plugins from directories with support for:
- Slash commands from .md files
- Specialized agents from agent definitions
- Hooks from hooks.json configurations
- Plugin metadata from .claude-plugin/plugin.json

Plugin structure:
plugin-name/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata
├── commands/                 # Slash commands (optional)
│   └── command-name.md
├── agents/                   # Specialized agents (optional)
│   └── agent-name.md
├── hooks/                    # Hooks (optional)
│   └── hooks.json
└── README.md                # Plugin documentation
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""
    name: str
    version: str
    description: str
    author: Optional[str] = None
    plugin_path: str = ""


@dataclass
class CommandDefinition:
    """Definition of a slash command from a plugin."""
    name: str
    description: str
    argument_hint: Optional[str]
    content: str
    plugin_name: str
    allowed_tools: List[str] = None
    disable_model_invocation: bool = False

    def __post_init__(self):
        if self.allowed_tools is None:
            self.allowed_tools = []


@dataclass
class AgentDefinition:
    """Definition of a specialized agent from a plugin."""
    name: str
    description: str
    content: str
    plugin_name: str
    tools: List[str] = None
    model: str = "sonnet"
    color: str = "blue"

    def __post_init__(self):
        if self.tools is None:
            self.tools = []


class PluginLoader:
    """Loads plugins from directories."""

    def __init__(self):
        self.plugins: Dict[str, PluginMetadata] = {}
        self.commands: Dict[str, CommandDefinition] = {}
        self.agents: Dict[str, AgentDefinition] = {}
        self.hook_configs: List[str] = []

    def load_plugin_directory(self, plugin_path: str) -> Optional[PluginMetadata]:
        """
        Load a single plugin from a directory.

        Args:
            plugin_path: Path to plugin directory

        Returns:
            PluginMetadata if successful, None otherwise
        """
        plugin_path = os.path.abspath(plugin_path)

        if not os.path.isdir(plugin_path):
            return None

        # Load plugin metadata
        metadata = self._load_plugin_metadata(plugin_path)
        if not metadata:
            # If no metadata file, create basic metadata from directory name
            plugin_name = os.path.basename(plugin_path)
            metadata = PluginMetadata(
                name=plugin_name,
                version="unknown",
                description=f"Plugin: {plugin_name}",
                plugin_path=plugin_path,
            )

        self.plugins[metadata.name] = metadata

        # Load commands
        commands_dir = os.path.join(plugin_path, "commands")
        if os.path.isdir(commands_dir):
            self._load_commands_from_directory(commands_dir, metadata.name)

        # Load agents
        agents_dir = os.path.join(plugin_path, "agents")
        if os.path.isdir(agents_dir):
            self._load_agents_from_directory(agents_dir, metadata.name)

        # Load hooks
        hooks_file = os.path.join(plugin_path, "hooks", "hooks.json")
        if os.path.isfile(hooks_file):
            self.hook_configs.append(hooks_file)

        return metadata

    def load_plugins_from_directories(self, plugin_dirs: List[str]) -> int:
        """
        Load plugins from multiple directories.

        Args:
            plugin_dirs: List of paths to plugin directories

        Returns:
            Number of plugins successfully loaded
        """
        count = 0
        for plugin_dir in plugin_dirs:
            if not os.path.isdir(plugin_dir):
                continue

            # Load all subdirectories as potential plugins
            for item in os.listdir(plugin_dir):
                item_path = os.path.join(plugin_dir, item)
                if os.path.isdir(item_path):
                    if self.load_plugin_directory(item_path):
                        count += 1

        return count

    def _load_plugin_metadata(self, plugin_path: str) -> Optional[PluginMetadata]:
        """Load plugin.json metadata file."""
        metadata_file = os.path.join(plugin_path, ".claude-plugin", "plugin.json")

        if not os.path.isfile(metadata_file):
            return None

        try:
            with open(metadata_file, 'r') as f:
                data = json.load(f)

            return PluginMetadata(
                name=data.get("name", os.path.basename(plugin_path)),
                version=data.get("version", "unknown"),
                description=data.get("description", ""),
                author=data.get("author"),
                plugin_path=plugin_path,
            )
        except (json.JSONDecodeError, IOError, KeyError):
            return None

    def _load_commands_from_directory(self, commands_dir: str, plugin_name: str):
        """Load command definitions from a commands directory."""
        for filename in os.listdir(commands_dir):
            if not filename.endswith('.md'):
                continue

            command_path = os.path.join(commands_dir, filename)
            command = self._load_command_from_file(command_path, plugin_name)

            if command:
                self.commands[command.name] = command

    def _load_command_from_file(self, filepath: str, plugin_name: str) -> Optional[CommandDefinition]:
        """Load a single command definition from a markdown file."""
        try:
            with open(filepath, 'r') as f:
                content = f.read()

            # Extract frontmatter
            frontmatter, body = self._parse_markdown_frontmatter(content)

            # Command name is the filename without extension
            command_name = os.path.splitext(os.path.basename(filepath))[0]

            # Parse allowed-tools if present
            allowed_tools = []
            if "allowed-tools" in frontmatter:
                tools_str = frontmatter["allowed-tools"]
                # Parse format like "Bash(gh issue view:*), Bash(gh pr view:*)"
                allowed_tools = [t.strip() for t in tools_str.split(',')]

            return CommandDefinition(
                name=command_name,
                description=frontmatter.get("description", ""),
                argument_hint=frontmatter.get("argument-hint"),
                content=body,
                plugin_name=plugin_name,
                allowed_tools=allowed_tools,
                disable_model_invocation=frontmatter.get("disable-model-invocation", "false").lower() == "true",
            )
        except (IOError, ValueError):
            return None

    def _load_agents_from_directory(self, agents_dir: str, plugin_name: str):
        """Load agent definitions from an agents directory."""
        for filename in os.listdir(agents_dir):
            if not filename.endswith('.md'):
                continue

            agent_path = os.path.join(agents_dir, filename)
            agent = self._load_agent_from_file(agent_path, plugin_name)

            if agent:
                self.agents[agent.name] = agent

    def _load_agent_from_file(self, filepath: str, plugin_name: str) -> Optional[AgentDefinition]:
        """Load a single agent definition from a markdown file."""
        try:
            with open(filepath, 'r') as f:
                content = f.read()

            # Extract frontmatter
            frontmatter, body = self._parse_markdown_frontmatter(content)

            # Agent name is the filename without extension
            agent_name = os.path.splitext(os.path.basename(filepath))[0]

            # Parse tools if present
            tools = []
            if "tools" in frontmatter:
                tools_str = frontmatter["tools"]
                tools = [t.strip() for t in tools_str.split(',')]

            return AgentDefinition(
                name=agent_name,
                description=frontmatter.get("description", ""),
                content=body,
                plugin_name=plugin_name,
                tools=tools,
                model=frontmatter.get("model", "sonnet"),
                color=frontmatter.get("color", "blue"),
            )
        except (IOError, ValueError):
            return None

    def _parse_markdown_frontmatter(self, content: str) -> tuple[Dict[str, str], str]:
        """
        Parse YAML frontmatter from markdown content.

        Returns:
            (frontmatter_dict, body_content)
        """
        lines = content.split('\n')

        if not lines or lines[0].strip() != '---':
            return {}, content

        # Find end of frontmatter
        end_index = -1
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == '---':
                end_index = i
                break

        if end_index == -1:
            return {}, content

        # Parse frontmatter
        frontmatter = {}
        for line in lines[1:end_index]:
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip()

        # Body is everything after frontmatter
        body = '\n'.join(lines[end_index + 1:])

        return frontmatter, body

    def get_command(self, name: str) -> Optional[CommandDefinition]:
        """Get a command definition by name."""
        return self.commands.get(name)

    def get_agent(self, name: str) -> Optional[AgentDefinition]:
        """Get an agent definition by name."""
        return self.agents.get(name)

    def list_commands(self) -> List[str]:
        """List all available command names."""
        return list(self.commands.keys())

    def list_agents(self) -> List[str]:
        """List all available agent names."""
        return list(self.agents.keys())

    def list_plugins(self) -> List[PluginMetadata]:
        """List all loaded plugins."""
        return list(self.plugins.values())


# Global plugin loader instance
_PLUGIN_LOADER: Optional[PluginLoader] = None


def get_plugin_loader() -> PluginLoader:
    """Get or create the global plugin loader."""
    global _PLUGIN_LOADER

    if _PLUGIN_LOADER is None:
        _PLUGIN_LOADER = PluginLoader()

        # Load plugins from standard locations
        standard_plugin_dirs = [
            "plugins",
            ".claude/plugins",
            "claude-code/plugins",
            os.path.expanduser("~/.claude/plugins"),
        ]

        for plugin_dir in standard_plugin_dirs:
            if os.path.isdir(plugin_dir):
                _PLUGIN_LOADER.load_plugins_from_directories([plugin_dir])

    return _PLUGIN_LOADER


def reset_plugin_loader():
    """Reset the global plugin loader (mainly for testing)."""
    global _PLUGIN_LOADER
    _PLUGIN_LOADER = None
