"""
Push bot files to GitHub via REST API.
Usage: python push_to_github.py
You will be prompted for your GitHub Personal Access Token.
Create one at: https://github.com/settings/tokens/new
  -> Select 'repo' scope -> Generate token
"""
import os, base64, getpass, requests

REPO  = "prateek02061997/cv-bot"
API   = "https://api.github.com"

# Files to upload (relative paths in this folder)
FILES = [
    "bot.py",
    "cv_data.py",
    "cv_store.py",
    "pdf_generator.py",
    "prompts.py",
    "requirements.txt",
    "Procfile",
    ".gitignore",
    "runtime.txt",
]

def push(token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    base = os.path.dirname(os.path.abspath(__file__))

    for fname in FILES:
        fpath = os.path.join(base, fname)
        if not os.path.exists(fpath):
            print(f"  SKIP (not found): {fname}")
            continue

        with open(fpath, "rb") as f:
            content = base64.b64encode(f.read()).decode()

        url = f"{API}/repos/{REPO}/contents/{fname}"

        # Check if file already exists (need its SHA to update)
        existing = requests.get(url, headers=headers)
        sha = existing.json().get("sha") if existing.status_code == 200 else None

        payload = {"message": f"add {fname}", "content": content}
        if sha:
            payload["sha"] = sha

        resp = requests.put(url, json=payload, headers=headers)
        if resp.status_code in (200, 201):
            print(f"  OK: {fname}")
        else:
            print(f"  FAIL: {fname} -> {resp.status_code} {resp.json().get('message','')}")

if __name__ == "__main__":
    token = os.environ.get("GH_TOKEN") or getpass.getpass(prompt="Token: ")
    if not token.strip():
        print("No token entered. Exiting.")
    else:
        print(f"\nPushing to {REPO}...")
        push(token.strip())
        print("\nDone! Check https://github.com/" + REPO)
