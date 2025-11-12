import re


def parse_labels_input(s: str) -> list[str]:
    s = (s or "").strip()
    if not s:
        return []
    tags = re.findall(r"#[\w\-/\.]+", s)
    if tags:
        return [t[1:] for t in tags]
    parts = [p.strip() for p in re.split(r"[\s,]+", s) if p.strip()]
    return parts


def parse_assignees_input(s: str) -> list[str]:
    s = (s or "").strip()
    if not s:
        return []
    plus = re.findall(r"\+([A-Za-z0-9-]+)", s)
    if plus:
        return plus
    parts = [p.strip() for p in re.split(r"[\s,]+", s) if p.strip()]
    return parts
