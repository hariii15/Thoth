import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

def test_openrouter_connection():
    """Test basic OpenRouter API connection and kimi-k2 model"""

    # Get API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY not found in environment variables")
        print("Please add OPENROUTER_API_KEY to your .env file")
        return False

    print("✅ OPENROUTER_API_KEY found")
    print(f"API Key (first 10 chars): {api_key[:10]}...")

    try:
        # Initialize OpenRouter client
        print("\n🔄 Initializing OpenRouter client...")
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        print("✅ OpenRouter client initialized successfully")

        # Test basic completion
        print("\n🔄 Testing kimi-k2 model with simple query...")
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://thoth-ai.com",
                "X-Title": "Thoth GitHub Agent Test",
            },
            extra_body={},
            model="moonshotai/kimi-k2:free",
            messages=[
                {
                    "role": "user",
                    "content": "Hello! Can you respond with 'OpenRouter connection successful' to confirm you're working?"
                }
            ],
            max_tokens=100,
            temperature=0.3
        )

        response = completion.choices[0].message.content
        print("✅ Model response received:")
        print(f"Response: {response}")

        return True

    except Exception as e:
        print(f"❌ Error testing OpenRouter connection: {str(e)}")
        return False

def test_github_focused_query():
    """Test OpenRouter with a GitHub-focused query"""

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY not found")
        return False

    try:
        print("\n🔄 Testing GitHub-focused query...")
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://thoth-ai.com",
                "X-Title": "Thoth GitHub Agent Test",
            },
            extra_body={},
            model="moonshotai/kimi-k2:free",
            messages=[
                {
                    "role": "user",
                    "content": "What are the key things to look for when reviewing a pull request in a software project?"
                }
            ],
            max_tokens=200,
            temperature=0.3
        )

        response = completion.choices[0].message.content
        print("✅ GitHub-focused response received:")
        print(f"Response: {response}")

        return True

    except Exception as e:
        print(f"❌ Error with GitHub-focused query: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Testing OpenRouter API with kimi-k2 model...")
    print("=" * 50)

    # Test basic connection
    basic_test = test_openrouter_connection()

    if basic_test:
        # Test GitHub-focused query
        github_test = test_github_focused_query()

        if github_test:
            print("\n🎉 All tests passed! OpenRouter is working correctly.")
            print("You can now proceed to test the full GitHub agent.")
        else:
            print("\n⚠️ Basic connection works but GitHub query failed.")
    else:
        print("\n❌ Basic connection failed. Please check your API key and internet connection.")

    print("=" * 50)
