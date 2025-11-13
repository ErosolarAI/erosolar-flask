# Claude Code Integration for Erosolar Universal Agent

This document describes the Claude Code features integrated into the Erosolar Universal Agent, preserving all original capabilities while adding powerful new coding workflows, security checks, and extensibility.

## 🎯 What's New

The integration adds **four major systems** from Claude Code:

### 1. **Hooks System** (`hooks_system.py`)
Security and validation hooks that run before/after tool execution.

- **PreToolUse Hooks**: Validate or block tool calls before execution
- **PostToolUse Hooks**: Process tool outputs after execution
- **Built-in Security Checks**: XSS, SQL injection, command injection, pickle deserialization, etc.
- **Session-based State**: Warnings only shown once per session
- **Plugin Hooks**: Load hooks from plugin directories

### 2. **Specialized Agents** (`specialized_agents.py`)
Parallel agent execution for different perspectives and expertise.

- **Code Explorers**: Deep codebase tracing, architecture analysis, finding similar features
- **Code Architects**: Design multiple implementation approaches with trade-off analysis
- **Code Reviewers**: Multi-pass review with confidence scoring (filters false positives at ≥80)

### 3. **Plugin System** (`plugin_loader.py`)
Load commands, agents, and hooks from plugin directories.

- **Slash Commands**: Load from `.md` files with frontmatter
- **Agent Definitions**: Specialized agent templates
- **Hooks**: Load from `hooks.json` configurations
- **Standard Locations**: `plugins/`, `.claude/plugins/`, `claude-code/plugins/`

### 4. **Enhanced Workflows** (enhanced `claude_integration.py`)
Better phase tracking and user interaction.

- **Phase Gates**: Explicit user confirmation at key phases
- **Phase Data Storage**: Store files to read, approaches chosen, etc.
- **Phase Headers**: Visual "PHASE 1 – DISCOVERY" indicators
- **Plugin Command Loading**: Automatically load slash commands from plugins

### 5. **Enhanced UI** (enhanced `cli_ui.py`)
Better formatting and visual feedback.

- **Phase Headers**: Bold, centered phase announcements
- **Confidence Scoring**: Color-coded issue severity badges
- **Agent Results**: Formatted summaries of multi-agent findings
- **File Citations**: Clickable file:line references

---

## 📖 Usage Guide

### Security Hooks

Security hooks run automatically on file editing tools (Edit, Write, MultiEdit):

```python
# Example: Editing a file with potential XSS
# Hook will warn: "⚠️ Setting innerHTML with untrusted content can lead to XSS..."

# You'll see:
# [!] [hook] ⚠️ Setting innerHTML with untrusted content can lead to XSS. Use textContent or safe DOM methods.
```

**Built-in Security Patterns:**
- GitHub Actions command injection (`.github/workflows/*.yml`)
- JavaScript: `eval()`, `new Function()`, `child_process.exec()`
- React: `dangerouslySetInnerHTML`, `innerHTML`
- Python: `pickle.load()`, `os.system()`
- SQL injection via string formatting

**Customize Hooks:**
Create `.claude/hooks/hooks.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/my_hook.py"
          }
        ]
      }
    ]
  }
}
```

### Specialized Agents

#### Launch Code Explorers
```python
from specialized_agents import launch_parallel_explorers

results = launch_parallel_explorers([
    "Find features similar to dark mode in the codebase",
    "Map the state management architecture",
    "Trace the authentication flow comprehensively",
], context="Building a new theme system")

# Results contain:
# - Detailed findings
# - List of 5-10 key files to read
# - Architecture insights
```

#### Launch Code Architects
```python
from specialized_agents import launch_parallel_architects

results = launch_parallel_architects(
    feature_description="Add dark mode toggle",
    codebase_context="React app with Tailwind CSS",
    approaches=["minimal", "clean", "pragmatic"]
)

# Results contain:
# - Architecture design for each approach
# - Trade-offs (pros/cons)
# - Complexity, effort, risk ratings
```

#### Launch Code Reviewers
```python
from specialized_agents import launch_parallel_reviewers

results = launch_parallel_reviewers(
    code_context="git diff output or file contents",
    review_focuses=["simplicity", "bugs", "conventions"],
    confidence_threshold=80  # Only issues ≥80 confidence
)

# Results contain:
# - Issues with confidence scores
# - Filtered by threshold (default: 80)
# - Location, severity, reason, suggestion
```

