import os
import sys

import pandas as pd

# Add the project root to sys.path to resolve 'backend' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.github_client import GitHubClient


def fetch_training_data(owner: str, repo: str, limit: int = 100):
    client = GitHubClient(os.environ.get("GITHUB_TOKEN", ""))

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/comments"
    params = {"per_page": 100, "sort": "created", "direction": "desc"}

    data = []

    while url and len(data) < limit:
        resp = client._client.get(url, params=params)
        resp.raise_for_status()
        comments = resp.json()

        for c in comments:
            # We map human comments to "approved" findings (True label)
            data.append(
                {
                    "file_path": c.get("path"),
                    "line": c.get("line"),
                    "body": c.get("body"),
                    "hunk": c.get("diff_hunk", ""),
                    "is_actionable": 1,  # 1 = accepted
                }
            )

        url = resp.links.get("next", {}).get("url")
        params = None

    return pd.DataFrame(data)


if __name__ == "__main__":
    # Generate some synthetic negatives for balance
    print("Fetching positive labels from GitHub...")
    df_pos = fetch_training_data("fastapi", "fastapi", limit=200)

    df_neg = pd.DataFrame(
        [
            {
                "file_path": "test.py",
                "line": 10,
                "body": "Nitpick: space here",
                "hunk": "@@ -1 +1 @@",
                "is_actionable": 0,
            },
            {
                "file_path": "app.py",
                "line": 42,
                "body": "Should this be async?",
                "hunk": "@@ -40 +42 @@",
                "is_actionable": 0,
            },
        ]
    )

    df = pd.concat([df_pos, df_neg], ignore_index=True)
    os.makedirs("ml/data", exist_ok=True)
    df.to_csv("ml/data/training_set.csv", index=False)
    print(f"Saved {len(df)} rows to ml/data/training_set.csv")
