import os 
import sys
from dotenv import load_dotenv
from google import genai


load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in .env")
    sys.exit(1)

client = genai.Client(api_key=api_key)
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

chat = client.chats.create(model=MODEL_NAME)
print("=" * 60)
print(f"Interactive Chat Session Started with {MODEL_NAME}")
print("Special commands:")
print("  - Type 'history' to inspect the raw message list stored in memory")
print("  - Type 'exit' or 'quit' to end")
print("=" * 60)

while True:
    try:
        user_input = input("\You: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nSession ended.")
        break

    if not user_input:
        continue
    if user_input.lower() in ("exit", "quit"):
        print("Goodbye!")
        break

    if user_input.lower() == "history":
        print("\n--- CURRENT CONVERSATION HISTORY IN MEMORY ---")
        current_history = chat.get_history()
        for idx, message in enumerate(current_history):
            role = message.role.upper()
            text_preview = message.parts[0].text[:80].replace("\n", " ")
            print(f"[{idx}] {role}: {text_preview}...")
        print("----------------------------------------")
        continue

    response = chat.send_message(user_input)
    print(f"\nAI: {response.text}")

    if response.usage_metadata:
        usage = response.usage_metadata
        print(f"[Tokens: {usage.prompt_token_count} in (history + prompt) | {usage.candidates_token_count} out]")