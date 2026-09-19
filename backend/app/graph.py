from langgraph.graph import END, StateGraph

from backend.app.db import SessionLocal
from backend.app.llm import build_default_llm, build_prompt, parse_llm_output
from backend.app.models import Finding, Review
from backend.app.schemas import DiffChunk, ReviewState

_llm = build_default_llm()


def parse_diff(state: ReviewState) -> ReviewState:
    # GitHubClient + diff_parser plug in here in the real pipeline.
    state.raw_files = [{"filename": "app.py", "patch": "@@ -1,1 +1,1 @@\n+print('hi')"}]
    return state


def filter_files(state: ReviewState) -> ReviewState:
    IGNORE_SUFFIXES = (".lock", ".min.js", ".png", ".jpg")
    state.raw_files = [f for f in state.raw_files if not f["filename"].endswith(IGNORE_SUFFIXES)]
    return state


def chunk_diff(state: ReviewState) -> ReviewState:
    for f in state.raw_files:
        state.chunks.append(
            DiffChunk(
                file_path=f["filename"],
                added_lines=[{"new_line": 1, "content": "print('hi')"}],
            )
        )
    return state


def analyze_chunk(state: ReviewState) -> ReviewState:
    for chunk in state.chunks:
        prompt = build_prompt(chunk.file_path, chunk.added_lines)
        raw_response = _llm.analyze(prompt)
        state.raw_findings.extend(parse_llm_output(raw_response, chunk.file_path))
    return state


def validate_finding(state: ReviewState) -> ReviewState:
    valid = []
    for f in state.raw_findings:
        if len(f.explanation.split()) < 5:
            continue
        if f.confidence < 0.3:
            continue
        valid.append(f)
    state.validated_findings = valid
    return state


def deduplicate_findings(state: ReviewState) -> ReviewState:
    seen = set()
    deduped = []
    for f in state.validated_findings:
        key = (f.file_path, f.line // 5, f.category)
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    state.deduped_findings = deduped
    return state


def generate_summary(state: ReviewState) -> ReviewState:
    if not state.deduped_findings:
        state.summary = "No actionable findings."
        return state

    counts = {}
    for f in state.deduped_findings:
        counts[f.category] = counts.get(f.category, 0) + 1

    summary_parts = [f"{count} {cat} issue(s)" for cat, count in counts.items()]
    state.summary = "Found: " + ", ".join(summary_parts)
    return state


def persist_review(state: ReviewState) -> ReviewState:
    db = SessionLocal()
    try:
        review = Review(
            pull_request_id=state.pull_request_id,
            status="PENDING_HUMAN_REVIEW",
            summary=state.summary,
        )
        db.add(review)
        db.flush()
        for f in state.deduped_findings:
            db_finding = Finding(
                review_id=review.id,
                file_path=f.file_path,
                line=f.line,
                category=f.category,
                explanation=f.explanation,
                llm_confidence=f.confidence,
            )
            db.add(db_finding)

        db.commit()
        state.db_review_id = int(review.id)  # type: ignore[arg-type]
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
    return state


def build_graph():
    graph = StateGraph(ReviewState)
    graph.add_node("parse_diff", parse_diff)
    graph.add_node("filter_files", filter_files)
    graph.add_node("chunk_diff", chunk_diff)
    graph.add_node("analyze_chunk", analyze_chunk)
    graph.add_node("validate_finding", validate_finding)
    graph.add_node("deduplicate_findings", deduplicate_findings)
    graph.add_node("generate_summary", generate_summary)
    graph.add_node("persist_review", persist_review)

    graph.set_entry_point("parse_diff")
    graph.add_edge("parse_diff", "filter_files")
    graph.add_edge("filter_files", "chunk_diff")
    graph.add_edge("chunk_diff", "analyze_chunk")
    graph.add_edge("analyze_chunk", "validate_finding")
    graph.add_edge("validate_finding", "deduplicate_findings")
    graph.add_edge("deduplicate_findings", "generate_summary")
    graph.add_edge("generate_summary", "persist_review")
    graph.add_edge("persist_review", END)

    return graph.compile()


compiled_graph = build_graph()
