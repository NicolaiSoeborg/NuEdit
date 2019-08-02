import multiprocessing as mp


def multicursor(params: dict, view, rpc_channel: mp.Queue) -> None:
    sview = view.current_view
    if not sview.lines.has_selection:
        sview.config['modify_selection'] = 'add'
        for (line, col) in sview.lines.cursors:
            rpc_channel.edit('gesture', {
                'line': line,
                'col': col,
                'ty': {'select': {'granularity': 'word', 'multi': True}}
            })
        rpc_channel.edit('selection_for_find', {
            'case_sensitive': False,
        })
        # Remove any old multicursor_cancel, if they are left:
        while ('multicursor_cancel', {}) in sview.undo_stack:
            sview.undo_stack.remove(('multicursor_cancel', {}))
        sview.undo_stack.append(
            ('multicursor_cancel', {})
        )
    else:
        rpc_channel.edit('find_next', {
            'wrap_around': True,
            'allow_same': True,
            'modify_selection': sview.config.get('modify_selection', 'add'),
        })
        sview.config['modify_selection'] = 'add'
        # Add
        if ('multicursor_cancel', {}) not in sview.undo_stack:
            sview.undo_stack.append(('multicursor_cancel', {}))


def multicursor_skip(params: dict, view, rpc_channel: mp.Queue) -> None:
    view.current_view.config['modify_selection'] = 'add_removing_current'
    # TODO: Add [esc] => "cancel ctrl+k" (but it should be removed from event_stack after pressing e.g. ctrl+d again)


def multicursor_cancel(params: dict, view, rpc_channel: mp.Queue) -> bool:
    if len(list(view.current_view.lines.cursors)) > 1:
        rpc_channel.edit('collapse_selections')
    else:
        # multicursors has already been cancel/removed, so do next "Esc operation"
        return False
