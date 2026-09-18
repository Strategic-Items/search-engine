"""What a search returns. The stores translate their rows into these models."""

from pydantic import BaseModel


class Passage(BaseModel):
    """A further chunk of a document that already matched."""

    id: str
    body: str = ""
    score: float | None = None


class SearchHit(BaseModel):
    """One document chunk, with the parent it belongs to."""

    id: str
    parent_id: str
    # The retriever's own score, on whatever scale that retriever uses.
    score: float | None = None
    title: str = ""
    body: str = ""
    code: str = ""
    source_type: str = "unknown"
    source_url: str = ""
    published_at: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    date_basis: str = "unknown"
    # Set when a newer edition of the same form exists, so a caller can say so.
    superseded_by: str | None = None
    # Other chunks of this same parent that also matched, best first. Ranking
    # picks one chunk to stand for a document, but the sentence that answers the
    # question is often in a different chunk of it, and that chunk used to be
    # dropped. `id`/`body` stay the document's primary chunk.
    passages: list[Passage] = []
    # Present only for the isolated call-centre corpus.  Keeping these optional
    # lets the shared retriever return a compact, useful case card without
    # changing the official-document response contract.
    call_id: str = ""
    call_inquiry: str = ""
    categories: list[str] = []
    start_sec: float | None = None
    end_sec: float | None = None

    @property
    def chunk_ids(self) -> list[str]:
        """Every chunk this hit carries, primary first."""
        return [self.id] + [passage.id for passage in self.passages]

    @property
    def bodies(self) -> list[str]:
        return [self.body] + [passage.body for passage in self.passages]


class HskHit(BaseModel):
    """One HSK linkage row. Never a final strategic-items determination."""

    id: str
    hsk_code: str = ""
    control_number: str = ""
    name_ko: str = ""
    name_en: str = ""
    source_url: str = ""
    retrieved_at: str | None = None
    linkage_notice: str = ""


class HskResults(BaseModel):
    total: int
    hits: list[HskHit]


class SearchResults(BaseModel):
    query: str
    hits: list[SearchHit]
    hsk: HskResults | None = None


class ModeResults(BaseModel):
    """What one search mode returned for a query, and what it cost to get it."""

    mode: str
    hits: list[SearchHit] = []
    latency_ms: float = 0.0
    # Set when this mode alone failed. A comparison whose whole request failed
    # because one retriever was down would hide the very thing being compared,
    # so a dead mode reports its own reason and the others still answer.
    error: str = ""


class ModeComparison(BaseModel):
    """The same query run through every retrieval mode, for side-by-side reading."""

    query: str
    modes: list[ModeResults]


class DocumentChunk(BaseModel):
    """One chunk of a document, in the order the document was written."""

    id: str
    body: str = ""


class Document(BaseModel):
    """A whole document, reassembled from the chunks it was indexed as.

    Search ranks chunks, so a hit shows a fragment torn out of the middle of a
    공고문. Reading it in context means reading the document, and the document
    only exists in the index as its chunks.
    """

    parent_id: str
    title: str = ""
    code: str = ""
    source_type: str = "unknown"
    source_url: str = ""
    published_at: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    superseded_by: str | None = None
    chunks: list[DocumentChunk] = []
