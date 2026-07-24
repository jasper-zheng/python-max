# python-max

A request/response protocol between a Python script and a Max/MSP patch, via
[Socket.IO](https://socket.io/). In Python you call `request(route, type, data)` and get back whatever the Max patch returns. 

Allows for sending/receiving typed values (int, float, symbol, list, dict) and audio buffers (as a dict of arrays) up to 32 MB in size.


## Python side (client)

### Setup

```bash
pip install python-max
```

The audio example additionally needs [`soundfile`](https://pypi.org/project/soundfile/):

```bash
pip install "python-max[audio]"
```

### Use

Below is an example of sending a typed value to Max without awaiting a reply.

```python
from python_max import MaxClient

client = MaxClient(url="http://127.0.0.1", port=5002)
client.connect()

client.emit(
   route="test", 
   type="dict", 
   value={"freq": 440, "gain": 0.5}
)

client.disconnect()
```


Below is an example of sending a typed request to Max and awaiting a reply.

```python
from python_max import MaxClient

client = MaxClient(url="http://127.0.0.1", port=5002)
client.connect()

result = client.request(
   route="test", 
   type="symbol", 
   value="hello max",
   timeout=5.0
) 
# Raises `TimeoutError` if Max doesn't reply in 5s.

client.disconnect()
```


### Route

`route` (required, first arg) is prepended to the value and needs to be routed in the Max patch. Use `[route <route>]` to catch it. 


### Types

`type` is required and must be one of five Max data types:

|   type   | Python value                          | notes                                    |
|----------|---------------------------------------|------------------------------------------|
| `int`    | `int`                                 |                                          |
| `float`  | `float`                               |                                          |
| `symbol` | `str`                                 | ≤ 2048 characters (Max's symbol limit)   |
| `list`   | `list` of `int` / `float` / `str`     | flat list only, **no nested list/dict**  |
| `dict`   | `dict` with `str` keys                | JSON-object.                             |


```python
emit("test", "int", 5)
emit("test", "float", 3.14)
emit("test", "symbol", "hello max")
emit("test", "list", [1, 2.0, "three"])
emit("test", "dict", {"freq": [440, 880, 1760], "gain": 0.5})
```

## Max side (server)

`max_server.js` runs inside a `node.script` object and hosts the Socket.IO server on port `5002`. 

### Run it

See [python-max.maxpat](python-max.maxpat).

## How to send/receive audio data

Node for Max does not have access to Max's `buffer~` objects (it's a diferent JS runtime than v8). So to send audio data between Python and Max, you need to send it as an Array via a dictionary. In practice, use `array.tobuffer` to copy it into a `buffer~` object, or use `array.frombuffer` to copy it from a `buffer~` object. See [example_audio.py](python/example_audio.py) and [python-max-audio.maxpat](python-max-audio.maxpat) for a working example.