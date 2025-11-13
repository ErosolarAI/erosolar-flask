from __future__ import annotations

import textwrap
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Deque, Dict, Iterable, List, Literal, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage


@dataclass
class WorkflowPhase:
    key: str
    title: str
    focus: str
    instructions: str
    requires_confirmation: bool = False


@dataclass
class WorkflowPreset:
    slug: str
    title: str
    description: str
    phases: List[WorkflowPhase]
    general_rules: List[str]


@dataclass
class WorkflowState:
    preset: WorkflowPreset
    goal: str
    started_at: datetime
    source: str
    current_phase_index: int = 0
    phase_confirmations: Dict[int, bool] = None
    phase_data: Dict[int, Any] = None  # Store data from each phase (e.g., files to read, approaches)

    def __post_init__(self):
        if self.phase_confirmations is None:
            self.phase_confirmations = {}
        if self.phase_data is None:
            self.phase_data = {}


@dataclass
class WorkflowNotification:
    kind: Literal["info", "warning", "panel"]
    body: str
    title: Optional[str] = None


def _wrap_lines(block: Iterable[str]) -> str:
    return "\n".join(textwrap.dedent(line).strip() for line in block if line is not None).strip()


FEATURE_DEV_PRESET = WorkflowPreset(
    slug="feature-dev",
    title="Feature Development Workflow",
    description=_wrap_lines(
        [
            "Seven explicit phases inspired by Claude Code's /feature-dev command.",
            "Designed for large coding tasks that require planning, architecture choices, code implementation, review, and documentation.",
        ]
    ),
    general_rules=[
        "Always announce the active phase as 'PHASE X – Name' at the top of each reply.",
        "Do not skip phases. Wait for the user's answers whenever a phase demands approval or clarification.",
        "Use the existing tool suite (git, glob_files, grep_files, edit_file, run_shell, manage_todos, etc.) exactly as the base agent would.",
        "Summarize concrete findings, cite files with path:line references, and keep a running todo list via manage_todos when appropriate.",
        "Never lose other Erosolar capabilities: you may still research, browse, or edit files normally while honoring this workflow overlay.",
    ],
    phases=[
        WorkflowPhase(
            key="phase1",
            title="Phase 1 – Discovery",
            focus="Understand the problem and constraints.",
            instructions=(
                "Clarify the feature request, restate the user problem, capture constraints, and highlight unknowns."
                " End the phase with a confirmation checklist before moving on."
            ),
            requires_confirmation=True,
        ),
        WorkflowPhase(
            key="phase2",
            title="Phase 2 – Codebase Exploration",
            focus="Map relevant files and existing implementations.",
            instructions=(
                "Launch multiple investigations (think independent code-explorer agents) focusing on similar features, architecture layers, and"
                " integration points. Use glob_files, grep_files, git_log, and read_text to cite concrete paths and line numbers."
            ),
        ),
        WorkflowPhase(
            key="phase3",
            title="Phase 3 – Clarifying Questions",
            focus="Resolve ambiguities before designing.",
            instructions=(
                "List targeted questions covering edge cases, integrations, error handling, performance, and backward compatibility."
                " Stop and wait for user answers before moving ahead."
            ),
            requires_confirmation=True,
        ),
        WorkflowPhase(
            key="phase4",
            title="Phase 4 – Architecture Design",
            focus="Present multiple approaches and pick one.",
            instructions=(
                "Design at least three approaches (minimal change, clean architecture, pragmatic balance). Compare trade-offs, cite impacted files,"
                " and explicitly ask the user to choose or confirm the recommended option."
            ),
            requires_confirmation=True,
        ),
        WorkflowPhase(
            key="phase5",
            title="Phase 5 – Implementation",
            focus="Execute the chosen plan safely.",
            instructions=(
                "Before touching files, request explicit approval to proceed. Implement incrementally, referencing relevant files, keeping git diff clean,"
                " and updating manage_todos to track sub-work. Use edit_file/run_shell/gIT as needed."
            ),
            requires_confirmation=True,
        ),
        WorkflowPhase(
            key="phase6",
            title="Phase 6 – Quality Review",
            focus="Launch specialized review passes.",
            instructions=(
                "Emulate multiple reviewers (simplicity, bug catching, conventions). Summarize issues with severity + confidence."
                " Ask the user whether to fix now, defer, or accept as-is before taking action."
            ),
            requires_confirmation=True,
        ),
        WorkflowPhase(
            key="phase7",
            title="Phase 7 – Summary",
            focus="Document what was built and next steps.",
            instructions=(
                "Summarize completed work, key decisions, touched files, testing status, and suggested follow-ups."
                " Close any related todos."
            ),
        ),
    ],
)


