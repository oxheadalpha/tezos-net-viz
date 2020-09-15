from __future__ import annotations

from typing import Any, AsyncIterator
import aiohttp
import asyncio
import argparse
import graphviz

RPC_ENDPOINT = "http://{endpoint}:8732/network/connections/"

Address = str


async def fetch(
    session: aiohttp.ClientSession, url: Address
) -> AsyncIterator[dict[str, Any]]:
    async with session.get(url) as response:
        lst = await response.json()
        for item in lst:
            yield item


async def traverse_node(
    loop: asyncio.AbstractEventLoop,
    session: aiohttp.ClientSession,
    visited: set[Address],
    graph: graphviz.Digraph,
    endpoint: Address,
) -> None:
    visited.add(endpoint)
    print(f"Getting neighbours of {endpoint}...")
    node_rpc = RPC_ENDPOINT.format(endpoint=endpoint)
    try:
        content = fetch(session, node_rpc)
        async for neighbour in content:
            addr = neighbour["id_point"]["addr"]
            if addr.startswith("::ffff:"):  # remove ipv6
                addr = addr[7:]  # TODO: replace with <str>.removeprefix in python 3.9
            if neighbour["incoming"]:
                print(f"Added edge {addr} {endpoint}")
                graph.edge(addr, endpoint)
            else:
                print(f"Added edge {endpoint} {addr}")
                graph.edge(endpoint, addr)
            if addr not in visited:
                loop.create_task(traverse_node(loop, session, visited, graph, addr))
    except asyncio.TimeoutError:
        print(f"Connection timed out. Node unreachable.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "endpoint",
        help="ip address or domain of tezos node to start exploring from",
        type=Address,
    )
    parser.add_argument(
        "--timeout",
        help="connection timeout",
        default=5,
        type=int,
    )
    args = parser.parse_args()

    g = graphviz.Digraph("G", filename="graph.gv", format="svg", strict=True)
    timeout_config = aiohttp.ClientTimeout(total=args.timeout)
    session = aiohttp.ClientSession(timeout=timeout_config)
    visited: set[Address] = set()

    loop = asyncio.get_event_loop()
    loop.create_task(traverse_node(loop, session, visited, g, args.endpoint))
    while pending := [task for task in asyncio.all_tasks(loop) if not task.done()]:
        loop.run_until_complete(asyncio.gather(*pending))
    loop.run_until_complete(session.close())

    g.render()
    print(
        f"Done traversal. Traversed through {len(visited)} nodes, with {len(g.body)} edges"
    )


if __name__ == "__main__":
    main()
