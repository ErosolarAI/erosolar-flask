"""Shared terminal UI helpers for the weather demo scripts."""

from __future__ import annotations

import json
import os
import shutil
import sys
import textwrap
from typing import Iterable

# ANSI style codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

PALETTE = {
    "accent": "\033[38;5;45m",
    "user": "\033[38;5;81m",
    "assistant": "\033[38;5;214m",
    "tool": "\033[38;5;141m",
    "info": "\033[38;5;110m",
    "warning": "\033[38;5;221m",
    "error": "\033[38;5;203m",
    "success": "\033[38;5;120m",
    "muted": "\033[38;5;247m",
}

ICONS = {
    "info": "[i]",
    "success": "[+]",
    "warning": "[!]",
    "error": "[x]",
}

DEFAULT_WIDTH = 90
MIN_WIDTH = 48


def _stdout_supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    stream = getattr(sys.stdout, "isatty", None)
    return bool(stream and stream())


USE_COLOR = _stdout_supports_color()


def _style_code(style: str) -> str:
    return PALETTE.get(style, "")


def color_text(
    text: str,
    style: str = "accent",
    *,
    bold: bool = False,
    dim: bool = False,
) -> str:
    if not USE_COLOR:
        return text
    codes: list[str] = []
    if bold:
        codes.append(BOLD)
    if dim:
        codes.append(DIM)
    color = _style_code(style)
    if color:
        codes.append(color)
    if not codes:
        return text
    return "".join(codes) + text + RESET


def prompt_label(role: str = "YOU", symbol: str = ">>") -> str:
    role_key = role.strip().lower()
    if role_key in {"you", "user", "human"}:
        style = "user"
    elif role_key in {"assistant", "ai", "bot"}:
        style = "assistant"
    else:
        style = "accent"
    label = f"{role.upper()} {symbol} "
    return color_text(label, style=style, bold=True)


def print_status(message: str, kind: str = "info") -> None:
    icon = ICONS.get(kind, "[*]")
    style = kind if kind in PALETTE else "info"
    text = f"{icon} {message}"
    print(color_text(text, style=style))


def _terminal_width() -> int:
    try:
        columns = shutil.get_terminal_size((DEFAULT_WIDTH, 20)).columns
    except OSError:
        columns = DEFAULT_WIDTH
    return max(MIN_WIDTH, min(columns, 100))


def print_banner(title: str, subtitle: str | None = None) -> None:
    width = _terminal_width()
    line = "=" * width
    print(color_text(line, style="accent"))
    print(color_text(title.center(width), style="accent", bold=True))
    if subtitle:
        print(color_text(subtitle.center(width), style="muted"))
    print(color_text(line, style="accent"))


def _stringify(body: str | Iterable[str] | None) -> str:
    if body is None:
        return ""
    if isinstance(body, str):
        return body
    if isinstance(body, (list, tuple, set)):
        return "\n".join(str(item) for item in body)
    if isinstance(body, dict):
        try:
            return json.dumps(body, indent=2, ensure_ascii=False)
        except TypeError:
            return str(body)
    return str(body)


def _wrap_lines(text: str, width: int) -> list[str]:
    if width <= 0:
        return [text]
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        stripped = raw_line.rstrip()
        if not stripped:
            lines.append("")
            continue
        wrapped = textwrap.wrap(
            stripped,
            width=width,
            replace_whitespace=False,
            drop_whitespace=False,
        )
        lines.extend(wrapped or [""])
    return lines or [""]


def format_panel(
    title: str,
    body: str | Iterable[str] | None,
    *,
    style: str = "accent",
    width: int | None = None,
) -> str:
    max_width = width or _terminal_width()
    max_width = max(MIN_WIDTH, min(max_width, 100))
    inner_width = max_width - 4
    text = _stringify(body)
    content_lines = _wrap_lines(text, inner_width)
    full_width = inner_width + 4

    frame_color = style if style in PALETTE else "accent"
    top_border = "+" + "=" * (full_width - 2) + "+"
    bottom_border = "+" + "=" * (full_width - 2) + "+"
    header_text = (title.strip() or "MESSAGE")[: full_width - 4]
    header_line = header_text.center(full_width - 2)
    separator = "|" + "-" * (full_width - 2) + "|"

    lines = [
        color_text(top_border, style=frame_color),
        color_text("|", style=frame_color)
        + color_text(header_line, style="muted", bold=True)
        + color_text("|", style=frame_color),
        color_text(separator, style=frame_color),
    ]

    left = color_text("|", style=frame_color)
    right = color_text("|", style=frame_color)
    for line in content_lines:
        padded = line.ljust(inner_width)
        lines.append(f"{left} {padded} {right}")

    lines.append(color_text(bottom_border, style=frame_color))
    return "\n".join(lines)


def print_panel(
    title: str,
    body: str | Iterable[str] | None,
    *,
    style: str = "accent",
    width: int | None = None,
) -> None:
    print(format_panel(title, body, style=style, width=width))


def print_phase_header(phase_num: int, phase_title: str) -> None:
    """Print a Claude Code-style phase header."""
    header = f"PHASE {phase_num} – {phase_title.upper()}"
    width = _terminal_width()
    separator = "=" * width

    print()
    print(color_text(separator, style="accent", bold=True))
    print(color_text(header.center(width), style="accent", bold=True))
    print(color_text(separator, style="accent", bold=True))
    print()


