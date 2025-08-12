import os
from dotenv import load_dotenv
from github import Github, GithubException
import json
import requests

# Load environment variables
load_dotenv()

def get_github_client():
    """Initialize GitHub client"""
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_TOKEN environment variable not set")
    try:
        g = Github(github_token)
        user = g.get_user()
        print(f"[GitHubAPI] Authenticated as: {user.login}")
        return g
    except Exception as e:
        print(f"[GitHubAPI] Error: {e}")
        raise ValueError(f"GitHub authentication failed: {e}")

def call_openrouter_api(messages):
    """Call OpenRouter API directly using requests"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "Error: OPENROUTER_API_KEY not found"

    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://thoth-ai.com",
            "X-Title": "Thoth GitHub Agent",
            "Content-Type": "application/json"
        }
        data = {
            "model": "moonshotai/kimi-k2:free",
            "messages": messages,
            "max_tokens": 1500,
            "temperature": 0.3
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error calling OpenRouter API: {str(e)}"

def github_list_prs_tool(repo_full_name: str, state: str = "open") -> str:
    """List PRs for a repository"""
    try:
        g = get_github_client()
        repo = g.get_repo(repo_full_name)
        if state not in ["open", "closed", "all"]:
            return json.dumps({"error": "Invalid 'state' parameter. Must be 'open', 'closed', or 'all'."})

        pulls = repo.get_pulls(state=state, sort="created", direction="desc")
        pr_list = []
        for i, pull in enumerate(pulls):
            pr_list.append({
                "number": pull.number,
                "title": pull.title,
                "by": pull.user.login,
                "url": pull.html_url,
                "created": pull.created_at.isoformat(),
                "state": pull.state
            })
            if i >= 9:
                break

        if not pr_list:
            return json.dumps({
                "repository": repo_full_name,
                "pull_requests": [],
                "message": f"No {state} Pull Requests found for '{repo_full_name}'."
            })

        return json.dumps({
            "repository": repo_full_name,
            "state": state.capitalize(),
            "count": len(pr_list),
            "pull_requests": pr_list
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Error listing PRs: {str(e)}"})

def github_get_pr_details_tool(repo_full_name: str, pr_number: int) -> str:
    """Get detailed PR information"""
    try:
        g = get_github_client()
        repo = g.get_repo(repo_full_name)
        pull = repo.get_pull(pr_number)

        files_changed = []
        for file in pull.get_files():
            files_changed.append({
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "changes": file.changes
            })

        pr_diff = pull.get_patch()
        details = {
            "number": pull.number,
            "title": pull.title,
            "description": pull.body if pull.body else "No description provided.",
            "user": pull.user.login,
            "html_url": pull.html_url,
            "state": pull.state,
            "created_at": pull.created_at.isoformat(),
            "updated_at": pull.updated_at.isoformat(),
            "merged": pull.merged,
            "commits": pull.commits,
            "additions": pull.additions,
            "deletions": pull.deletions,
            "changed_files": pull.changed_files,
            "files_changed_list": files_changed,
            "diff_preview": pr_diff[:1000] if pr_diff else "No diff available"
        }
        return json.dumps(details, indent=2)
    except Exception as e:
        return f"Error getting PR details: {str(e)}"

def run_github_agent(user_query: str) -> str:
    """Main function to run the GitHub agent"""
    print(f"[GitHubAgent] Processing: '{user_query}'")

    try:
        # Simple query routing
        if "list" in user_query.lower() and ("pr" in user_query.lower() or "pull request" in user_query.lower()):
            # Extract repo name or use default
            words = user_query.split()
            repo_name = None
            for word in words:
                if "/" in word and len(word.split("/")) == 2:
                    repo_name = word
                    break

            if not repo_name:
                repo_name = "octocat/Hello-World"  # Default test repo

            result = github_list_prs_tool(repo_name, "open")

            # Check if result is valid JSON (structured data)
            try:
                pr_data = json.loads(result)
                if "pull_requests" in pr_data:
                    # Get AI analysis of the structured data
                    messages = [
                        {"role": "system", "content": "You are a GitHub PR review assistant. Analyze the PR data and provide insights."},
                        {"role": "user", "content": f"Here is the PR data: {result}\n\nProvide a brief analysis of these pull requests, focusing on patterns, activity, and notable PRs."}
                    ]
                    ai_analysis = call_openrouter_api(messages)

                    # Return structured response
                    return json.dumps({
                        "type": "github_pr_list",
                        "data": pr_data,
                        "analysis": ai_analysis
                    }, indent=2)
                else:
                    return result  # Return error as-is
            except:
                return result  # Fallback to original response

        elif "review" in user_query.lower() or "analyze" in user_query.lower():
            # Extract repo and PR number
            words = user_query.split()
            repo_name = None
            pr_number = None

            for word in words:
                if "/" in word and len(word.split("/")) == 2:
                    repo_name = word
                elif word.isdigit():
                    pr_number = int(word)
                elif word.startswith("#") and word[1:].isdigit():
                    pr_number = int(word[1:])

            if not repo_name:
                repo_name = "octocat/Hello-World"
            if not pr_number:
                pr_number = 1

            pr_details = github_get_pr_details_tool(repo_name, pr_number)

            # Get AI review
            messages = [
                {"role": "system", "content": "You are an expert code reviewer. Analyze the pull request and provide constructive feedback."},
                {"role": "user", "content": f"Please review this pull request:\n{pr_details}\n\nProvide a comprehensive review with suggestions."}
            ]
            ai_review = call_openrouter_api(messages)

            return f"📋 PR Details:\n{pr_details}\n\n🔍 AI Review:\n{ai_review}"

        else:
            # General GitHub query
            messages = [
                {"role": "system", "content": "You are a GitHub expert assistant. Help users with GitHub-related questions and tasks."},
                {"role": "user", "content": user_query}
            ]
            response = call_openrouter_api(messages)
            return response

    except Exception as e:
        return f"Error processing GitHub query: {str(e)}"

# Test function
if __name__ == "__main__":
    print("🚀 Testing GitHub Agent...")
    test_query = "List the open pull requests for octocat/Hello-World"
    result = run_github_agent(test_query)
    print("Result:", result)