WORKFLOWS: Dict[str, WorkflowPreset] = {
    FEATURE_DEV_PRESET.slug: FEATURE_DEV_PRESET,
}


class WorkflowManager:
    """Tracks active Claude-style workflows and emits UI notifications."""

    def __init__(self) -> None:
        self.state: Optional[WorkflowState] = None
        self._notifications: Deque[WorkflowNotification] = deque()
        self._specialized_agents_available = False

        # Try to import specialized agents module
        try:
            from specialized_agents import SpecializedAgentsManager
            self._agents_manager = SpecializedAgentsManager()
            self._specialized_agents_available = True
        except ImportError:
            self._agents_manager = None

    def activate(self, slug: str, goal: str, source: str) -> List[BaseMessage]:
        preset = WORKFLOWS.get(slug)
        if not preset:
            raise ValueError(f"Unknown workflow '{slug}'.")
        goal_text = goal or "Work with the user to define the feature goal before continuing."
        self.state = WorkflowState(
            preset=preset,
            goal=goal_text,
            started_at=datetime.utcnow(),
            source=source,
        )
        system_prompt = self._build_system_prompt(preset, goal_text)
        panel_text = self._render_panel(preset, goal_text)
        self.notify("panel", panel_text, title=preset.title)
        return [SystemMessage(content=system_prompt)]

    def clear(self) -> None:
        if self.state is not None:
            self.notify("info", f"Cleared workflow '{self.state.preset.title}'.")
        self.state = None

    def status_text(self) -> Optional[str]:
        if not self.state:
            return None
        preset = self.state.preset
        return self._render_panel(preset, self.state.goal)

    def pop_notifications(self) -> List[WorkflowNotification]:
        items = list(self._notifications)
        self._notifications.clear()
        return items

    def notify(self, kind: Literal["info", "warning", "panel"], body: str, title: Optional[str] = None):
        self._notifications.append(WorkflowNotification(kind=kind, body=body, title=title))

    def get_current_phase(self) -> Optional[WorkflowPhase]:
        """Get the current active phase."""
        if not self.state:
            return None
        if self.state.current_phase_index >= len(self.state.preset.phases):
            return None
        return self.state.preset.phases[self.state.current_phase_index]

    def advance_phase(self) -> bool:
        """
        Advance to the next phase.

        Returns:
            True if advanced, False if no more phases
        """
        if not self.state:
            return False

        self.state.current_phase_index += 1

        if self.state.current_phase_index >= len(self.state.preset.phases):
            # Workflow complete
            self.notify("info", f"Workflow '{self.state.preset.title}' completed!")
            return False

        # Notify about new phase
        phase = self.get_current_phase()
        if phase:
            self.notify("panel", f"Phase {self.state.current_phase_index + 1}: {phase.title}\n\n{phase.focus}", title="New Phase")

        return True

    def confirm_phase(self, phase_index: Optional[int] = None) -> bool:
        """
        Mark a phase as confirmed by the user.

        Args:
            phase_index: Index of phase to confirm, or None for current phase

        Returns:
            True if phase can now advance
        """
        if not self.state:
            return False

        if phase_index is None:
            phase_index = self.state.current_phase_index

        self.state.phase_confirmations[phase_index] = True

        phase = self.state.preset.phases[phase_index]
        if phase.requires_confirmation:
            self.notify("info", f"Phase {phase_index + 1} ({phase.title}) confirmed by user.")

        return True

    def is_phase_confirmed(self, phase_index: Optional[int] = None) -> bool:
        """Check if a phase has been confirmed."""
        if not self.state:
            return False

        if phase_index is None:
            phase_index = self.state.current_phase_index

        phase = self.state.preset.phases[phase_index]

        # If phase doesn't require confirmation, it's always "confirmed"
        if not phase.requires_confirmation:
            return True

        return self.state.phase_confirmations.get(phase_index, False)

    def store_phase_data(self, key: str, data: Any, phase_index: Optional[int] = None):
        """Store data associated with a phase."""
        if not self.state:
            return

        if phase_index is None:
            phase_index = self.state.current_phase_index

        if phase_index not in self.state.phase_data:
            self.state.phase_data[phase_index] = {}

        self.state.phase_data[phase_index][key] = data

    def get_phase_data(self, key: str, phase_index: Optional[int] = None) -> Any:
        """Retrieve data associated with a phase."""
        if not self.state:
            return None

        if phase_index is None:
            phase_index = self.state.current_phase_index

        if phase_index not in self.state.phase_data:
            return None

        return self.state.phase_data[phase_index].get(key)

    def get_phase_header(self) -> Optional[str]:
        """Get formatted phase header for output."""
        if not self.state:
            return None

        phase = self.get_current_phase()
        if not phase:
            return None

        return f"PHASE {self.state.current_phase_index + 1} – {phase.title.upper()}"

    def _build_system_prompt(self, preset: WorkflowPreset, goal: str) -> str:
        lines: List[str] = [
            f"You are running the Claude Code '{preset.title}' workflow inside the Erosolar Universal Agent.",
            "Retain every default capability and safety rule, but add the workflow contract below.",
            f"Feature goal: {goal}",
            "",
            "General workflow rules:",
        ]
        for rule in preset.general_rules:
            lines.append(f"- {rule}")
        lines.append("")
        lines.append("Phase breakdown:")
        for idx, phase in enumerate(preset.phases, start=1):
            require_note = " (wait for user confirmation before moving on)" if phase.requires_confirmation else ""
            lines.append(f"{idx}. {phase.title}{require_note}")
            lines.append(f"   Focus: {phase.focus}")
            lines.append(f"   Instructions: {phase.instructions}")
        lines.append("")
        lines.append(
            "During implementation and git workflows you must continue to use the normal tool usage discipline"
            " (explain why a tool is needed, run it, observe results, and update the plan)."
        )
        lines.append(
            "Ask the user for explicit approval when required by a phase, and pause until you receive it."
            " Surface options and trade-offs clearly so the user can choose."
        )
        return "\n".join(lines).strip()

    def _render_panel(self, preset: WorkflowPreset, goal: str) -> str:
        bullet_lines = [f"Goal: {goal}", ""]
        bullet_lines.append("Phases:")
        for idx, phase in enumerate(preset.phases, start=1):
            flag = " (wait for user)" if phase.requires_confirmation else ""
            bullet_lines.append(f"{idx}. {phase.title}{flag}")
        return "\n".join(bullet_lines)


