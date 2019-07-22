import multiprocessing as mp


def multicursor(params: dict, view, rpc_channel: mp.Queue) -> None:
    if not view.current_view.lines.has_selection:
        view.current_view.config = {'modify_selection': 'add'}
        for (line, col) in view.current_view.lines.cursors:
            rpc_channel.edit('gesture', {
                'line': line,
                'col': col,
                'ty': {'select': {'granularity': 'word', 'multi': True}}
            })
        rpc_channel.edit('selection_for_find', {
            'case_sensitive': False,
        })
        view.current_view.undo_stack.append(
            ('multicursor_cancel', {})
        )
    else:
        rpc_channel.edit('find_next', {
            'wrap_around': True,
            'allow_same': True,
            'modify_selection': view.current_view.config['modify_selection'],
        })
        view.current_view.config = {'modify_selection': 'add'}


def multicursor_skip(params: dict, view, rpc_channel: mp.Queue) -> None:
    view.current_view.config['modify_selection'] = 'add_removing_current'
    # TODO: Add [esc] => "cancel ctrl+k" (but it should be removed from event_stack after pressing e.g. ctrl+d again)


def multicursor_cancel(params: dict, view, rpc_channel: mp.Queue) -> None:
    if len(list(view.current_view.lines.cursors)) > 1:
        rpc_channel.edit('collapse_selections')
    else:
        # multicursors has already been cancel/removed, so do next "Esc operation"
        pass #undo(self.shared_state['event_stack'], self.shared_state)
