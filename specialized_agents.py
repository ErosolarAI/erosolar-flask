"""
Specialized Agents for Erosolar Universal Agent
================================================
Implements Claude Code-style specialized agents for:
- Code exploration and tracing
- Architecture design
- Code review with confidence scoring

These agents run in parallel for different perspectives and return
structured results that can be aggregated and filtered.
"""

import concurrent.futures
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


@dataclass
class AgentResult:
    """Result from a specialized agent."""
    agent_type: Literal["explorer", "architect", "reviewer"]
    agent_name: str
    findings: str
    key_files: List[str] = None
    issues: List[Dict[str, Any]] = None
    confidence: Optional[int] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.key_files is None:
            self.key_files = []
        if self.issues is None:
            self.issues = []
        if self.metadata is None:
            self.metadata = {}


class SpecializedAgentsManager:
    """Manages specialized agent execution."""

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        Initialize the specialized agents manager.

        Args:
            llm: LangChain LLM to use for agents. If None, uses DeepSeek default.
        """
        self.llm = llm
        if self.llm is None:
            # Use DeepSeek by default
            import os
            self.llm = ChatOpenAI(
                model=os.environ.get("DEEPSEEK_MODEL", "deepseek-reasoner"),
                temperature=0,
                api_key=os.environ.get("DEEPSEEK_API_KEY"),
                base_url=os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
            )

    def launch_code_explorers(
        self,
        prompts: List[str],
        context: str = "",
        max_workers: int = 3,
    ) -> List[AgentResult]:
        """
        Launch multiple code-explorer agents in parallel.

        Args:
            prompts: List of exploration prompts (e.g., "Find similar features to X")
            context: Additional context for all agents
            max_workers: Max parallel agents

        Returns:
            List of AgentResult objects with findings and key files
        """
        system_prompt = """You are an expert code analyst specializing in tracing and understanding feature implementations.

## Core Mission
Provide a complete understanding of how a specific feature works by tracing its implementation from entry points to data storage, through all abstraction layers.

## Analysis Approach

1. **Feature Discovery**: Find entry points (APIs, UI components, CLI commands), locate core implementation files, map feature boundaries
2. **Code Flow Tracing**: Follow call chains, trace data transformations, identify dependencies, document state changes
3. **Architecture Analysis**: Map abstraction layers, identify design patterns, document interfaces, note cross-cutting concerns
4. **Implementation Details**: Key algorithms, error handling, edge cases, performance considerations

## Output Requirements

Provide comprehensive analysis including:
- Entry points with file:line references
- Step-by-step execution flow with data transformations
- Key components and their responsibilities
- Architecture insights: patterns, layers, design decisions
- Dependencies (external and internal)
- **List of 5-10 key files to read for deep understanding** (CRITICAL)
- Observations about strengths, issues, or opportunities

Format your response as:
```
## Analysis
[Your detailed analysis]

## Key Files to Read
1. path/to/file1.ext:line - Reason
2. path/to/file2.ext:line - Reason
...

## Summary
[Brief summary of findings]
```
"""

        def run_explorer(prompt: str) -> AgentResult:
            messages = [
                SystemMessage(content=system_prompt),
            ]
            if context:
                messages.append(HumanMessage(content=f"Context:\n{context}\n\n"))
            messages.append(HumanMessage(content=prompt))

            response = self.llm.invoke(messages)
            content = response.content if isinstance(response.content, str) else str(response.content)

            # Extract key files from response
            key_files = self._extract_key_files(content)

            return AgentResult(
                agent_type="explorer",
                agent_name=f"code-explorer-{prompts.index(prompt) + 1}",
                findings=content,
                key_files=key_files,
            )

        # Run explorers in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_explorer, prompt) for prompt in prompts]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        return results

    def launch_code_architects(
        self,
        feature_description: str,
        codebase_context: str,
        approaches: List[str],
        max_workers: int = 3,
    ) -> List[AgentResult]:
        """
        Launch multiple code-architect agents in parallel.

        Args:
            feature_description: What needs to be built
            codebase_context: Findings from code exploration
            approaches: List of approaches to design (e.g., ["minimal", "clean", "pragmatic"])
            max_workers: Max parallel agents

        Returns:
            List of AgentResult objects with architecture designs
        """
        system_prompt = """You are an expert software architect specializing in designing elegant, maintainable solutions.

## Core Mission
Design a concrete implementation approach for the requested feature, considering the existing codebase patterns and constraints.

## Design Approach

1. **Understand Constraints**: Analyze existing architecture, identify integration points, consider technical debt
2. **Design Solution**: Create concrete implementation plan, specify files to create/modify, define interfaces
3. **Identify Trade-offs**: Complexity vs simplicity, performance vs maintainability, speed vs quality
4. **Provide Blueprint**: Step-by-step implementation guide, key design decisions, potential pitfalls

