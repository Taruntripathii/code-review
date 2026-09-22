import httpx


class GitHubClient:
    def __init__(self, token: str):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._client = httpx.Client(
            headers=headers,
            timeout=15.0,
        )

    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Handles pagination via the Link header — GitHub caps each page at 100 files."""
        files: list[dict] = []
        url: str | None = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        params: dict[str, int] | None = {"per_page": 100}
        while url:
            resp = self._client.get(url, params=params)
            resp.raise_for_status()
            files.extend(resp.json())
            url = resp.links.get("next", {}).get("url")
            params = None  # the "next" URL already has query params baked in
        return files

    def get_pr(self, owner: str, repo: str, pr_number: int) -> dict:
        resp = self._client.get(f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}")
        resp.raise_for_status()
        return resp.json()

    def create_review(self, owner: str, repo: str, pr_number: int, comments: list[dict]):
        # Comments shape: [{"path": "file.py", "line": 42, "body": "comment text"}]
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        payload = {
            "event": "COMMENT",  # or REQUEST_CHANGES
            "comments": comments,
        }
        resp = self._client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
