import os
import requests
from google import genai
from github import Github
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
PR_NUMBER = os.getenv("PR_NUMBER")

if not all([GITHUB_TOKEN, GEMINI_API_KEY, REPO_NAME]):
    raise ValueError("Missing required environment variables. Please check your .env file.")

# Initialize clients
gh = Github(GITHUB_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

def get_latest_open_pr(repo):
    """Fetch the most recent open pull request."""
    pulls = repo.get_pulls(state='open', sort='created', direction='desc')
    if pulls.totalCount == 0:
        return None
    return pulls[0]

def get_pr_diff(pr):
    """Fetch the diff of the pull request."""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff"
    }
    response = requests.get(pr.url, headers=headers)
    response.raise_for_status()
    
    return response.text

def get_ai_review(diff_text):
    """Send the diff to Gemini for review."""
    prompt = f"""
    You are an expert software developer and code reviewer.
    Please review the following code diff from a GitHub Pull Request.
    
    Provide constructive feedback, point out any potential bugs, security issues, 
    or performance improvements. Keep your review concise and professional.
    
    Code Diff:
    ```diff
    {diff_text}
    ```
    """
    
    print("Analyzing code with Google Gemini...")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return response.text

def main():
    print(f"Connecting to GitHub Repository: {REPO_NAME}")
    repo = gh.get_repo(REPO_NAME)
    
    if PR_NUMBER:
        print(f"Fetching diff for specific PR #{PR_NUMBER}...")
        pr = repo.get_pull(int(PR_NUMBER))
    else:
        print("Finding the most recent open PR...")
        pr = get_latest_open_pr(repo)
        if not pr:
            print("No open pull requests found.")
            return
        print(f"Fetching diff for latest PR #{pr.number}...")

    diff_text = get_pr_diff(pr)
    
    if not diff_text.strip():
        print("No changes found in this PR.")
        return

    # Truncate if diff is too large
    if len(diff_text) > 15000:
        diff_text = diff_text[:15000] + "\n... [Diff truncated due to length]"

    review_comment = get_ai_review(diff_text)
    
    print("Posting review to GitHub...")
    final_comment = f"🤖 **AI Code Review (by Gemini):**\n\n{review_comment}"
    pr.create_issue_comment(final_comment)
    
    print("AI Review posted successfully!")

if __name__ == "__main__":
    main()
