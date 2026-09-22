from pydantic import BaseModel, Field


class DiffChunk(BaseModel):
    file_path: str
    added_lines: list[dict]


class LLMFinding(BaseModel):
    file_path: str
    line: int
    category: str
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)


class ReviewState(BaseModel):
    pull_request_id: int
    head_sha: str
    owner: str = ""
    repo: str = ""
    pr_number: int = 0
    raw_files: list[dict] = []
    chunks: list["DiffChunk"] = []
    raw_findings: list["LLMFinding"] = []
    validated_findings: list["LLMFinding"] = []
    deduped_findings: list["LLMFinding"] = []
    summary: str = ""
    db_review_id: int | None = None
