import logging

# from prompt_toolkit.application.current import get_app

from ..XiChannel import XiChannel

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..view import View


def copy(params: dict, view: 'View', rpc_channel: XiChannel) -> None:
    result = view.manager.Queue()
    view_id = params.get('view_id') or view.current_view.view_id
    # For some reason params is a `[]` and we need result, so can't use .edit(...)
    rpc_channel.put('edit', {'method': 'copy', 'params': [], 'view_id': view_id}, result=result)
    view.app.clipboard.set_text(result.get() or "")


def cut(params: dict, view: 'View', rpc_channel: XiChannel) -> None:
    result = view.manager.Queue()
    view_id = params.get('view_id') or view.current_view.view_id
    rpc_channel.put('edit', {'method': 'cut', 'params': [], 'view_id': view_id}, result=result)
    view.app.clipboard.set_text(result.get() or "")


def paste(params: dict, view: 'View', rpc_channel: XiChannel) -> None:
    text = view.app.clipboard.get_data()
    view_id = params.get('view_id') or view.current_view.view_id
    if text.type == 'CHARACTERS':
        rpc_channel.edit('paste', {'chars': text.text}, view_id)
    else:
        logging.warning(f"[ACTION] Can't paste {text.type=}")