def print_confidence_score(description: str, confidence: int) -> None:
    """Print an issue with its confidence score."""
    # Determine color based on confidence
    if confidence >= 90:
        style = "error"
        badge = "[CRITICAL]"
    elif confidence >= 80:
        style = "warning"
        badge = "[HIGH]"
    elif confidence >= 50:
        style = "info"
        badge = "[MEDIUM]"
    else:
        style = "muted"
        badge = "[LOW]"

    confidence_text = f"{confidence}/100"
    print(f"{color_text(badge, style=style, bold=True)} {description} {color_text(f'({confidence_text})', style='muted')}")


def print_agent_results_summary(agent_results: list, result_type: str = "findings") -> None:
    """
    Print a summary of specialized agent results.

    Args:
        agent_results: List of AgentResult objects
        result_type: Type of results ("findings", "issues", "files")
    """
    if not agent_results:
        print_status("No agent results to display.", "info")
        return

    for idx, result in enumerate(agent_results, 1):
        header = f"Agent {idx}: {result.agent_name}"

        if result_type == "files" and result.key_files:
            body = ["Key files to read:"] + [f"  {i+1}. {f}" for i, f in enumerate(result.key_files)]
            print_panel(header, body, style="info")

        elif result_type == "issues" and result.issues:
            issues_text = [f"Found {len(result.issues)} issues:"]
            for issue in result.issues:
                conf = issue.get("confidence", 0)
                desc = issue.get("description", "Unknown issue")
                loc = issue.get("location", "")
                issues_text.append(f"\n  • {desc}")
                if loc:
                    issues_text.append(f"    Location: {loc}")
                issues_text.append(f"    Confidence: {conf}/100")

            print_panel(header, "\n".join(issues_text), style="warning")

        elif result_type == "findings":
            # Show truncated findings
            findings = result.findings[:500] + "..." if len(result.findings) > 500 else result.findings
            print_panel(header, findings, style="assistant")


def print_file_citation(file_path: str, line_num: int = None, description: str = "") -> None:
    """Print a file citation with line number."""
    if line_num:
        citation = f"{file_path}:{line_num}"
    else:
        citation = file_path

    if description:
        print(f"  {color_text('→', style='accent', bold=True)} {color_text(citation, style='info')} - {description}")
    else:
        print(f"  {color_text('→', style='accent', bold=True)} {color_text(citation, style='info')}")


def print_divider(char: str = "-", style: str = "muted") -> None:
    """Print a horizontal divider."""
    width = _terminal_width()
    print(color_text(char * width, style=style))


def print_plan_mode_indicator(mode: str) -> None:
    """Print the current mode indicator."""
    if mode.upper() == "PLAN":
        badge = "[PLAN MODE]"
        style = "info"
        desc = "Interactive planning with questions"
    else:
        badge = "[EXECUTION MODE]"
        style = "success"
        desc = "Direct plan and execute"

    print()
    print(color_text(f"{badge} {desc}", style=style, bold=True))
    print()


def print_interactive_plan(plan_dict: dict, show_details: bool = True) -> None:
    """Print an interactive plan with steps and questions."""
    width = _terminal_width()

    # Header
    print()
    print(color_text("=" * width, style="accent", bold=True))
    print(color_text("INTERACTIVE PLAN".center(width), style="accent", bold=True))
    print(color_text("=" * width, style="accent", bold=True))
    print()

    # Mode
    mode = plan_dict.get("mode", "single")
    print(f"{color_text('Execution Mode:', style='muted')} {color_text(mode.upper(), style='info', bold=True)}")
    print()

    # Steps
    steps = plan_dict.get("steps", [])
    if steps:
        print(color_text("STEPS:", style="assistant", bold=True))
        for i, step in enumerate(steps, 1):
            step_id = step.get("id", f"step{i}")
            desc = step.get("description", "No description")
            print(f"  {color_text(f'{i}.', style='accent', bold=True)} [{color_text(step_id, style='muted')}] {desc}")
        print()

    # Questions
    questions = plan_dict.get("questions", [])
    if questions and show_details:
        print(color_text("QUESTIONS:", style="warning", bold=True))
        print(color_text("Answer these questions to customize the execution.", style="muted"))
        print()

        # Group by category
        categories = {}
        for q in questions:
            cat = q.get("category", "general")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(q)

        for category, cat_questions in categories.items():
            print(color_text(f"  [{category.upper()}]", style="info", bold=True))

            for q in cat_questions:
                q_id = q.get("id", "unknown")
                question = q.get("question", "")
                choices = q.get("choices", [])
                default = q.get("default")
                allow_custom = q.get("allow_custom", True)

                print(f"    {color_text('Q:', style='warning', bold=True)} [{color_text(q_id, style='accent')}] {question}")

                for i, choice in enumerate(choices, 1):
                    default_marker = color_text(" ← default", style="success") if choice == default else ""
                    print(f"       {i}. {choice}{default_marker}")

                if allow_custom:
                    print(f"       {len(choices) + 1}. {color_text('(Custom answer)', style='muted')}")

                print(f"       {color_text(f'Answer with: /answer {q_id}:<your choice or custom text>', style='tool')}")
                print()

    print(color_text("=" * width, style="accent"))
    print()


def print_plan_status(plan) -> None:
    """Print the status of questions in a plan."""
    answered = len(plan.answers)
    total = len(plan.questions)
    remaining = total - answered

    if remaining == 0:
        status_text = color_text("✓ All questions answered!", style="success", bold=True)
        next_step = color_text("Use /execute-plan to run the plan.", style="info")
    else:
        status_text = f"{color_text(f'{answered}/{total}', style='warning', bold=True)} questions answered"
        next_step = color_text(f"{remaining} question(s) remaining. Use /show-plan to review.", style="muted")

    print()
    print(status_text)
    print(next_step)
    print()
