"""Small internal shapes used by the RAG pipeline."""

from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str
