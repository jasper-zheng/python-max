"""Minimal demo of the fire-and-forget Python -> Max emit protocol.

`emit(route, type, value)` sends a typed value one-way: it returns as soon as
the message is queued, without awaiting a reply (no return value, no timeout).
Use it for triggers and streaming control values.

IMPORTANT: point emits at a route that does NOT feed the patch's
`prepend response` reply path. A one-way selector that echoed back could have its
stray `response` paired with an in-flight `request`, resolving the wrong call.
"""

import time

from python_max import emit, disconnect


def main() -> None:
    # emit(route, type, value): the route is the Max outlet selector, and here it
    # should NOT feed the reply path. There is no return value -- emit never waits
    # for Max to answer.
    emit("emit", "int", 5)
    emit("emit", "float", 3.14)
    emit("emit", "symbol", "hello max")
    emit("emit", "list", [1, 2.0, "three"])
    emit("emit", "dict", {"freq": [440, 442, 441], "gain": 0.5})

    # disconnect() closes the socket without draining
    # the write queue, so give the last messages a moment to flush before closing.
    time.sleep(0.1)
    disconnect()


if __name__ == "__main__":
    main()
