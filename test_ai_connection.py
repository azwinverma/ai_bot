import os
import ollama
from dotenv import load_dotenv

load_dotenv()

def test_ai():
    # Model name from your terminal output
    model = "qwen3:8b" 
    print(f"Testing connectivity to Ollama model: {model}...")
    try:
        response = ollama.chat(model=model, messages=[
            {'role': 'user', 'content': 'Hello! Crypto bot test. Briefly say ready.'},
        ])
        print("Response received:")
        print(response['message']['content'])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ai()
