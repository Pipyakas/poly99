"""Scriptable Unreal MCP client (Linux port of ue.py).

  ue-linux.py tools <substring>       # search tool names across all toolsets
  ue-linux.py describe <toolset>      # full toolset JSON
  ue-linux.py call <toolset> <tool> @args.json|'{json}'
  ue-linux.py py @script.py           # run editor Python (via ProgrammaticToolset or console)
"""
import asyncio, base64, json, os, sys, time
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# linux: same MCP endpoint/port as Windows ue.py.
URL = "http://localhost:8000/mcp"


IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence", "captures")


def _save_png(b64: str) -> str:
    os.makedirs(IMG_DIR, exist_ok=True)
    path = os.path.join(IMG_DIR, "shot_%d.png" % int(time.time() * 1000))
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(b64))
    return path


def text(res):
    parts = []
    for c in res.content:
        if getattr(c, "type", "") == "image":
            parts.append("[image saved] " + _save_png(c.data))
            continue
        t = getattr(c, "text", "") or ""
        try:
            rv = json.loads(t)["returnValue"]
            t = "[image saved] " + _save_png(rv["image"]["data"])
        except (ValueError, KeyError, TypeError):
            pass
        parts.append(t)
    return "\n".join(parts), res.isError


async def with_session(fn):
    async with streamablehttp_client(URL, timeout=600, sse_read_timeout=600) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await fn(s)


def load(arg):
    if arg.startswith("@"):
        return open(arg[1:], encoding="utf-8").read()
    return arg


async def main(argv):
    cmd = argv[0]

    async def go(s):
        if cmd == "tools":
            sets = (await s.call_tool("list_toolsets", {})).content[0].text
            names = [l[2:].split(":")[0] for l in sets.splitlines() if l.startswith("- ") and "." in l.split(":")[0]]
            for n in names:
                d = json.loads((await s.call_tool("describe_toolset", {"toolset_name": n})).content[0].text)
                for t in d.get("tools", []):
                    short = t["name"].rsplit(".", 1)[-1]
                    if len(argv) < 2 or argv[1].lower() in (t["name"] + t.get("description", "")).lower():
                        print(f"{n} :: {short} — {t.get('description', '').strip().splitlines()[0][:100] if t.get('description') else ''}")
        elif cmd == "describe":
            print((await s.call_tool("describe_toolset", {"toolset_name": argv[1]})).content[0].text)
        elif cmd == "py":
            code = load(argv[1])
            out, err = text(await s.call_tool("call_tool", {"toolset_name": "poly99_toolset.toolset.Poly99Toolset", "tool_name": "run_python", "arguments": {"code": code}}))
            try:
                print(json.loads(out)["returnValue"])
            except Exception:
                print(out)
            if err:
                sys.exit(2)
        elif cmd == "call":
            args = json.loads(load(argv[3])) if len(argv) > 3 else {}
            out, err = text(await s.call_tool("call_tool", {"toolset_name": argv[1], "tool_name": argv[2], "arguments": args}))
            print(out)
            if err:
                sys.exit(2)

    await with_session(go)


asyncio.run(main(sys.argv[1:]))
