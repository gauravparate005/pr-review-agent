import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Try importing the Google GenAI SDK
try:
    from google import genai
except ImportError:
    print("Error: google-genai library is missing. Please run: pip install google-genai python-dotenv")
    sys.exit(1)

# Load environment variables (Make sure you have a .env file with GEMINI_API_KEY in the folder you run this)
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error: GEMINI_API_KEY environment variable not found.")
    print("Please set it in a .env file or your system environment.")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

# Folders to ignore during scan
IGNORED_DIRS = {'.git', 'venv', 'env', '__pycache__', 'node_modules', '.idea', '.vscode'}
# File types you want to check (you can add more like '.html', '.css', '.php')
ALLOWED_EXTENSIONS = {'.py', '.js', '.ts', '.html'}

def get_files_to_scan(start_path: str) -> list[str]:
    """
    Scans the given directory and its subdirectories for files with allowed extensions,
    while ignoring specified directories.

    Args:
        start_path: The root directory to start scanning from.

    Returns:
        A list of absolute file paths that match the allowed extensions and are not in ignored directories.
    """
    files_to_scan = []
    for root, dirs, files in os.walk(start_path):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]
        
        for file in files:
            ext = Path(file).suffix
            if ext in ALLOWED_EXTENSIONS:
                files_to_scan.append(os.path.join(root, file))
    return files_to_scan

def scan_file_for_issues(file_path: str) -> str | None:
    """
    Sends the content of a file to the AI model for a code review.
    The AI identifies code smells, unused variables, poor formatting, missing docstrings, or bad practices.

    Args:
        file_path: The absolute path to the file to be scanned.

    Returns:
        A string containing the identified issues if refactoring is needed,
        or None if the code is perfect or an API error occurred.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not content.strip():
            return None # Skip empty files

        # AI Prompt for Scanning
        prompt = f"""
You are an expert software engineer. Review the following code for code smells, unused variables, poor formatting, missing docstrings, or bad practices.
If the code is clean, follows best practices, and needs NO refactoring, reply EXACTLY with 'STATUS: PERFECT'.
If it needs refactoring, reply with 'STATUS: NEEDS_REFACTOR' on the first line, followed by 1-2 short bullet points explaining what needs to be fixed.

Code:
```
{content}
```
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        text = response.text.strip()
        if 'STATUS: NEEDS_REFACTOR' in text:
            # Extract issues by removing the status line
            issues = text.replace('STATUS: NEEDS_REFACTOR', '').strip()
            return issues
        else:
            return None # Perfect or unclear response
    except Exception as e:
        return f"API_ERROR: {e}"

def refactor_file(file_path: str, issues: str) -> bool:
    """
    Sends the content of a file along with identified issues to the AI model for refactoring.
    The AI returns the refactored code, which then overwrites the original file.

    Args:
        file_path: The absolute path to the file to be refactored.
        issues: A string describing the issues that need to be fixed in the code.

    Returns:
        True if the file was successfully refactored and overwritten, False otherwise.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # AI Prompt for Fixing
        prompt = f"""
You are an expert software engineer. Refactor the following code to fix the following issues:
{issues}

Rules:
1. Return ONLY the fully refactored code. 
2. DO NOT include any conversational text or explanations.
3. Wrap the code in standard markdown code blocks.

Code to refactor:
```
{content}
```
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        response_text = response.text.strip()
        
        # Robustly extract code from markdown block
        refactored_code = response_text
        start_marker = "```"
        end_marker = "```"
        
        start_index = response_text.find(start_marker)
        if start_index != -1:
            # Try to find the end of the first markdown block start line (e.g., ```python)
            code_block_start = response_text.find('\n', start_index)
            if code_block_start == -1: # No newline after ```, assume it's the whole string
                code_block_start = start_index + len(start_marker)
            else:
                code_block_start += 1 # Move past the newline character
            
            end_index = response_text.rfind(end_marker)
            
            # Ensure a valid code block was found and end marker is after the start
            if code_block_start > start_index and end_index != -1 and end_index > code_block_start:
                refactored_code = response_text[code_block_start:end_index].strip()
            # Else, fall back to the entire response text if extraction is ambiguous/failed

        # Overwrite the file with clean code
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(refactored_code)
            
        return True
    except Exception as e:
        print(f"Error refactoring {file_path}: {e}")
        return False

def main():
    """
    Main function to orchestrate the code scanning and refactoring process.
    It scans the current directory for supported files, identifies issues using AI,
    and optionally refactors the files based on user confirmation.
    """
    print("🚀 Starting AI Codebase Refactoring & Cleanup Agent...")
    current_dir = os.getcwd() # Gets the folder where the script is currently running
    print(f"📂 Scanning directory: {current_dir}\n")
    
    files = get_files_to_scan(current_dir)
    if not files:
        print("No supported files found to scan in this folder (e.g., .py, .js, .ts, .html).")
        return

    print(f"Found {len(files)} files to check. Scanning with AI...\n")
    
    files_to_refactor = []
    
    for file in files:
        rel_path = os.path.relpath(file, current_dir)
        print(f"🔍 Checking {rel_path}...", end=" ", flush=True)
        issues = scan_file_for_issues(file)
        
        if issues and str(issues).startswith("API_ERROR"):
            print(f"❌ {issues}")
        elif issues:
            print("⚠️ Needs Refactor")
            files_to_refactor.append((file, rel_path, issues))
        else:
            print("✅ Looks Good")
            
    if not files_to_refactor:
        print("\n🎉 Awesome! Your codebase is clean. No refactoring needed.")
        return
        
    # Show Summary
    print("\n" + "="*50)
    print("📋 REFACTORING REPORT (What needs to change)")
    print("="*50)
    
    for idx, (_, rel_path, issues) in enumerate(files_to_refactor, 1):
        print(f"\n[{idx}] 📄 File: {rel_path}")
        print(f"   💡 Issues Found:\n   {issues}")
        
    print("\n" + "="*50)
    choice = input("Do you want me to automatically fix all these files? (y/n): ").strip().lower()
    
    if choice == 'y':
        print("\n⚙️ Applying changes (AI is writing code)...")
        for file, rel_path, issues in files_to_refactor:
            print(f"🛠️ Refactoring {rel_path}...", end=" ", flush=True)
            success = refactor_file(file, issues)
            if success:
                print("✅ Done")
            else:
                print("❌ Failed")
        print("\n🎉 All refactoring tasks completed! Check your files.")
    else:
        print("\n🚫 Refactoring cancelled. No files were changed. You are safe!")

if __name__ == "__main__":
    main()
