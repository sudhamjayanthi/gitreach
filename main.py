import os
import csv
import json
import subprocess
from typing import Dict, List, Optional, TypedDict
from ghapi.core import GhApi
from mem0 import Memory
from dotenv import load_dotenv

load_dotenv()

# Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TARGET_REPO = "mem0ai/mem0"
MAX_DEPENDENTS = 10  # Limit for testing purposes

# Initialize clients
gh = GhApi(token=GITHUB_TOKEN)
memory = Memory.from_config(
    {
        "llm": {
            "provider": "gemini",
            "config": {
                "model": "gemini-1.5-flash-latest",
                "temperature": 0.2,
                "max_tokens": 2000,
            },
        },
        "embedder": {
            "provider": "gemini",
            "config": {
                "model": "models/text-embedding-004",
            },
        },
    }
)


class UserData(TypedDict):
    username: str
    name: Optional[str]
    email: Optional[str]
    repo_name: str
    repo_url: str


def get_repo_dependents() -> List[Dict]:
    """Get list of repositories depending on target repo."""
    print(f"Fetching dependents for {TARGET_REPO}...")
    try:
        # cmd = [
        #     "github-dependents-info",
        #     "--repo",
        #     TARGET_REPO,
        #     "--json",
        #     "--sort",
        #     "stars",
        # ]
        # result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # dependents = json.loads(result.stdout)
        dependents = json.loads(open("dependants.json").read())
        print(dependents.values())
        return list(dependents["all_public_dependent_repos"])
    except Exception as e:
        print(f"Error fetching dependents: {str(e)}")
        return []


def get_email_from_commits(username: str, repo: str) -> Optional[str]:
    """Extract user's email from their recent commits."""
    try:
        commits = gh.repos.list_commits(owner=username, repo=repo)
        for commit in commits:
            if commit.commit.author and not commit.commit.author.email.endswith(
                "@users.noreply.github.com"
            ):
                return commit.commit.author.email
    except:
        print(f"Error fetching commits for {username}/{repo}")
    return None


def get_user_data(dependent: Dict) -> Optional[UserData]:
    """Get GitHub user profile and email."""
    owner, repo_name = dependent["name"].split("/")
    try:
        user = gh.users.get_by_username(owner)
        email = user.email or get_email_from_commits(owner, repo_name)

        return {
            "username": owner,
            "name": user.name,
            "email": email,
            "repo_name": repo_name,
            "repo_url": f"https://github.com/{dependent['name']}",
        }
    except Exception as e:
        print(f"Error getting data for {owner}: {str(e)}")
        return None


def process_user(user: UserData) -> Optional[str]:
    """Store user context and generate personalized email."""
    # Store context
    memory.add(f"GitHub user @{user['username']} uses mem0 in their repo {user['repo_name']} ({user['repo_url']})", user_id=user["username"])
    # Generate email
    prompt = f"Write a short, friendly email to {user['name'] or user['username']} about their use of mem0 in {user['repo_name']}. List a brief of the features of mem0 and how it can be used to enhance their project. End the email asking to book a call for any kind of help, feedback or questions."
    result = memory.add(prompt, user_id=user["username"])
    return result.content if result else None


def save_contact(writer, user: UserData, email_content: str):
    """Save contact info and print email."""
    print(f"\nProcessed: {user['username']}")
    print("Generated Email:")
    print(email_content)
    print("-" * 80)
    writer.writerow([user["name"] or user["username"], user["email"]])


def main():
    if not all([GITHUB_TOKEN, GEMINI_API_KEY]):
        print("Error: Please set GITHUB_TOKEN and GEMINI_API_KEY environment variables")
        return

    # Get and process dependents
    dependents = get_repo_dependents()
    print(f"Found {len(dependents)} dependents, processing first {MAX_DEPENDENTS}...")

    # Process users and save results
    with open("emails.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "email"])

        for dependent in dependents[:MAX_DEPENDENTS]:
            if user := get_user_data(dependent):
                if user["email"]:
                    if email := process_user(user):
                        save_contact(writer, user, email)


if __name__ == "__main__":
    main()
