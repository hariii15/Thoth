from tavily import TavilyClient
import os
import json
import psutil
import subprocess
import platform
import wikipediaapi
from pathlib import Path
import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def get_tavily_client():
    if not TAVILY_API_KEY:
        raise ValueError("Tavily API key not set in .env file.")
    return TavilyClient(TAVILY_API_KEY)

# --- TOOL DEFINITIONS ---
def web_search_tool(query: str) -> str:
    print(f"[Tool:web_search] Called with query: {query}")
    client = get_tavily_client()
    try:
        print(f"🔍 Performing web search for: '{query}'")
        response = client.search(
            query=query,
            max_results=5,
            search_depth="advanced"
        )
        print(f"[Tool:web_search] Tavily response: {response}")
        if "error" in response or not response.get("results"):
            return "Sorry, I failed to retrieve information from the web."
        results = []
        citations = []
        for i, result in enumerate(response["results"], 1):
            title = result.get('title', 'N/A')
            content = result.get('content', 'N/A')
            url = result.get('url', 'N/A')
            
            # Add to results with citation number
            results.append(f"[{i}] {content}")
              
            # Add to citations list
            citations.append(f"[{i}] {title} - {url}")
        
        # Combine results with citations at the end
        formatted_results = "\n\n".join(results)
        citations_section = "\n\nSources:\n" + "\n".join(citations)
        
        print(f"[Tool:web_search] Returning results with citations.")
        return formatted_results + citations_section
    except Exception as e:
        print(f"[Tool:web_search] Error: {e}")
        return f"Error during web search: {str(e)}"

def load_profile_tool(query: str = "") -> str:
    print(f"[Tool:load_profile] Called with query: {query}")
    try:
        with open("profile.md", "r", encoding="utf-8") as f:
            profile_content = f.read()
        print("[Tool:load_profile] Loaded profile.md successfully.")
        return f"User Profile Context:\n{profile_content}"
    except Exception as e:
        print(f"[Tool:load_profile] Error: {e}")
        return f"Error loading profile: {str(e)}"

def memory_analysis_tool(response: str, profile: str = "") -> str:
    """
    Analyze the response and profile, and return memory management JSON.
    This tool should be called at the end of every agent workflow.
    """
    import re
    print("[Tool:memory_analysis] Called.")
    # Try to extract the memory JSON from the response
    match = re.search(r'\{\s*"should_save_memory"\s*:\s*(true|false)\s*,\s*"summary"\s*:\s*"(.*?)"\s*\}', response, re.DOTALL)
    if match:
        should_save = match.group(1) == "true"
        summary = match.group(2)
        print(f"[Tool:memory_analysis] Found memory JSON: should_save_memory={should_save}, summary={summary}")
        return match.group(0)
    else:
        print("[Tool:memory_analysis] No valid memory JSON found.")
        return '{"should_save_memory": false, "summary": ""}'

def list_directory_tool(path: str = ".") -> str:
    """
    List the contents of a directory, including files and subdirectories.
    If path is not provided, lists the current directory.
    """
    print(f"[Tool:list_directory] Called with path: {path}")
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            return f"Error: Path '{path}' does not exist."
        
        if not path_obj.is_dir():
            return f"Error: '{path}' is not a directory."
        
        contents = []
        for item in path_obj.iterdir():
            if item.is_dir():
                contents.append(f"📁 {item.name}/")
            else:
                size = item.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024**2:
                    size_str = f"{size/1024:.1f}KB"
                else:
                    size_str = f"{size/(1024**2):.1f}MB"
                contents.append(f"📄 {item.name} ({size_str})")
        
        result = f"Directory: {path_obj.absolute()}\nContents ({len(contents)} items):\n" + "\n".join(contents)
        print(f"[Tool:list_directory] Listed {len(contents)} items.")
        return result
    except PermissionError:
        return f"Error: Permission denied accessing '{path}'"
    except Exception as e:
        print(f"[Tool:list_directory] Error: {e}")
        return f"Error listing directory: {str(e)}"

