# filepath: /home/hari/Desktop/Thoth/thoth_backend/test_github_agent.py
from github_agent import run_github_agent

def test_github_agent():
    # Example query to list open pull requests for a repository
    query = "List the open pull requests for octocat/Hello-World"
    print(f"Running query: {query}")
    response = run_github_agent(query)
    print("Response:")
    print(response)

if __name__ == "__main__":
    test_github_agent()
