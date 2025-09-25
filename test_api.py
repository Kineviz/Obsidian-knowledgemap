#!/usr/bin/env python3
"""Simple script to validate OpenAI API key"""

import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

def test_api_key():
    """Test if the OpenAI API key is valid"""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ No API key found in environment variables")
        return False
    
    print(f"🔑 API Key found: {api_key[:20]}...")
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Make a simple test call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        
        print("✅ API key is valid!")
        print(f"Response: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"❌ API key validation failed: {e}")
        return False

if __name__ == "__main__":
    test_api_key()
