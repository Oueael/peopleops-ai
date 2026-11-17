import json
import re
from pathlib import Path

import tiktoken
import yaml


HANDBOOK_DIR = Path("data/handbook")

MAX_TOKENS = 700
OVERLAP_TOKENS = 80

encoding = tiktoken.get_encoding("cl100k_base")


def load_document(path: Path):
    """Load Markdown and extract YAML frontmatter."""

    content = path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        raise ValueError(f"Missing YAML frontmatter: {path}")

    _, frontmatter, body = content.split("---", 2)

    metadata = yaml.safe_load(frontmatter) or {}

    return metadata, body.strip()


def split_sections(text: str):
    """Split a document at Markdown headings."""

    sections = []
    current_heading = "Introduction"
    current_content = []

    for line in text.splitlines():

        match = re.match(r"^#{1,6}\s+(.+)$", line)

        if match:
            if current_content:
                sections.append({
                    "heading": current_heading,
                    "content": "\n".join(current_content).strip()
                })

            current_heading = match.group(1).strip()
            current_content = []

        else:
            current_content.append(line)

    if current_content:
        sections.append({
            "heading": current_heading,
            "content": "\n".join(current_content).strip()
        })

    return sections


def chunk_section(section_text: str):
    """Create token-limited chunks with overlapping context."""

    paragraphs = [
        p.strip()
        for p in section_text.split("\n\n")
        if p.strip()
    ]

    chunks = []
    current_tokens = []

    for paragraph in paragraphs:

        paragraph_tokens = encoding.encode(paragraph)

        if len(paragraph_tokens) > MAX_TOKENS:
            raise ValueError(
                "Paragraph exceeds maximum chunk size. "
                "Split it into smaller paragraphs."
            )

        candidate = current_tokens + (
            encoding.encode("\n\n") + paragraph_tokens
            if current_tokens else paragraph_tokens
        )

        if len(candidate) > MAX_TOKENS and current_tokens:

            chunks.append(encoding.decode(current_tokens))

            overlap = current_tokens[-OVERLAP_TOKENS:]

            current_tokens = overlap + encoding.encode("\n\n")
            current_tokens += paragraph_tokens

        else:
            current_tokens = candidate

    if current_tokens:
        chunks.append(encoding.decode(current_tokens))

    return chunks


def ingest_document(path: Path):
    """Load, split, chunk, and attach metadata."""

    metadata, body = load_document(path)

    sections = split_sections(body)

    document_chunks = []

    for section in sections:

        chunks = chunk_section(section["content"])

        for chunk in chunks:

            document_chunks.append({
                "source": path.name,
                "title": metadata.get("title"),
                "section": section["heading"],
                "last_updated": str(metadata.get("last_updated"))
                    if metadata.get("last_updated")else None,
                "audience": metadata.get("audience"),
                "region": metadata.get("region"),
                "text": chunk,
                "token_count": len(encoding.encode(chunk))
            })

    return document_chunks


def main():

    all_chunks = []

    for path in HANDBOOK_DIR.glob("*.md"):

        print(f"Processing: {path.name}")

        chunks = ingest_document(path)

        all_chunks.extend(chunks)

        print(f"Created {len(chunks)} chunks")

    output_path = Path("data/chunks.json")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(all_chunks, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\nIngestion complete!")
    print(f"Documents processed: {len(list(HANDBOOK_DIR.glob('*.md')))}")
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()