## Output Requirements

Provide detailed architecture design including:
- **Approach name and summary** (1-2 sentences)
- **Files to create/modify** with specific changes
- **Key design decisions** and rationale
- **Trade-offs** (pros and cons)
- **Implementation complexity** (1-5 scale)
- **Estimated effort** (small/medium/large)
- **Risk assessment** (low/medium/high)

Format your response as:
```
## Approach: [Name]
[Summary]

## Files to Modify/Create
1. path/to/file.ext - [Change description]
2. ...

## Key Design Decisions
- Decision 1: [Rationale]
- Decision 2: [Rationale]

## Trade-offs
**Pros:**
- Pro 1
- Pro 2

**Cons:**
- Con 1
- Con 2

## Complexity: [1-5]
## Effort: [small/medium/large]
## Risk: [low/medium/high]
```
"""

        def run_architect(approach: str) -> AgentResult:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Feature to build:\n{feature_description}\n\nCodebase context:\n{codebase_context}\n\nDesign approach: {approach}\n\nProvide a detailed architecture design following this approach."),
            ]

            response = self.llm.invoke(messages)
            content = response.content if isinstance(response.content, str) else str(response.content)

            # Extract metadata (complexity, effort, risk)
            metadata = self._extract_architect_metadata(content)

            return AgentResult(
                agent_type="architect",
                agent_name=f"code-architect-{approach}",
                findings=content,
                metadata=metadata,
            )

        # Run architects in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_architect, approach) for approach in approaches]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        return results

    def launch_code_reviewers(
        self,
        code_context: str,
        review_focuses: List[str],
        max_workers: int = 3,
    ) -> List[AgentResult]:
        """
        Launch multiple code-reviewer agents in parallel.

        Args:
            code_context: Code to review (changes, files, etc.)
            review_focuses: List of review focuses (e.g., ["simplicity", "bugs", "conventions"])
            max_workers: Max parallel agents

        Returns:
            List of AgentResult objects with issues and confidence scores
        """
        system_prompt = """You are an expert code reviewer specializing in identifying bugs, complexity, and convention violations.

## Core Mission
Review code changes and identify real issues, filtering out false positives and nitpicks.

## Review Approach

1. **Understand Changes**: Read the code carefully, understand intent, identify modified areas
2. **Apply Focus**: Review through your assigned lens (simplicity/bugs/conventions)
3. **Find Real Issues**: Identify bugs, complexity, violations - avoid false positives
4. **Score Confidence**: Rate each issue 0-100 for confidence it's real

## Confidence Scoring

- **0-25**: Low confidence, might be false positive, pre-existing, or nitpick
- **25-50**: Moderate confidence, could be real but not certain
- **50-75**: High confidence, likely real issue but not critical
- **75-100**: Very high confidence, definitely real and important issue

## Output Requirements

For each issue found, provide:
- **Description**: Clear, specific issue description
- **Location**: File path and line number
- **Severity**: low/medium/high/critical
- **Confidence**: 0-100 score
- **Reason**: Why this is an issue
- **Suggestion**: How to fix (optional)

Format your response as:
```
## Review Focus: [Your focus area]

### Issues Found

#### Issue 1: [Brief description]
- **Location**: `path/to/file.ext:line`
- **Severity**: [low/medium/high/critical]
- **Confidence**: [0-100]
- **Reason**: [Why this is an issue]
- **Suggestion**: [How to fix]

#### Issue 2: ...

## Summary
[Count and overview of issues]
```

