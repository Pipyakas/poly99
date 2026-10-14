"""poly99 project toolset exposed over Unreal MCP.

Gives agents unrestricted editor Python (the stock ProgrammaticToolset is
sandboxed to toolset APIs). Local-only: the MCP server binds to localhost.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import sys
import traceback

import unreal
import toolset_registry


def _run(code: str, filename: str) -> str:
    out = io.StringIO()
    scope = {"__name__": "__poly99__", "unreal": unreal}
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(compile(code, filename, "exec"), scope)
    except Exception:
        out.write(traceback.format_exc())
        raise RuntimeError(out.getvalue())
    result = scope.get("result")
    if result is not None:
        out.write("\nresult = {!r}".format(result))
    return out.getvalue()


@unreal.uclass()
class Poly99Toolset(unreal.ToolsetDefinition):
    """poly99 project tools: run editor Python and project pipeline helpers."""

    @toolset_registry.tool_call
    def run_python(code: str) -> str:
        """Execute Python in the editor's Python environment (full `unreal` API).

        Args:
            code: Python source. stdout/stderr are captured and returned. Assign to a
                variable named `result` to have its repr appended to the output.

        Returns:
            Captured output. Raises with the traceback on error.
        """
        return _run(code, "<run_python>")

    @toolset_registry.tool_call
    def run_python_file(path: str) -> str:
        """Execute a Python file from disk in the editor (same semantics as run_python).

        Args:
            path: Absolute path to a .py file.

        Returns:
            Captured output.
        """
        with open(path, encoding="utf-8") as fh:
            return _run(fh.read(), path)

    @toolset_registry.tool_call
    def reload_module(module_name: str) -> str:
        """Reload an already-imported Python module (pick up edits without restarting).

        Args:
            module_name: Dotted module name, e.g. "poly99_pipeline.importers".

        Returns:
            Confirmation message.
        """
        mod = sys.modules.get(module_name) or importlib.import_module(module_name)
        importlib.reload(mod)
        return "reloaded " + module_name
