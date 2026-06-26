from typing import Any

from app.handlers.admin.constants import STAGE_ORDER

_stats_pages: dict[int, dict[str, int]] = {}
_form_state: dict[int, dict[str, Any]] = {}


def default_stats_pages() -> dict[str, int]:
    return {key: 0 for key in STAGE_ORDER}


def get_admin_stats_pages(admin_id: int) -> dict[str, int]:
    return _stats_pages.setdefault(admin_id, default_stats_pages())


def reset_admin_stats_pages(admin_id: int) -> None:
    _stats_pages[admin_id] = default_stats_pages()


def default_form_state() -> dict[str, Any]:
    return {"filter": "completed", "page": 0}


def get_admin_form_state(admin_id: int) -> dict[str, Any]:
    return _form_state.setdefault(admin_id, default_form_state())


def reset_admin_form_state(admin_id: int) -> None:
    _form_state[admin_id] = default_form_state()
