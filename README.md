
> [!NOTE]
> see [future](https://github.com/sudhamjayanthi/gitreach/tree/future) branch for WIP web version with flask

# GitReach

An automated developer outreach tool that discovers users of your OSS Github repository, enriches their public context, stores their profile as persistent memory via mem0, and creates personalized, contextual emails.


## Features

-   Discovers repositories depending on your Github repository
-   Enriches user profiles with Github data
-   Creates persistent memories using mem0
-   Generates personalized outreach emails
-   Exports contact information to CSV

## Prerequisites

-   Python 3.13+
-   GitHub API Token
-   Google Gemini API Key
-   Mem0 API Key

## Installation

1. Clone the repository
2. Install dependencies:

```bash
uv venv
source .venv/bin/activate
uv sync
```

## Configuration

Set the following environment variables:

```bash
export GITHUB_TOKEN="your-github-token"
export GEMINI_API_KEY="your-gemini-api-key"
export MEM0_API_KEY="your-mem0-api-key"
```

Note: This repo uses the Mem0 Hosted Platform for the memories. You can visit [docs](https://docs.mem0.ai/open-source/quickstart) to learn how to use the OSS version.

## Usage

Run the script:

```bash
uv run main.py
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

## Future

- [ ] Better Personalisation
    - [ ] Add more memories about the user from their social media profiles
    - [ ] Run a Agent to figure out how they're implemening library in their repo currently to suggest improvements
- [ ] Integrate Email Sending API
- [ ] Setup an AI Agent to autoreply to people that responsd to cold emails
- [ ] Create a web interface to fetch, send, track and manage all these agents