class SlashCommandRouter:
    """Translates Claude Code-style slash commands into agent-ready prompts."""

    def __init__(self, workflow_manager: WorkflowManager, plan_mode_manager=None) -> None:
        self.workflow_manager = workflow_manager
        self.plan_mode_manager = plan_mode_manager
        self._handlers = {
            "feature_dev": self._handle_feature_dev,
            "feature-dev": self._handle_feature_dev,
            "commit": self._handle_commit,
            "commit_push_pr": self._handle_commit_push_pr,
            "commit-push-pr": self._handle_commit_push_pr,
            "clean_gone": self._handle_clean_gone,
            "clean-gone": self._handle_clean_gone,
            "code_review": self._handle_code_review,
            "code-review": self._handle_code_review,
            "workflow_clear": self._handle_workflow_clear,
            "workflow-clear": self._handle_workflow_clear,
            "plan_mode": self._handle_plan_mode,
            "plan-mode": self._handle_plan_mode,
            "execution_mode": self._handle_execution_mode,
            "execution-mode": self._handle_execution_mode,
            "exec_mode": self._handle_execution_mode,
            "exec-mode": self._handle_execution_mode,
            "answer": self._handle_answer,
            "show_plan": self._handle_show_plan,
            "show-plan": self._handle_show_plan,
            "execute_plan": self._handle_execute_plan,
            "execute-plan": self._handle_execute_plan,
        }

        # Load plugin commands
        self._load_plugin_commands()

    def _load_plugin_commands(self):
        """Load commands from plugins and register them."""
        try:
            from plugin_loader import get_plugin_loader
            loader = get_plugin_loader()

            for cmd_name, cmd_def in loader.commands.items():
                # Create a handler for this plugin command
                def make_handler(command_def):
                    def handler(argument: str, source: str) -> List[BaseMessage]:
                        # Expand $ARGUMENTS placeholder
                        content = command_def.content.replace("$ARGUMENTS", argument or "")

                        return [HumanMessage(
                            content=content,
                            name=f"command:{command_def.name}",
                        )]
                    return handler

                # Register with both dash and underscore versions
                normalized_name = cmd_name.replace('-', '_')
                self._handlers[normalized_name] = make_handler(cmd_def)
                self._handlers[cmd_name] = make_handler(cmd_def)

        except ImportError:
            # plugin_loader not available
            pass

    def transform(self, text: str, source: str) -> List[BaseMessage]:
        stripped = (text or "").strip()
        if not stripped or not stripped.startswith("/"):
            return [HumanMessage(content=text, name=source)]

        body = stripped[1:]
        command, _, rest = body.partition(" ")
        key = command.replace("-", "_").lower()
        handler = self._handlers.get(key)
        if handler is None:
            # Unknown command: fall back to raw text but notify the user.
            self.workflow_manager.notify(
                "warning",
                f"Unknown command '/{command}'. Sending literal text to the agent.",
            )
            return [HumanMessage(content=text, name=source)]
        return handler(rest.strip(), source)

    # ---- Individual handlers -------------------------------------------------

    def _handle_feature_dev(self, argument: str, source: str) -> List[BaseMessage]:
        goal = argument or "Work with the user to define the feature or improvement."
        workflow_msgs = self.workflow_manager.activate("feature-dev", goal, source)
        kickoff = textwrap.dedent(
            f"""
            /feature-dev invoked by {source}.
            Feature goal: {goal}
            Start Phase 1 (Discovery) now. Surface what you know, list uncertainties, and ask the user targeted
            questions before moving to Phase 2. Remember: announce the phase name at the very top of each reply.
            """
        ).strip()
        kickoff_msg = HumanMessage(content=kickoff, name="command:feature-dev")
        return workflow_msgs + [kickoff_msg]

    def _handle_commit(self, _: str, source: str) -> List[BaseMessage]:
        prompt = textwrap.dedent(
            f"""
            /commit command from {source}.
            Follow the Claude Code git workflow:
            1. Inspect git status and diff (staged + unstaged). Cite files when summarizing.
            2. Review recent commit messages to match the repository's voice.
            3. Stage the right files (avoid secrets or generated artifacts).
            4. Draft a concise commit message (optionally in Conventional Commit style if repo uses it) and show it to the user.
            5. Ask for confirmation before running git_commit if anything is unclear; otherwise run git_commit with add_all=True.
            6. Show the resulting git_status/git_log summary.
            Always explain each tool you call and ensure the commit actually reflects current changes.
            """
        ).strip()
        return [HumanMessage(content=prompt, name="command:commit")]

    def _handle_commit_push_pr(self, _: str, source: str) -> List[BaseMessage]:
        prompt = textwrap.dedent(
            f"""
            /commit-push-pr command from {source}.
            Execute the combined workflow:
            - If currently on main/master, create a descriptive feature branch (git checkout -b ...).
            - Summarize staged/unstaged changes and craft a commit as in /commit.
            - Push the branch to origin. If push fails (no remote, auth issues), explain and ask for guidance.
            - Use the GitHub CLI (`gh pr create`) when available to open a pull request with:
              • Summary (2-3 bullet points)
              • Test plan checklist
              • Attribution that the change was generated via the universal agent
            - Return the PR URL and next steps.
            Always narrate planned shell commands before execution and confirm destructive actions with the user.
            """
        ).strip()
        return [HumanMessage(content=prompt, name="command:commit-push-pr")]

    def _handle_clean_gone(self, _: str, source: str) -> List[BaseMessage]:
        prompt = textwrap.dedent(
            f"""
            /clean_gone command from {source}.
            Clean up local git branches marked as [gone]:
            1. Enumerate local branches and worktrees.
            2. Identify branches whose upstream is gone.
            3. Remove related worktrees safely before deleting the branch.
            4. Delete the local branches and report what changed. If nothing to clean, state that explicitly.
            Require confirmation if more than five branches will be removed.
            """
        ).strip()
        return [HumanMessage(content=prompt, name="command:clean-gone")]

    def _handle_code_review(self, _: str, source: str) -> List[BaseMessage]:
        prompt = textwrap.dedent(
            f"""
            /code-review command from {source}.
            Perform an automated PR review inspired by Claude Code:
            - Detect the current branch's upstream PR (git status / gh pr view) and skip if closed, draft, or already reviewed.
            - Gather CLAUDE.md guideline files or other convention docs (glob_files/grep_files).
            - Summarize the PR changes (files touched, risk areas).
            - Run multiple passes (conceptually independent agents): guideline compliance, bug detection, historical context (git blame/log).
            - Score each issue 0-100 for confidence and only report issues ≥80 unless the user asks otherwise.
            - Present findings grouped by severity with direct file:line links (use git rev-parse HEAD for the SHA).
            - Ask the user whether to fix now, file follow-ups, or approve as-is.
            If GitHub CLI is available, prepare a comment body that could be posted via `gh pr comment`, but do not post automatically unless asked.
            """
        ).strip()
        return [HumanMessage(content=prompt, name="command:code-review")]

    def _handle_workflow_clear(self, _: str, __: str) -> List[BaseMessage]:
        self.workflow_manager.clear()
        # Swallow the command by returning an empty list. The caller should skip invoking the agent.
        return []

    def _handle_plan_mode(self, _: str, source: str) -> List[BaseMessage]:
        """Switch to Plan mode."""
        if not self.plan_mode_manager:
            self.workflow_manager.notify(
                "warning",
                "Plan mode manager not available."
            )
            return []

        from plan_mode import AgentMode
        self.plan_mode_manager.set_mode(AgentMode.PLAN)
        self.workflow_manager.notify(
            "info",
            "Switched to PLAN MODE. The agent will create a detailed plan with questions before executing."
        )
        return []

    def _handle_execution_mode(self, _: str, source: str) -> List[BaseMessage]:
        """Switch to Execution mode."""
        if not self.plan_mode_manager:
            return []

        from plan_mode import AgentMode
        self.plan_mode_manager.set_mode(AgentMode.EXECUTION)
        self.plan_mode_manager.clear_plan()
        self.workflow_manager.notify(
            "info",
            "Switched to EXECUTION MODE. The agent will plan and execute immediately."
        )
        return []

    def _handle_answer(self, argument: str, source: str) -> List[BaseMessage]:
        """Answer a question from the interactive plan."""
        if not self.plan_mode_manager:
            return []

        # Parse answer format: question_id:answer
        # e.g., /answer q1:Option A
        # or /answer q1:My custom answer
        if not argument or ":" not in argument:
            self.workflow_manager.notify(
                "warning",
                "Invalid answer format. Use: /answer question_id:your_answer"
            )
            return []

        question_id, _, answer = argument.partition(":")
        question_id = question_id.strip()
        answer = answer.strip()

        if not question_id or not answer:
            self.workflow_manager.notify(
                "warning",
                "Both question ID and answer are required."
            )
            return []

        # Check if there's an active plan
        plan = self.plan_mode_manager.get_active_plan()
        if not plan:
            self.workflow_manager.notify(
                "warning",
                "No active plan. Request a task in plan mode first."
            )
            return []

        # Find the question
        question = None
        for q in plan.questions:
            if q.id == question_id:
                question = q
                break

        if not question:
            self.workflow_manager.notify(
                "warning",
                f"Question '{question_id}' not found in plan."
            )
            return []

        # Determine if answer is custom or a choice
        is_custom = answer not in question.choices

        # Store the answer
        self.plan_mode_manager.answer_question(question_id, answer, is_custom)

        # Notify user
        remaining = len(plan.get_unanswered_questions())
        if remaining == 0:
            self.workflow_manager.notify(
                "info",
                f"Answer recorded for {question_id}. All questions answered! Use /execute-plan to run."
            )
        else:
            self.workflow_manager.notify(
                "info",
                f"Answer recorded for {question_id}. {remaining} question(s) remaining."
            )

        return []

    def _handle_show_plan(self, _: str, source: str) -> List[BaseMessage]:
        """Show the current plan and its status."""
        if not self.plan_mode_manager:
            return []

        plan = self.plan_mode_manager.get_active_plan()
        if not plan:
            self.workflow_manager.notify(
                "info",
                "No active plan. Create a plan by requesting a task in plan mode."
            )
            return []

        from plan_mode import format_plan_summary, format_questions_for_display

        # Show plan summary
        plan_text = format_plan_summary(plan)
        self.workflow_manager.notify("panel", plan_text, title="Current Plan")

        # Show questions with their status
        lines = []
        for q in plan.questions:
            if q.id in plan.answers:
                ans = plan.answers[q.id]
                status = f"✓ Answered: {ans.answer}"
            else:
                status = "○ Unanswered"
            lines.append(f"{status} [{q.id}] {q.question}")

        self.workflow_manager.notify("panel", "\n".join(lines), title="Question Status")

        return []

    def _handle_execute_plan(self, _: str, source: str) -> List[BaseMessage]:
        """Execute the current plan after all questions are answered."""
        if not self.plan_mode_manager:
            return []

        if not self.plan_mode_manager.can_execute():
            plan = self.plan_mode_manager.get_active_plan()
            if not plan:
                self.workflow_manager.notify(
                    "warning",
                    "No active plan to execute."
                )
            else:
                remaining = plan.get_unanswered_questions()
                self.workflow_manager.notify(
                    "warning",
                    f"Cannot execute: {len(remaining)} question(s) still unanswered."
                )
            return []

        # Get plan context
        context = self.plan_mode_manager.get_plan_context()

        # Create a message to execute the plan
        prompt = textwrap.dedent(
            f"""
            Execute the following plan with the user's preferences:

            {context}

            Follow the plan steps and use the user's answers to customize the implementation.
            Be thorough and precise.
            """
        ).strip()

        # Clear the plan after execution starts
        self.plan_mode_manager.clear_plan()

        return [HumanMessage(content=prompt, name="command:execute-plan")]
