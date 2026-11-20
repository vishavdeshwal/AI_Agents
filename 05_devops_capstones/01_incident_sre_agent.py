"""
Stage 5 Capstone: Autonomous SRE Incident Responder with Human-in-the-Loop Gate
--------------------------------------------------------------------------------
Mental Model:
1. Real DevOps agents must be able to remediate issues, not just talk.
2. Giving an agent raw shell access is dangerous without guardrails.
3. The Solution: A Human-in-the-Loop (HITL) Security Gate:
   - Read-only commands (grep, cat, ls, df, ps) execute automatically.
   - Mutating/destructive commands (rm, kill, systemctl, chmod) pause the loop
     and require explicit human authorization [y/N] in the terminal!
"""

import os
import sys
import re
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ==========================================
# 1. Human-in-the-Loop Security Gate & Tools
# ==========================================

DANGEROUS_PATTERNS = [
    r"\brm\b", r"\bkill\b", r"\bpkill\b", r"\bsystemctl\b",
    r"\bchmod\b", r"\bchown\b", r"\btruncate\b", r"\bdd\b",
    r"\breboot\b", r"\bshutdown\b", r"\bmkfs\b", r">>"
]

def is_dangerous(command: str) -> bool:
    """Checks if a shell command contains potentially destructive operations."""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            return True
    return False

def execute_shell_command(command: str) -> dict:
    """
    Executes a shell command.
    Safe read commands execute automatically.
    Destructive commands (rm, kill, systemctl) require human authorization.
    """
    if is_dangerous(command):
        print("\n" + "!" * 65)
        print("🚨 [HUMAN-IN-THE-LOOP SECURITY GATE TRIGGERED]")
        print(f"The SRE Agent wants to execute: '{command}'")
        print("!" * 65)
        
        try:
            approval = input("👉 Authorize this command? [y/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            approval = "n"

        if approval != "y":
            print("   ⛔ [PERMISSION DENIED] Command execution was blocked by human operator.\n")
            return {
                "status": "denied",
                "error": f"Human operator DENIED permission to run '{command}'. Please propose an alternative or explain why it is needed."
            }
        print("   ✅ [PERMISSION GRANTED] Human operator authorized execution.\n")

    print(f"   💻 [SHELL EXEC] Running: {command}")
    try:
        res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)
        return {
            "exit_code": res.returncode,
            "stdout": res.stdout[:2000] if res.stdout else "",
            "stderr": res.stderr[:1000] if res.stderr else "",
        }
    except Exception as e:
        return {"error": str(e)}

def search_log_file(log_path: str, filter_keyword: str = None, max_lines: int = 40) -> dict:
    """
    Reads a log file and optionally filters for lines containing filter_keyword
    (e.g., 'ERROR', 'WARN', 'FATAL', 'Timeout').
    """
    print(f"   🔍 [LOG SEARCH] {log_path} (keyword='{filter_keyword}')")
    try:
        p = Path(log_path)
        if not p.exists():
            return {"error": f"Log file '{log_path}' not found."}

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if filter_keyword:
            kw = filter_keyword.lower()
            matched = [line.strip() for line in lines if kw in line.lower()]
        else:
            matched = [line.strip() for line in lines]

        return {
            "log_file": str(p),
            "total_matches": len(matched),
            "lines": matched[-max_lines:],  # Return the latest matches
        }
    except Exception as e:
        return {"error": str(e)}

def inspect_json_config(config_path: str) -> dict:
    """Reads and parses a JSON configuration file."""
    print(f"   📄 [CONFIG INSPECT] {config_path}")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}

TOOL_REGISTRY = {
    "execute_shell_command": execute_shell_command,
    "search_log_file": search_log_file,
    "inspect_json_config": inspect_json_config,
}

# ==========================================
# 2. SQLite Incident Persistence
# ==========================================
DB_PATH = Path("agent_memory.db")

