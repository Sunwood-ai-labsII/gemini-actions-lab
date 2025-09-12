def build_body_with_footer(body: str, author: str, source_url: str | None):
    parts = [body]
    meta = []
    if author:
        meta.append(f"Reported via Discord by: {author}")
    if source_url:
        meta.append(f"Source: {source_url}")
    if meta:
        parts.append("\n\n---\n" + "\n".join(meta))
    return "".join(parts)
