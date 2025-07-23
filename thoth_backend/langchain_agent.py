import os
from dotenv import load_dotenv
from typing import Dict, Any, List
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.schema import SystemMessage, HumanMessage
from tavily import TavilyClient
import re
import json
import dateutil.parser
from tools import (
    web_search_tool, 
    load_profile_tool, 
    list_directory_tool, 
    read_file_tool, 
    create_directory_tool, 
    get_system_usage_tool, 
    open_application_tool, 
    search_wikipedia_tool,
    list_calendar_events,
    create_calendar_event,
    retrieve_relevant_tool
)

def create_calendar_event_wrapper(action_input):
    """
    Wrapper for create_calendar_event that handles input parsing.
    """
    try:
        # Parse the input
        if isinstance(action_input, dict):
            summary = action_input.get('summary')
            start_time = action_input.get('start_time_iso')
            end_time = action_input.get('end_time_iso')
            description = action_input.get('description')
        elif isinstance(action_input, str):
            # Try to parse JSON string
            try:
                parsed = json.loads(action_input)
                summary = parsed.get('summary')
                start_time = parsed.get('start_time_iso')
                end_time = parsed.get('end_time_iso')
                description = parsed.get('description')
            except:
                # Fallback to comma-separated
                parts = [p.strip() for p in action_input.split(',')]
                if len(parts) >= 3:
                    summary, start_time, end_time = parts[:3]
                    description = parts[3] if len(parts) > 3 else None
                else:
                    return json.dumps({"error": "Invalid input format. Expected: summary, start_time_iso, end_time_iso"})
        else:
            return json.dumps({"error": "Invalid input format"})
        
        # Validate required fields
        if not summary or not start_time or not end_time:
            return json.dumps({"error": "Missing required fields: summary, start_time_iso, end_time_iso"})
        
        # Try to parse dates to ensure valid format
        try:
            start_time_iso = dateutil.parser.parse(start_time).isoformat()
            end_time_iso = dateutil.parser.parse(end_time).isoformat()
        except:
            start_time_iso = start_time
            end_time_iso = end_time
        
        # Call the actual function
        return create_calendar_event(summary, start_time_iso, end_time_iso, description)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

# Load environment variables
load_dotenv()

# Get API keys
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TAVILY_API_KEY or not GEMINI_API_KEY:
    raise ValueError("Tavily and/or Gemini API key not set in .env file.")


