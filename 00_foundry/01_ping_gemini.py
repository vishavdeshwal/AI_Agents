"""
Step 0: The Foundry - First API Ping
------------------------------------
Mental Model:
An LLM is not a "magical thinking person".
It is a stateless function that maps:
   (Input Tokens) -> (Probability Distribution) -> (Output Tokens)

Every time you call the API, you are making an HTTP POST request over the wire.
"""

import os
import sys
from dotenv import load_dotenv
from google import genai

# 1. Load environment variables (from .env or parent .env)
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("\n[ERROR] GEMINI_API_KEY not found in environment or .env file!")
    print("1. Get a free API key at: https://aistudio.google.com/")
    print("2. Create a .env file:")
    print("   echo 'GEMINI_API_KEY=your_key_here' > .env\n")
    sys.exit(1)

# 2. Initialize the Google GenAI Client
# Under the hood, this client manages HTTP sessions, authentication headers,
# and JSON payload serialization.
client = genai.Client(api_key=api_key)

# 3. Model selection (defaulting to the fast and responsive flash-lite model):
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

print(f"[*] Sending prompt to {MODEL_NAME}...")

# 4. Make the call:
prompt = "Explain in 2 sentences what an AI Agent is to a DevOps engineer."
prompt2 = "Write 100 words on Cow considering the Hindu faith."

response = client.models.generate_content(
    model=MODEL_NAME,
    contents=prompt,
)
response2 = client.models.generate_content(
    model=MODEL_NAME,
    contents=prompt2
)

# 5. Inspect the response
print("\n" + "=" * 50)
print("RESPONSE FROM LLM:")
print("=" * 50)
print(response.text)
print("=" * 50)


#5.1 
print("\n" + "=" * 50)
print("RESPONSE FROM LLM:")
print("=" * 50)
print(response2.text)
print("=" * 50)

# 6. Inspect Token Usage (Crucial for cost & context management!)
if response.usage_metadata:
    usage = response.usage_metadata
    print(f"Prompt Tokens:     {usage.prompt_token_count}")
    print(f"Candidates Tokens: {usage.candidates_token_count}")
    print(f"Total Tokens:      {usage.total_token_count}")
print("=" * 50)
