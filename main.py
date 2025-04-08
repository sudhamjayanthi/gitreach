from ghapi.core import GhApi

# Parse owner and repo from your URL
repo_url = "https://github.com/mem0ai/mem0"
owner, repo = repo_url.split("/")[-2:]

# Initialize the API (if you have a token, add token=your_token)
api = GhApi(owner=owner, repo=repo)

# Get repository data
repo_data = api.repos.get(owner, repo)

# The dependent_count will show the "Used by" number
used_by_count = repo_data.get("dependent_count", 0)
print(f"Repository is used by {used_by_count} repositories")
