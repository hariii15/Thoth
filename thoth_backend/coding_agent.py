import os
from dotenv import load_dotenv
from openai import OpenAI
import json
import re

# Load environment variables
load_dotenv()

def get_coding_client():
    """Initialize OpenRouter client for coding tasks"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")
    
    try:
        # Initialize with minimal parameters to avoid compatibility issues
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        return client
    except Exception as e:
        print(f"[CodingAgent] Error initializing OpenAI client: {e}")
        raise ValueError(f"Failed to initialize OpenRouter client: {str(e)}")

def get_user_skillset():
    """Load user's coding skillset from profile"""
    try:
        profile_path = os.path.join(os.path.dirname(__file__), "profile.md")
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile_content = f.read()
        return profile_content
    except Exception as e:
        return "User profile not available. Assume intermediate level programming knowledge."

def format_coding_response(response_text: str) -> dict:
    """Format the coding response with proper structure for frontend styling"""
    
    # Extract code blocks with language detection
    code_blocks = []
    code_pattern = r'```(\w+)?\n?(.*?)```'
    matches = re.finditer(code_pattern, response_text, re.DOTALL)
    
    for match in matches:
        language = match.group(1) or 'text'
        code_content = match.group(2).strip()
        code_blocks.append({
            "language": language,
            "code": code_content
        })
    
    # Remove code blocks from main text for separate rendering
    main_text = re.sub(code_pattern, '', response_text, flags=re.DOTALL)
    main_text = re.sub(r'\n\s*\n\s*\n', '\n\n', main_text).strip()
    
    return {
        "type": "coding_response",
        "main_content": main_text,
        "code_blocks": code_blocks,
        "has_code": len(code_blocks) > 0
    }

def call_coding_agent(user_query: str, user_skillset: str = None) -> str:
    """Call the Qwen3 Coder model for coding-related queries"""
    print(f"[CodingAgent] Processing coding query: '{user_query}'")
    
    try:
        client = get_coding_client()
        
        if not user_skillset:
            user_skillset = get_user_skillset()
        
        # Create a specialized prompt for coding education
        system_prompt = f"""You are a distinguished computer science professor from a top-tier university (think MIT, Stanford, Carnegie Mellon). Your teaching style emphasizes deep understanding of fundamental concepts before diving into implementation details.

User's Background/Skillset:
{user_skillset}

CRITICAL FORMATTING INSTRUCTIONS:
- Use markdown formatting for headers: # for main title, ## for sections, ### for subsections
- Use **bold** for important terms and concepts
- Use `inline code` for small code snippets and variable names
- Use ```language blocks for multi-line code examples
- Write explanatory text between code blocks, not as comments inside code
- Start with a clear title using # Header format

Teaching Philosophy & Guidelines:

**THEORETICAL FOUNDATION FIRST:**
1. **Always start with conceptual explanation** - What is the concept? Why does it exist? What problem does it solve?
2. **Provide historical context** when relevant - How did this concept evolve? Who invented it?
3. **Explain the underlying principles** - What are the mathematical or logical foundations?
4. **Discuss trade-offs and complexity** - Time/space complexity, when to use vs not use

**CODE AS ILLUSTRATION, NOT CENTERPIECE:**
5. **Use small, focused code snippets** (5-15 lines max per block) that illustrate ONE specific concept
6. **Provide extensive explanations BETWEEN code blocks** - explain what each block does and why
7. **Show multiple approaches** when beneficial for understanding
8. **Include proper language syntax** - for JSX use ```jsx, for React use ```jsx, for JavaScript use ```javascript

**PEDAGOGICAL STRUCTURE:**
9. **Build knowledge incrementally** - Start simple, add complexity gradually
10. **Use analogies and real-world examples** to explain abstract concepts
11. **Ask rhetorical questions** to guide student thinking
12. **Provide "Why this matters"** sections connecting concepts to real applications
13. **End with practice suggestions** and further reading

**RESPONSE FORMAT:**
- Start with a clear title using # Header
- Break down into logical sections with ## headers
- Use ### for subsections
- Provide detailed explanations between code examples
- Include complexity analysis where appropriate
- Suggest practical exercises and next steps

Remember: You're teaching computer science, not just showing code. Focus on developing deep understanding and problem-solving thinking. Return ONLY markdown text, no JSON formatting."""

        # Create the completion with proper error handling
        completion = client.chat.completions.create(
            model="qwen/qwen3-coder:free",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            max_tokens=2000,
            temperature=0.3,
            extra_headers={
                "HTTP-Referer": "https://thoth-ai.com",
                "X-Title": "Thoth Coding Agent",
            }
        )
        
        response_content = completion.choices[0].message.content
        
        print(f"[CodingAgent] Generated educational response")
        return response_content  # Return plain markdown text, not JSON
        
    except Exception as e:
        print(f"[CodingAgent] Error in call_coding_agent: {e}")
        error_response = f"I encountered an error while processing your coding query. Please try again or contact support if the issue persists.\n\nError details: {str(e)}"
        return error_response

def run_coding_agent(user_query: str) -> str:
    """Main function to run the coding agent"""
    print(f"[CodingAgent] Received query: '{user_query}'")
    return call_coding_agent(user_query)

# Test function
if __name__ == "__main__":
    print("🚀 Testing Coding Agent...")
    test_query = "Explain how to implement a binary search algorithm and when to use it"
    result = run_coding_agent(test_query)
    print("Result:", result)