"""Bounded, process-local conversation memory."""

from collections import OrderedDict

from search_engine.rag.models import Message

DEFAULT_CONVERSATION_ID = "default"
MAX_TURNS_PER_SESSION = 10
MAX_SESSIONS = 1_000


class ChatMemory:
    def __init__(self, max_turns: int = MAX_TURNS_PER_SESSION,
                 max_sessions: int = MAX_SESSIONS) -> None:
        self.max_messages = max_turns * 2
        self.max_sessions = max_sessions
        self._sessions: OrderedDict[str, list[Message]] = OrderedDict()

    def get(self, session_id: str) -> list[Message]:
        messages = self._sessions.get(session_id, [])
        if session_id in self._sessions:
            self._sessions.move_to_end(session_id)
        return list(messages)

    def add(self, session_id: str, message: Message) -> None:
        messages = self._sessions.setdefault(session_id, [])
        self._sessions.move_to_end(session_id)
        messages.append(message)
        del messages[:-self.max_messages]
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)


chat_memory = ChatMemory()
