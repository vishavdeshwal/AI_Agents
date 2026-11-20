"""
Stage 1: Context & The Conversation Loop (Simulating Memory)
------------------------------------------------------------
Mental Model:
1. LLMs are 100% stateless. They do NOT have a brain that remembers you.
2. Memory is an illusion created by your Python script.
3. Every time you send a new message, Python passes the ENTIRE previous
   transcript (history) back to the API.

In this script, you will:
- See the conversation loop running in your terminal.
- Inspect how the list of messages grows over time.
- Watch how token count increases with every turn.
"""

import os
import sys
from dotenv import load_dotenv
from google import genai

# 1. Load API Key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in .env!")
    sys.exit(1)

# 2. Initialize Client & Model
client = genai.Client(api_key=api_key)
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# 3. Create a Stateful Chat Session
# Under the hood, `chat` is just a Python object holding a list:
# history = [
#     {"role": "user", "parts": ["Hi"]},
#     {"role": "model", "parts": ["Hello! How can I help?"]}
# ]
chat = client.chats.create(model=MODEL_NAME)

print("=" * 60)
print(f"Interactive Chat Session Started with {MODEL_NAME}")
print("Special commands:")
print("  - Type 'history' to inspect the raw message list stored in memory")
print("  - Type 'exit' or 'quit' to end")
print("=" * 60)

# 4. The Conversation Loop (The REPL)
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

    # Inspect what the Python script is holding in memory
    if user_input.lower() == "history":
        print("\n--- CURRENT CONVERSATION HISTORY IN MEMORY ---")
        current_history = chat.get_history()
        for idx, message in enumerate(current_history):
            role = message.role.upper()
            text_preview = message.parts[0].text[:80].replace("\n", " ")
            print(f"[{idx}] {role}: {text_preview}...")
        print("----------------------------------------------")
        continue

    # Send message:
    # `chat.send_message` does 3 things under the hood:
    #   1. Appends your new message to the internal history list.
    #   2. Sends the FULL history list to Google's API over HTTP.
    #   3. Appends the model's reply to the internal history list.
    response = chat.send_message(user_input)

    print(f"\nAI: {response.text}")

    # Track how tokens grow with every turn
    if response.usage_metadata:
        usage = response.usage_metadata
        print(f"[Tokens: {usage.prompt_token_count} in (history + prompt) | {usage.candidates_token_count} out]")
