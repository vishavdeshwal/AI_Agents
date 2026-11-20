"""
Stage 4: State, Persistence & Context Compaction
------------------------------------------------
Mental Model:
1. Short-Term Memory vs Long-Term Storage:
   - Instead of volatile RAM, sessions are saved into SQLite (agent_memory.db).
   - Each session records its goal, timestamp, tool calls, and final summary.
2. Search & Resume:
   - On startup, the agent displays past sessions or lets you search them.
   - You can resume an existing session or start a new one.
3. Context Compaction (Sliding Window):
   - Keeps token usage small and fast by retaining the initial goal + latest N turns.
"""

import os
import sys
import json
import sqlite3
import platform
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ==========================================
# 1. Database Manager (SQLite)
# ==========================================
DB_PATH = Path("agent_memory.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            goal TEXT,
            summary TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            turn INTEGER,
            role TEXT,
            content_json TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        )
    """)
    conn.commit()
    conn.close()

def save_session_meta(session_id: str, goal: str, summary: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO sessions (session_id, created_at, updated_at, goal, summary)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            updated_at = excluded.updated_at,
            summary = COALESCE(excluded.summary, sessions.summary)
    """, (session_id, now, now, goal, summary))
    conn.commit()
    conn.close()

def log_message(session_id: str, turn: int, role: str, content_dict: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO messages (session_id, turn, role, content_json)
        VALUES (?, ?, ?, ?)
    """, (session_id, turn, role, json.dumps(content_dict)))
    conn.commit()
    conn.close()

def get_recent_sessions(limit: int = 5):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session_id, goal, updated_at, summary
        FROM sessions
        ORDER BY updated_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def search_sessions(query: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session_id, goal, updated_at, summary
        FROM sessions
        WHERE goal LIKE ? OR summary LIKE ?
        ORDER BY updated_at DESC
    """, (f"%{query}%", f"%{query}%"))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ==========================================
# 2. Toolset (Read-Only)
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
    """Lists files and folders inside directory_path."""
    try:
        p = Path(directory_path)
        if not p.exists() or not p.is_dir():
            return {"error": f"Invalid directory '{directory_path}'"}
        items = [{"name": item.name, "type": "DIR" if item.is_dir() else "FILE"} for item in sorted(p.iterdir())]
        return {"directory": str(p.resolve()), "items": items}
    except Exception as e:
        return {"error": str(e)}

def read_file_content(file_path: str, max_lines: int = 50) -> dict:
    """Reads lines from a file safely."""
    try:
        p = Path(file_path)
        if not p.is_file():
            return {"error": f"File '{file_path}' not found."}
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
        return {"file": str(p.resolve()), "content": "".join(lines)}
    except Exception as e:
        return {"error": str(e)}

TOOL_REGISTRY = {
    "get_system_metrics": get_system_metrics,
    "list_directory": list_directory,
    "read_file_content": read_file_content,
}

# ==========================================
# 3. Context Compaction (Sliding Window)
# ==========================================
MAX_TURNS = 8
MAX_RECENT_TURNS = 4

def compact_contents(contents: list) -> list:
    """
    If conversation history grows too large, keep:
    1. The original initial goal (Index 0).
    2. The most recent N turns.
    Prunes away ancient intermediate tool outputs to keep context lean and fast!
    """
    if len(contents) <= (MAX_RECENT_TURNS * 2) + 1:
        return contents

    print(f"\n [CONTEXT COMPACTOR] Trimming history from {len(contents)} to keep context fast & cheap...")
    initial_goal = contents[0]
    recent_tail = contents[-(MAX_RECENT_TURNS * 2):]
    return [initial_goal] + recent_tail

# ==========================================
# 4. Agent Engine with Persistence
# ==========================================
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
AGENT_CONFIG = types.GenerateContentConfig(
    tools=[get_system_metrics, list_directory, read_file_content],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
)