def read_file_tool(file_path: str) -> str:
    """
    Read and return the contents of a text file.
    """
    print(f"[Tool:read_file] Called with file_path: {file_path}")
    try:
        path_obj = Path(file_path)
        if not path_obj.exists():
            return f"Error: File '{file_path}' does not exist."
        
        if not path_obj.is_file():
            return f"Error: '{file_path}' is not a file."
        
        # Check if file is too large (limit to 1MB for safety)
        size = path_obj.stat().st_size
        if size > 1024 * 1024:
            return f"Error: File '{file_path}' is too large ({size/1024/1024:.1f}MB). Maximum size is 1MB."
        
        with open(path_obj, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"[Tool:read_file] Successfully read {len(content)} characters.")
        return f"File: {file_path}\nContent:\n{content}"
    except UnicodeDecodeError:
        return f"Error: '{file_path}' is not a text file or contains binary data."
    except PermissionError:
        return f"Error: Permission denied reading '{file_path}'"
    except Exception as e:
        print(f"[Tool:read_file] Error: {e}")
        return f"Error reading file: {str(e)}"

def create_directory_tool(path: str) -> str:
    """
    Create a new directory at the specified path.
    Creates parent directories if they don't exist.
    """
    print(f"[Tool:create_directory] Called with path: {path}")
    try:
        path_obj = Path(path)
        
        if path_obj.exists():
            if path_obj.is_dir():
                return f"Directory '{path}' already exists."
            else:
                return f"Error: '{path}' exists but is not a directory."
        
        path_obj.mkdir(parents=True, exist_ok=True)
        print(f"[Tool:create_directory] Successfully created directory: {path}")
        return f"Successfully created directory: {path_obj.absolute()}"
    except PermissionError:
        return f"Error: Permission denied creating directory '{path}'"
    except Exception as e:
        print(f"[Tool:create_directory] Error: {e}")
        return f"Error creating directory: {str(e)}"

def get_system_usage_tool(query: str = "") -> str:
    """
    Get current system resource usage including CPU, memory, disk, and running processes.
    """
    print(f"[Tool:get_system_usage] Called with query: {query}")
    try:
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Get memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used / (1024**3)  # GB
        memory_total = memory.total / (1024**3)  # GB
        
        # Get disk usage
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        disk_used = disk.used / (1024**3)  # GB
        disk_total = disk.total / (1024**3)  # GB
        
        # Get system info
        system_info = platform.system()
        system_release = platform.release()
        system_version = platform.version()
        
        # Get top processes by CPU usage
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by CPU usage and get top 5
        top_processes = sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:5]
        
        result = f"""System Usage Report:

🖥️ System Info:
- OS: {system_info} {system_release}
- Version: {system_version}

⚡ CPU Usage:
- Current: {cpu_percent}%
- Cores: {cpu_count}

💾 Memory Usage:
- Used: {memory_used:.1f}GB / {memory_total:.1f}GB ({memory_percent}%)

💿 Disk Usage:
- Used: {disk_used:.1f}GB / {disk_total:.1f}GB ({disk_percent:.1f}%)

🔥 Top Processes (by CPU):"""
        
        for i, proc in enumerate(top_processes, 1):
            result += f"\n{i}. {proc['name']} (PID: {proc['pid']}) - CPU: {proc['cpu_percent'] or 0:.1f}%, Memory: {proc['memory_percent'] or 0:.1f}%"
        
        print("[Tool:get_system_usage] System usage data collected.")
        return result
    except Exception as e:
        print(f"[Tool:get_system_usage] Error: {e}")
        return f"Error getting system usage: {str(e)}"

