from langgraph.graph import StateGraph, END
from backend.app.schemas import ReviewState, DiffChunk, LLMFinding
from backend.app.llm import build_default_llm, build_prompt, parse_llm_output

_llm = build_default_llm()


def parse_diff(state: ReviewState) -> ReviewState:
    #GitHubClient + diff_parser plug in here in the real pipeline.
    state.raw_files = [{"filename": "app.py", "patch": "@@ -1,1 +1,1 @@\n+print('hi')"}]
    return state


def filter_files(state: ReviewState) -> ReviewState:
    IGNORE_SUFFIXES = (".lock", ".min.js", ".png", ".jpg")
    state.raw_files = [f for f in state.raw_files if not f["filename"].endswith(IGNORE_SUFFIXES)]
    return state


def chunk_diff(state: ReviewState) -> ReviewState:
    for f in state.raw_files:
        state.chunks.append(DiffChunk(file_path=f["filename"], added_lines=[{"new_line": 1, "content": "print('hi')"}]))
    return state


def analyze_chunk(state: ReviewState) -> ReviewState:
    for chunk in state.chunks:
        prompt = build_prompt(chunk.file_path, chunk.added_lines)
        raw_response = _llm.analyze(prompt)
        state.raw_findings.extend(parse_llm_output(raw_response, chunk.file_path))
    return state


def validate_finding(state: ReviewState) -> ReviewState:
    state.validated_findings = [f for f in state.raw_findings if len(f.explanation) > 10]
    return state


def build_graph():
    graph = StateGraph(ReviewState)
    graph.add_node("parse_diff", parse_diff)
    graph.add_node("filter_files", filter_files)
    graph.add_node("chunk_diff", chunk_diff)
    graph.add_node("analyze_chunk", analyze_chunk)
    graph.add_node("validate_finding", validate_finding)

    graph.set_entry_point("parse_diff")
    graph.add_edge("parse_diff", "filter_files")
    graph.add_edge("filter_files", "chunk_diff")
    graph.add_edge("chunk_diff", "analyze_chunk")
    graph.add_edge("analyze_chunk", "validate_finding")
    graph.add_edge("validate_finding", END)
    return graph.compile()


compiled_graph = build_graph()