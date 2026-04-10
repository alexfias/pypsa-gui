from __future__ import annotations

from pypsa_gui.models.network_session import NetworkSession


class NetworkStore:
    def __init__(self) -> None:
        self._sessions: dict[str, NetworkSession] = {}
        self._active_session_id: str | None = None

    def add_session(self, session: NetworkSession) -> None:
        self._sessions[session.id] = session
        self._active_session_id = session.id

    def remove_session(self, session_id: str) -> None:
        was_active = self._active_session_id == session_id
        self._sessions.pop(session_id, None)

        if was_active:
            self._active_session_id = next(iter(self._sessions), None)

    def get_session(self, session_id: str) -> NetworkSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[NetworkSession]:
        return list(self._sessions.values())

    def set_active_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._active_session_id = session_id

    def get_active_session(self) -> NetworkSession | None:
        if self._active_session_id is None:
            return None
        return self._sessions.get(self._active_session_id)

    def clear(self) -> None:
        self._sessions.clear()
        self._active_session_id = None

    def has_sessions(self) -> bool:
        return bool(self._sessions)

    @property
    def sessions(self) -> list[NetworkSession]:
        return list(self._sessions.values())