def open_application_tool(application_name: str) -> str:
    """
    Open an application or program on the system.
    """
    print(f"[Tool:open_application] Called with application_name: {application_name}")
    try:
        system = platform.system()
        
        if system == "Windows":
            # Try to start the application
            try:
                subprocess.Popen([application_name], shell=True)
                return f"Successfully opened '{application_name}' on Windows."
            except FileNotFoundError:
                # Try common application paths
                common_apps = {
                    "notepad": "notepad.exe",
                    "calculator": "calc.exe",
                    "paint": "mspaint.exe",
                    "chrome": "chrome.exe",
                    "firefox": "firefox.exe",
                    "edge": "msedge.exe",
                    "code": "code.exe",
                    "vscode": "code.exe"
                }
                app_exe = common_apps.get(application_name.lower())
                if app_exe:
                    subprocess.Popen([app_exe], shell=True)
                    return f"Successfully opened '{app_exe}' on Windows."
                else:
                    return f"Application '{application_name}' not found. Try using the exact executable name."
        
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", "-a", application_name])
            return f"Successfully opened '{application_name}' on macOS."
        
        elif system == "Linux":
            subprocess.Popen([application_name], shell=False)
            return f"Successfully opened '{application_name}' on Linux."
        
        else:
            return f"Unsupported operating system: {system}"
    
    except subprocess.SubprocessError as e:
        return f"Error opening application: {str(e)}"
    except Exception as e:
        print(f"[Tool:open_application] Error: {e}")
        return f"Error opening application: {str(e)}"

def search_wikipedia_tool(query: str) -> str:
    """
    Search Wikipedia for information on a given topic using the modern wikipediaapi library.
    """
    print(f"[Tool:search_wikipedia] Called with query: {query}")
    try:
        # Set a custom user agent as required by the API
        wiki_client = wikipediaapi.Wikipedia('ThothAgent/1.0 (harih@example.com)', 'en')
        page = wiki_client.page(query)
        
        if not page.exists():
            # Try searching for similar pages
            search_page = wiki_client.page(f"{query} (disambiguation)")
            if search_page.exists():
                # Get some related links from disambiguation page
                links = list(search_page.links.keys())[:5] if search_page.links else []
                suggestions = "\n".join([f"- {link}" for link in links])
                return f"The page '{query}' does not exist on Wikipedia.\n\nDid you mean:\n{suggestions}"
            else:
                return f"The page '{query}' does not exist on Wikipedia. Try being more specific or checking the spelling."
        
        # Get the first 3 sentences of the summary
        summary = ". ".join(page.summary.split(". ")[0:3]) + "."
        
        # Get some related links
        related_links = list(page.links.keys())[:3] if page.links else []
        related_section = ""
        if related_links:
            related_section = f"\n\n🔗 Related Topics:\n" + "\n".join([f"- {link}" for link in related_links])
        
        result = f"""Wikipedia Search Results for '{query}':

📖 Title: {page.title}
🔗 URL: {page.fullurl}

📝 Summary:
{summary}{related_section}"""
        
        print(f"[Tool:search_wikipedia] Found Wikipedia article: {page.title}")
        return result
        
    except Exception as e:
        print(f"[Tool:search_wikipedia] Error: {e}")
        return f"Error searching Wikipedia: {str(e)}"

def get_google_credentials(scopes):
    """
    Retrieves Google API credentials from credentials.json for user authorization.
    """
    try:
        token_path = 'token.json'
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Manual OAuth flow for installed app
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', scopes)
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        return creds
    except Exception as e:
        print(f"Error loading Google credentials: {e}")
        raise

def list_calendar_events(query: str = "") -> str:
    """
    Lists the next 10 upcoming events from the user's primary Google Calendar.
    Use this to check for upcoming meetings, find free time, or see what's on the schedule.
    This tool does not require any specific input.
    """
    print(f"[Tool:list_calendar_events] Called to get next 10 events.")
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    try:
        creds = get_google_credentials(SCOPES)
        service = build('calendar', 'v3', credentials=creds)
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=now,
            maxResults=10, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        if not events:
            return json.dumps({"status": "success", "events": "No upcoming events found."})
        formatted_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            formatted_events.append({
                "summary": event['summary'],
                "start_time": start
            })
        return json.dumps({"status": "success", "events": formatted_events})
    except Exception as e:
        return json.dumps({"error": str(e)})

