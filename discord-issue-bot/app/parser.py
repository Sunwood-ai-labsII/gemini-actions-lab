import re
from . import config


def parse_legacy_command(content: str):
    """
    Parse legacy text command like:
      !issue owner/repo "Title" Body text ... #label1 +assignee1
    or  !issue owner/repo Title on first line\nBody from second line ... #bug
    Returns: dict(repo, title, body, labels[], assignees[]) or {error}
    """
    text = content.strip()
    prefix = config.PREFIX
    if text.lower().startswith(prefix.lower()):
        text = text[len(prefix):].strip()

    # Find first owner/repo token
    m_repo = re.search(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b", text)
    repo = m_repo.group(1) if m_repo else ""
    if not repo:
        return {"error": "リポジトリ (owner/repo) を含めてください: 例) !issue owner/repo \"タイトル\" 本文"}

    # Remove repo from text before parsing title/body
    text_wo_repo = (text[:m_repo.start()] + text[m_repo.end():]).strip() if m_repo else text

    # Title/body parsing
    m = re.match(r'^"([^"]+)"\s*(.*)$', text_wo_repo, flags=re.S)
    if m:
        title = m.group(1).strip()
        body = m.group(2).strip()
    else:
        lines = text_wo_repo.splitlines()
        title = lines[0].strip() if lines else "New Issue"
        body = "\n".join(lines[1:]).strip()

    # Extract labels (#label) and assignees (+user) from non-code text only
    # Remove fenced and inline code to avoid accidental captures
    text_no_code = re.sub(r"```[\s\S]*?```", "", text_wo_repo)
    text_no_code = re.sub(r"`[^`]*`", "", text_no_code)
    labels = [tok[1:].strip() for tok in re.findall(r'(#[\w\-/\.]+)', text_no_code)]
    assignees = [tok[1:].strip() for tok in re.findall(r'(\+[A-Za-z0-9-]+)', text_no_code)]

    # Clean tokens from body
    body = re.sub(r'(#[\w\-/\.]+)', '', body)
    body = re.sub(r'(\+[A-Za-z0-9-]+)', '', body).strip()

    return {
        "repo": repo,
        "title": title or "New Issue",
        "body": body or "(no body)",
        "labels": list(dict.fromkeys(labels)),
        "assignees": list(dict.fromkeys(assignees)),
    }


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
