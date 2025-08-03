import os
from dotenv import load_dotenv
from typing import Dict, Any, List, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import json
import re

# Import our existing agents
from langchain_agent import run_langchain_agent, thoth_agent
from github_agent import run_github_agent
from coding_agent import run_coding_agent

load_dotenv()

class CollaborativeState(TypedDict):
    """State for the collaborative agent system"""
    messages: Annotated[List[BaseMessage], add_messages]
    user_query: str
    routing_decision: str
    thoth_response: str
    github_response: str
    coding_response: str
    final_response: str
    needs_collaboration: bool
    chat_history: str
    validation_passed: bool
    validation_message: str
    is_coding_request: bool

def validate_github_response(response: str, query: str) -> Dict[str, Any]:
    """
    Validate if GitHub agent response follows the expected JSON format
    Returns validation result with feedback
    """
    print(f"[Validator] Validating GitHub response for query: '{query}'")

    # Check if it's a PR listing query
    is_pr_list_query = "list" in query.lower() and ("pr" in query.lower() or "pull request" in query.lower())

    if is_pr_list_query:
        try:
            # Try to parse as JSON
            parsed = json.loads(response)

            # Check if it has the expected structure for PR list
            expected_fields = ["type", "data", "analysis"]
            if parsed.get("type") == "github_pr_list" and "data" in parsed:
                data = parsed["data"]
                required_data_fields = ["repository", "pull_requests"]

                if all(field in data for field in required_data_fields):
                    # Check if pull_requests is a list with proper structure
                    pr_list = data.get("pull_requests", [])
                    if isinstance(pr_list, list):
                        if len(pr_list) > 0:
                            # Validate first PR structure
                            first_pr = pr_list[0]
                            required_pr_fields = ["number", "title", "by", "url", "created"]
                            if all(field in first_pr for field in required_pr_fields):
                                return {
                                    "valid": True,
                                    "message": "✅ GitHub response format is correct",
                                    "format_type": "structured_pr_list"
                                }
                            else:
                                missing_fields = [f for f in required_pr_fields if f not in first_pr]
                                return {
                                    "valid": False,
                                    "message": f"❌ PR objects missing required fields: {missing_fields}",
                                    "format_type": "invalid_pr_structure"
                                }
                        else:
                            # Empty PR list is valid
                            return {
                                "valid": True,
                                "message": "✅ Valid response - no PRs found",
                                "format_type": "empty_pr_list"
                            }
                    else:
                        return {
                            "valid": False,
                            "message": "❌ pull_requests should be a list",
                            "format_type": "invalid_pr_list_type"
                        }
                else:
                    missing_fields = [f for f in required_data_fields if f not in data]
                    return {
                        "valid": False,
                        "message": f"❌ Missing required data fields: {missing_fields}",
                        "format_type": "missing_data_fields"
                    }
            else:
                return {
                    "valid": False,
                    "message": "❌ Response missing 'type': 'github_pr_list' or 'data' field",
                    "format_type": "missing_structure"
                }

        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "message": f"❌ Response is not valid JSON: {str(e)}",
                "format_type": "invalid_json"
            }
    else:
        # For non-PR listing queries, check if it's valid JSON (for other structured responses)
        try:
            json.loads(response)
            return {
                "valid": True,
                "message": "✅ Valid JSON response",
                "format_type": "valid_json"
            }
        except:
            # For non-structured responses, consider them valid
            return {
                "valid": True,
                "message": "✅ Valid text response",
                "format_type": "text_response"
            }

def provide_format_feedback(validation_result: Dict[str, Any], original_query: str) -> str:
    """Provide feedback to help fix format issues"""
    if validation_result["valid"]:
        return ""

    feedback_messages = {
        "invalid_json": """
🔧 **Format Error**: The response should be valid JSON format.

**Expected format for PR listings:**
```json
{
    "type": "github_pr_list",
    "data": {
        "repository": "owner/repo",
        "state": "Open",
        "count": 1,
        "pull_requests": [
            {
                "number": 4166,
                "title": "PR Title",
                "by": "username",
                "url": "https://github.com/owner/repo/pull/4166",
                "created": "2025-08-03T07:00:06"
            }
        ]
    },
    "analysis": "AI analysis text"
}
```
""",
        "missing_structure": """
🔧 **Format Error**: Missing required structure.

The response should include:
- `"type": "github_pr_list"`
- `"data"` object with repository and pull_requests
- `"analysis"` text (optional)
""",
        "missing_data_fields": """
🔧 **Format Error**: The data object is missing required fields.

Required fields in data:
- `repository`: string (e.g., "octocat/Hello-World")
- `pull_requests`: array of PR objects
""",
        "invalid_pr_structure": """
🔧 **Format Error**: PR objects missing required fields.

Each PR object must have:
- `number`: integer
- `title`: string
- `by`: string (author username)
- `url`: string (full GitHub URL)
- `created`: string (ISO date)
""",
        "invalid_pr_list_type": """
🔧 **Format Error**: pull_requests must be an array/list, not a different type.
"""
    }

    error_type = validation_result.get("format_type", "unknown")
    return feedback_messages.get(error_type, f"❌ Unknown format error: {validation_result['message']}")

