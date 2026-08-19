
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import requests


class TavusError(RuntimeError):
    """Raised for any non-recoverable Tavus API failure."""


class TavusAuthError(TavusError):
    """Raised when the API key is missing or rejected."""


@dataclass
class ConversationHandle:
    conversation_id: str
    conversation_url: str
    status: str


class TavusClient:
    def __init__(self, api_key: str, base_url: str = "https://tavusapi.com/v2", timeout: int = 15):
        if not api_key:
            raise TavusAuthError("No key configured for live interviews. Set it in .env.")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json", "x-api-key": api_key})

    def verify_key(self) -> None:
        """Raises TavusAuthError/TavusError if the key can't be used."""
        resp = self._session.get(f"{self._base_url}/replicas", timeout=self._timeout)
        if resp.status_code == 401:
            raise TavusAuthError("The configured key was rejected (401 Unauthorized). Double-check it in .env.")
        resp.raise_for_status()

    def create_conversation(
        self,
        *,
        replica_id: str = "",
        persona_id: str = "",
        conversation_name: str,
        conversational_context: str,
        custom_greeting: Optional[str] = None,
        max_call_duration: int = 300,
        enable_recording: bool = True,
        language: str = "english",
    ) -> ConversationHandle:
        if not replica_id and not persona_id:
            raise TavusError("Either a replica_id or a persona_id is required to start a conversation.")

        payload: dict[str, Any] = {
            "conversation_name": conversation_name,
            "conversational_context": conversational_context,
            "properties": {
                "max_call_duration": max_call_duration,
                "participant_left_timeout": 30,
                "participant_absent_timeout": 300,
                "enable_recording": enable_recording,
                "language": language,
            },
        }
        if replica_id:
            payload["replica_id"] = replica_id
        if persona_id:
            payload["persona_id"] = persona_id
        if custom_greeting:
            payload["custom_greeting"] = custom_greeting

        resp = self._session.post(f"{self._base_url}/conversations", json=payload, timeout=self._timeout)
        self._raise_for_tavus_error(resp)
        data = resp.json()
        return ConversationHandle(
            conversation_id=data["conversation_id"],
            conversation_url=data["conversation_url"],
            status=data.get("status", "active"),
        )

    def end_conversation(self, conversation_id: str) -> None:
        resp = self._session.post(f"{self._base_url}/conversations/{conversation_id}/end", timeout=self._timeout)
        # Tavus returns 400 once a conversation has already ended -- treat that as success,
        # since the caller's intent ("make sure this call is over") is already satisfied.
        if resp.status_code not in (200, 400):
            self._raise_for_tavus_error(resp)

    def get_conversation(self, conversation_id: str, verbose: bool = False) -> dict:
        url = f"{self._base_url}/conversations/{conversation_id}"
        if verbose:
            url += "?verbose=true"
        resp = self._session.get(url, timeout=self._timeout)
        self._raise_for_tavus_error(resp)
        return resp.json()

    def _raise_for_tavus_error(self, resp: requests.Response) -> None:
        if resp.status_code == 401:
            raise TavusAuthError("The configured key was rejected (401 Unauthorized).")
        if not resp.ok:
            detail = ""
            try:
                detail = resp.json().get("message", "")
            except ValueError:
                detail = resp.text[:300]
            raise TavusError(f"The interview service returned an error ({resp.status_code}): {detail or 'no further detail returned'}")
