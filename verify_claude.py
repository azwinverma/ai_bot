import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

def test_claude():
    print("Testing Claude API...")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env")
        return

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello Claude! This is a crypto bot test. Briefly say you are ready."}]
        )
        print("Claude Response:")
        print(response.content[0].text)
    except Exception as e:
        print(f"Error connecting to Claude: {e}")

if __name__ == "__main__":
    test_claude()
