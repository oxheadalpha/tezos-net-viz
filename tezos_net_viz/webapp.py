import aiohttp
import aiofiles
import asyncio
import importlib.resources
from aiohttp import web
from typing import Callable, Awaitable, Optional, AsyncIterator
from . import resources

routes = web.RouteTableDef()


async def sleep_iterator(
    limit: Optional[int] = None, sleep_time: int = 5
) -> AsyncIterator[None]:
    while limit or (limit is None):
        yield
        await asyncio.sleep(sleep_time)
        if limit:
            limit -= 1

HOME_PAGE = """
<!DOCTYPE html>
<meta charset="utf-8">
<body>
<script src="//d3js.org/d3.v5.min.js"></script>
<script src="https://unpkg.com/@hpcc-js/wasm@0.3.11/dist/index.min.js"></script>
<script src="https://unpkg.com/d3-graphviz@3.0.5/build/d3-graphviz.js"></script>
<div id="graph" style="text-align: center;"></div>
<script>

var loc = window.location, new_uri;
if (loc.protocol === "https:") {
    new_uri = "wss:";
} else {
    new_uri = "ws:";
}
new_uri += "//" + loc.host;
new_uri += "/dot/"
webSocket = new WebSocket(new_uri)

webSocket.onmessage = function (event) {
    d3.select("#graph").graphviz()
        .renderDot(event.data);
}

</script>
"""

@routes.get("/")
async def home(request: web.Request) -> web.Response:
    return web.Response(text=HOME_PAGE, content_type="text/html")


@routes.get("/dot/")
async def serve_dot(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for _ in sleep_iterator():
        async with aiofiles.open("graph.dot", mode="r") as f:  # type: ignore
            contents = await f.read()
            await ws.send_str(contents)
    print("websocket connection closed")
    return ws


# with importlib.resources.path(resources, ".") as f:
#     routes.static("/", f)


app = web.Application()
app.add_routes(routes)
# web.run_app(app)
