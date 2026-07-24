"""Minimal demo of the typed Python -> Max request/response protocol.

"""

from max_client import request, disconnect


def main() -> None:
    # first arg is the route: the Max outlet selector (use it for `route test`)
    print(request("request", "int", 5))
    print(request("request", "float", 3.14))
    print(request("request", "symbol", "hello max"))
    print(request("request", "list", [1, 2.0, "three"]))
    print(request("request", "dict", {"freq": [440, 442, 441], "gain": 0.5}))

    disconnect()

if __name__ == "__main__":
    main()
