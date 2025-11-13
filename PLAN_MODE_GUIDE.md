# Plan Mode - Interactive Planning Guide

## Overview

Plan Mode is an interactive planning feature that allows you to review and customize the agent's execution plan before it starts working. Instead of immediately executing tasks, the agent creates a detailed plan with questions for you to answer, ensuring the implementation matches your exact requirements and preferences.

## Modes

The Universal Agent supports two operating modes:

### 1. **Execution Mode** (Default)
- Agent plans and executes immediately
- Minimal user interaction during planning
- Fast for straightforward tasks
- Best for: Quick operations, well-defined tasks, research

### 2. **Plan Mode** (Interactive)
- Agent creates a detailed plan first
- Presents questions about approach, implementation, tools, etc.
- User answers questions to customize the execution
- Agent executes plan after all questions are answered
- Best for: Complex features, architecture decisions, customizable workflows

## Commands

### Mode Switching

```bash
/plan-mode              # Switch to interactive Plan mode
/execution-mode         # Switch back to default Execution mode
```

### Working with Plans

```bash
/show-plan              # Display current plan and question status
/answer <id>:<choice>   # Answer a question (see examples below)
/execute-plan           # Execute plan after all questions answered
```

## Workflow Example

### Step 1: Enable Plan Mode

```
You >> /plan-mode
[i] Switched to PLAN MODE. The agent will create a detailed plan with questions before executing.
```

### Step 2: Request a Task

```
You >> Build a REST API for user authentication with JWT tokens
```

### Step 3: Review the Plan

The agent will create a plan with steps and questions:

```
================================================================================
                            INTERACTIVE PLAN
================================================================================

Execution Mode: SEQUENTIAL

STEPS:
  1. [design] Design the API endpoints and data models
  2. [implement_auth] Implement JWT token generation and validation
  3. [implement_endpoints] Create authentication endpoints (login, register, refresh)
  4. [security] Add security middleware and rate limiting
  5. [testing] Write tests for authentication flows
  6. [docs] Document the API endpoints

QUESTIONS:
Answer these questions to customize the execution.

  [APPROACH]
    Q: [q1] Which web framework should we use?
       1. Flask ← default
       2. FastAPI
       3. Django REST Framework
       4. (Custom answer)
       Answer with: /answer q1:<your choice or custom text>

    Q: [q2] How should we handle password storage?
       1. bcrypt with salt ← default
       2. argon2
       3. PBKDF2
       4. (Custom answer)
       Answer with: /answer q2:<your choice or custom text>

  [IMPLEMENTATION]
    Q: [q3] Should we include refresh token rotation?
       1. Yes, implement automatic rotation ← default
       2. No, simple refresh tokens
       3. (Custom answer)
       Answer with: /answer q3:<your choice or custom text>

  [TESTING]
    Q: [q4] What testing approach should we use?
       1. Unit tests + integration tests ← default
       2. Unit tests only
       3. Integration tests only
       4. (Custom answer)
       Answer with: /answer q4:<your choice or custom text>

================================================================================
```

### Step 4: Answer Questions

Answer each question using the `/answer` command:

```
You >> /answer q1:FastAPI
[i] Answer recorded for q1. 3 question(s) remaining.

You >> /answer q2:bcrypt with salt
[i] Answer recorded for q2. 2 question(s) remaining.

You >> /answer q3:Yes, implement automatic rotation
[i] Answer recorded for q3. 1 question(s) remaining.

You >> /answer q4:Unit tests + integration tests
[i] Answer recorded for q4. All questions answered! Use /execute-plan to run.
```

You can also provide custom answers:

```
You >> /answer q1:Use Flask with JWT-Extended library for better token management
[i] Answer recorded for q1. 3 question(s) remaining.
```

### Step 5: Review Your Choices (Optional)

```
You >> /show-plan
```

This displays the plan again with your answers marked.

### Step 6: Execute the Plan

```
You >> /execute-plan
```

The agent will now execute the plan using your preferences:

```
Execute the following plan with the user's preferences:

=== INTERACTIVE PLAN ===
Mode: sequential

Steps:
1. [design] Design the API endpoints and data models
2. [implement_auth] Implement JWT token generation and validation
3. [implement_endpoints] Create authentication endpoints (login, register, refresh)
4. [security] Add security middleware and rate limiting
5. [testing] Write tests for authentication flows
6. [docs] Document the API endpoints

User Preferences:
• Which web framework should we use?
  Answer: FastAPI
• How should we handle password storage?
  Answer: bcrypt with salt
• Should we include refresh token rotation?
  Answer: Yes, implement automatic rotation
• What testing approach should we use?
  Answer: Unit tests + integration tests
```

## Question Categories

Questions are grouped into categories for better organization:

- **approach**: High-level strategy and architecture decisions
- **implementation**: Specific implementation choices (libraries, patterns, etc.)
- **testing**: Testing and validation approaches
- **tools**: Which tools/libraries to use
- **scope**: What features to include or exclude

## Advanced Usage

### Switching Modes Mid-Task

You can switch modes at any time:

```
You >> /execution-mode
[i] Switched to EXECUTION MODE. The agent will plan and execute immediately.
```

Any active plan will be cleared when switching to execution mode.