def log_incident_step(session_id: str, turn: int, step_type: str, details: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incident_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp TIMESTAMP,
            turn INTEGER,
            step_type TEXT,
            details_json TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO incident_logs (session_id, timestamp, turn, step_type, details_json)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, datetime.now().isoformat(), turn, step_type, json.dumps(details)))
    conn.commit()
    conn.close()

# ==========================================
# 3. Autonomous Incident Engine
# ==========================================
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

SYSTEM_INSTRUCTION = """
You are an expert DevOps Site Reliability Engineer (SRE).
Your mission is to autonomously investigate outages, server failures, and degraded services.
Methodology:
1. Search and inspect logs to identify the exact root cause and timestamps.
2. Inspect configuration files or system state related to the failure.
3. Propose or execute remediation actions using shell commands.
4. Remember: Destructive commands like 'rm' or 'kill' will pause for human confirmation.
5. Provide a crisp Post-Mortem summary: Root Cause, Actions Taken, and Prevention Recommendations.
"""

AGENT_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_INSTRUCTION,
    tools=[execute_shell_command, search_log_file, inspect_json_config],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)

MAX_TURNS = 10

def triage_incident(incident_id: str, incident_report: str):
    print("\n" + "=" * 65)
    print(f"🚨 ACTIVE INCIDENT: [{incident_id}]")
    print(f"📋 REPORT: {incident_report}")
    print("=" * 65)

    contents = [types.Content(role="user", parts=[types.Part.from_text(text=incident_report)])]
    log_incident_step(incident_id, 0, "incident_reported", {"report": incident_report})

    turn = 1
    while turn <= MAX_TURNS:
        print(f"\n--- [Turn {turn}/{MAX_TURNS}] SRE Agent Reasoning... ---")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=AGENT_CONFIG
        )

        # Check if SRE reached resolution
        if not response.function_calls:
            print("\n" + "=" * 65)
            print("📋 [POST-MORTEM & RESOLUTION SUMMARY]")
            print("=" * 65)
            print(response.text)
            print("=" * 65)
            log_incident_step(incident_id, turn, "incident_resolved", {"summary": response.text})
            return

        # Record decision
        contents.append(response.candidates[0].content)

        # Execute Tools with Safety Gates
        for call in response.function_calls:
            func_name = call.name
            func_args = call.args or {}
            print(f"ACTION: {func_name}({func_args})")

            tool_fn = TOOL_REGISTRY.get(func_name)
            tool_output = tool_fn(**func_args) if tool_fn else {"error": "Tool not found"}

            preview = str(tool_output)[:120].replace("\n", " ")
            print(f"OBSERVATION: {preview}...")

            log_incident_step(incident_id, turn, "tool_executed", {
                "tool": func_name, "args": func_args, "output": tool_output
            })

            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=func_name, response={"result": tool_output})]
            ))

        turn += 1

    print("\nMax triage turns reached.")

# ==========================================
# 4. Interactive CLI
# ==========================================
if __name__ == "__main__":
    print("=" * 65)
    print("🛡️  SRE Incident Responder Agent (Human-in-the-Loop Safe)")
    print("=" * 65)
    print("Mock server incident files ready at:")
    print("  - Log:    05_devops_capstones/mock_server/app_backend.log")
    print("  - Config: 05_devops_capstones/mock_server/config.json")
    print("  - Lock:   05_devops_capstones/mock_server/db.lock")
    print("\nSample Incident Prompts:")
    print("  1. 'The checkout service is reporting 504 Gateway Timeouts. Investigate 05_devops_capstones/mock_server and fix the root cause.'")
    print("  2. 'Type exit to quit'")
    print("=" * 65)

    while True:
        try:
            report = input("\nEnter Incident Description: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not report:
            continue
        if report.lower() in ("exit", "quit"):
            print("Stand down.")
            break

        inc_id = f"INC-{datetime.now().strftime('%m%d-%H%M')}"
        triage_incident(inc_id, report)
