"""
Plan Mode System - Interactive planning with user Q&A before execution.

This module provides a Plan mode that can be toggled from the default Execution mode.
In Plan mode, the agent creates a detailed plan with questions for the user to answer
before executing the plan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage


class AgentMode(Enum):
    """Operating mode for the agent."""
    EXECUTION = "execution"  # Default: plan and execute immediately
    PLAN = "plan"  # Interactive: create plan, ask questions, then execute


@dataclass
class PlanQuestion:
    """A question the planner wants to ask before execution."""
    id: str
    question: str
    choices: List[str]  # Pre-determined choices
    allow_custom: bool = True  # Allow user to provide custom answer
    default: Optional[str] = None
    category: str = "general"  # For grouping questions (e.g., "approach", "implementation", "testing")


@dataclass
class PlanAnswer:
    """User's answer to a plan question."""
    question_id: str
    answer: str
    is_custom: bool = False  # True if user provided custom text vs selecting choice
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class InteractivePlan:
    """A plan with questions that need to be answered before execution."""
    mode: str  # "single", "sequential", "parallel"
    steps: List[Dict[str, str]]  # Same as original Plan
    questions: List[PlanQuestion]
    answers: Dict[str, PlanAnswer] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_complete(self) -> bool:
        """Check if all questions have been answered."""
        return len(self.answers) == len(self.questions)

    def get_unanswered_questions(self) -> List[PlanQuestion]:
        """Get list of questions that haven't been answered yet."""
        answered_ids = set(self.answers.keys())
        return [q for q in self.questions if q.id not in answered_ids]

    def add_answer(self, question_id: str, answer: str, is_custom: bool = False):
        """Add an answer to a question."""
        self.answers[question_id] = PlanAnswer(
            question_id=question_id,
            answer=answer,
            is_custom=is_custom
        )

    def to_context_string(self) -> str:
        """Convert plan and answers to a context string for the executor."""
        lines = [
            "=== INTERACTIVE PLAN ===",
            f"Mode: {self.mode}",
            "",
            "Steps:",
        ]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"{i}. [{step['id']}] {step['description']}")

        if self.answers:
            lines.extend([
                "",
                "User Preferences:",
            ])
            for q in self.questions:
                if q.id in self.answers:
                    ans = self.answers[q.id]
                    custom_flag = " (custom)" if ans.is_custom else ""
                    lines.append(f"• {q.question}")
                    lines.append(f"  Answer: {ans.answer}{custom_flag}")

        return "\n".join(lines)


class PlanModeManager:
    """Manages the agent's operating mode and interactive planning state."""

    def __init__(self):
        self.current_mode: AgentMode = AgentMode.EXECUTION
        self.active_plan: Optional[InteractivePlan] = None
        self._mode_history: List[tuple[datetime, AgentMode]] = []

    def get_mode(self) -> AgentMode:
        """Get current operating mode."""
        return self.current_mode

    def set_mode(self, mode: AgentMode):
        """Set operating mode."""
        if mode != self.current_mode:
            self._mode_history.append((datetime.utcnow(), self.current_mode))
            self.current_mode = mode
            # Clear active plan when switching to execution mode
            if mode == AgentMode.EXECUTION:
                self.active_plan = None

    def is_plan_mode(self) -> bool:
        """Check if currently in Plan mode."""
        return self.current_mode == AgentMode.PLAN

    def create_plan(self, mode: str, steps: List[Dict[str, str]], questions: List[PlanQuestion]) -> InteractivePlan:
        """Create a new interactive plan."""
        self.active_plan = InteractivePlan(
            mode=mode,
            steps=steps,
            questions=questions
        )
        return self.active_plan

    def get_active_plan(self) -> Optional[InteractivePlan]:
        """Get the current active plan."""
        return self.active_plan

    def answer_question(self, question_id: str, answer: str, is_custom: bool = False) -> bool:
        """
        Answer a question in the active plan.

        Returns:
            True if answer was added, False if no active plan or invalid question_id
        """
        if not self.active_plan:
            return False

        # Verify question exists
        question_ids = {q.id for q in self.active_plan.questions}
        if question_id not in question_ids:
            return False

        self.active_plan.add_answer(question_id, answer, is_custom)
        return True

    def can_execute(self) -> bool:
        """Check if plan is ready for execution (all questions answered)."""
        if not self.active_plan:
            return False
        return self.active_plan.is_complete()

    def clear_plan(self):
        """Clear the active plan."""
        self.active_plan = None

    def get_plan_context(self) -> Optional[str]:
        """Get plan context string for executor."""
        if not self.active_plan:
            return None
        return self.active_plan.to_context_string()


# ===== Plan Generation Prompts =====

