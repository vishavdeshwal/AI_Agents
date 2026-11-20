"""
Stage 3: The True Agent Engine (Autonomous ReAct Loop)
------------------------------------------------------
Mental Model:
1. We DISABLE the SDK's automatic magic (AutomaticFunctionCallingConfig(disable=True)).
2. We write the autonomous while-loop OURSELVES in pure Python.
3. The ReAct Pattern:
      REASON:  The LLM inspects history & decides if it needs a tool or final text.
      ACT:     If it returns a function_call, our Python code executes the tool locally.
      OBSERVE: The tool's output is added to the conversation history.
      REPEAT:  The loop repeats until the model produces final text or hits MAX_TURNS.
4. Circuit Breaker:
      MAX_TURNS = 10 prevents infinite loops and protects your API budget.
"""

import os
import sys
import platform
import shutil
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ==========================================
# 1. Define Our Toolset
# ==========================================

def get_system_metrics() -> dict:
    """Returns OS name, release, architecture, CPU count, and disk space usage."""
    total, used, free = shutil.disk_usage("/")
    return {
        "os": platform.system(),
        "release": platform.release(),
        "architecture": platform.machine(),
        "cpu_cores": os.cpu_count(),
        "disk_free_gb": round(free / (1024**3), 2),
        "disk_total_gb": round(total / (1024**3), 2),
    }

def list_directory(directory_path: str = ".") -> dict:
    """Lists files and folders inside the directory path with types and sizes."""
    try:
        p = Path(directory_path)
        if not p.exists():
            return {"error": f"Path '{directory_path}' does not exist."}
        if not p.is_dir():
            return {"error": f"Path '{directory_path}' is not a directory."}

        items = []
        for item in sorted(p.iterdir()):
            items.append({
                "name": item.name,
                "type": "DIR" if item.is_dir() else "FILE",
                "size_bytes": item.stat().st_size if item.is_file() else None,
            })
        return {"directory": str(p.resolve()), "items": items}
    except Exception as e:
        return {"error": str(e)}

def read_file_content(file_path: str, max_lines: int = 50) -> dict:
    """Reads up to max_lines from a file safely."""
    try:
        p = Path(file_path)
        if not p.exists():
            return {"error": f"File '{file_path}' does not exist."}
        if not p.is_file():
            return {"error": f"Path '{file_path}' is not a regular file."}

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
        return {"file_path": str(p.resolve()), "lines_read": len(lines), "content": "".join(lines)}
    except Exception as e:
        return {"error": str(e)}

# The Tool Registry: maps function names (strings) to actual Python functions
TOOL_REGISTRY = {
    "get_system_metrics": get_system_metrics,
    "list_directory": list_directory,
    "read_file_content": read_file_content,
}

# ==========================================
# 2. Setup Client & Configuration
# ==========================================
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in .env!")
    sys.exit(1)

client = genai.Client(api_key=api_key)
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# CRITICAL: We pass our tools, but DISABLE automatic SDK calling
# so that WE control the execution loop!
AGENT_CONFIG = types.GenerateContentConfig(
    tools=[get_system_metrics, list_directory, read_file_content],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
)

MAX_TURNS = 10  # DevOps Guardrail: Circuit Breaker

# ==========================================
# 3. The Autonomous ReAct Engine Function
# ==========================================
def run_autonomous_agent(goal: str):
    print("\n" + "=" * 60)
    print(f"🎯 NEW GOAL: {goal}")
    print("=" * 60)

    # Initialize conversation history with user's goal
    contents = [
        types.Content(role="user", parts=[types.Part.from_text(text=goal)])
    ]

    turn = 1
    while turn <= MAX_TURNS:
        print(f"\n--- [Turn {turn}/{MAX_TURNS}] Thinking... ---")

        # 1. Ask the Brain (LLM)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=AGENT_CONFIG
        )

        # 2. Check: Did the Brain return a tool call or final text?
        if not response.function_calls:
            # No tool requested! The agent has finished reasoning and produced the final answer.
            print("\n🏁 [GOAL COMPLETE!]")
            print("=" * 60)
            print(response.text)
            print("=" * 60)
            return

        # 3. Append the model's tool-call decision to conversation history
        contents.append(response.candidates[0].content)

        # 4. EXECUTE THE TOOL CALLS (The Hands)
        for call in response.function_calls:
            func_name = call.name
            func_args = call.args or {}

            print(f"🔧 ACTION: Call tool '{func_name}'")
            print(f"   Args: {func_args}")

            # Lookup function in our registry
            if func_name in TOOL_REGISTRY:
                tool_fn = TOOL_REGISTRY[func_name]
                try:
                    # Execute the local Python function!
                    tool_output = tool_fn(**func_args)
                except Exception as exc:
                    tool_output = {"error": f"Execution failed: {str(exc)}"}
            else:
                tool_output = {"error": f"Unknown tool '{func_name}'"}

            preview = str(tool_output)[:120].replace("\n", " ")
            print(f"OBSERVATION: {preview}...")

            # 5. Send tool result back into conversation history
            function_response_content = types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(
                        name=func_name,
                        response={"result": tool_output}
                    )
                ]
            )
            contents.append(function_response_content)

        turn += 1

    print(f"\n⚠️ [CIRCUIT BREAKER TRIGGERED] Reached maximum limit of {MAX_TURNS} turns.")

# ==========================================
# 4. Main Interactive Prompt
# ==========================================
if __name__ == "__main__":
    print("=" * 65)
    print("🤖 Autonomous ReAct Agent Engine Ready (Zero SDK Black-Box)")
    print("=" * 65)
    print("Give the agent a complex multi-step task, such as:")
    print("  - 'Inspect this project, tell me all files, and read README.md to see what is done'")
    print("  - 'Check my OS and available disk space, and tell me if disk is low'")
    print("  - Type 'exit' to quit")
    print("=" * 65)

    while True:
        try:
            task = input("\nEnter Task for Agent: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not task:
            continue
        if task.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        run_autonomous_agent(task)