### Complex Custom Answers

For questions requiring detailed explanations, you can provide multi-word answers:

```
You >> /answer q1:Use FastAPI with SQLAlchemy ORM, PostgreSQL database, and Alembic for migrations
[i] Answer recorded for q1. 3 question(s) remaining.
```

### Partial Planning

If you switch to execution mode before answering all questions, the plan will be cleared. You can start fresh with a new request.

## Best Practices

### When to Use Plan Mode

✅ **Use Plan Mode for:**
- Complex feature development with multiple approaches
- Projects where architecture choices matter
- Tasks requiring specific tool/library selections
- Work that needs user approval before proceeding
- Learning/educational contexts where you want to see options

❌ **Use Execution Mode for:**
- Quick one-off tasks
- Well-defined operations with clear requirements
- Research and information gathering
- Bug fixes with known solutions
- File operations and simple edits

### Tips for Better Plans

1. **Be specific in your requests**: More detailed requests lead to better questions
   - ✅ "Build a REST API for user authentication with OAuth2 and social login"
   - ❌ "Make an API"

2. **Review all questions before answering**: Understand the full scope first

3. **Use defaults when appropriate**: Defaults are chosen based on best practices

4. **Provide context in custom answers**: Help the agent understand your requirements
   - ✅ "/answer q1:Flask because we're already using it in other microservices"
   - ❌ "/answer q1:Flask"

5. **Check the plan before executing**: Use `/show-plan` to review your choices

## Integration with Workflows

Plan Mode works seamlessly with other workflow features:

```bash
# You can use both Plan Mode and feature-dev workflow
/plan-mode
/feature-dev Add user authentication system
# Answer the questions
# Then execute
/execute-plan
```

## Troubleshooting

### Plan Not Appearing

If you request a task but don't see a plan with questions:

1. Verify you're in Plan mode: `/plan-mode`
2. Request might be too simple for interactive planning
3. Try a more complex task or switch to execution mode

### Questions Not Matching Your Needs

The agent generates questions based on common decision points. If questions don't cover your specific needs:

1. Use custom answers to provide detailed specifications
2. After execution starts, you can refine with additional requests
3. Provide more context in your initial request

### Can't Execute Plan

If `/execute-plan` doesn't work:

```
[!] Cannot execute: 2 question(s) still unanswered.
```

Use `/show-plan` to see which questions need answers.

## Examples

### Example 1: Web Scraper

```
You >> /plan-mode
You >> Build a web scraper for e-commerce product prices
```

Possible questions:
- Which scraping library? (BeautifulSoup, Scrapy, Selenium, Playwright)
- How to handle dynamic content? (Wait for JS, API extraction, headless browser)
- Data storage format? (CSV, JSON, Database)
- Error handling approach? (Retry logic, logging, alerting)

### Example 2: Data Analysis Pipeline

```
You >> /plan-mode
You >> Create a data analysis pipeline for customer churn prediction
```

Possible questions:
- Which ML framework? (scikit-learn, TensorFlow, PyTorch)
- Feature engineering approach? (Automated, manual selection, both)
- Model selection? (Logistic regression, random forest, neural network, ensemble)
- Validation strategy? (Cross-validation, train-test split, time-based split)
- Deployment format? (Pickle file, ONNX, REST API)

### Example 3: Documentation Generator

```
You >> /plan-mode
You >> Generate API documentation from Python code
```

Possible questions:
- Documentation format? (Sphinx, MkDocs, pdoc, custom)
- Docstring style? (Google, NumPy, reStructuredText)
- Include examples? (Yes with auto-generation, manual only, none)
- Output format? (HTML, Markdown, PDF, all)

## API Reference

### PlanModeManager Methods

```python
# Get current mode
mode = plan_mode_manager.get_mode()  # Returns AgentMode enum

# Switch modes
plan_mode_manager.set_mode(AgentMode.PLAN)
plan_mode_manager.set_mode(AgentMode.EXECUTION)

# Check mode
is_plan_mode = plan_mode_manager.is_plan_mode()

# Get active plan
plan = plan_mode_manager.get_active_plan()

# Answer question
success = plan_mode_manager.answer_question("q1", "FastAPI", is_custom=False)

# Check if ready to execute
can_run = plan_mode_manager.can_execute()

# Get plan context for execution
context = plan_mode_manager.get_plan_context()
```

## Technical Details

### Plan Structure

```python
{
    "mode": "single" | "sequential" | "parallel",
    "steps": [
        {"id": "step1", "description": "What to do..."},
        {"id": "step2", "description": "Next step..."}
    ],
    "questions": [
        {
            "id": "q1",
            "question": "Which approach?",
            "choices": ["Option A", "Option B", "Option C"],
            "allow_custom": True,
            "default": "Option A",
            "category": "approach"
        }
    ]
}
```

### Execution Modes

- **single**: All steps can run in one go
- **sequential**: Steps must run in order (dependencies)
- **parallel**: Steps can run concurrently (no dependencies)

## See Also

- [Claude Integration Guide](CLAUDE_CODE_INTEGRATION.md) - Workflow features
- [README](README.md) - Main documentation
- [Release Notes](RELEASE_NOTES.md) - Version history
