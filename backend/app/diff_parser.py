import re

HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class ParsedLine:
    def __init__(self, new_line: int | None, old_line: int | None, content: str, kind: str):
        self.new_line = new_line  # None for pure deletions
        self.old_line = old_line  # None for pure additions
        self.content = content
        self.kind = kind  # "added" | "removed" | "context"


def parse_patch(patch: str) -> list[ParsedLine]:
    old_line = new_line = 0
    result: list[ParsedLine] = []

    for raw in patch.splitlines():
        header = HUNK_HEADER_RE.match(raw)
        if header:
            old_line = int(header.group(1))
            new_line = int(header.group(3))
            continue

        if raw.startswith("\\ No newline at end of file"):
            continue  # marker line, not real content — don't advance counters

        if raw.startswith("+"):
            result.append(ParsedLine(new_line=new_line, old_line=None, content=raw[1:], kind="added"))
            new_line += 1
        elif raw.startswith("-"):
            result.append(ParsedLine(new_line=None, old_line=old_line, content=raw[1:], kind="removed"))
            old_line += 1
        else:
            result.append(
                ParsedLine(
                    new_line=new_line,
                    old_line=old_line,
                    content=raw[1:] if raw.startswith(" ") else raw,
                    kind="context",
                )
            )
            old_line += 1
            new_line += 1

    return result


def get_file_patches(pr_files: list[dict]) -> dict[str, dict]:
    """Normalizes GitHub's per-file response, flagging the edge cases explicitly."""
    out = {}
    for f in pr_files:
        path = f["filename"]
        if "patch" not in f:
            # binary file, or diff too large — GitHub omits `patch` in both cases
            out[path] = {
                "skipped": True,
                "reason": "no patch (binary or too large)",
                "renamed_from": f.get("previous_filename"),
            }
            continue
        out[path] = {
            "skipped": False,
            "renamed_from": f.get("previous_filename"),
            "lines": parse_patch(f["patch"]),
        }
    return out