If no issues found, output:
```
## Review Focus: [Your focus area]

No issues found in this review pass.
```
"""

        def run_reviewer(focus: str) -> AgentResult:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Code to review:\n{code_context}\n\nReview focus: {focus}\n\nPerform a thorough review focusing on {focus}. Remember to score confidence for each issue."),
            ]

            response = self.llm.invoke(messages)
            content = response.content if isinstance(response.content, str) else str(response.content)

            # Extract issues with confidence scores
            issues = self._extract_review_issues(content)

            return AgentResult(
                agent_type="reviewer",
                agent_name=f"code-reviewer-{focus}",
                findings=content,
                issues=issues,
            )

        # Run reviewers in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_reviewer, focus) for focus in review_focuses]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        return results

    def _extract_key_files(self, content: str) -> List[str]:
        """Extract key files from explorer output."""
        key_files = []
        in_files_section = False

        for line in content.split('\n'):
            line = line.strip()

            # Detect key files section
            if 'key files' in line.lower() or 'files to read' in line.lower():
                in_files_section = True
                continue

            # End of section
            if in_files_section and (line.startswith('##') or line.startswith('**')):
                in_files_section = False

            # Extract file paths
            if in_files_section and line:
                # Look for patterns like "1. path/to/file.ext" or "- path/to/file.ext"
                import re
                match = re.search(r'[0-9\-\*\.]+\s+([a-zA-Z0-9_/.:-]+\.[a-zA-Z]+)', line)
                if match:
                    key_files.append(match.group(1))

        return key_files

    def _extract_architect_metadata(self, content: str) -> Dict[str, Any]:
        """Extract metadata from architect output."""
        metadata = {
            "complexity": None,
            "effort": None,
            "risk": None,
        }

        for line in content.split('\n'):
            line = line.strip().lower()

            if line.startswith('## complexity:') or line.startswith('**complexity:**'):
                try:
                    metadata["complexity"] = int(line.split(':')[-1].strip().split()[0])
                except (ValueError, IndexError):
                    pass

            if line.startswith('## effort:') or line.startswith('**effort:**'):
                effort = line.split(':')[-1].strip()
                if 'small' in effort:
                    metadata["effort"] = "small"
                elif 'large' in effort:
                    metadata["effort"] = "large"
                else:
                    metadata["effort"] = "medium"

            if line.startswith('## risk:') or line.startswith('**risk:**'):
                risk = line.split(':')[-1].strip()
                if 'low' in risk:
                    metadata["risk"] = "low"
                elif 'high' in risk:
                    metadata["risk"] = "high"
                else:
                    metadata["risk"] = "medium"

        return metadata

    def _extract_review_issues(self, content: str) -> List[Dict[str, Any]]:
        """Extract issues with confidence scores from reviewer output."""
        issues = []
        current_issue = None

        for line in content.split('\n'):
            line = line.strip()

            # Detect new issue
            if line.startswith('####') or (line.startswith('**Issue') and '**' in line):
                if current_issue and current_issue.get('confidence', 0) > 0:
                    issues.append(current_issue)

                # Extract issue description
                description = line.replace('####', '').replace('**', '').replace('Issue', '').strip()
                description = description.split(':')[-1].strip() if ':' in description else description

                current_issue = {
                    "description": description,
                    "location": "",
                    "severity": "medium",
                    "confidence": 0,
                    "reason": "",
                    "suggestion": "",
                }

            # Extract issue fields
            if current_issue:
                if '**location:**' in line.lower() or '- location:' in line.lower():
                    location = line.split(':', 1)[-1].strip().replace('`', '')
                    current_issue["location"] = location

                elif '**severity:**' in line.lower() or '- severity:' in line.lower():
                    severity = line.split(':', 1)[-1].strip().lower()
                    current_issue["severity"] = severity

                elif '**confidence:**' in line.lower() or '- confidence:' in line.lower():
                    try:
                        confidence = int(line.split(':', 1)[-1].strip().split()[0])
                        current_issue["confidence"] = confidence
                    except (ValueError, IndexError):
                        pass

                elif '**reason:**' in line.lower() or '- reason:' in line.lower():
                    reason = line.split(':', 1)[-1].strip()
                    current_issue["reason"] = reason

                elif '**suggestion:**' in line.lower() or '- suggestion:' in line.lower():
                    suggestion = line.split(':', 1)[-1].strip()
                    current_issue["suggestion"] = suggestion

        # Add last issue
        if current_issue and current_issue.get('confidence', 0) > 0:
            issues.append(current_issue)

        return issues


# Convenience functions

def launch_parallel_explorers(
    prompts: List[str],
    context: str = "",
    llm: Optional[ChatOpenAI] = None,
) -> List[AgentResult]:
    """Launch code-explorer agents in parallel."""
    manager = SpecializedAgentsManager(llm=llm)
    return manager.launch_code_explorers(prompts, context)


def launch_parallel_architects(
    feature_description: str,
    codebase_context: str,
    approaches: List[str] = None,
    llm: Optional[ChatOpenAI] = None,
) -> List[AgentResult]:
    """Launch code-architect agents in parallel."""
    if approaches is None:
        approaches = ["minimal", "clean", "pragmatic"]

    manager = SpecializedAgentsManager(llm=llm)
    return manager.launch_code_architects(feature_description, codebase_context, approaches)


def launch_parallel_reviewers(
    code_context: str,
    review_focuses: List[str] = None,
    confidence_threshold: int = 80,
    llm: Optional[ChatOpenAI] = None,
) -> List[AgentResult]:
    """
    Launch code-reviewer agents in parallel.

    Args:
        code_context: Code to review
        review_focuses: List of review focuses
        confidence_threshold: Only return issues with confidence >= this
        llm: Optional LLM to use

    Returns:
        List of AgentResult objects with filtered issues
    """
    if review_focuses is None:
        review_focuses = ["simplicity", "bugs", "conventions"]

    manager = SpecializedAgentsManager(llm=llm)
    results = manager.launch_code_reviewers(code_context, review_focuses)

    # Filter issues by confidence threshold
    for result in results:
        result.issues = [
            issue for issue in result.issues
            if issue.get("confidence", 0) >= confidence_threshold
        ]

    return results
