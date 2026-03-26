from __future__ import annotations

import asyncio
import io
import traceback
from contextlib import redirect_stdout

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


@tool
async def python_repl(code: str) -> str:
    """在沙箱化的 REPL 中执行 Python 代码并返回输出。

    Args:
        code: 要执行的 Python 代码。使用 print() 显示输出。
    """
    stdout_capture = io.StringIO()
    local_vars: dict = {}

    def _execute() -> str:
        with redirect_stdout(stdout_capture):
            try:
                exec(compile(code, "<repl>", "exec"), {"__builtins__": __builtins__}, local_vars)
                output = stdout_capture.getvalue()
                return output if output else "Code executed successfully (no output)."
            except Exception:
                return f"Error:\n{traceback.format_exc()}"

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _execute)
    logger.debug("Python REPL 执行完毕", code_len=len(code))
    return result
