import httpx


class GitHubClient:
    def __init__(self, token: str):
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
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