class ThothLangChainAgent:
    def __init__(self):
        print("[ThothLangChainAgent] Initializing agent...")
        # Initialize Gemini LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=GEMINI_API_KEY,
            temperature=0.5,
            max_output_tokens=2000
        )
        print("[ThothLangChainAgent] Gemini LLM initialized.")
        # Initialize Tavily client
        self.tavily_client = TavilyClient(TAVILY_API_KEY)
        print("[ThothLangChainAgent] Tavily client initialized.")
        # Create tools
        self.tools = self._create_tools()
        print("[ThothLangChainAgent] Tools created.")
        # Create agent
        self.agent = self._create_agent()
        print("[ThothLangChainAgent] Agent created.")        # Create agent executor
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10  # Increased from 3 to 10
        )
        print("[ThothLangChainAgent] Agent executor ready.")

    def _create_tools(self) -> List[Tool]:
        print("[ThothLangChainAgent] Creating tools...")
        # Import tools from tools.py
        return [
            Tool(
                name="web_search",
                description="Search the web for current information, news, or recent developments. Use when user explicitly asks for web information or current data. CRITICAL: Always include the complete 'Sources:' section from this tool's output in your final answer to provide proper attribution.",
                func=web_search_tool
            ),
            Tool(
                name="load_profile",
                description="Load the user's profile information including skills, projects, and background. Use when answering questions about user's capabilities, projects, or personal information.",
                func=load_profile_tool
            ),
            Tool(
                name="list_directory",
                description="List the contents of a directory, showing files and subdirectories with their sizes. Use when user wants to explore or browse directory contents.",
                func=list_directory_tool
            ),
            Tool(
                name="read_file",
                description="Read and return the contents of a text file. Use when user wants to view, analyze, or work with file contents.",
                func=read_file_tool
            ),
            Tool(
                name="create_directory",
                description="Create a new directory at the specified path, including parent directories if needed. Use when user wants to organize files or create project structure.",
                func=create_directory_tool
            ),
            Tool(
                name="get_system_usage",
                description="Get current system resource usage including CPU, memory, disk usage, and top processes. Use when user asks about system performance or resource monitoring.",
                                func=get_system_usage_tool
            ),
            Tool(
                name="open_application",
                description="Open an application or program on the system. Use when user wants to launch software or utilities.",
                func=open_application_tool
            ),
            Tool(
                name="search_wikipedia",
                description="Search Wikipedia for information on any topic. Use when user asks for encyclopedic knowledge, historical facts, or general information.",
                func=search_wikipedia_tool
            ),
            Tool(
                name="list_calendar_events",
                description="List upcoming events from Google Calendar. Use when user asks about schedule, meetings, or calendar events.",
                func=list_calendar_events
            ),            Tool(
                name="create_calendar_event",
                description="Create a new event in the Google Calendar. Use when user wants to schedule a meeting, appointment, or any event on the calendar. Required arguments: summary (string), start_time_iso (ISO 8601 string, e.g. '2025-07-21T08:00:00'), end_time_iso (ISO 8601 string, e.g. '2025-07-21T09:00:00'). Optional: description (string).",
                func=create_calendar_event_wrapper
            ),
            Tool(
                name="retrieve_relevant",
                description="Search for relevant memories from previous conversations using semantic similarity. Use when you need context from past interactions, when user references something discussed before, or when building on previous knowledge to provide better assistance.",
                func=retrieve_relevant_tool
            )
        ]

    def _create_agent(self):
        print("[ThothLangChainAgent] Creating agent with custom prompt...")
        # Create a custom prompt template
        agent_prompt = PromptTemplate.from_template("""
You are Thoth, a personalized AI collaborator created by Hari. Your purpose is to act as his strategic guide, personal assistant, and development partner. Think of yourself as a friendly JARVIS—brilliantly technical, but with a supportive and engaging personality.

Your primary goal is to help Hari learn, build, and solve problems in the most effective way possible.

Your Guiding Principles:
- Be a Knowledgeable Collaborator: Use the tools available to gather context about Hari's profile, skills, and projects
- Be Direct, Not Robotic: Provide clear technical solutions and teach step-by-step when needed
- Think Ahead: Connect the dots between current queries and larger goals
- Adapt Your Depth: Communicate on a technical level appropriate to the topic
- Be Flexible: Handle casual conversation naturally

TOOLS:
------
You have access to the following tools:

{tools}

Tool Capabilities Overview:
• web_search: Search the internet for current information, news, and developments. IMPORTANT: When using web_search, ALWAYS include the complete "Sources:" section from the tool output in your final answer to provide proper attribution.and your response should be based on the information provided by the tool.
• load_profile: Access Hari's profile including skills, projects, and background
• list_directory: Explore directory contents, view files and folder structure
• read_file: Read and analyze text file contents
• create_directory: Create new directories for project organization
• get_system_usage: Monitor system resources (CPU, memory, disk, processes)
• open_application: Launch applications and software utilities
• search_wikipedia: Access encyclopedic knowledge and factual information, you should use this tool when the user asks for historical stuffs and explicitly asks for Wikipedia information.
• list_calendar_events: Access upcoming Google Calendar events and schedule information
• create_calendar_event: Create new events in Google Calendar for scheduling. Required arguments: summary (string), start_time_iso (ISO 8601 string, e.g. '2025-07-21T08:00:00'), end_time_iso (ISO 8601 string, e.g. '2025-07-21T09:00:00'). Optional: description (string).
• retrieve_relevant: Search for relevant memories from previous conversations using semantic similarity. Use this tool when you need context from past interactions, when the user references something discussed before, or when building on previous knowledge. This helps provide continuity and personalized responses based on conversation history.

To use a tool, please use the following format:

```
Thought: Do I need to use a tool? Yes
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action (for create_calendar_event, provide all required arguments: summary, start_time_iso, end_time_iso, and optionally description)
Observation: the result of the action
```

When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:

```
Thought: Do I need to use a tool? No
Final Answer: [your response here]
```

IMPORTANT: If you used the web_search tool, you MUST include the complete "Sources:" section from the web search results at the end of your Final Answer. This provides proper attribution and allows users to verify information.

Always include a memory management analysis at the end of your response in this JSON format:
{{
    "should_save_memory": true_or_false,
    "summary": "If true, provide a concise summary of NEW information not already in user profile. If false, empty string."
}}

Begin!

Previous conversation history: {chat_history}

Human: {input}

Thought: {agent_scratchpad}
""")
        print("[ThothLangChainAgent] Custom agent prompt created.")
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=agent_prompt
        )
        print("[ThothLangChainAgent] ReAct agent created.")
        return agent

    def _parse_calendar_event_input(self, action_input):
        """
        Parse and validate input for create_calendar_event tool.
        Accepts dict, list, or string. Returns tuple (summary, start_time_iso, end_time_iso, description).
        """
        import dateutil.parser
        if isinstance(action_input, dict):
            summary = action_input.get('summary')
            start_time = action_input.get('start_time_iso')
            end_time = action_input.get('end_time_iso')
            description = action_input.get('description')
        elif isinstance(action_input, list) and len(action_input) >= 3:
            summary, start_time, end_time = action_input[:3]
            description = action_input[3] if len(action_input) > 3 else None
        elif isinstance(action_input, str):
            # Try to parse comma-separated string
            parts = [p.strip() for p in action_input.split(',')]
            if len(parts) >= 3:
                summary, start_time, end_time = parts[:3]
                description = parts[3] if len(parts) > 3 else None
            else:
                raise ValueError("create_calendar_event input must have summary, start_time_iso, end_time_iso")
        else:
            raise ValueError("Invalid input format for create_calendar_event")
        # Try to parse dates to ISO 8601
        try:
            start_time_iso = dateutil.parser.parse(start_time).isoformat()
            end_time_iso = dateutil.parser.parse(end_time).isoformat()
        except Exception:
            start_time_iso = start_time
            end_time_iso = end_time
        return summary, start_time_iso, end_time_iso, description

    def process_query(self, user_query: str, chat_history: str = "") -> Dict[str, Any]:
        print(f"[ThothLangChainAgent] Processing query: '{user_query}' with chat history length: {len(chat_history)}")
        if chat_history:
            print(f"[ThothLangChainAgent] Chat history content: {chat_history}")
        else:
            print("[ThothLangChainAgent] No chat history provided.")
        try:
            result = self.agent_executor.invoke({
                "input": user_query,
                "chat_history": chat_history
            })
            print(f"[ThothLangChainAgent] Agent output: {result}")
            response_text = result.get("output", "Sorry, I couldn't generate a response.")
            memory_info = self._extract_memory_json(response_text)
            print(f"[ThothLangChainAgent] Memory info: {memory_info}")
            return {
                "response": response_text,
                "memory": memory_info,
                "success": True
            }
        except Exception as e:
            error_msg = f"Error processing query: {str(e)}"
            print(f"[ThothLangChainAgent] {error_msg}")
            return {
                "response": error_msg,
                "memory": {"should_save_memory": False, "summary": ""},
                "success": False
            }

    def _extract_memory_json(self, response_text: str) -> Dict[str, Any]:
        print("[ThothLangChainAgent] Extracting memory JSON...")
        try:
            match = re.search(
                r'\{\s*"should_save_memory"\s*:\s*(true|false)\s*,\s*"summary"\s*:\s*"(.*?)"\s*\}',
                response_text,
                re.DOTALL
            )
            if match:
                should_save = match.group(1) == "true"
                summary = match.group(2)
                print(f"[ThothLangChainAgent] Found memory JSON: should_save_memory={should_save}, summary={summary}")
                return {
                    "should_save_memory": should_save,
                    "summary": summary
                }
            else:
                print("[ThothLangChainAgent] No valid memory JSON found.")
                return {
                    "should_save_memory": False,
                    "summary": ""
                }
        except Exception as e:
            print(f"[ThothLangChainAgent] Error extracting memory JSON: {e}")
            return {
                "should_save_memory": False,
                "summary": ""
            }

# Initialize the agent globally
print("[Global] Initializing ThothLangChainAgent...")
thoth_agent = ThothLangChainAgent()
print("[Global] ThothLangChainAgent initialized.")

def run_langchain_agent(user_query: str, chat_history: str = "") -> str:
    print(f"[run_langchain_agent] Received query: '{user_query}'")
    result = thoth_agent.process_query(user_query, chat_history)
    memory = result["memory"]
    print(f"[run_langchain_agent] Should Save Memory: {memory['should_save_memory']}")
    print(f"[run_langchain_agent] Summary: {memory['summary']}")
    return result["response"]
