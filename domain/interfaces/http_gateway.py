"""HTTP gateway protocol for outgoing webhook delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, Union, runtime_checkable


@dataclass(frozen=True)
class HttpTimeouts:
    """Strict timeout contract for delivery transports."""

    connect_seconds: float = 5.0
    read_seconds: float = 15.0

    def __post_init__(self) -> None:
        if self.connect_seconds <= 0:
            raise ValueError("connect_seconds must be greater than zero")
        if self.read_seconds <= 0:
            raise ValueError("read_seconds must be greater than zero")


@dataclass(frozen=True)
class HttpRequest:
    """Transport-agnostic request sent to a subscriber endpoint."""

    url: str
    body: Union[str, bytes]
    headers: Mapping[str, str]
    timeouts: HttpTimeouts = field(default_factory=HttpTimeouts)
    metadata: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("url is required")


@dataclass(frozen=True)
class HttpResponse:
    """Transport-agnostic response returned by an HTTP gateway."""

    status_code: int
    body: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)
    elapsed_seconds: Optional[float] = None

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


@runtime_checkable
class HttpGateway(Protocol):
    """Contract for posting signed webhook payloads to subscribers."""

    def post(self, request: HttpRequest) -> HttpResponse:
        ...