INTERACTIVE_PLANNER_SYSTEM = """You are a planning agent operating in INTERACTIVE PLAN MODE.

Your task is to:
1. Analyze the user's request
2. Design a concrete plan with specific steps
3. Identify key decisions and questions that would benefit from user input
4. Present questions to the user BEFORE execution begins

When generating a plan, you must output JSON in this exact format:
{
  "mode": "single" | "sequential" | "parallel",
  "steps": [
    {"id": "step1", "description": "What to do..."},
    {"id": "step2", "description": "What to do next..."}
  ],
  "questions": [
    {
      "id": "q1",
      "question": "Clear question text?",
      "choices": ["Option A", "Option B", "Option C"],
      "allow_custom": true,
      "default": "Option A",
      "category": "approach"
    }
  ]
}

Question Categories:
- "approach": High-level strategy/architecture questions
- "implementation": Specific implementation choices
- "testing": Testing and validation approach
- "tools": Which tools/libraries to use
- "scope": What to include/exclude

Question Design Guidelines:
- Ask questions where user preference matters (UI/UX, architecture patterns, etc.)
- Provide 2-4 concrete choices whenever possible
- Allow custom answers for flexibility
- Set sensible defaults
- Keep questions focused and specific
- Avoid yes/no questions - ask "which" or "how" instead

Available tools for workers/executors:
WEB & SEARCH: tavily_search, tavily_extract, web_search_simple, get_weather
CODE EXECUTION: run_python, run_shell
FILE OPS: list_directory, read_text, write_text, edit_file, glob_files, grep_files
GIT: git_status, git_diff, git_commit, git_log
AUTOMATION: save_shell_automation, headless_browse
JUPYTER: edit_notebook_cell
CODE ANALYSIS: analyze_code_quality
TASK MANAGEMENT: manage_todos
PERSISTENT: tool_library, research_vault, self_improve

Focus on creating actionable steps and meaningful questions that help customize the execution to the user's needs.
"""


def create_planner_messages(user_request: str, mode: AgentMode) -> List[BaseMessage]:
    """Create messages for the planner based on the mode."""
    if mode == AgentMode.PLAN:
        return [
            SystemMessage(content=INTERACTIVE_PLANNER_SYSTEM),
            HumanMessage(content=user_request)
        ]
    else:
        # Use the original planner system for execution mode
        # This will be the default behavior
        return None  # Signal to use default planning


def parse_interactive_plan(planner_response: BaseMessage) -> Optional[InteractivePlan]:
    """Parse planner response into an InteractivePlan."""
    try:
        # Try to extract JSON from the response
        content = getattr(planner_response, "content", "")

        if isinstance(content, str):
            # Try to find JSON in the content
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                json_str = content[start:end + 1]
                data = json.loads(json_str)
            else:
                return None
        elif isinstance(content, dict):
            data = content
        else:
            return None

        # Parse the data
        mode = data.get("mode", "single")
        steps = data.get("steps", [])
        questions_data = data.get("questions", [])

        # Convert questions to PlanQuestion objects
        questions = []
        for q_data in questions_data:
            question = PlanQuestion(
                id=q_data.get("id", f"q{len(questions) + 1}"),
                question=q_data.get("question", ""),
                choices=q_data.get("choices", []),
                allow_custom=q_data.get("allow_custom", True),
                default=q_data.get("default"),
                category=q_data.get("category", "general")
            )
            questions.append(question)

        return InteractivePlan(
            mode=mode,
            steps=steps,
            questions=questions
        )

    except (json.JSONDecodeError, KeyError, AttributeError):
        return None


def format_questions_for_display(questions: List[PlanQuestion]) -> str:
    """Format questions for CLI display."""
    if not questions:
        return "No questions to answer."

    lines = ["=" * 80, "PLAN QUESTIONS", "=" * 80, ""]

    # Group by category
    categories: Dict[str, List[PlanQuestion]] = {}
    for q in questions:
        cat = q.category or "general"
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(q)

    for category, cat_questions in categories.items():
        lines.append(f"[{category.upper()}]")
        lines.append("")

        for q in cat_questions:
            lines.append(f"Question {q.id}: {q.question}")
            lines.append("Choices:")
            for i, choice in enumerate(q.choices, 1):
                default_marker = " (default)" if choice == q.default else ""
                lines.append(f"  {i}. {choice}{default_marker}")
            if q.allow_custom:
                lines.append(f"  {len(q.choices) + 1}. Custom (enter your own)")
            lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


def format_plan_summary(plan: InteractivePlan) -> str:
    """Format plan summary for display."""
    lines = [
        "=" * 80,
        "EXECUTION PLAN",
        "=" * 80,
        "",
        f"Mode: {plan.mode}",
        "",
        "Steps:",
    ]

    for i, step in enumerate(plan.steps, 1):
        lines.append(f"{i}. [{step['id']}] {step['description']}")

    lines.extend(["", "=" * 80])
    return "\n".join(lines)
