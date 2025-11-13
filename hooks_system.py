"""
Hooks System for Erosolar Universal Agent
==========================================
Implements Claude Code-style hooks for pre/post tool execution validation,
security checks, and extensibility.

Supports:
- PreToolUse hooks: Run before tool execution, can block/modify calls
- PostToolUse hooks: Process tool outputs after execution
- Session-based state management
- Plugin-based hook loading
- Security pattern detection

Exit codes for hook scripts:
- 0: Allow tool to proceed
- 1: Show error to user only (not to Claude)
- 2: Block tool and show error to Claude
"""

import json
import os
import re
import subprocess
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Tuple


@dataclass
class HookDefinition:
    """Definition of a single hook."""
    hook_type: Literal["PreToolUse", "PostToolUse"]
    matcher: str  # Regex pattern for tool names
    command: Optional[str] = None
    function: Optional[Callable] = None
    source: str = "internal"  # "internal", "plugin", or "user"


@dataclass
class HookResult:
    """Result from executing a hook."""
    allowed: bool
    exit_code: int
    stdout: str
    stderr: str
    modified_input: Optional[Dict[str, Any]] = None


class HooksManager:
    """Manages hook execution for tool calls."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or self._generate_session_id()
        self.hooks: Dict[str, List[HookDefinition]] = defaultdict(list)
        self._lock = threading.Lock()
        self._state_cache: Dict[str, Any] = {}

        # Built-in security patterns
        self._security_patterns = self._load_security_patterns()

        # Register built-in hooks
        self._register_builtin_hooks()

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    def _load_security_patterns(self) -> List[Dict[str, Any]]:
        """Load security patterns for validation."""
        return [
            {
                "ruleName": "github_actions_workflow",
                "path_check": lambda path: ".github/workflows/" in path and (path.endswith(".yml") or path.endswith(".yaml")),
                "reminder": "⚠️ GitHub Actions workflow detected. Beware of command injection via untrusted inputs like issue titles, PR descriptions, commit messages. Use env: variables instead of direct interpolation.",
            },
            {
                "ruleName": "child_process_exec",
                "substrings": ["child_process.exec", "exec(", "execSync("],
                "reminder": "⚠️ child_process.exec() can lead to command injection. Consider using execFile() or a safer alternative.",
            },
            {
                "ruleName": "eval_injection",
                "substrings": ["eval(", "new Function("],
                "reminder": "⚠️ eval() and new Function() execute arbitrary code. Consider safer alternatives like JSON.parse() for data.",
            },
            {
                "ruleName": "dangerously_set_html",
                "substrings": ["dangerouslySetInnerHTML"],
                "reminder": "⚠️ dangerouslySetInnerHTML can lead to XSS. Ensure content is sanitized using DOMPurify or similar.",
            },
            {
                "ruleName": "innerHTML_xss",
                "substrings": [".innerHTML =", ".innerHTML="],
                "reminder": "⚠️ Setting innerHTML with untrusted content can lead to XSS. Use textContent or safe DOM methods.",
            },
            {
                "ruleName": "pickle_deserialization",
                "substrings": ["pickle.load", "pickle.loads"],
                "reminder": "⚠️ pickle with untrusted content can lead to arbitrary code execution. Use JSON or other safe serialization.",
            },
            {
                "ruleName": "os_system_injection",
                "substrings": ["os.system(", "from os import system"],
                "reminder": "⚠️ os.system() should only be used with static arguments, never with user-controlled input.",
            },
            {
                "ruleName": "sql_injection",
                "substrings": ["execute(f\"", "execute(f'", ".format("],
                "reminder": "⚠️ String formatting in SQL queries can lead to SQL injection. Use parameterized queries instead.",
            },
        ]

    def _register_builtin_hooks(self):
        """Register built-in security and validation hooks."""
        # Security checker for Edit/Write tools
        self.register_hook(HookDefinition(
            hook_type="PreToolUse",
            matcher="Edit|Write|MultiEdit",
            function=self._security_checker_hook,
            source="builtin",
        ))

    def register_hook(self, hook: HookDefinition):
        """Register a hook for execution."""
        with self._lock:
            self.hooks[hook.hook_type].append(hook)

    def register_hooks_from_config(self, config_path: str):
        """Load hooks from a JSON configuration file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            hooks_config = config.get("hooks", {})

            for hook_type in ["PreToolUse", "PostToolUse"]:
                for hook_group in hooks_config.get(hook_type, []):
                    matcher = hook_group.get("matcher", "*")
                    for hook_def in hook_group.get("hooks", []):
                        if hook_def.get("type") == "command":
                            command = hook_def.get("command")
                            # Expand environment variables in command
                            command = os.path.expandvars(command)

                            self.register_hook(HookDefinition(
                                hook_type=hook_type,
                                matcher=matcher,
                                command=command,
                                source=f"config:{config_path}",
                            ))
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            # Silently ignore hook loading errors
            pass

    def _matches_pattern(self, tool_name: str, pattern: str) -> bool:
        """Check if tool name matches the pattern."""
        if pattern == "*":
            return True
        try:
            return bool(re.match(pattern, tool_name))
        except re.error:
            return tool_name == pattern

    def _execute_command_hook(
        self,
        hook: HookDefinition,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Optional[str] = None,
    ) -> HookResult:
        """Execute a command-based hook."""
        if not hook.command:
            return HookResult(allowed=True, exit_code=0, stdout="", stderr="")

        # Prepare input data for hook
        hook_input = {
            "session_id": self.session_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
        }
        if tool_output is not None:
            hook_input["tool_output"] = tool_output

        try:
            # Execute hook command with JSON input
            result = subprocess.run(
                hook.command,
                input=json.dumps(hook_input),
                capture_output=True,
                text=True,
                shell=True,
                timeout=10,
            )

            allowed = result.returncode == 0
            return HookResult(
                allowed=allowed,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return HookResult(
                allowed=False,
                exit_code=1,
                stdout="",
                stderr="Hook execution timed out",
            )
        except Exception as e:
            return HookResult(
                allowed=False,
                exit_code=1,
                stdout="",
                stderr=f"Hook execution error: {e}",
            )

    def _execute_function_hook(
        self,
        hook: HookDefinition,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Optional[str] = None,
    ) -> HookResult:
        """Execute a function-based hook."""
        if not hook.function:
            return HookResult(allowed=True, exit_code=0, stdout="", stderr="")

        try:
            result = hook.function(
                session_id=self.session_id,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
            )
            return result
        except Exception as e:
            return HookResult(
                allowed=False,
                exit_code=1,
                stdout="",
                stderr=f"Hook function error: {e}",
            )

    def _security_checker_hook(
        self,
        session_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Optional[str] = None,
    ) -> HookResult:
        """Built-in security checker for file operations."""
        # Only check file editing tools
        if tool_name not in ["Edit", "Write", "MultiEdit"]:
            return HookResult(allowed=True, exit_code=0, stdout="", stderr="")

        # Get file path
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return HookResult(allowed=True, exit_code=0, stdout="", stderr="")

        # Extract content to check
        if tool_name == "Write":
            content = tool_input.get("content", "")
        elif tool_name == "Edit":
            content = tool_input.get("new_string", "")
        elif tool_name == "MultiEdit":
            edits = tool_input.get("edits", [])
            content = " ".join(edit.get("new_string", "") for edit in edits)
        else:
            content = ""

        # Check security patterns
        for pattern in self._security_patterns:
            # Check path-based patterns
            if "path_check" in pattern:
                try:
                    if pattern["path_check"](file_path):
                        warning_key = f"{file_path}-{pattern['ruleName']}"
                        if not self._was_warning_shown(warning_key):
                            self._mark_warning_shown(warning_key)
                            return HookResult(
                                allowed=False,
                                exit_code=2,
                                stdout="",
                                stderr=pattern["reminder"],
                            )
                except Exception:
                    pass

            # Check content-based patterns
            if "substrings" in pattern and content:
                for substring in pattern["substrings"]:
                    if substring in content:
                        warning_key = f"{file_path}-{pattern['ruleName']}"
                        if not self._was_warning_shown(warning_key):
                            self._mark_warning_shown(warning_key)
                            return HookResult(
                                allowed=False,
                                exit_code=2,
                                stdout="",
                                stderr=pattern["reminder"],
                            )

        return HookResult(allowed=True, exit_code=0, stdout="", stderr="")

    def _was_warning_shown(self, warning_key: str) -> bool:
        """Check if a warning was already shown in this session."""
        cache_key = f"warning:{warning_key}"
        return self._state_cache.get(cache_key, False)

    def _mark_warning_shown(self, warning_key: str):
        """Mark a warning as shown in this session."""
        cache_key = f"warning:{warning_key}"
        self._state_cache[cache_key] = True

    def run_pre_tool_hooks(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Run all PreToolUse hooks for a tool.

        Returns:
            (allowed, messages): Whether tool should proceed and any messages
        """
        messages = []

        with self._lock:
            hooks = self.hooks.get("PreToolUse", [])

        for hook in hooks:
            if not self._matches_pattern(tool_name, hook.matcher):
                continue

            if hook.command:
                result = self._execute_command_hook(hook, tool_name, tool_input)
            elif hook.function:
                result = self._execute_function_hook(hook, tool_name, tool_input)
            else:
                continue

            if result.stderr:
                messages.append(result.stderr)

            # Exit code 2 means block and show to Claude
            if result.exit_code == 2:
                return False, messages

            # Exit code 1 means show to user only, but continue
            # (we'll just continue here)

        return True, messages

    def run_post_tool_hooks(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: str,
    ) -> Tuple[str, List[str]]:
        """
        Run all PostToolUse hooks for a tool.

        Returns:
            (output, messages): Potentially modified output and any messages
        """
        messages = []
        output = tool_output

        with self._lock:
            hooks = self.hooks.get("PostToolUse", [])

        for hook in hooks:
            if not self._matches_pattern(tool_name, hook.matcher):
                continue

            if hook.command:
                result = self._execute_command_hook(hook, tool_name, tool_input, output)
            elif hook.function:
                result = self._execute_function_hook(hook, tool_name, tool_input, output)
            else:
                continue

            if result.stderr:
                messages.append(result.stderr)
            if result.stdout:
                messages.append(result.stdout)

            # PostToolUse hooks can modify output (though we don't currently support this)

        return output, messages


# Global hooks manager instance
_HOOKS_MANAGER: Optional[HooksManager] = None
_HOOKS_LOCK = threading.Lock()


def get_hooks_manager(session_id: Optional[str] = None) -> HooksManager:
    """Get or create the global hooks manager."""
    global _HOOKS_MANAGER

    with _HOOKS_LOCK:
        if _HOOKS_MANAGER is None:
            _HOOKS_MANAGER = HooksManager(session_id=session_id)

            # Try to load hooks from standard locations
            standard_locations = [
                ".claude/hooks/hooks.json",
                os.path.expanduser("~/.claude/hooks/hooks.json"),
            ]

            for location in standard_locations:
                if os.path.exists(location):
                    _HOOKS_MANAGER.register_hooks_from_config(location)

        return _HOOKS_MANAGER


def reset_hooks_manager():
    """Reset the global hooks manager (mainly for testing)."""
    global _HOOKS_MANAGER
    with _HOOKS_LOCK:
        _HOOKS_MANAGER = None
