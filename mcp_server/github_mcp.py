import os
import sys
import logging
import requests
from mcp.server.fastmcp import FastMCP

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("github-mcp-server")

# Load configuration from environment
GITHUB_PAT = os.getenv("GITHUB_PAT")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")  # Default repo (e.g. 'owner/repo')

# Validate token at startup
if not GITHUB_PAT:
    logger.warning("WARNING: GITHUB_PAT environment variable is not set. GitHub tools will fail to authenticate.")

# Initialize FastMCP Server
mcp = FastMCP("GitHub-MCP-Server")

def get_headers():
    if not GITHUB_PAT:
        raise ValueError("GitHub PAT is not configured. Please set the GITHUB_PAT environment variable.")
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevAssist-MCP-Server"
    }

@mcp.tool()
def github_search_code(query: str, repo: str = None) -> str:
    """
    Search for code or files in a GitHub repository.
    
    Args:
        query: The search term or query (e.g. 'def authenticate', 'TODO', 'filename:auth.py').
        repo: The repository to search in, in 'owner/repo' format. If not provided, the default GITHUB_REPOSITORY is used.
    
    Returns:
        A markdown-formatted string with search results or an error message.
    """
    target_repo = repo or GITHUB_REPOSITORY
    if not target_repo:
        return "Error: No GitHub repository specified and no default GITHUB_REPOSITORY configured in environment."

    logger.info(f"Searching code in repo '{target_repo}' with query '{query}'")
    
    # GitHub code search API requires search qualifiers like `repo:owner/repo`
    # URL: https://api.github.com/search/code
    url = "https://api.github.com/search/code"
    params = {"q": f"{query} repo:{target_repo}"}
    
    try:
        response = requests.get(url, headers=get_headers(), params=params)
        if response.status_code == 403 or response.status_code == 429:
            # Check rate limiting or scope issues
            return f"Error: GitHub API Rate limit exceeded or access denied (Status {response.status_code}). Detail: {response.text}"
        
        response.raise_for_status()
        data = response.json()
        
        items = data.get("items", [])
        if not items:
            return f"No results found for query '{query}' in repository '{target_repo}'."
            
        results = [f"### Code Search Results for '{query}' in {target_repo} (Total: {data.get('total_count', 0)})\n"]
        for idx, item in enumerate(items[:5]):  # limit to top 5 results for context window efficiency
            name = item.get("name")
            path = item.get("path")
            html_url = item.get("html_url")
            results.append(f"{idx+1}. **[{name}]({html_url})**\n   - Path: `{path}`")
            
        return "\n".join(results)
    except requests.exceptions.HTTPError as e:
        logger.error(f"GitHub Search HTTP Error: {e.response.text}")
        return f"Error searching code in GitHub: HTTP {e.response.status_code} - {e.response.json().get('message', str(e))}"
    except Exception as e:
        logger.error(f"GitHub Search Error: {str(e)}")
        return f"Error searching code: {str(e)}"

@mcp.tool()
def github_create_issue(title: str, body: str, repo: str = None) -> str:
    """
    Create a new issue in a GitHub repository.
    
    Args:
        title: The title of the issue.
        body: The body content of the issue (markdown supported).
        repo: The repository to create the issue in, in 'owner/repo' format. If not provided, the default GITHUB_REPOSITORY is used.
        
    Returns:
        A success message with the issue URL or an error message.
    """
    target_repo = repo or GITHUB_REPOSITORY
    if not target_repo:
        return "Error: No GitHub repository specified and no default GITHUB_REPOSITORY configured in environment."

    logger.info(f"Creating issue in repo '{target_repo}' with title '{title}'")
    
    url = f"https://api.github.com/repos/{target_repo}/issues"
    payload = {"title": title, "body": body}
    
    try:
        response = requests.post(url, headers=get_headers(), json=payload)
        response.raise_for_status()
        data = response.json()
        issue_number = data.get("number")
        html_url = data.get("html_url")
        return f"Successfully created GitHub issue #{issue_number}: [Issue Link]({html_url})"
    except requests.exceptions.HTTPError as e:
        logger.error(f"GitHub Create Issue HTTP Error: {e.response.text}")
        return f"Error creating GitHub issue: HTTP {e.response.status_code} - {e.response.json().get('message', str(e))}"
    except Exception as e:
        logger.error(f"GitHub Create Issue Error: {str(e)}")
        return f"Error creating issue: {str(e)}"

@mcp.tool()
def github_comment_pr(pr_number: int, comment: str, repo: str = None) -> str:
    """
    Add a comment to an existing GitHub Pull Request (or Issue).
    
    Args:
        pr_number: The pull request (or issue) number to comment on.
        comment: The markdown text of the comment.
        repo: The repository, in 'owner/repo' format. If not provided, the default GITHUB_REPOSITORY is used.
        
    Returns:
        A success message with the comment URL or an error message.
    """
    target_repo = repo or GITHUB_REPOSITORY
    if not target_repo:
        return "Error: No GitHub repository specified and no default GITHUB_REPOSITORY configured in environment."

    logger.info(f"Commenting on PR/Issue #{pr_number} in repo '{target_repo}'")
    
    # In GitHub, Pull Requests are also Issues, so commenting on them uses the issues comments API
    url = f"https://api.github.com/repos/{target_repo}/issues/{pr_number}/comments"
    payload = {"body": comment}
    
    try:
        response = requests.post(url, headers=get_headers(), json=payload)
        response.raise_for_status()
        data = response.json()
        html_url = data.get("html_url")
        return f"Successfully added comment to PR/Issue #{pr_number}: [Comment Link]({html_url})"
    except requests.exceptions.HTTPError as e:
        logger.error(f"GitHub Comment PR HTTP Error: {e.response.text}")
        return f"Error commenting on PR: HTTP {e.response.status_code} - {e.response.json().get('message', str(e))}"
    except Exception as e:
        logger.error(f"GitHub Comment PR Error: {str(e)}")
        return f"Error commenting on PR: {str(e)}"

if __name__ == "__main__":
    logger.info("Starting GitHub MCP Server...")
    mcp.run()
