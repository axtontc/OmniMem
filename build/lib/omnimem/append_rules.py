import os

rules = """
## 14. Full Implementations Only (MANDATORY)
Never use stubbed, simulated, fake, or mocked code. You MUST provide complete, fully functional implementations for all logic, functions, and architecture components. 

## 15. Single Timer Constraint (MANDATORY)
If you have started a background timer or scheduled a task, you MUST NOT start another one until the first timer finishes. Execute timers strictly one at a time to prevent overlapping background tasks and race conditions.
"""

path = r"C:\Users\axton\.gemini\config\AGENTS.md"
with open(path, "a", encoding="utf-8") as f:
    f.write(rules)
