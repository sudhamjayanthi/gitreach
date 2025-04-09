# GitReach

An automated developer outreach tool that discovers engineers and organizations using the mem0 GitHub repository, enriches their public context, stores their profile as persistent memory via mem0, and creates personalized, contextual emails.

## Features

-   Discovers repositories depending on mem0
-   Enriches user profiles with GitHub data
-   Creates persistent memories using mem0
-   Generates personalized outreach emails
-   Exports contact information to CSV

## Prerequisites

-   Python 3.13+
-   GitHub API Token
-   Google Gemini API Key

## Installation

1. Clone the repository
2. Install dependencies:

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Configuration

Set the following environment variables:

```bash
export GITHUB_TOKEN="your-github-token"
export GEMINI_API_KEY="your-gemini-api-key"
```

_Note: This tool uses Mem0 with Google Gemini (via its OpenAI-compatible endpoint) as the LLM and Qdrant as the vector store. Ensure Qdrant is running locally or update the configuration in `main.py`._

## Usage

Run the script:

```bash
python main.py
```

The script will:

1. Fetch all repositories depending on mem0
2. Enrich user profiles with GitHub data
3. Create memories in mem0
4. Generate personalized emails
5. Save contact information to `emails.csv`

## Output

-   Console output showing processed profiles and generated emails
-   `emails.csv` containing name and email of discovered users
