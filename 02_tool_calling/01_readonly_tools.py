"""
Stage 2: Giving Hands to the Brain (Read-Only Tools)
---------------------------------------------------
Mental Model:
1. LLMs cannot run shell commands or touch your filesystem directly.
2. We provide Python functions into `config={"tools": [...]}`.
3. When the model needs information, it pauses and requests a FunctionCall.
4. The Python function executes locally on your machine.
5. The function's output is sent back as a FunctionResponse.
6. The model reads the output and gives you a human-friendly answer.
"""

import os
import sys
import platform
import shutil
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# ==========================================
# 1. Define Read-Only Cross-Platform Tools
# ==========================================

def get_system_metrics() -> dict:
    """
    Returns system information including OS name, release/kernel version,
    architecture, CPU core count, and disk space usage on the root mount.
    Works on macOS and Linux.
    """
    print("[TOOL CALLED] get_system_metrics() executing on your machine...")
    total, used, free = shutil.disk_usage("/")
    return {
        "os": platform.system(),
        "release": platform.release(),
        "architecture": platform.machine(),
        "cpu_cores": os.cpu_count(),
        "disk_total_gb": round(total / (1024**3), 2),
        "disk_free_gb": round(free / (1024**3), 2),
        "disk_used_percent": round((used / total) * 100, 1),
    }


def list_directory(directory_path: str = ".") -> dict:
    """
    Lists the files and folders inside the specified directory path.
    Shows the name, type (DIR or FILE), and file size in bytes.
    """
    print(f"   ⚡ [TOOL CALLED] list_directory('{directory_path}') executing on your machine...")
    try:
        p = Path(directory_path)
        if not p.exists():
            return {"error": f"Path '{directory_path}' does not exist."}
        if not p.is_dir():
            return {"error": f"Path '{directory_path}' is a file, not a directory."}

        items = []
        for item in sorted(p.iterdir()):
            items.append({
                "name": item.name,
                "type": "DIR" if item.is_dir() else "FILE",
                "size_bytes": item.stat().st_size if item.is_file() else None,
            })
        return {"directory": str(p.resolve()), "total_items": len(items), "items": items}
    except Exception as e:
        return {"error": str(e)}


def read_file_content(file_path: str, max_lines: int = 50) -> dict:
    """
    Reads up to max_lines from a file and returns its content safely.
    Use this to inspect config files, logs, or scripts.
    """
    print(f"   ⚡ [TOOL CALLED] read_file_content('{file_path}', max_lines={max_lines}) executing on your machine...")
    try:
        p = Path(file_path)
        if not p.exists():
            return {"error": f"File '{file_path}' does not exist."}
        if not p.is_file():
            return {"error": f"Path '{file_path}' is not a regular file."}

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
            content = "".join(lines)

        return {"file_path": str(p.resolve()), "lines_read": len(lines), "content": content}
    except Exception as e:
        return {"error": str(e)}


# ==========================================
# 2. Setup Client & Register Tools
# ==========================================
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in .env!")
    sys.exit(1)

client = genai.Client(api_key=api_key)
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Bundle our Python functions into the tools list
TOOLS = [get_system_metrics, list_directory, read_file_content]

# Create chat with tools enabled
chat = client.chats.create(
    model=MODEL_NAME,
    config={"tools": TOOLS}
)

print("=" * 65)
print(f"Agent with 3 Read-Only Tools Ready ({MODEL_NAME})")
print("Available Tools:")
print("  1. get_system_metrics()")
print("  2. list_directory(directory_path)")
print("  3. read_file_content(file_path, max_lines)")
print("\nTry asking:")
print("  - 'How much free disk space do I have?'")
print("  - 'What files are in this project directory?'")
print("  - 'Read the README.md file and summarize it.'")
print("  - 'What OS and CPU cores am I running?'")
print("=" * 65)

# ==========================================
# 3. Interactive Agent Loop
# ==========================================
while True:
    try:
        user_input = input("\nYou: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nSession ended.")
        break

    if not user_input:
        continue

    if user_input.lower() in ("exit", "quit"):
        print("Goodbye!")
        break

    if user_input.lower() == "history":
        print("\n--- MESSAGE & TOOL CALL HISTORY ---")
        for idx, msg in enumerate(chat.get_history()):
            role = msg.role.upper()
            for part in msg.parts:
                if part.text:
                    print(f"[{idx}] {role} TEXT: {part.text[:80].replace(chr(10), ' ')}...")
                elif part.function_call:
                    call = part.function_call
                    print(f"[{idx}] {role} FUNCTION CALL: {call.name}(args={call.args})")
                elif part.function_response:
                    resp = part.function_response
                    print(f"[{idx}] {role} FUNCTION RESPONSE: {resp.name} -> {str(resp.response)[:80]}...")
        print("-----------------------------------")
        continue

    # Send message:
    # Because tools are registered, if the model requests a function call,
    # the SDK executes our Python function, captures the return value,
    # and sends it back to the model automatically!
    response = chat.send_message(user_input)

    print(f"\nAgent: {response.text}")
