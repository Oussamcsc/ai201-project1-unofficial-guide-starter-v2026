"""
Stage 2 of the pipeline: splitting documents into chunks.

Two chunkers live here.

`fallback_split` is the starter's original: fixed 800-character windows with a
character overlap, paying no attention to where sentences or paragraphs end.
On campus_life it never fires at all — the longest post is 549 characters — so
it returns 88 documents as 88 chunks. It is kept as the baseline to measure
against, and Milestone 3's stop rule points back at it.

`split_documents` is mine (Milestone 3): title-anchored paragraph packing. Its
docstring has the rule and the reasons; README "Chunking Strategy" has the
measurements that produced the numbers in config.py.
"""

import re
from dataclasses import dataclass

import config
from ingest import Document

# A block whose first (and only) line is shorter than this is treated as the
# document's title rather than as content. Every campus_life post opens with
# one — "On the parking permits", "Kestrel Commons", "CS 210 Data Structures"
# — and the longest is 39 characters.
TITLE_MAX_CHARS = 100

# Split on sentence-ending punctuation followed by whitespace. Used only to
# decide where the carried-forward overlap starts, so that overlap is always
# whole sentences and never a fragment like "exams come from the".
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    """One piece of one document."""

    text: str
    source: str        # which file it came from
    index: int         # which chunk within that file, starting at 0
    produced_by: str   # the function that made it — cite this in your README

    @property
    def label(self) -> str:
        return f"{self.source}#{self.index}"


def fallback_split(
    documents: list[Document],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """
    The starter's original chunker. Fixed-size character windows with overlap.

    Keep this function. Milestone 3's stop rule points back at it, and having
    something to compare your own strategy against is useful in unit 2.
    """
    chunk_size = chunk_size or config.CHUNK_SIZE
    overlap = overlap or config.CHUNK_OVERLAP

    if overlap >= chunk_size:
        raise ValueError("overlap has to be smaller than chunk_size")

    chunks: list[Chunk] = []
    for doc in documents:
        start = 0
        index = 0
        while start < len(doc.text):
            piece = doc.text[start : start + chunk_size].strip()
            if piece:
                chunks.append(
                    Chunk(
                        text=piece,
                        source=doc.source,
                        index=index,
                        produced_by="chunker.py::fallback_split",
                    )
                )
                index += 1
            start += chunk_size - overlap

    return chunks


def _split_title(text: str) -> tuple[str, list[str]]:
    """
    Separate a document's title line from its body paragraphs.

    Returns ("", blocks) when the first block doesn't look like a title, so
    this doesn't invent a heading for documents that haven't got one.
    """
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if not blocks:
        return "", []

    first = blocks[0]
    looks_like_title = "\n" not in first and len(first) <= TITLE_MAX_CHARS
    if looks_like_title and len(blocks) > 1:
        return first, blocks[1:]
    return "", blocks


def _pack(blocks: list[str], budget: int) -> list[list[str]]:
    """
    Group consecutive paragraphs together until adding one more would exceed
    `budget`, then start a new group.

    A paragraph is never cut. A group therefore runs over budget when a single
    paragraph is longer than the whole budget — that is deliberate. A chunk
    that's slightly too big is a chunk you can still answer from; half a
    sentence is not.
    """
    groups: list[list[str]] = []
    current: list[str] = []
    size = 0

    for block in blocks:
        if current and size + len(block) + 2 > budget:
            groups.append(current)
            current, size = [], 0
        current.append(block)
        size += len(block) + 2

    if current:
        groups.append(current)
    return groups


def _carry(previous: str, overlap: int) -> str:
    """
    The overlap: the last whole sentences of the previous group, up to
    `overlap` characters.

    Character-window overlap (what fallback_split does) can hand the next chunk
    a fragment. Walking backwards a sentence at a time means the carried text
    is always something a reader could use.
    """
    if overlap <= 0:
        return ""

    sentences = [s for s in _SENTENCE_END.split(previous) if s]
    tail: list[str] = []
    used = 0
    for sentence in reversed(sentences):
        if used + len(sentence) > overlap:
            break
        tail.insert(0, sentence)
        used += len(sentence) + 1

    return " ".join(tail)


def split_documents(documents: list[Document]) -> list[Chunk]:
    """
    Title-anchored paragraph packing — the Milestone 3 strategy.

    The rule, in one sentence: **one post stays one chunk unless it's long
    enough to be covering several things, and then it splits at a paragraph
    boundary with its title re-attached.**

    Four decisions, each answering something measured in the corpus (the
    numbers are in README "Chunking Strategy"):

    1. The title line comes off and is prepended to every chunk the document
       produces. All 88 campus_life posts open with one, and it is where the
       topic identifier lives. Without this, Kestrel Commons' second paragraph
       reads "Hours are 7:00am to 9:00pm weekdays" — hours for *what*?

    2. Chunks are packed out of whole paragraphs, never cut mid-sentence. A
       plain split on every blank line produces 271 chunks averaging 101
       characters, the shortest being 10 — the fragment case.

    3. config.CHUNK_SIZE is a soft target, so a long paragraph stays intact
       rather than being halved.

    4. The overlap carries whole trailing sentences forward, not a character
       window, so the shared text is never a fragment either.

    On campus_life this produces 136 chunks: 42 of the 88 posts are a single
    thought and stay exactly as they were, 46 hold more than one and come
    apart. Where it earns its keep is the long multi-topic posts. Ask "which
    building has heating that runs hot and can't be adjusted" and the 549-char
    whole-post chunk answers at 0.687 — above the 0.6 gate, so the system
    refuses a question the corpus plainly answers. Split, the same question
    comes back at 0.586 and gets answered.
    """
    chunk_size = config.CHUNK_SIZE
    overlap = config.CHUNK_OVERLAP

    if overlap >= chunk_size:
        raise ValueError("overlap has to be smaller than chunk_size")

    chunks: list[Chunk] = []
    for doc in documents:
        title, blocks = _split_title(doc.text)
        if not blocks:
            continue

        # Whatever the title takes up is not available for content.
        budget = max(chunk_size - len(title) - 2, 80)
        groups = _pack(blocks, budget)

        for index, group in enumerate(groups):
            body = "\n\n".join(group)
            carried = _carry("\n\n".join(groups[index - 1]), overlap) if index else ""

            parts = [p for p in (title, carried, body) if p]
            chunks.append(
                Chunk(
                    text="\n\n".join(parts),
                    source=doc.source,
                    index=index,
                    produced_by="chunker.py::split_documents",
                )
            )

    return chunks


def describe(chunks: list[Chunk]) -> str:
    """A one-line summary, printed after indexing."""
    if not chunks:
        return "0 chunks"
    lengths = [len(c.text) for c in chunks]
    return (
        f"{len(chunks)} chunks, "
        f"{sum(lengths) // len(lengths)} characters on average "
        f"(shortest {min(lengths)}, longest {max(lengths)}), "
        f"produced by {chunks[0].produced_by}"
    )


if __name__ == "__main__":
    from ingest import load_documents

    chunks = split_documents(load_documents())
    print(describe(chunks))
