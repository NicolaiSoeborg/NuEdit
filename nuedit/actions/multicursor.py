from ..XiChannel import XiChannel

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from nuedit.view import View


def multicursor(params: dict, view: 'View', rpc_channel: XiChannel) -> None:
    sview = view.current_view
    if not sview.lines.has_selection:
        sview.config['modify_selection'] = 'add'
        for (line, col) in sview.lines.cursors:
            rpc_channel.edit('gesture', {
                'line': line,
                'col': col,
                'ty': {'select': {'granularity': 'word', 'multi': True}}
            }, sview.view_id)
        rpc_channel.edit('selection_for_find', {
            'case_sensitive': False,
        }, sview.view_id)
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
        }, sview.view_id)
        sview.config['modify_selection'] = 'add'
        # Add
        if ('multicursor_cancel', {}) not in sview.undo_stack:
            sview.undo_stack.append(('multicursor_cancel', {}))


def multicursor_skip(params: dict, view: 'View', rpc_channel: XiChannel) -> None:
    view.current_view.config['modify_selection'] = 'add_removing_current'
    # TODO: Add [esc] => "cancel ctrl+k" (but it should be removed from event_stack after pressing e.g. ctrl+d again)


def multicursor_cancel(params: dict, view: 'View', rpc_channel: XiChannel) -> bool:
    sview = view.current_view
    if len(list(sview.lines.cursors)) > 1:
        rpc_channel.edit('collapse_selections', sview.view_id)
    else:
        # multicursors has already been cancel/removed, so do next "Esc operation"
        return False
    return True  # ... right?