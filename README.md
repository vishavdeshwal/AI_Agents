# AI Agents from Scratch for DevOps Engineers

Welcome to the completed hands-on AI Agent masterclass!

## 📌 Complete Course Roadmap

- [x] **Stage 0: The Foundry**
  - [x] Initialized modern environment with `uv` (`google-genai`, `python-dotenv`)
  - [x] Connected to Gemini API (`gemini-3.5-flash-lite`) and tracked token costs
  - [x] File: `00_foundry/01_ping_gemini.py`
- [x] **Stage 1: Context & The Conversation Loop (Simulating Memory)**
  - [x] Overcame LLM amnesia by building an interactive terminal chat REPL
  - [x] Managed conversation history and observed token growth per turn
  - [x] File: `01_core_mechanics/01_chat_with_memory.py`
- [x] **Stage 2: Giving Hands to the Brain (Read-Only Tool Calling)**
  - [x] Defined native Python tools with docstrings & type hints
  - [x] Understood the `FunctionCall` and `FunctionResponse` wire protocol
  - [x] Built cross-platform metrics, directory listing, and file reader tools
  - [x] File: `02_tool_calling/01_readonly_tools.py`
- [x] **Stage 3: The ReAct Autonomous Engine (Zero Black-Box)**
  - [x] Built the raw `while` loop: Reason -> Act -> Observe -> Repeat
  - [x] Disabled automatic SDK calling (`AutomaticFunctionCallingConfig(disable=True)`)
  - [x] Implemented circuit breakers (`MAX_TURNS = 10`) and self-healing
  - [x] File: `03_react_loop/01_autonomous_agent.py`
- [x] **Stage 4: State, Persistence & Compaction (SQLite Memory)**
  - [x] Gave the agent permanent disk storage using Python's built-in `sqlite3`
  - [x] Implemented a sliding window context compactor to prune old tool outputs
  - [x] Added smart session search and auto-resume CLI menu
  - [x] File: `04_memory_and_state/01_persistent_agent.py`
- [x] **Stage 5: Production DevOps Capstone (Incident SRE with Security Gate)**
  - [x] Built an autonomous Incident Responder with shell execution powers
  - [x] Created a Human-in-the-Loop (HITL) gate for dangerous commands (`rm`, `kill`)
  - [x] Investigated a mock 504 outage and completed a post-mortem
  - [x] File: `05_devops_capstones/01_incident_sre_agent.py`
- [x] **Stage 6: Multi-Agent Systems & Framework Deep Dive**
  - [x] Built an Orchestrator-Worker team (Incident Commander + 2 Specialists)
  - [x] File: `06_multi_agent/01_supervisor_workers.py`
  - [x] Created the Framework Rosetta Stone (LangGraph, CrewAI, AutoGen)
  - [x] File: `06_multi_agent/FRAMEWORK_TRANSLATION_GUIDE.md`

---

## 🚀 How to Run Stage 6

Run the multi-agent incident drill:
```bash
uv run python 06_multi_agent/01_supervisor_workers.py
```
Watch the Incident Commander delegate tasks to the Log Detective and the System Auditor, and synthesize a complete Executive Post-Mortem!
