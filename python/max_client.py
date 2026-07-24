"""Synchronous Socket.IO client for talking to a Max/MSP patch.

Topology: Max hosts the Socket.IO *server* (Node.js `node.script`); this module is
the Python *client*. We send a `request` event carrying a `route` (the Max
outlet selector the value is routed to), a Max data `type`, the `value`, and a
unique `request_id`, then block until a matching `response` event
`{"request_id": ..., "results": ...}` arrives.

For fire-and-forget delivery, `emit` sends the same typed payload on a separate
`emit` event (no `request_id`) and returns without awaiting a reply.

Supported types (Max's way of naming data):
    int    -> a Python int
    float  -> a Python int or float (sent as float)
    symbol -> a Python str, at most 2048 characters
    list   -> a Python list of atoms (int / float / str)
    dict   -> a Python dict with str keys

Basic usage:

    from max_client import request

    # send to the "test" selector (matches `route test` in the patch)
    results = request("test", "symbol", "hello max")
    print(results)
"""

import threading
import uuid
from typing import Any, Optional

import socketio

SERVER_URL = "http://127.0.0.1"
SERVER_PORT = 5002
# Default namespace "/" keeps both sides minimal. If you switch to a named
# namespace, set it on connect() and pass `namespace=` on every emit/on.

SUPPORTED_TYPES = ("int", "float", "symbol", "list", "dict")
MAX_SYMBOL_LEN = 2048  # Max symbols are strings capped at 2048 characters.


def _validate_atom(v: Any) -> Any:
    """Validate a single Max list atom (int / float / symbol)."""
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise TypeError("list elements must be int, float, or str (Max atoms)")
    if isinstance(v, str) and len(v) > MAX_SYMBOL_LEN:
        raise ValueError(f"list symbol exceeds {MAX_SYMBOL_LEN} chars")
    return v


def _validate_route(route: str) -> None:
    """Check the Max outlet selector: a non-empty str within the symbol limit."""
    if not isinstance(route, str):
        raise TypeError(f"route must be a str, got {route.__class__.__name__}")
    if not route:
        raise ValueError("route must be a non-empty str")
    if len(route) > MAX_SYMBOL_LEN:
        raise ValueError(f"route exceeds {MAX_SYMBOL_LEN} chars (got {len(route)})")


def _validate(type: str, value: Any) -> Any:
    """Check `value` against the declared Max `type` and return it normalized.

    Raises ValueError for an unsupported type / out-of-range symbol, or
    TypeError when the Python value does not match the declared type.
    """
    if type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported type {type!r}; expected one of {SUPPORTED_TYPES}")
    if type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"type 'int' needs an int, got {value.__class__.__name__}")
        return value
    if type == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"type 'float' needs an int or float, got {value.__class__.__name__}"
            )
        return float(value)
    if type == "symbol":
        if not isinstance(value, str):
            raise TypeError(f"type 'symbol' needs a str, got {value.__class__.__name__}")
        if len(value) > MAX_SYMBOL_LEN:
            raise ValueError(f"symbol exceeds {MAX_SYMBOL_LEN} chars (got {len(value)})")
        return value
    if type == "list":
        if not isinstance(value, list):
            raise TypeError(f"type 'list' needs a list, got {value.__class__.__name__}")
        return [_validate_atom(v) for v in value]
    # dict
    if not isinstance(value, dict):
        raise TypeError(f"type 'dict' needs a dict, got {value.__class__.__name__}")
    if any(not isinstance(k, str) for k in value):
        raise TypeError("dict keys must be str (Max symbols)")
    return value


class _Pending:
    """A single in-flight request: a threading.Event plus the result slot the
    `response` handler fills in from the background thread."""

    __slots__ = ("event", "result")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: Any = None


class MaxClient:
    """One persistent connection to the Max-side Socket.IO server."""

    def __init__(self, url: str = SERVER_URL, port: int = SERVER_PORT):
        self.url = url
        self.port = port
        # Sync client: connect/emit/disconnect block, and inbound events are
        # dispatched on a background thread (so request() can block on an Event).
        # websocket-client has no default receive-size cap, so large echoed
        # replies (e.g. audio buffers) get through without extra options.
        self.sio = socketio.Client()
        # request_id -> _Pending, guarded by _lock because _on_response runs on
        # the client's background thread while request() runs on the caller's.
        self._pending: dict[str, _Pending] = {}
        self._lock = threading.Lock()
        self.sio.on("response", self._on_response)

    def _on_response(self, data: dict) -> None:
        request_id = data.get("request_id")
        if request_id is None:
            return
        with self._lock:
            pending = self._pending.get(request_id)
        if pending is not None:
            pending.result = data.get("results")
            pending.event.set()

    def connect(self) -> None:
        self.sio.connect(f"{self.url}:{self.port}")

    def disconnect(self) -> None:
        self.sio.disconnect()

    def request(
        self, route: str, type: str, value: Any, timeout: float = 5.0
    ) -> Any:
        """Send a typed `value` to Max and return the `results` from its reply.

        Blocks the calling thread until Max replies (or `timeout` elapses).
        `route` is the Max outlet selector the value is routed to (e.g. "test"
        for `route test`). `type` is one of int / float / symbol / list / dict.
        Raises TypeError or ValueError if `route`/`value` are invalid (see
        `_validate_route` / `_validate`), or TimeoutError if Max does not
        reply within `timeout` seconds.
        """
        _validate_route(route)
        value = _validate(type, value)
        request_id = str(uuid.uuid4())
        pending = _Pending()
        with self._lock:
            self._pending[request_id] = pending
        try:
            self.sio.emit(
                "request",
                {"route": route, "type": type, "value": value, "request_id": request_id},
            )
            if not pending.event.wait(timeout):
                raise TimeoutError(f"No response from Max within {timeout}s")
            return pending.result
        finally:
            with self._lock:
                self._pending.pop(request_id, None)

    def emit(self, route: str, type: str, value: Any) -> None:
        """Fire-and-forget: send a typed `value` to Max without awaiting a reply.

        `route`, `type`, and `value` are validated exactly as in `request`.
        Uses a separate `emit` wire event so it never enters the server's
        request/response FIFO — that keeps `request` correlation clean even when
        the emitted value's `route` has no reply path wired. There is no
        return value and no timeout: delivery is best-effort.
        """
        _validate_route(route)
        value = _validate(type, value)
        self.sio.emit(
            "emit",
            {"route": route, "type": type, "value": value},
        )


# --- Module-level convenience: lazy singleton so callers can just call it. ---

_client: Optional[MaxClient] = None


def request(route: str, type: str, value: Any, timeout: float = 5.0) -> Any:
    """Send a typed `value` to a Max `route` and return the `results`.

    Connects the shared client on first use. `route` is the Max outlet
    selector the value is routed to (e.g. "test").
    """
    global _client
    if _client is None:
        client = MaxClient()
        client.connect()  # if this raises, leave the singleton unset to retry
        _client = client
    return _client.request(route, type, value, timeout)


def emit(route: str, type: str, value: Any) -> None:
    """Fire-and-forget send of a typed `value` to a Max `route`; no reply.

    Same route/type/value validation as `request`, but returns immediately
    without awaiting a response. Connects the shared client on first use.
    """
    global _client
    if _client is None:
        client = MaxClient()
        client.connect()  # if this raises, leave the singleton unset to retry
        _client = client
    _client.emit(route, type, value)


def disconnect() -> None:
    """Close the shared connection, if one was opened."""
    global _client
    if _client is not None:
        _client.disconnect()
        _client = None
