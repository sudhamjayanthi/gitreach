import os
import subprocess
import sys
import time
import json
import traceback
import csv
from typing import Dict, List, Optional, TypedDict, Generator, Any
from flask import (
    Flask,
    render_template,
    request,
    Response,
    stream_with_context,
    jsonify,
)
from ghapi.core import GhApi
from mem0 import MemoryClient
from google import genai
from dotenv import load_dotenv
import base64

load_dotenv()

# Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MEM0_API_KEY = os.getenv("MEM0_API_KEY")

# Limit for testing purposes
MAX_DEPENDENTS = 5

# Initialize clients
gh = GhApi(token=GITHUB_TOKEN)
memory = MemoryClient(api_key=MEM0_API_KEY)


# --- Type Definitions (copied from main.py) ---
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


# --- Core Logic Functions (adapted from main.py) ---

def get_repo_dependents(target_repo: str) -> List[Dict]:
    """Get list of repositories depending on target repo."""
    print(f"Fetching dependents for {target_repo}...")
    try:
        cmd = [
            "github-dependents-info",
            "--repo", 
            target_repo,
            "--json",
            "--sort",
            "stars",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)    
        dependents = json.loads(result.stdout)
        with open(f"{target_repo.replace('/', '-')}-dependants.json", "w") as f:
            json.dump(dependents, f, indent=2)

        print(f"Found {len(dependents['all_public_dependent_repos'])} public repositories depending on {target_repo}")
        print("Saved to dependents.json")
        
        # Commented out hardcoded json loading
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
            # Check author presence and avoid noreply emails
            if (
                commit.commit.author
                and commit.commit.author.email
                and not commit.commit.author.email.endswith("@users.noreply.github.com")
            ):
                return commit.commit.author.email
    except Exception as e:
        # Log specific error but don't stop the process for other users
        print(f"Warning: Error fetching commits for {username}/{repo}: {str(e)}")
    return None


def get_user_data(dependent: Dict) -> Optional[UserData]:
    """Get GitHub user profile, email and repository details."""
    if "/" not in dependent.get("name", ""):
        print(f"Warning: Skipping dependent with invalid name format: {dependent}")
        return None

    owner, repo_name = dependent["name"].split("/", 1)
    try:
        user = gh.users.get_by_username(owner)
        # Attempt to get email from profile first, then commits
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
            "repo_topics": repo.topics or [],  # Ensure topics is always a list
        }
    except Exception as e:
        print(f"Warning: Error getting data for {owner}: {str(e)}")
        return None


def get_target_repo_details(owner: str, repo: str) -> Dict:
    """Fetch README and repository details for the target repository."""
    try:
        # Get repository details
        repo_info = gh.repos.get(owner=owner, repo=repo)

        # Get README content
        try:
            readme = gh.repos.get_readme(owner=owner, repo=repo)
            raw_readme = base64.b64decode(readme.content).decode("utf-8")
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"Extract and list only the key features from this README: {raw_readme}"
            response = gemini_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            readme_content = response.text if response else "Could not extract features from README"

        except Exception as e:
            print(f"Warning: Could not fetch README for {owner}/{repo}: {str(e)}")
            readme_content = "No README available"

        return {
            "description": repo_info.description or "No description available",
            "readme": readme_content,
            "stars": repo_info.stargazers_count,
            "topics": repo_info.topics or [],
            "homepage": repo_info.homepage,
            "language": repo_info.language,
        }
    except Exception as e:
        print(f"Error fetching repository details for {owner}/{repo}: {str(e)}")
        return {
            "description": "Could not fetch repository details",
            "readme": "Could not fetch README",
            "stars": 0,
            "topics": [],
            "homepage": None,
            "language": None,
        }


def process_user(user: UserData, target_repo: str) -> Optional[str]:
    """Store user context and generate personalized email."""
    if not target_repo or "/" not in target_repo:
        print(
            f"Warning: Invalid target_repo format '{target_repo}' for processing user {user['username']}"
        )
        return None

    target_owner, target_repo_name = target_repo.split("/")

    # Get target repository details
    target_details = get_target_repo_details(target_owner, target_repo_name)

    system = [
        {
            "role": "system",
            "content": f"""You are an AI assistant designed to help discover and connect with developers using {target_repo_name}.
            Your goal is to understand their usage context and create personalized, meaningful outreach as a Developer Relations Engineer at {target_repo_name}.
            
            About {target_repo_name}:
            Description: {target_details["description"]}
            Stars: {target_details["stars"]}
            Language: {target_details["language"]}
            Topics: {", ".join(target_details["topics"])}
            
            Key Features from README:
            {target_details["readme"]}
            
            Focus on building genuine connections by highlighting relevant {target_repo_name} features that could benefit their specific project.""",
        },
    ]

    # Use a unique user_id, maybe combine username and repo?
    user_id = f"{user['username']}_{user['repo_name']}"
    memory.add(system, user_id=user_id, version="v2")

    context = [
        {"role": "user", "content": f"GitHub user @{user['username']} is a developer"},
        {
            "role": "user",
            "content": f"They have a repository called {user['repo_name']} which {user['repo_description'] or 'has no description'}",
        },
        {
            "role": "user",
            "content": f"Their repository is located at {user['repo_url']} and has {user['repo_stars'] or 0} stars",
        },
        {
            "role": "user",
            "content": f"The primary language used in the repository is {user['repo_language'] or 'not specified'}",
        },
        {
            "role": "user",
            "content": f"Repository topics: {', '.join(user['repo_topics']) if user['repo_topics'] else 'none specified'}",
        },
        {"role": "user", "content": f"They use {target_repo} in their project"},
    ]

    memory.add(context, user_id=user_id, infer=False, version="v2")

    prompt = f"Write a short, personalised email to {user['name'] or user['username']} about their use of {target_repo_name}."

    memories = memory.search(query=prompt, user_id=user_id)

    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    full_prompt = f"""
    {prompt} \
    Brief features of {target_repo_name} relevant to their project. \
    End the email asking to reach out for any kind of questions, feedback .
    Keep it short, simple and friendly. DO NOT INCLUDE ANY TAGS LIKE [Your Name] or [Insert two or three points here].
    
    User Details:
    {memories}
    """

    try:
        # Correct API call structure
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash", contents=full_prompt
        )
        # Access the text content correctly
        return response.text if response and hasattr(response, "text") else None
    except Exception as e:
        print(f"Error generating email for {user['username']} using Gemini: {str(e)}")
        traceback.print_exc()
        return None


