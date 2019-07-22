from __future__ import annotations
import logging
import threading
import multiprocessing as mp
from collections import OrderedDict
from time import time

from typing import Union

from prompt_toolkit import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.clipboard import InMemoryClipboard
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import DynamicContainer, Container, Window, HSplit, VSplit
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.output.color_depth import ColorDepth
from prompt_toolkit.widgets import HorizontalLine, VerticalLine, TextArea
from prompt_toolkit.widgets.base import Border

from .line import Lines
from .filemanager import Filemanager
from .keybinding import get_view_kb


class SimpleView:
    def __init__(self, file_path: str, channel: mp.Queue, view_id: str, global_view: View):
        self.file_path = file_path
        self.view_id = view_id
        self.global_view = global_view

        self.config = {}  # font size, word wrap, line ending, etc
        self.undo_stack = [('close_view', {'view_id': view_id})]
        self.lines = Lines(shared_styles=global_view.shared_state['styles'])
        self.is_dirty = False

        self.input_field = Window(
            content=FormattedTextControl(
                key_bindings=get_view_kb(global_view),
                show_cursor=False,
                text="LOADING...",
            )
        )
        self.lineNo = Window(width=2, content=FormattedTextControl(text="  "))
        self.container = VSplit([self.lineNo, VerticalLine(), self.input_field])

        # Start _bg_worker (listen for msgs on shared_state['view_channels'][this-view-id] and apply them to self):
        self.thread = threading.Thread(target=self._bg_worker, args=(channel, ))
        self.thread.start()

        # Notify Xi about terminal size:
        #def _resizeHandler(signum, frame):
        #    proc = os.popen('stty size', 'r')
        #    rows, columns = proc.read().split()
        #    self.rpc_channel.edit('scroll', [int(columns), int(rows)])
        #    #        'width': int(columns),  # <-- TODO: in pixels
        #    #        'height': int(rows)     # .input_field.width, ?
        #    logging.debug("[RESIZE] {} {} | w/h:{}/{}".format(signum, frame, columns, rows))
        #    proc.close()
        #signal.signal(signal.SIGWINCH, _resizeHandler)
        #_resizeHandler(None, None)

    def __pt_container__(self) -> Container:
        return self.container

    def _bg_worker(self, channel):
        try:
            while True:
                (method, params) = channel.get()
                if hasattr(self, method):
                    getattr(self, method)(**params)
                elif method == 'kill':
                    break
                else:
                    logging.warning("[SimpleView] Unknown method: {}".format(method))
        except Exception as ex:
            logging.warning("[SimpleView] Got exception: ", ex)

    def _update_controls(self):
        new_text, new_lineNo, len_of_lineno_col = self.lines.get_formatted(self)
        self.lineNo.content.text = new_lineNo
        self.lineNo.width = len_of_lineno_col
        self.input_field.content.text = new_text
        get_app().invalidate()  # <-- redraw content
        logging.debug("[SimpleView] Update took {:.4f}s".format(time() - self._debug_update_timer))

    # Commands from Xi below
    def language_changed(self, language_id: str):
        pass

    def available_plugins(self, plugins: list):
        self.plugins = plugins

    def config_changed(self, changes: dict):
        self.config.update(changes)

    def update(self, update: dict):
        self._debug_update_timer = time()
        self.is_dirty = not update['pristine']
        self.lines = self.lines.apply(update)
        self._update_controls()

    def scroll_to(self, col: int, line: int):
        pass  # "frontend should scroll its cursor to the given line and column."

    def find_status(self, queries: list):
        pass
        # queries = [{'case_sensitive': False, 'chars': 'HELLO', 'id': 1, 'is_regex': False, 'lines': [1, 1, 3, 4], 'matches': 4, 'whole_words': True}]


class View:
    def __init__(self, manager: mp.Manager, shared_state: dict, rpc_channel: mp.Queue):
        self.manager = manager
        self.shared_state = shared_state
        self.rpc_channel = rpc_channel

        self.fileman = Filemanager(self)
        self.fileman_visible = True
        self.views = OrderedDict()  # type: Dict[str, SimpleView]
        self.app = Application(
            full_screen=True,
            mouse_support=True,
            color_depth=ColorDepth.DEPTH_24_BIT,
            clipboard=InMemoryClipboard(),
            enable_page_navigation_bindings=False,
            # key_bindings=get_filemanager_kb()
            layout=Layout(
                container=HSplit([
                    DynamicContainer(lambda: VSplit(
                        children=[sview for sview in self.views.values()] + ([self.fileman] if self.fileman_visible else []),
                        padding_char=Border.VERTICAL,
                        padding=1,
                        padding_style='#ffff00'
                    ))
                ]),
                focused_element=(self.current_view or self.fileman).input_field,
            ),
        )

    @property
    def current_view(self) -> SimpleView:
        return self.views.get(self.shared_state['focused_view'])

    def set_focus(self, view_id: str) -> None:
        self.shared_state['focused_view'] = view_id
        self.app.layout.focus(self.current_view.input_field)

    def new_view(self, file_path: str = None):
        channel = self.manager.Queue()
        self.rpc_channel.edit_request('new_view', {} if file_path is None else {'file_path': file_path}, channel)
        # Wait for 'view-id-X' identifier:
        view_id = channel.get()
        assert view_id not in self.shared_state['view_channels'], "Duplicate view_id: {} ({})".format(view_id, self.shared_state)
        self.shared_state['view_channels'][view_id] = channel
        self.views[view_id] = SimpleView(file_path, channel, view_id, self)
        self.set_focus(view_id)

    def close_view(self, view_id: str):
        self.rpc_channel.notify('close_view', {'view_id': view_id})
        self.shared_state['view_channels'][view_id].put(('kill', {}))
        self.views[view_id].thread.join()
        del self.shared_state['view_channels'][view_id]
        del self.views[view_id]
        if view_id == self.shared_state['focused_view']:
            self.shared_state['focused_view'] = None
            try:
                new_focused_view = list(self.views)[0]
                self.set_focus(new_focused_view)
            except IndexError:
                if self.fileman_visible:
                    self.app.layout.focus(self.fileman.input_field)
                else:
                    logging.debug("[View] Calling app.exit()")
                    self.app.exit()
