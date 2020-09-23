# By: Simon Zeng (TQ Tezos)
# Released under BSD 3-clause license
# Type checked with Pyright (non-strict due to missing type stubs from aiohttp and graphviz)
# Formatted with Black

from __future__ import annotations
import argparse
import asyncio
import itertools
from typing import (
    Dict,
    Any,
    AsyncIterator,
    Iterable,
    Literal,
    NewType,
    Optional,
    TypeVar,
    get_args,
)

import aiohttp
import pygraphviz

Color = Literal["black", "red", "orange", "yellow", "green", "blue"]
Address = NewType("Address", str)
Hash = NewType("Hash", str)
Json = Dict[str, Any]
Timestamp = float
K = TypeVar("K")
V = TypeVar("V")

ENDPOINT_ROOT = "http://{endpoint}:{port}"
NEIGHBOURS_ENDPOINT = "{root}/network/connections/"
HEAD_HASH_ENDPOINT = "{root}/chains/main/blocks/head/hash/"
COLORS = get_args(Color)

# TODO: capital Dict from typing is deprecated in python 3.9; replace with lowercase `dict`
class IncrementingDefaultDict(Dict[K, V]):
    """
    Like defaultdict, but the default that we return increments based off of a provided iterable

    Example:
    > x = IncrementingDefaultDict([3, 4])
    > x[1]
    3
    > x[2]
    4
    > x[3]
    3
    > x
    {1: 3, 2: 4, 3: 3}
    """

    def __init__(self, defaults: Iterable[V]) -> None:
        self.defaults = itertools.cycle(defaults)

    def __getitem__(self, key: K) -> V:
        if key in self:
            return dict.__getitem__(self, key)
        else:
            self[key] = next(self.defaults)
            return dict.__getitem__(self, key)


async def fetch(session: aiohttp.ClientSession, url: Address) -> AsyncIterator[Json]:
    async with session.get(url) as response:
        lst = await response.json()
        # turning this into an async iterator instead of just returning the json gives us more chances to switch tasks
        for item in lst:
            yield item


class NodeTraverser:
    def __init__(
        self,
        refresh_interval: int,
        rpc_port: int,
        timeout: int,
        run_once: bool = False,
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop(),
        graph: pygraphviz.AGraph = pygraphviz.AGraph(directed=True, strict=True),
        color_map: dict[Hash, Color] = IncrementingDefaultDict(COLORS),
        visited: set[Address] = set(),
    ) -> None:
        self.loop = loop
        self.graph = graph
        self.color_map = color_map
        self.visited = visited
        self.refresh_interval = refresh_interval
        self.rpc_port = rpc_port
        self.timeout = timeout
        self.run_once = run_once
        self.session: Optional[aiohttp.ClientSession] = None

    def start(self, endpoint: Address) -> None:
        self.loop.create_task(self.start_traverse(endpoint))

        try:
            if self.run_once:
                self.finalize_tasks()
            else:
                self.loop.run_forever()
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, finalizing graph...")
            self.run_once = True
            self.loop.create_task(self.restart_traversal(endpoint))
            self.finalize_tasks()
        finally:
            self.loop.close()

    def finalize_tasks(self) -> None:
        while pending := [
            task for task in asyncio.all_tasks(self.loop) if not task.done()
        ]:
            self.loop.run_until_complete(asyncio.gather(*pending))
        self.loop.run_until_complete(self.session.close())
        self.graph.draw("graph.svg", prog="dot")

    async def restart_traversal(self, starting_addr: Address) -> None:
        self.graph.draw("graph.svg", prog="dot")
        print("Updating graph state...")
        self.visited = set()
        self.loop.create_task(self.traverse_node(starting_addr))
        if not self.run_once:
            await asyncio.sleep(self.refresh_interval)
            self.loop.create_task(self.restart_traversal(starting_addr))

    async def start_traverse(self, starting_addr: Address) -> None:
        # Initialize aiohttp session.
        # We can't use the context manager since that doens't survive across tasks.
        # The downside is we don't have a way to close the session, but the program is intended to run forever anyhow.
        if self.session is None:
            timeout_config = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout_config)

        self.loop.create_task(self.restart_traversal(starting_addr))

    async def traverse_node(self, node_addr: Address) -> None:
        self.visited.add(node_addr)

        # if already visited, we refresh neighbours by deleting node and repopulating
        try:
            self.graph.delete_node(node_addr)
        except KeyError:
            pass

        print(f"Currently visiting {node_addr}...")

        node_rpc_root = ENDPOINT_ROOT.format(endpoint=node_addr, port=self.rpc_port)
        node_rpc_neighbours = Address(NEIGHBOURS_ENDPOINT.format(root=node_rpc_root))
        node_rpc_hash = Address(HEAD_HASH_ENDPOINT.format(root=node_rpc_root))

        # we try/catch in case of unreachable rpc ports
        try:
            neighbours = fetch(self.session, node_rpc_neighbours)
            head_hash = Hash("".join([x async for x in fetch(self.session, node_rpc_hash)]))  # type: ignore
            self.graph.add_node(node_addr)

            # set color based off of head hash
            node_obj = self.graph.get_node(node_addr)
            node_obj.attr["shape"] = "record"
            node_obj.attr["label"] = f"{node_addr}|{head_hash}"
            node_obj.attr["color"] = self.color_map[head_hash]

            async for neighbour in neighbours:
                neighbour_addr: Address = neighbour["id_point"]["addr"]
                if neighbour_addr.startswith("::ffff:"):  # remove ipv6
                    neighbour_addr = Address(
                        neighbour_addr[7:]
                    )  # TODO: replace with <str>.removeprefix in python 3.9
                if neighbour["incoming"]:
                    print(f"Added edge {neighbour_addr} {node_addr}")
                    self.graph.add_edge(neighbour_addr, node_addr)
                else:
                    print(f"Added edge {node_addr} {neighbour_addr}")
                    self.graph.add_edge(node_addr, neighbour_addr)
                if neighbour_addr not in self.visited:
                    self.loop.create_task(self.traverse_node(neighbour_addr))
        except asyncio.TimeoutError:
            print(f"Connection timed out for node {node_addr}. RPC unreachable.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "endpoint",
        help="ip address or domain of tezos node to start exploring from",
        type=Address,
    )
    parser.add_argument(
        "--rpc_port",
        help="rpc port of every node to explore",
        default=8732,
        type=int,
    )
    parser.add_argument(
        "--timeout",
        help="connection timeout",
        default=5,
        type=int,
    )
    parser.add_argument(
        "--run_once",
        help="time until graph refresh",
        action="store_true",
    )
    parser.add_argument(
        "--refresh_interval",
        help="time until graph refresh",
        default=15,
        type=int,
    )
    args = parser.parse_args()

    traverser = NodeTraverser(
        args.refresh_interval,
        args.rpc_port,
        args.timeout,
        args.run_once,
    )
    traverser.start(args.endpoint)