def generate_email_stream(target_repo: str) -> Generator[str, None, None]:
    """
    Yields JSON strings for streaming: status updates, user data + email, or errors.
    """
    if not all([GITHUB_TOKEN, GEMINI_API_KEY, MEM0_API_KEY]):
        yield json.dumps({"error": "Missing API keys in environment variables."}) + "\n"
        return

    if not target_repo or "/" not in target_repo:
        yield (
            json.dumps(
                {
                    "error": f"Invalid target repository format: {target_repo}. Use 'owner/repo'."
                }
            )
            + "\n"
        )
        return

    # --- CSV Setup ---
    csv_filename = "emails.csv"
    try:
        with open(
            csv_filename, "w", newline="", encoding="utf-8"
        ) as f:  # Added encoding
            writer = csv.writer(f)
            writer.writerow(["name", "email", "email_content"])  # Write header

            # --- Streaming Logic ---
            yield (
                json.dumps({"status": f"Fetching dependents for {target_repo}..."})
                + "\n"
            )
            dependents = get_repo_dependents(target_repo)
            total_dependents = len(dependents)
            yield (
                json.dumps(
                    {
                        "status": f"Found {total_dependents} dependents. Processing up to {MAX_DEPENDENTS}..."
                    }
                )
                + "\n"
            )

            processed_count = 0
            for i, dependent in enumerate(dependents[:MAX_DEPENDENTS]):
                if "name" not in dependent:
                    yield (
                        json.dumps(
                            {
                                "warning": f"Skipping dependent at index {i} due to missing 'name': {dependent}"
                            }
                        )
                        + "\n"
                    )
                    continue

                yield (
                    json.dumps(
                        {
                            "status": f"Processing dependent {i + 1}/{min(total_dependents, MAX_DEPENDENTS)}: {dependent['name']}"
                        }
                    )
                    + "\n"
                )

                user_data = get_user_data(dependent)
                if user_data:
                    if user_data["email"]:
                        email_content = process_user(user_data, target_repo)
                        if email_content:
                            processed_count += 1
                            user_name_for_csv = (
                                user_data["name"] or user_data["username"]
                            )  # Use username if name is missing

                            # Yield data for frontend stream
                            yield (
                                json.dumps(
                                    {
                                        "user": user_data["username"],
                                        "name": user_data["name"],
                                        "email_address": user_data["email"],
                                        "repo": user_data["repo_name"],
                                        "email_body": email_content,
                                    }
                                )
                                + "\n"
                            )

                            # Write data to CSV
                            writer.writerow(
                                [user_name_for_csv, user_data["email"], email_content]
                            )

                            time.sleep(1)  # Avoid hitting rate limits
                        else:
                            yield (
                                json.dumps(
                                    {
                                        "warning": f"Could not generate email for {user_data['username']}"
                                    }
                                )
                                + "\n"
                            )
                    else:
                        yield (
                            json.dumps(
                                {
                                    "warning": f"No email found for {user_data['username']}"
                                }
                            )
                            + "\n"
                        )
                else:
                    yield (
                        json.dumps(
                            {
                                "warning": f"Could not fetch user data for dependent: {dependent['name']}"
                            }
                        )
                        + "\n"
                    )

            yield (
                json.dumps(
                    {
                        "status": f"Finished processing. Generated emails for {processed_count} users. Saved to {csv_filename}"  # Updated status
                    }
                )
                + "\n"
            )
    # --- Error Handling ---
    except FileNotFoundError:
        yield (
            json.dumps(
                {
                    "error": "Could not find 'dependants.json'. Make sure the file exists."
                }
            )
            + "\n"
        )
    except json.JSONDecodeError:
        yield (
            json.dumps(
                {"error": "Failed to parse 'dependants.json'. Check its format."}
            )
            + "\n"
        )
    except Exception as e:
        print(f"An error occurred during streaming: {str(e)}")
        traceback.print_exc()
        yield json.dumps({"error": f"An unexpected error occurred: {str(e)}"}) + "\n"


# --- Flask App ---
app = Flask(__name__)


@app.route("/")
def index():
    """Serves the main HTML page."""
    return render_template("index.html")


@app.route("/generate_emails", methods=["POST"])
def generate_emails():
    """API endpoint to start the email generation stream."""
    data = request.get_json()
    target_repo = data.get("repository")

    if not target_repo:
        return jsonify({"error": "Repository not provided"}), 400
    if "/" not in target_repo:
        return jsonify({"error": "Invalid repository format. Use 'owner/repo'."}), 400

    # Return a streaming response
    return Response(
        stream_with_context(generate_email_stream(target_repo)),
        mimetype="application/x-ndjson",
    )


if __name__ == "__main__":
    app.run(
        debug=True, port=8080
    )  # debug=True for development, set to False for production
