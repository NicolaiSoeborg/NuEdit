import logging
import multiprocessing as mp

from prompt_toolkit.keys import ALL_KEYS as SPECIAL_KEYS
from prompt_toolkit.key_binding import ConditionalKeyBindings, KeyBindings, merge_key_bindings
from prompt_toolkit.filters import Condition

import nuedit.actions as ACTIONS


def undo(view, rpc_channel: mp.Queue):
    (action, params) = view.current_view.undo_stack.pop()
    getattr(ACTIONS, action)(params, view, rpc_channel)


def get_view_kb(view):
    kb_map = view.shared_state['settings']['keybindings']
    rpc_channel = view.rpc_channel

    kb = KeyBindings()

    def do_action(key: str):
        if key not in kb_map:
            logging.debug("[KB] Unknown special key: {}".format(key))
            return

        if kb_map[key][0] == '.':
            action = kb_map[key][1:]
            assert action[0] != '_'
            logging.debug("[KB] Calling {} (KB: {})".format(action, key))
            getattr(ACTIONS, action)({}, view, rpc_channel)
        else:
            rpc_channel.edit(kb_map[key])

    @kb.add('escape', '[', '1', ';', '4', 'A', eager=True)
    def c_s_up(_): do_action('c-s-up')

    @kb.add('escape', '[', '1', ';', '4', 'B', eager=True)
    def c_s_down(_): do_action('c-s-down')

    @kb.add('escape', '[', '1', ';', '6', 'D', eager=True)
    def c_s_left(_): do_action('c-s-left')

    @kb.add('escape', '[', '1', ';', '6', 'C', eager=True)
    def c_s_left(_): do_action('c-s-right')

    @kb.add('escape', filter=Condition(lambda: len(view.current_view.undo_stack) > 0))
    def kb_undo(_):
        undo(view, rpc_channel)

    @kb.add('<any>')
    def _(event):
        for sequence in event.key_sequence:
            if sequence.key in SPECIAL_KEYS:
                do_action(sequence.key)
            else:
                rpc_channel.edit('insert', {'chars': sequence.key})

    return ConditionalKeyBindings(kb, filter=Condition(lambda: view.current_view is not None))


def test_keybindings():
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import FormattedTextControl, Window
    textarea = FormattedTextControl(
        text='Press "a b c" to quit.',
        show_cursor=False,
    )

    kb = KeyBindings()
    @kb.add('a', 'b', 'c')
    def _(event):
        event.app.exit()

    @kb.add('<any>')
    def _(event):
        textarea.text += "\n{}".format(event.key_sequence)

    app = Application(layout=Layout(Window(textarea)), key_bindings=kb)
    app.run()



"""
    return merge_key_bindings([
        ConditionalKeyBindings(
            key_bindings=kb,
            filter=Condition(lambda: shared_state['keybindings_enabled'])
        ),
        kb_always])
"""
