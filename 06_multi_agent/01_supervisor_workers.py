"""
Stage 6: Multi-Agent Orchestration (Supervisor & Specialist Workers)
--------------------------------------------------------------------
Mental Model:
1. The Tool Confusion Problem:
   Giving one single agent 30 tools causes hallucinations and prompt bloat.
2. The Solution: Multi-Agent Teams (Orchestrator-Worker Pattern):
   - Worker 1 (Log Detective): Specialist with log search tools.
   - Worker 2 (System Auditor): Specialist with system and filesystem tools.
   - Supervisor (Incident Commander): Has NO low-level tools. Its only tools
     are delegating tasks to Worker 1 and Worker 2!
3. Hierarchical Execution:
   The Commander plans the investigation, delegates subtasks, receives reports,
   and writes the final executive post-mortem.
"""

import os
import sys
import platform
import shutil
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in .env!")
    sys.exit(1)

client = genai.Client(api_key=api_key)
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# ==========================================
# 1. Specialist Worker 1: Log Detective
# ==========================================
def search_log_file(log_path: str, filter_keyword: str = None) -> dict:
    """Searches a log file for errors, warnings, or specific keywords."""
    p = Path(log_path)
    if not p.exists():
        return {"error": f"Log file '{log_path}' not found."}
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if filter_keyword:
        kw = filter_keyword.lower()
        matched = [l.strip() for l in lines if kw in l.lower()]
    else:
        matched = [l.strip() for l in lines]
    return {"log": str(p), "matched_count": len(matched), "recent_lines": matched[-15:]}

LOG_WORKER_CONFIG = types.GenerateContentConfig(
    system_instruction="You are a Log Detective Specialist. You analyze log files to find timestamps, error codes, and root causes. Be concise.",
    tools=[search_log_file],
)

def run_log_detective_agent(instruction: str) -> str:
    """Delegates a log investigation task to the specialized Log Detective Agent."""
    print(f"\n   🕵️  [LOG DETECTIVE WORKER ACTIVATED]")
    print(f"       Instruction: {instruction}")
    
    # Autonomous call for the worker
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=instruction,
        config=LOG_WORKER_CONFIG
    )
    result = response.text or "Log analysis completed."
    print(f"       Log Detective Report: {result[:100]}...")
    return result


# ==========================================
# 2. Specialist Worker 2: System Auditor
# ==========================================
def get_system_metrics() -> dict:
    """Returns OS name, architecture, CPU count, and root disk usage."""
    total, used, free = shutil.disk_usage("/")
    return {
        "os": platform.system(),
        "arch": platform.machine(),
        "cpu_cores": os.cpu_count(),
        "disk_free_gb": round(free / (1024**3), 2),
        "disk_total_gb": round(total / (1024**3), 2),
    }

def list_directory(directory_path: str = ".") -> dict:
    """Lists files and directories at directory_path."""
    p = Path(directory_path)
    if not p.exists():
        return {"error": f"Path '{directory_path}' does not exist"}
    return {"items": [item.name for item in p.iterdir()][:20]}

AUDIT_WORKER_CONFIG = types.GenerateContentConfig(
    system_instruction="You are a System Infrastructure Auditor. You inspect host resources, OS metrics, and directory contents. Be concise.",
    tools=[get_system_metrics, list_directory],
)

def run_system_auditor_agent(instruction: str) -> str:
    """Delegates a system or filesystem inspection task to the System Auditor Agent."""
    print(f"\n   ⚙️  [SYSTEM AUDITOR WORKER ACTIVATED]")
    print(f"       Instruction: {instruction}")
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=instruction,
        config=AUDIT_WORKER_CONFIG
    )
    result = response.text or "System audit completed."
    print(f"       System Auditor Report: {result[:100]}...")
    return result


# ==========================================
# 3. The Supervisor: Incident Commander
# ==========================================
# NOTICE: The Commander's tools are the WORKER AGENTS THEMSELVES!
SUPERVISOR_TOOLS = [
    run_log_detective_agent,
    run_system_auditor_agent,
]

SUPERVISOR_CONFIG = types.GenerateContentConfig(
    system_instruction="""
You are the Incident Commander (Supervisor Agent).
You lead an SRE response team. You DO NOT run bash commands or grep logs yourself.
Instead, you delegate tasks to your two specialist workers:
  1. run_log_detective_agent: for inspecting log files and errors.
  2. run_system_auditor_agent: for checking system health, OS metrics, and files.

Workflow:
- Break the user's incident report into sub-goals.
- Delegate sub-goals to the appropriate worker.
- Once you have reports from both specialists, synthesize a complete Executive Post-Mortem.
""",
    tools=SUPERVISOR_TOOLS,
)

def orchestrate_incident(incident_report: str):
    print("=" * 65)
    print("👑 INCIDENT COMMANDER ACTIVATED (Orchestrator-Worker Team)")
    print(f"📋 INCIDENT REPORT: {incident_report}")
    print("=" * 65)

    # Use a stateful chat so the commander remembers worker responses
    chat = client.chats.create(
        model=MODEL_NAME,
        config=SUPERVISOR_CONFIG
    )

    response = chat.send_message(incident_report)

    print("\n" + "=" * 65)
    print("🏁 [EXECUTIVE INCIDENT POST-MORTEM & RESOLUTION]")
    print("=" * 65)
    print(response.text)
    print("=" * 65)


# ==========================================
# 4. Interactive CLI Entrypoint
# ==========================================
if __name__ == "__main__":
    print("=" * 65)
    print("👑 Interactive Multi-Agent Incident Commander Ready")
    print("=" * 65)
    print("Options:")
    print("  - Type your own incident description")
    print("  - Type '1' for the sample Checkout API 504 outage")
    print("  - Type 'exit' or 'quit' to end")
    print("=" * 65)

    while True:
        try:
            user_prompt = input("\nEnter Incident for Commander: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nCommander signing off.")
            break

        if not user_prompt:
            continue

        if user_prompt.lower() in ("exit", "quit"):
            print("Commander signing off. Goodbye!")
            break

        if user_prompt == "1":
            user_prompt = (
                "We have a high-priority incident on the checkout service. "
                "First, have the Log Detective check '05_devops_capstones/mock_server/app_backend.log' for errors. "
                "Second, have the System Auditor check host metrics and disk space to see if the server is healthy. "
                "Then synthesize a unified post-mortem report."
            )

        orchestrate_incident(user_prompt)

