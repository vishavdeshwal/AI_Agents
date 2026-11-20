"""
Stage 7: Universal Framework-Centric Agent (LangGraph + Multi-Provider Hot-Swapping)
------------------------------------------------------------------------------------
Mental Model:
1. Model Agnostic:
   Code once. Switch between Gemini, OpenAI, Claude, Perplexity, or Local Ollama/vLLM
   just by changing `LLM_PROVIDER` in your .env file!
2. Universal Looping Engine (LangGraph):
   LangGraph provides a standardized ReAct StateGraph loop, state checkpointing,
   and tool execution across all models.
3. Human-in-the-Loop Security Gate:
   Destructive shell commands (rm, kill, chmod) still pause and require human authorization!
"""

import os
import sys
import re
import platform
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# LangChain & LangGraph Universal Imports
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

# 1. Load active .env file (and search parent if needed)
load_dotenv()

# ==========================================
# 1. The Universal Model Factory
# ==========================================
def get_model():
    """
    Instantiates the appropriate ChatModel based on LLM_PROVIDER in .env.
    Supports: Gemini, OpenAI, Anthropic, Perplexity, and Local (Ollama/vLLM).
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    print(f"🔌 [MODEL FACTORY] Active Provider: '{provider}'")

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[ERROR] GEMINI_API_KEY not found in .env!")
            sys.exit(1)
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        print(f"   Model: {model_name}")
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[ERROR] OPENAI_API_KEY not found in .env!")
            sys.exit(1)
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        print(f"   Model: {model_name}")
        return ChatOpenAI(model=model_name, api_key=api_key)

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("[ERROR] ANTHROPIC_API_KEY not found in .env!")
            sys.exit(1)
        model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        print(f"   Model: {model_name}")
        return ChatAnthropic(model=model_name, api_key=api_key)

    elif provider == "perplexity":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            print("[ERROR] PERPLEXITY_API_KEY not found in .env!")
            sys.exit(1)
        model_name = os.getenv("PERPLEXITY_MODEL", "sonar")
        print(f"   Model: {model_name} (via Perplexity API)")
        return ChatOpenAI(model=model_name, api_key=api_key, base_url="https://api.perplexity.ai")

    elif provider in ("local", "ollama", "vllm"):
        from langchain_openai import ChatOpenAI
        base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
        model_name = os.getenv("LOCAL_MODEL_NAME", "llama3")
        print(f"   Local Server: {base_url} (Model: {model_name})")
        return ChatOpenAI(model=model_name, api_key="not-needed", base_url=base_url)

    else:
        print(f"[ERROR] Unsupported LLM_PROVIDER: '{provider}'. Choose gemini, openai, anthropic, perplexity, or local.")
        sys.exit(1)


# ==========================================
# 2. Universal Tools (@tool decorator)
# ==========================================

DANGEROUS_PATTERNS = [
    r"\brm\b", r"\bkill\b", r"\bpkill\b", r"\bsystemctl\b",
    r"\bchmod\b", r"\bchown\b", r"\btruncate\b", r"\bdd\b",
    r"\breboot\b", r"\bshutdown\b", r"\bmkfs\b"
]

@tool
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

@tool
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
    return {"log": str(p), "matched_count": len(matched), "recent_lines": matched[-20:]}

@tool
def execute_shell_command(command: str) -> dict:
    """
    Executes a shell command.
    Safe read commands run automatically.
    Destructive commands (rm, kill, systemctl) require explicit human authorization.
    """
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            print("\n" + "!" * 65)
            print("🚨 [HUMAN-IN-THE-LOOP SECURITY GATE]")
            print(f"   The Agent wants to execute: '{command}'")
            print("!" * 65)
            try:
                confirm = input("👉 Authorize command? [y/N]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                confirm = "n"

            if confirm != "y":
                print("   ⛔ [BLOCKED] Command rejected by operator.\n")
                return {"status": "denied", "error": "Operator DENIED permission to run this command."}
            print("   ✅ [AUTHORIZED] Operator granted permission.\n")
            break

    print(f"   💻 [SHELL] Running: {command}")
    res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)
    return {
        "exit_code": res.returncode,
        "stdout": res.stdout[:1500] if res.stdout else "",
        "stderr": res.stderr[:1000] if res.stderr else "",
    }

TOOLS = [get_system_metrics, search_log_file, execute_shell_command]


# ==========================================
# 3. LangGraph Universal ReAct Agent
# ==========================================
SYSTEM_PROMPT = """
You are an expert DevOps Site Reliability Engineer (SRE).
Troubleshoot incidents systematically:
1. Search and inspect logs.
2. Check host and system metrics.
3. Fix or remediate root causes using shell commands.
4. Provide a crisp Post-Mortem summary when done.
"""

def create_universal_sre_agent():
    llm = get_model()
    # MemorySaver provides persistent state across turns
    checkpointer = MemorySaver()
    agent = create_react_agent(
        llm,
        tools=TOOLS,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer
    )
    return agent


# ==========================================
# 4. Interactive CLI Loop
# ==========================================
if __name__ == "__main__":
    print("=" * 65)
    print("🌐 Universal Multi-Provider SRE Agent (LangGraph Powered)")
    print("=" * 65)
    print("Supported Providers (change LLM_PROVIDER in .env):")
    print("  • gemini       (Google Gemini)")
    print("  • openai       (OpenAI GPT-4o / GPT-4o-mini)")
    print("  • anthropic    (Claude 3.5 Sonnet / Haiku)")
    print("  • perplexity   (Sonar)")
    print("  • local        (Ollama / vLLM on localhost:11434)")
    print("=" * 65)
    print("Options:")
    print("  - Type your own incident description")
    print("  - Type '1' for the sample Checkout API 504 outage")
    print("  - Type 'exit' or 'quit' to end")
    print("=" * 65)

    agent_app = create_universal_sre_agent()
    # In LangGraph, thread_id represents the session memory ID
    config = {"configurable": {"thread_id": "devops-session-1"}}

    while True:
        try:
            prompt = input("\nEnter Incident for Agent: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not prompt:
            continue
        if prompt.lower() in ("exit", "quit"):
            print("Session closed. Goodbye!")
            break

        if prompt == "1":
            prompt = (
                "The checkout service is reporting 504 Gateway Timeouts. "
                "Investigate 05_devops_capstones/mock_server and fix the root cause."
            )

        print("\n" + "=" * 65)
        print(f"🚀 [LANGGRAPH EXECUTION STARTED]")
        print("=" * 65)

        # Stream LangGraph events turn by turn
        for event in agent_app.stream({"messages": [("user", prompt)]}, config=config, stream_mode="values"):
            latest_message = event["messages"][-1]
            if latest_message.type == "ai" and latest_message.tool_calls:
                for tc in latest_message.tool_calls:
                    print(f"🔧 [LANGGRAPH ACTION] Requesting tool: {tc['name']}({tc['args']})")
            elif latest_message.type == "tool":
                preview = str(latest_message.content)[:100].replace("\n", " ")
                print(f"👁️  [LANGGRAPH OBSERVATION] {preview}...")

        # Final answer
        final_message = event["messages"][-1]
        print("\n" + "=" * 65)
        print("🏁 [LANGGRAPH INCIDENT RESOLUTION]")
        print("=" * 65)
        if isinstance(final_message.content, list):
            for part in final_message.content:
                if isinstance(part, dict) and "text" in part:
                    print(part["text"])
                else:
                    print(part)
        else:
            print(final_message.content)
        print("=" * 65)
