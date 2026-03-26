from __future__ import annotations

from typing import Any

from fastapi import Request


def get_settings(request: Request) -> Any:
    return request.app.state.settings


def get_graph(request: Request) -> Any:
    return request.app.state.graph


def get_checkpointer(request: Request) -> Any:
    return request.app.state.checkpointer


def get_store(request: Request) -> Any | None:
    return getattr(request.app.state, "store", None)