def run_agent_session(session_id: str, goal: str):
    print("\n" + "=" * 65)
    print(f"📁 SESSION: {session_id}")
    print(f"🎯 GOAL:    {goal}")
    print("=" * 65)

    save_session_meta(session_id, goal)

    contents = [types.Content(role="user", parts=[types.Part.from_text(text=goal)])]
    log_message(session_id, turn=0, role="user", content_dict={"goal": goal})

    turn = 1
    while turn <= MAX_TURNS:
        # Apply compaction if history is getting long
        contents = compact_contents(contents)

        print(f"\n--- [Turn {turn}/{MAX_TURNS}] Reasoning... ---")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=AGENT_CONFIG
        )

        # 1. Goal Complete Check
        if not response.function_calls:
            print("\n[GOAL COMPLETED & PERSISTED TO SQLITE!]")
            print("=" * 65)
            print(response.text)
            print("=" * 65)
            save_session_meta(session_id, goal, summary=response.text[:300])
            log_message(session_id, turn=turn, role="model", content_dict={"final_answer": response.text})
            return

        # 2. Record Model Decision
        contents.append(response.candidates[0].content)

        # 3. Dispatch Tools Locally
        for call in response.function_calls:
            func_name = call.name
            func_args = call.args or {}
            print(f"🔧 ACTION: {func_name}({func_args})")

            tool_fn = TOOL_REGISTRY.get(func_name)
            tool_output = tool_fn(**func_args) if tool_fn else {"error": "Unknown tool"}

            preview = str(tool_output)[:100].replace("\n", " ")
            print(f"👁️  OBSERVE: {preview}...")

            # Persist tool execution into SQLite
            log_message(session_id, turn=turn, role="tool", content_dict={
                "tool": func_name, "args": func_args, "output": tool_output
            })

            # Append to in-memory context
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=func_name, response={"result": tool_output})]
            ))

        turn += 1

    print("\nCircuit breaker triggered.")

# ==========================================
# 5. Interactive Session Manager (CLI)
# ==========================================
def main():
    init_db()
    print("=" * 65)
    print("💾 Persistent AI Agent with SQLite Memory & Compaction")
    print("=" * 65)

    recent = get_recent_sessions(limit=4)
    if recent:
        print("\n📜 RECENT SESSIONS:")
        for idx, (sid, goal, updated, summary) in enumerate(recent, 1):
            time_str = updated.split("T")[0]
            print(f"  [{idx}] {sid} ({time_str}): '{goal[:45]}...'")
        print("\nOptions:")
        print("  - Press [Enter] to resume the latest session [1]")
        print("  - Type a number [1-4] to resume that session")
        print("  - Type 'search <keyword>' to find an old session")
        print("  - Type 'new' to start a fresh session")
    else:
        print("No previous sessions found. Starting fresh session.")

    choice = input("\nYour choice: ").strip()

    if choice.startswith("search "):
        q = choice[7:].strip()
        results = search_sessions(q)
        if not results:
            print(f"No past sessions found matching '{q}'.")
            return
        print(f"\n🔍 FOUND {len(results)} SESSIONS MATCHING '{q}':")
        for idx, (sid, goal, updated, summary) in enumerate(results, 1):
            print(f"  [{idx}] {sid}: '{goal}'")
            if summary:
                print(f"      Summary: {summary[:80]}...")
        return

    # Determine session ID
    if choice in ("new", "") and not recent:
        session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    elif choice == "" and recent:
        session_id = recent[0][0]
        print(f"Resuming latest session: {session_id}")
    elif choice.isdigit() and 1 <= int(choice) <= len(recent):
        session_id = recent[int(choice) - 1][0]
        print(f"Resuming session: {session_id}")
    else:
        session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    task = input(f"\nEnter task for [{session_id}]: ").strip()
    if task:
        run_agent_session(session_id, task)

if __name__ == "__main__":
    main()