class CollaborativeAgentSystem:
    def __init__(self):
        print("[CollaborativeAgent] Initializing collaborative agent system...")
        self.graph = self._create_graph()
        print("[CollaborativeAgent] LangGraph workflow created.")

    def _create_graph(self) -> StateGraph:
        """Create the LangGraph workflow for agent collaboration"""
        
        # Define the workflow
        workflow = StateGraph(CollaborativeState)
        
        # Add nodes
        workflow.add_node("router", self._route_query)
        workflow.add_node("thoth_agent", self._call_thoth_agent)
        workflow.add_node("github_agent", self._call_github_agent)
        workflow.add_node("coding_agent", self._call_coding_agent)
        workflow.add_node("collaboration_node", self._collaborate_agents)
        workflow.add_node("validation_node", self._validate_response)
        workflow.add_node("final_synthesis", self._synthesize_response)
        
        # Define the routing logic
        workflow.set_entry_point("router")
        
        # Router decides which agent(s) to call
        workflow.add_conditional_edges(
            "router",
            self._routing_decision,
            {
                "thoth_only": "thoth_agent",
                "github_only": "github_agent",
                "coding_only": "coding_agent",
                "collaborate": "collaboration_node",
                "end": "final_synthesis"
            }
        )
        
        # After individual agents, validate responses
        workflow.add_edge("thoth_agent", "validation_node")
        workflow.add_edge("github_agent", "validation_node")
        workflow.add_edge("coding_agent", "validation_node")
        workflow.add_edge("collaboration_node", "validation_node")
        
        # After validation, go to synthesis
        workflow.add_edge("validation_node", "final_synthesis")
        workflow.add_edge("final_synthesis", END)
        
        return workflow.compile()

    def _route_query(self, state: CollaborativeState) -> CollaborativeState:
        """Analyze the query and decide which agents to use"""
        query = state["user_query"].lower()
        
        # Check if this is explicitly a coding request
        is_coding_request = state.get("is_coding_request", False)
        
        # Coding-related keywords
        coding_keywords = [
            "code", "programming", "algorithm", "function", "class", "variable",
            "debug", "implement", "refactor", "optimize", "python", "javascript",
            "java", "c++", "react", "node.js", "api", "database", "sql",
            "data structure", "sorting", "recursion", "loop", "conditional",
            "teach me", "explain how to", "tutorial", "example code"
        ]
        
        # GitHub-related keywords
        github_keywords = [
            "github", "pull request", "pr", "repository", "repo", "code review",
            "commit", "merge", "branch", "fork", "issue", "pull", "push",
            "octocat", "hello-world", "list pr", "open pr", "review pr"
        ]
        
        # General assistant keywords  
        thoth_keywords = [
            "calendar", "schedule", "meeting", "event", "file", "directory",
            "system", "cpu", "memory", "wikipedia", "search", "web", "profile"
        ]
        
        # Check for different types of queries
        has_coding = is_coding_request or any(keyword in query for keyword in coding_keywords)
        has_github = any(keyword in query for keyword in github_keywords)
        has_thoth = any(keyword in query for keyword in thoth_keywords)
        
        # Special handling for GitHub repository patterns like "owner/repo"
        import re
        if re.search(r'\w+/\w+', query):  # Matches patterns like "octocat/Hello-World"
            has_github = True
        
        # Determine routing decision
        if has_coding and (has_github or has_thoth):
            routing_decision = "collaborate"
            needs_collaboration = True
        elif has_coding:
            routing_decision = "coding_only"
            needs_collaboration = False
        elif has_github and has_thoth:
            routing_decision = "collaborate"
            needs_collaboration = True
        elif has_github:
            routing_decision = "github_only"
            needs_collaboration = False
        elif has_thoth or "help" in query or "how" in query:
            routing_decision = "thoth_only"
            needs_collaboration = False
        else:
            # Default to Thoth for general queries
            routing_decision = "thoth_only"
            needs_collaboration = False
        
        print(f"[Router] Query: '{state['user_query']}'")
        print(f"[Router] Is coding request: {is_coding_request}")
        print(f"[Router] Has coding keywords: {has_coding}")
        print(f"[Router] Has GitHub keywords: {has_github}")
        print(f"[Router] Has Thoth keywords: {has_thoth}")
        print(f"[Router] Decision: {routing_decision}, Collaboration needed: {needs_collaboration}")
        
        state["routing_decision"] = routing_decision
        state["needs_collaboration"] = needs_collaboration
        state["is_coding_request"] = is_coding_request
        
        return state

    def _routing_decision(self, state: CollaborativeState) -> str:
        """Return the routing decision for conditional edges"""
        return state["routing_decision"]

    def _call_thoth_agent(self, state: CollaborativeState) -> CollaborativeState:
        """Call the Thoth LangChain agent"""
        print("[CollaborativeAgent] Calling Thoth agent...")
        try:
            result = thoth_agent.process_query(state["user_query"], state.get("chat_history", ""))
            state["thoth_response"] = result["response"]
            print(f"[CollaborativeAgent] Thoth response length: {len(state['thoth_response'])}")
        except Exception as e:
            state["thoth_response"] = f"Error from Thoth agent: {str(e)}"
            print(f"[CollaborativeAgent] Thoth agent error: {e}")

        return state

    def _call_github_agent(self, state: CollaborativeState) -> CollaborativeState:
        """Call the GitHub agent"""
        print("[CollaborativeAgent] Calling GitHub agent...")
        try:
            state["github_response"] = run_github_agent(state["user_query"])
            print(f"[CollaborativeAgent] GitHub response length: {len(state['github_response'])}")
        except Exception as e:
            state["github_response"] = f"Error from GitHub agent: {str(e)}"
            print(f"[CollaborativeAgent] GitHub agent error: {e}")

        return state

    def _call_coding_agent(self, state: CollaborativeState) -> CollaborativeState:
        """Call the coding agent"""
        print("[CollaborativeAgent] Calling Coding agent...")
        try:
            state["coding_response"] = run_coding_agent(state["user_query"])
            print(f"[CollaborativeAgent] Coding response length: {len(state['coding_response'])}")
        except Exception as e:
            state["coding_response"] = f"Error from Coding agent: {str(e)}"
            print(f"[CollaborativeAgent] Coding agent error: {e}")
        
        return state

    def _collaborate_agents(self, state: CollaborativeState) -> CollaborativeState:
        """Run multiple agents and prepare for collaboration"""
        print("[CollaborativeAgent] Running collaboration between agents...")
        
        routing = state["routing_decision"]
        
        # Always call Thoth agent for collaboration
        state = self._call_thoth_agent(state)
        
        # Call additional agents based on query content
        if state.get("is_coding_request", False) or any(keyword in state["user_query"].lower() 
                                                       for keyword in ["code", "programming", "algorithm"]):
            state = self._call_coding_agent(state)
        
        if any(keyword in state["user_query"].lower() 
               for keyword in ["github", "pull request", "repository"]):
            state = self._call_github_agent(state)
        
        print("[CollaborativeAgent] All agents completed for collaboration.")
        return state

    def _validate_response(self, state: CollaborativeState) -> CollaborativeState:
        """Validate the response format and provide feedback if needed"""
        print("[CollaborativeAgent] Validating response format...")

        routing = state["routing_decision"]

        # Validate GitHub agent responses
        if routing in ["github_only", "collaborate"] and state.get("github_response"):
            validation_result = validate_github_response(state["github_response"], state["user_query"])
            state["validation_passed"] = validation_result["valid"]
            state["validation_message"] = validation_result["message"]

            print(f"[Validator] GitHub response validation: {validation_result['message']}")

            # If validation failed, provide feedback
            if not validation_result["valid"]:
                feedback = provide_format_feedback(validation_result, state["user_query"])
                state["github_response"] = f"{state['github_response']}\n\n{feedback}"
                print(f"[Validator] Added format feedback to response")
        else:
            state["validation_passed"] = True
            state["validation_message"] = "No validation needed"

        return state

    def _synthesize_response(self, state: CollaborativeState) -> CollaborativeState:
        """Synthesize the final response from agent outputs"""
        print("[CollaborativeAgent] Synthesizing final response...")
        
        routing = state["routing_decision"]
        
        if routing == "thoth_only":
            state["final_response"] = state["thoth_response"]
        elif routing == "github_only":
            final_response = state["github_response"]
            if not state.get("validation_passed", True):
                final_response += f"\n\n⚠️ **Format Validation**: {state.get('validation_message', 'Format issues detected')}"
            state["final_response"] = final_response
        elif routing == "coding_only":
            state["final_response"] = state["coding_response"]
        elif routing == "collaborate":
            # Combine responses intelligently
            final_response = self._combine_responses(
                state["user_query"],
                state.get("thoth_response", ""),
                state.get("github_response", ""), 
                state.get("coding_response", "")
            )
            if not state.get("validation_passed", True):
                final_response += f"\n\n⚠️ **Format Validation**: {state.get('validation_message', 'Format issues detected')}"
            state["final_response"] = final_response
        else:
            state["final_response"] = "I'm not sure how to help with that query."
        
        print(f"[CollaborativeAgent] Final response length: {len(state['final_response'])}")
        return state

    def _combine_responses(self, query: str, thoth_response: str, github_response: str, coding_response: str) -> str:
        """Intelligently combine responses from multiple agents"""
        
        # If we have a coding response, prioritize it
        if coding_response:
            try:
                coding_data = json.loads(coding_response)
                if coding_data.get("type") == "coding_response":
                    return coding_response  # Return structured coding response as-is
            except:
                pass
        
        # Otherwise, use existing combination logic
        if github_response and thoth_response:
            synthesis_prompt = f"""
You are combining responses from specialized agents to provide a comprehensive answer.

Original Query: {query}

Thoth Agent Response: {thoth_response}
GitHub Agent Response: {github_response}
{f"Coding Agent Response: {coding_response}" if coding_response else ""}

Please provide a unified, coherent response that combines the best insights from all agents.
"""
            
            try:
                result = thoth_agent.process_query(synthesis_prompt, "")
                return result["response"]
            except Exception as e:
                return f"🤖 **Collaborative Response**\n\n{thoth_response}\n\n{github_response}\n\n{coding_response if coding_response else ''}"
        
        # Fallback to individual responses
        return coding_response or github_response or thoth_response or "No response generated."

    def process_query(self, user_query: str, chat_history: str = "", is_coding_request: bool = False) -> Dict[str, Any]:
        """Process a query through the collaborative system"""
        print(f"[CollaborativeAgent] Processing query: '{user_query}' (coding: {is_coding_request})")
        
        try:
            # Initialize state
            initial_state = CollaborativeState(
                messages=[HumanMessage(content=user_query)],
                user_query=user_query,
                routing_decision="",
                thoth_response="",
                github_response="",
                coding_response="",
                final_response="",
                needs_collaboration=False,
                chat_history=chat_history,
                validation_passed=True,
                validation_message="",
                is_coding_request=is_coding_request
            )
            
            # Run the workflow
            final_state = self.graph.invoke(initial_state)
            
            return {
                "response": final_state["final_response"],
                "routing_decision": final_state["routing_decision"],
                "needs_collaboration": final_state["needs_collaboration"],
                "validation_passed": final_state.get("validation_passed", True),
                "validation_message": final_state.get("validation_message", ""),
                "is_coding_request": final_state.get("is_coding_request", False),
                "success": True
            }
            
        except Exception as e:
            error_msg = f"Error in collaborative processing: {str(e)}"
            print(f"[CollaborativeAgent] {error_msg}")
            return {
                "response": error_msg,
                "routing_decision": "error",
                "needs_collaboration": False,
                "validation_passed": False,
                "validation_message": "Processing error",
                "is_coding_request": is_coding_request,
                "success": False
            }

# Initialize the collaborative system globally
print("[Global] Initializing CollaborativeAgentSystem...")
collaborative_system = CollaborativeAgentSystem()
print("[Global] CollaborativeAgentSystem initialized.")

def run_collaborative_agent(user_query: str, chat_history: str = "") -> str:
    """Main function to run the collaborative agent system"""
    print(f"[run_collaborative_agent] Received query: '{user_query}'")
    result = collaborative_system.process_query(user_query, chat_history)

    print(f"[run_collaborative_agent] Routing: {result['routing_decision']}")
    print(f"[run_collaborative_agent] Collaboration: {result['needs_collaborative']}")
