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


def next_view(params: dict, view, rpc_channel: mp.Queue) -> None:
    lst = list(view.views.values()) + ([view.fileman] if view.fileman_visible else [])
    for i, v in enumerate(lst):
        if view.app.layout.has_focus(v):
            _set_focus(view, lst[(i + 1) % len(lst)])
            break
    #view.app.layout.focus_next()


def previous_view(params: dict, view, rpc_channel: mp.Queue) -> None:
    lst = list(view.views.values()) + ([view.fileman] if view.fileman_visible else [])
    for i, v in enumerate(lst):
        if view.app.layout.has_focus(v):
            _set_focus(view, lst[(i - 1) % len(lst)])
            break
    #view.app.layout.focus_previous()


def _set_focus(view, elm):
    if elm in view.views.values():
        view.set_focus(elm.view_id)
    else:
        view.fileman_visible = True
        view.app.layout.focus(view.fileman.input_field)