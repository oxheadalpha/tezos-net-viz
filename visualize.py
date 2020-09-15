from __future__ import annotations

from typing import Any, AsyncIterator
from dataclasses import dataclass
import aiohttp
import asyncio
import argparse
import graphviz

RPC_ENDPOINT = "http://{endpoint}:8732/network/connections/"

Address = str


@dataclass
class Edge:
    node_one: Address
    node_two: Address


async def fetch(
    session: aiohttp.ClientSession, url: Address
) -> AsyncIterator[dict[str, Any]]:
    async with session.get(url) as response:
        lst = await response.json()
        for item in lst:
            yield item


async def get_neighbours(
    session: aiohttp.ClientSession, endpoint: Address
) -> AsyncIterator[Edge]:
    print(f"Getting neighbours of {endpoint}...")
    node_rpc = RPC_ENDPOINT.format(endpoint=endpoint)
    try:
        content = fetch(session, node_rpc)
        async for neighbour in content:
            addr = neighbour["id_point"]["addr"]
            if addr.startswith("::ffff:"):  # remove ipv6
                addr = addr[7:]  # TODO: replace with <str>.removeprefix in python 3.9
            if neighbour["incoming"]:
                yield Edge(addr, endpoint)
            else:
                yield Edge(endpoint, addr)
    except asyncio.TimeoutError:
        print(f"Connection timed out. Node unreachable.")


async def make_graph(starting_endpoint: Address, timeout: int) -> None:
    g = graphviz.Digraph("G", filename="graph.gv", format="svg", strict=True)
    visited: set[Address] = set()
    queue = asyncio.Queue()
    timeout_config = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(timeout=timeout_config) as session:
        visited.add(starting_endpoint)
        await queue.put(get_neighbours(session, starting_endpoint))
        while not queue.empty():
            top = await queue.get()
            async for edge in top:
                g.edge(edge.node_one, edge.node_two)
                for node in edge.__dict__.values():
                    if node not in visited:
                        visited.add(node)
                        await queue.put(get_neighbours(session, node))
            queue.task_done()
    g.render()


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
    asyncio.run(make_graph(args.endpoint, args.timeout))


if __name__ == "__main__":
    main()
