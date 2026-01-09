"""Test Grok API connection."""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Get API key
api_key = os.getenv("GROK_API_KEY")
if not api_key:
    # Try reading from .env.example if .env doesn't exist
    if os.path.exists(".env.example"):
        with open(".env.example", "r") as f:
            for line in f:
                if line.startswith("GROK_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break

print(f"API Key found: {api_key[:20]}..." if api_key else "No API key found!")

if not api_key:
    print("Please set GROK_API_KEY in .env file")
    exit(1)

# Create client
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1"
)

print("\nSending test request to Grok API...")

try:
    response = client.chat.completions.create(
        model="grok-4",
        messages=[
            {"role": "user", "content": "Say 'Hello PEPE trader!' in exactly 5 words."}
        ],
        max_tokens=50,
        temperature=0.7
    )

    print("\n" + "=" * 50)
    print("SUCCESS! Grok API is working!")
    print("=" * 50)
    print(f"\nResponse: {response.choices[0].message.content}")
    print(f"\nModel: {response.model}")
    print(f"Tokens used: {response.usage.total_tokens}")

except Exception as e:
    print(f"\nERROR: {e}")
    print("\nCheck your API key and try again.")