### Enhanced Workflows

The `/feature-dev` command now uses enhanced phase tracking:

```bash
> /feature-dev Add dark mode to the application

# Phase 1: Discovery (with confirmation gate)
PHASE 1 – DISCOVERY
[Agent clarifies requirements, asks questions]
> User confirms understanding

# Phase 2: Codebase Exploration (parallel explorers)
PHASE 2 – CODEBASE EXPLORATION
[Launches 2-3 code-explorer agents in parallel]
[Returns key files to read]
[Agent reads recommended files]

# Phase 3: Clarifying Questions (confirmation gate)
PHASE 3 – CLARIFYING QUESTIONS
[Lists specific edge cases, integration points]
> User provides answers

# Phase 4: Architecture Design (parallel architects)
PHASE 4 – ARCHITECTURE DESIGN
[Launches 2-3 code-architect agents]
[Presents approaches with trade-offs]
> User selects approach

# Phase 5: Implementation (confirmation gate + hooks)
PHASE 5 – IMPLEMENTATION
[Requests user approval]
[Edits files with security hook checks]
[Tracks progress with manage_todos]

# Phase 6: Quality Review (parallel reviewers)
PHASE 6 – QUALITY REVIEW
[Launches 3 code-reviewer agents]
[Filters issues by confidence ≥80]
> User decides: fix now / defer / accept

# Phase 7: Summary
PHASE 7 – SUMMARY
[Documents work, decisions, next steps]
```

**New Phase Management Methods:**
```python
# In WorkflowManager
workflow.get_current_phase()           # Get active phase
workflow.advance_phase()               # Move to next phase
workflow.confirm_phase()               # Mark phase as confirmed
workflow.is_phase_confirmed()          # Check confirmation status
workflow.store_phase_data(key, data)   # Store phase-specific data
workflow.get_phase_data(key)           # Retrieve phase data
workflow.get_phase_header()            # Get "PHASE X – TITLE"
```

### Plugin System

#### Plugin Directory Structure
```
my-plugin/
├── .claude-plugin/
│   └── plugin.json          # Metadata
├── commands/                 # Slash commands
│   └── my-command.md
├── agents/                   # Agent definitions
│   └── my-agent.md
├── hooks/                    # Hooks
│   └── hooks.json
└── README.md
```

#### Example Plugin Command (`commands/feature-dev.md`)
```markdown
---
description: Guided feature development with codebase understanding
argument-hint: Optional feature description
---

# Feature Development

You are helping a developer implement a new feature.
Follow the 7-phase workflow...

Initial request: $ARGUMENTS

[Full instructions...]
```

#### Example Plugin Agent (`agents/code-explorer.md`)
```markdown
---
name: code-explorer
description: Deeply analyzes existing codebase features
tools: Glob, Grep, Read
model: sonnet
color: yellow
---

You are an expert code analyst...
[Agent instructions...]
```

#### Load Plugins Automatically
Plugins are auto-loaded from:
1. `plugins/` (current directory)
2. `.claude/plugins/`
3. `claude-code/plugins/`
4. `~/.claude/plugins/`

---

## 🔧 Technical Architecture

### Hook Execution Flow
```
User → Agent → Tool Call
              ↓
         PreToolUse Hooks
              ↓
         [Allowed?]
         /        \
       Yes         No
        ↓           ↓
    Execute     Block + Return Error
        ↓
    PostToolUse Hooks
        ↓
    Return Result
```

### Specialized Agent Execution
```
User Request
    ↓
Launch Multiple Agents in Parallel
    ├── Agent 1 (Focus A) → Result 1
    ├── Agent 2 (Focus B) → Result 2
    └── Agent 3 (Focus C) → Result 3
    ↓
Aggregate Results
    ↓
Filter/Score (if reviewers)
    ↓
Present to User
```

### Workflow Phase Flow
```
Activate Workflow
    ↓
Phase 1 (current_phase_index=0)
    ↓
[requires_confirmation?]
    ↓
Wait for User Confirmation
    ↓
advance_phase()
    ↓
Phase 2 (current_phase_index=1)
    ...
```

---

## 🚀 Example Usage Scenarios

### Scenario 1: Building a New Feature

