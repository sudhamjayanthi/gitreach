import os
import random
import time
import csv
import json
import subprocess
from typing import Dict, List, Optional, TypedDict
from ghapi.core import GhApi
from mem0 import MemoryClient
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MEMO_API_KEY = os.getenv("MEM0_API_KEY")

TARGET_REPO = "mem0ai/mem0"

# Limit for testing purposes
MAX_DEPENDENTS = 5  

# Initialize clients
gh = GhApi(token=GITHUB_TOKEN)
memory = MemoryClient(MEMO_API_KEY)

class UserData(TypedDict):
    username: str
    name: Optional[str]
    email: Optional[str]
    repo_name: str
    repo_url: str
    repo_description: Optional[str]
    repo_stars: Optional[int]
    repo_language: Optional[str]
    repo_topics: Optional[List[str]]


def get_repo_dependents() -> List[Dict]:
    """Get list of repositories depending on target repo."""
    print(f"Fetching dependents for {TARGET_REPO}...")
    try:
        cmd = [
            "github-dependents-info",
            "--repo",
            TARGET_REPO,
            "--json",
            "--sort",
            "stars",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        dependents = json.loads(result.stdout)

        # hardcoded for mem0
        # dependents = json.loads(open("dependants.json").read())
        
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
    except Exception as e:
        print(f"Error fetching commits for {username}/{repo}: {str(e)}")
    return None


def get_user_data(dependent: Dict) -> Optional[UserData]:
    """Get GitHub user profile, email and repository details."""
    owner, repo_name = dependent["name"].split("/")
    try:
        user = gh.users.get_by_username(owner)
        email = user.email or get_email_from_commits(owner, repo_name)
        repo = gh.repos.get(owner=owner, repo=repo_name)

        return {
            "username": owner,
            "name": user.name,
            "email": email,
            "repo_name": repo_name,
            "repo_url": f"https://github.com/{dependent['name']}",
            "repo_description": repo.description,
            "repo_stars": repo.stargazers_count,
            "repo_language": repo.language,
            "repo_topics": repo.topics,
        }
    except Exception as e:
        print(f"Error getting data for {owner}: {str(e)}")
        return None


def process_user(user: UserData) -> Optional[str]:
    """Store user context and generate personalized email."""


    system = [
        {
            "role": "system",
            "content": f"""You are an AI assistant designed to help discover and connect with developers using {TARGET_REPO.split('/')[1]}.
            Your goal is to understand their usage context and create personalized, meaningful outreach as a Developer Relations Engineer at {TARGET_REPO.split('/')[1]}.
            Focus on building genuine connections by highlighting relevant {TARGET_REPO.split('/')[1]} features that could benefit their specific project.
            """,
        },
    ]

    #  we can use short term memory too here cause this is one time thing,
    # but lets stick to long term memory coz it will help us extend this into a whole platform to
    # manage these emails and reply to future emails agentically
    memory.add(system, user_id=user["username"], version="v2")

    context = [
        {"role": "user", "content": f"GitHub user @{user['username']} is a developer"},
        {
            "role": "user",
            "content": f"They have a repository called {user['repo_name']} which {user['repo_description'] or 'has no description'}",
        },
        {
            "role": "user",
            "content": f"Their repository is located at {user['repo_url']} and has {user['repo_stars']} stars",
        },
        {
            "role": "user",
            "content": f"The primary language used in the repository is {user['repo_language'] or 'not specified'}",
        },
        {
            "role": "user",
            "content": f"Repository topics: {', '.join(user['repo_topics']) if user['repo_topics'] else 'none specified'}",
        },
        {"role": "user", "content": f"They use {TARGET_REPO} in their project"},
        # add more info about the user from their github repo. like how they use it, project details, maybe run an agent to figure out how they are currently using mem0. you can also include more memories about user from their social media profiles or something, but its hard to find the correct user profiles and can often times go wrong cause of same names, unavailability of social profiles, using different handles on different platforms, etc.
    ]

    memory.add(context, user_id=user["username"], infer=False, version="v2")

    prompt = (
        f"Write a short, personalised email to {user['name']} about their use of {TARGET_REPO.split('/')[1]}."
    )
    memories = memory.search(query=prompt, user_id=user["username"])

    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    full_prompt = f"""
    {prompt} \
    Brief features of {TARGET_REPO.split('/')[1]} relevant to their project. \
    End the email asking to reach out for any kind of questions, feedback .
    Keep it short, simple and friendly. DO NOT INCLUDE ANY TAGS LIKE [Your Name] or [Insert two or three points here].
    
    User Details:
    {memories}
    """

    response = gemini_client.models.generate_content(
        model="gemini-2.0-flash", contents=full_prompt
    )
    return response.text if response else None


def save_contact(writer, user: UserData, email_content: str):
    """Save contact info and print email."""
    print(f"\nProcessed: {user['username']}")
    print("Generated Email:")
    print(email_content)
    print("-" * 80)
    writer.writerow([user["name"] or user["username"], user["email"], email_content])


def main():
    if not all([GITHUB_TOKEN, GEMINI_API_KEY, MEMO_API_KEY]):
        print("Error: Please set GITHUB_TOKEN, GEMINI_API_KEY, MEMO_API_KEY environment variables properly")
        return

    dependents = get_repo_dependents()
    print(f"Found {len(dependents)} dependents, processing first {MAX_DEPENDENTS}...")

    with open("emails.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "email", "email_content"])

        for dependent in random.sample(dependents, min(MAX_DEPENDENTS, len(dependents))):
            if user := get_user_data(dependent):
                if user["email"]:
                    if email := process_user(user):
                        save_contact(writer, user, email)
                        time.sleep(2)


if __name__ == "__main__":
    main()