def create_calendar_event(summary: str, start_time_iso: str, end_time_iso: str, description: str = None) -> str:
    """
    Creates a new event on the user's primary Google Calendar.
    The agent must provide the start and end times in ISO 8601 format (e.g., '2025-07-21T10:00:00').
    """
    print(f"[Tool:create_calendar_event] Called for summary: '{summary}'")
    SCOPES = ['https://www.googleapis.com/auth/calendar']  # Updated scope for full read/write access
    try:
        creds = get_google_credentials(SCOPES)
        service = build('calendar', 'v3', credentials=creds)
        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time_iso, 'timeZone': 'Asia/Kolkata'},
            'end': {'dateTime': end_time_iso, 'timeZone': 'Asia/Kolkata'},
        }
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return json.dumps({"status": "success", "event_link": created_event.get('htmlLink')})
    except Exception as e:
        return json.dumps({"error": str(e)})

def list_calendars() -> str:
    """
    Lists all calendars available in the user's Google Calendar account.
    This includes primary and secondary calendars.
    """
    print(f"[Tool:list_calendars] Called to list all calendars.")
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    try:
        creds = get_google_credentials(SCOPES)
        service = build('calendar', 'v3', credentials=creds)
        calendars_result = service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])
        
        if not calendars:
            return json.dumps({"status": "success", "calendars": "No calendars found."})
        
        formatted_calendars = []
        for calendar in calendars:
            formatted_calendars.append({
                "summary": calendar['summary'],
                "access_role": calendar['accessRole'],
                "id": calendar['id']
            })
        
        return json.dumps({"status": "success", "calendars": formatted_calendars})
    except Exception as e:
        return json.dumps({"error": str(e)})

def retrieve_relevant_tool(query: str) -> str:
    """
    Retrieve relevant memories from the vector database based on semantic similarity
    
    Args:
        query: The query text to search for relevant memories
        
    Returns:
        Formatted string with relevant memories or error message
    """
    print(f"[Tool:retrieve_relevant] Called with query: {query}")
    try:
        from vector_db import get_vector_db
        
        # Get vector database instance
        vector_db = get_vector_db()
        
        # Retrieve relevant memories
        memories = vector_db.retrieve_relevant_memories(query, top_k=3)
        
        if not memories:
            return "No relevant memories found for your query."
        
        # Format the results
        formatted_memories = []
        for i, memory in enumerate(memories, 1):
            score = memory["score"]
            text = memory["text"]
            timestamp = memory["timestamp"]
            
            # Only include high-confidence matches (score > 0.7)
            if score > 0.7:
                formatted_memories.append(
                    f"Memory {i} (Confidence: {score:.2f}):\n"
                    f"Time: {timestamp}\n"
                    f"Content: {text}\n"
                )
        
        if not formatted_memories:
            return "No highly relevant memories found (all matches below confidence threshold)."
        
        result = "Relevant memories from previous conversations:\n\n" + "\n".join(formatted_memories)
        print(f"[Tool:retrieve_relevant] Retrieved {len(formatted_memories)} relevant memories")
        return result
        
    except Exception as e:
        error_msg = f"Error retrieving memories: {str(e)}"
        print(f"[Tool:retrieve_relevant] Error: {error_msg}")
        return f"Unable to retrieve memories: {error_msg}"

# Tool registry mapping
tool_registry = {
    "web_search": web_search_tool,
    "load_profile": load_profile_tool,
    "list_directory": list_directory_tool,
    "read_file": read_file_tool,
    "create_directory": create_directory_tool,
    "get_system_usage": get_system_usage_tool,
    "open_application": open_application_tool,
    "search_wikipedia": search_wikipedia_tool,
    "list_calendar_events": list_calendar_events,
    "create_calendar_event": create_calendar_event,
    "list_calendars": list_calendars,
    "retrieve_relevant": retrieve_relevant_tool,
}

def get_tool(name: str):
    return tool_registry.get(name)

def get_all_tools():
    return tool_registry