```bash
> /feature-dev Add real-time collaboration to the editor

# System launches explorers to find similar features
# System asks clarifying questions (WebSocket? Operational Transform? CRDT?)
# System designs 3 approaches and presents trade-offs
# User selects "pragmatic" approach
# System implements with security hook checks
# System reviews code with 3 specialized reviewers
# System filters issues to only confidence ≥80
# System presents summary with files changed
```

### Scenario 2: Code Review with Confidence Scoring

```bash
> /code-review

# System launches 5 parallel reviewers:
# - CLAUDE.md compliance checker
# - Shallow bug scanner
# - Historical context analyzer (git blame)
# - Previous PR comment checker
# - Code comment compliance checker

# Each issue scored 0-100 for confidence
# Only issues ≥80 shown to user
# False positives filtered out automatically
```

### Scenario 3: Security Hook Blocks Dangerous Code

```bash
> User: "Write a script that evaluates user input"

# Agent writes: eval(user_input)
# PreToolUse hook catches `eval(`
# Hook blocks the write with warning:
# [!] [hook] ⚠️ eval() executes arbitrary code. Use JSON.parse() for data.

# Agent sees warning and revises approach
```

---

## 🎨 UI Enhancements

### Before Integration
```
Assistant: I've implemented the feature.
Tool result: File written successfully.
```

### After Integration
```
═════════════════════════════════════════════════════════════════
           PHASE 5 – IMPLEMENTATION
═════════════════════════════════════════════════════════════════

[!] [hook] ⚠️ Security check: Validating file edits...

+---------------------------------------------------------------------------+
|                       Agent 1: code-explorer-1                            |
+===========================================================================+
| Key files to read:                                                        |
|   1. src/theme/ThemeProvider.tsx:45                                      |
|   2. src/hooks/useTheme.ts:12                                            |
|   3. src/components/ThemeToggle.tsx:8                                    |
+---------------------------------------------------------------------------+

[HIGH] SQL query uses string formatting (confidence: 85/100)
[MEDIUM] Complex conditional could be simplified (confidence: 72/100)
```

---

## 📊 Performance & Scalability

**Parallel Execution:**
- Code explorers run in parallel (default: 3 concurrent)
- Code architects run in parallel (default: 3 approaches)
- Code reviewers run in parallel (default: 3 focuses)

**Hook Performance:**
- Hooks timeout after 10 seconds
- Built-in hooks are function-based (microsecond latency)
- Command-based hooks spawn subprocesses

**Memory:**
- Phase data stored in workflow state
- Hook warnings cached per session
- Plugin definitions loaded once at startup

---

## 🔒 Security Features

### Built-in Security Patterns

| Pattern | Risk | Detection |
|---------|------|-----------|
| GitHub Actions injection | Command injection via PR titles, commit messages | Path: `.github/workflows/*.yml` |
| `eval()` / `new Function()` | Arbitrary code execution | Content: `eval(`, `new Function(` |
| `dangerouslySetInnerHTML` | XSS attacks | Content: `dangerouslySetInnerHTML` |
| `.innerHTML =` | XSS attacks | Content: `.innerHTML=` |
| `pickle.load()` | Arbitrary code execution | Content: `pickle.load`, `pickle.loads` |
| `os.system()` | Command injection | Content: `os.system(` |
| SQL string formatting | SQL injection | Content: `execute(f"`, `.format(` |
| `child_process.exec()` | Command injection | Content: `exec(`, `execSync(` |

### Hook Exit Codes
- **0**: Allow tool to proceed
- **1**: Show error to user only (not to Claude)
- **2**: Block tool and show error to Claude (Claude can adjust)

---

## 🧪 Testing the Integration

### Test Hooks
```python
# Test security hook detection
from hooks_system import get_hooks_manager

hooks = get_hooks_manager()
allowed, messages = hooks.run_pre_tool_hooks(
    "Edit",
    {"file_path": "test.js", "new_string": "eval(userInput)"}
)

assert not allowed
assert "eval()" in messages[0]
```

### Test Specialized Agents
```python
# Test code explorer
from specialized_agents import launch_parallel_explorers

results = launch_parallel_explorers([
    "Find all API endpoints in the codebase"
])

assert len(results) == 1
assert len(results[0].key_files) > 0
```

### Test Plugin Loading
```python
# Test plugin loader
from plugin_loader import get_plugin_loader

loader = get_plugin_loader()
assert "feature-dev" in loader.list_commands()
assert "code-explorer" in loader.list_agents()
```

---

## 🎓 Advanced Usage

### Custom Hook Example
```python
# my_security_hook.py
import json
import sys

def main():
    input_data = json.load(sys.stdin)
    tool_name = input_data["tool_name"]
    tool_input = input_data["tool_input"]

    # Custom validation logic
    if tool_name == "Write":
        content = tool_input.get("content", "")
        if "SECRET_KEY" in content:
            print("⚠️ Warning: Hardcoded secret detected!", file=sys.stderr)
            sys.exit(2)  # Block and notify Claude

    sys.exit(0)  # Allow

if __name__ == "__main__":
    main()
```

### Custom Agent Template
```markdown
---
name: security-auditor
description: Performs security audit on code changes
tools: Grep, Read, Bash
model: sonnet
---

You are a security auditor specializing in finding vulnerabilities.

Review the provided code for:
1. Authentication bypasses
2. Authorization flaws
3. Data exposure risks
4. Input validation issues

For each issue found, provide:
- **Severity**: critical/high/medium/low
- **Confidence**: 0-100
- **Location**: file:line
- **Exploit scenario**: How it could be exploited
- **Fix**: Concrete remediation steps
```

---

## 🐛 Troubleshooting

**Hooks not running?**
- Check `.claude/hooks/hooks.json` exists and is valid JSON
- Verify hook script is executable: `chmod +x hook.py`
- Check hook script path is absolute
- Look for errors in hook script output

**Plugins not loading?**
- Verify plugin directory structure (`.claude-plugin/plugin.json`)
- Check frontmatter syntax in `.md` files (must start with `---`)
- Ensure plugin directory is in a standard location

**Specialized agents failing?**
- Check `DEEPSEEK_API_KEY` is set
- Verify LLM model is available
- Check for network connectivity
- Increase timeout if agents are slow

**Phase tracking not working?**
- Verify workflow is activated via `/feature-dev`
- Check phase confirmations are being called
- Look for workflow state in WorkflowManager

---

## 📚 API Reference

### HooksManager
```python
class HooksManager:
    def register_hook(self, hook: HookDefinition)
    def register_hooks_from_config(self, config_path: str)
    def run_pre_tool_hooks(self, tool_name: str, tool_input: Dict) -> Tuple[bool, List[str]]
    def run_post_tool_hooks(self, tool_name: str, tool_input: Dict, tool_output: str) -> Tuple[str, List[str]]
```

### SpecializedAgentsManager
```python
class SpecializedAgentsManager:
    def launch_code_explorers(self, prompts: List[str], context: str = "") -> List[AgentResult]
    def launch_code_architects(self, feature_description: str, codebase_context: str, approaches: List[str]) -> List[AgentResult]
    def launch_code_reviewers(self, code_context: str, review_focuses: List[str]) -> List[AgentResult]
```

### PluginLoader
```python
class PluginLoader:
    def load_plugin_directory(self, plugin_path: str) -> Optional[PluginMetadata]
    def load_plugins_from_directories(self, plugin_dirs: List[str]) -> int
    def get_command(self, name: str) -> Optional[CommandDefinition]
    def get_agent(self, name: str) -> Optional[AgentDefinition]
```

### WorkflowManager (Enhanced)
```python
class WorkflowManager:
    def get_current_phase(self) -> Optional[WorkflowPhase]
    def advance_phase(self) -> bool
    def confirm_phase(self, phase_index: Optional[int] = None) -> bool
    def is_phase_confirmed(self, phase_index: Optional[int] = None) -> bool
    def store_phase_data(self, key: str, data: Any)
    def get_phase_data(self, key: str) -> Any
    def get_phase_header(self) -> Optional[str]
```

---

## 🎉 Summary

The Claude Code integration enhances Erosolar Universal Agent with:

✅ **Security hooks** - Automatic vulnerability detection
✅ **Specialized agents** - Parallel multi-perspective analysis
✅ **Confidence scoring** - Filter false positives automatically
✅ **Plugin system** - Extensible commands and agents
✅ **Enhanced workflows** - Phase gates and tracking
✅ **Better UI** - Visual phase headers and formatting
✅ **100% backward compatible** - All original features preserved

**No capabilities lost, only gained!**
