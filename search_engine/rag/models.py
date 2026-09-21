"""RAG 파이프라인에서 사용하는 작은 내부 형태."""

from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str
