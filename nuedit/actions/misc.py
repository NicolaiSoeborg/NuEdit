import multiprocessing as mp


def new_view(params: dict, view, rpc_channel: mp.Queue) -> None:
    view.fileman_visible = True
    view.app.layout.focus(view.fileman)


def close_view(params: dict, view, rpc_channel: mp.Queue) -> None:
    view_id = params['view_id']
    if view.views[view_id].lines.has_selection:
        rpc_channel.edit('collapse_selections', {}, view_id)
        view.views[view_id].undo_stack.append(('close_view', {'view_id': view_id}))  # <-- re-add this action
    else:
        view.close_view(view_id)
