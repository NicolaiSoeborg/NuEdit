import logging
import multiprocessing as mp

# from prompt_toolkit.application.current import get_app


def copy(params: dict, view, rpc_channel: mp.Queue) -> None:
    result = view.manager.Queue()
    view_id = params.get('view_id') or view.current_view.view_id
    rpc_channel.edit_request('edit', {'method': 'copy', 'view_id': view_id}, result)
    view.app.clipboard.set_text(result.get() or "")


def cut(params: dict, view, rpc_channel: mp.Queue) -> None:
    result = view.manager.Queue()
    view_id = params.get('view_id') or view.current_view.view_id
    rpc_channel.edit_request('edit', {'method': 'cut', 'view_id': view_id}, result)
    view.app.clipboard.set_text(result.get() or "")


def paste(params: dict, view, rpc_channel: mp.Queue) -> None:
    text = view.app.clipboard.get_data()
    view_id = params.get('view_id') or view.current_view.view_id
    if text.type == 'CHARACTERS':
        rpc_channel.edit('paste', {'chars': text.text}, view_id )
    else:
        logging.warning('[ACTION] Cant paste {}'.format(text.type))
