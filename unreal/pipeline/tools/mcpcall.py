"""Tiny MCP client: list tools or call one. Usage:
  mcpcall.py stdio <cmd> list
  mcpcall.py stdio <cmd> call <tool> '<json-args>'
  mcpcall.py http <url> list|call ...
"""
import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client


async def run(session, argv):
    await session.initialize()
    if argv[0] == "list":
        tools = (await session.list_tools()).tools
        for t in tools:
            print(t.name, "-", (t.description or "").splitlines()[0][:110] if t.description else "")
        print(len(tools), "tools")
    else:
        raw = argv[2] if len(argv) > 2 else "{}"
        if raw.startswith("@"):
            raw = open(raw[1:], encoding="utf-8").read()
        res = await session.call_tool(argv[1], json.loads(raw))
        for c in res.content:
            print(getattr(c, "text", None) or f"<{c.type}>")
        if res.structuredContent:
            print(json.dumps(res.structuredContent, indent=1))
        if res.isError:
            sys.exit(2)


async def main():
    kind, target, *rest = sys.argv[1:]
    if kind == "stdio":
        async with stdio_client(StdioServerParameters(command=target, args=[])) as (r, w):
            async with ClientSession(r, w) as s:
                await run(s, rest)
    else:
        async with streamablehttp_client(target) as (r, w, _):
            async with ClientSession(r, w) as s:
                await run(s, rest)

asyncio.run(main())
