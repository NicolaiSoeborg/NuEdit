from __future__ import annotations
import logging
import threading
import multiprocessing as mp
from collections import OrderedDict
from time import time, sleep
from typing import Any, Dict, List, Optional

from prompt_toolkit import Application
from prompt_toolkit.clipboard import InMemoryClipboard
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import DynamicContainer, Container, Window, HSplit, VSplit
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.output.color_depth import ColorDepth
from prompt_toolkit.widgets import HorizontalLine, VerticalLine
from prompt_toolkit.widgets.base import Border

from .line import Lines
from .filemanager import Filemanager
from .menu import Toolbar
from .keybinding import get_view_kb


class SimpleView:
    def __init__(self, file_path: Optional[str], channel: mp.Queue, view_id: str, global_view: View):
        self.file_path = file_path
        self.view_id = view_id
        self.global_view = global_view
        self._debug_update_timer = time()

        self.config: dict[str, Any] = {}  # font size, word wrap, line ending, etc
        self.undo_stack = [('close_view', {'view_id': view_id})]
        self.lines = Lines(shared_styles=global_view.shared_state['styles'])
        self.is_dirty: Optional[bool] = None

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
                    logging.warning(f"[SimpleView] Unknown method: {method}")
        except Exception as ex:
            logging.warning("[SimpleView] Got exception: ", ex)

    def _update_controls(self):
        new_text, new_lineNo, len_of_lineno_col = self.lines.get_formatted(self)
        self.lineNo.content.text = new_lineNo
        self.lineNo.width = len_of_lineno_col
        self.input_field.content.text = new_text
        self.global_view.app.invalidate()  # <-- redraw content
        logging.debug("[SimpleView] Update + redraw took {:.5f}s".format(time() - self._debug_update_timer))

    # Commands from Xi below
    def language_changed(self, language_id: str):
        pass

    def available_plugins(self, plugins: list):
        self.config['plugins'] = plugins

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
        pass  # for query in queries:


class View:
    def __init__(self, manager: mp.Manager, shared_state: dict, rpc_channel: mp.Queue):
        self.manager = manager
        self.shared_state = shared_state
        self.rpc_channel = rpc_channel

        self.fileman = Filemanager(self)
        self.fileman_visible = True

        self.toolbar = Toolbar(self)

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
                    DynamicContainer(self._get_children),
                    DynamicContainer(lambda: self.toolbar)
                ]),
                # focused_element=(self.current_view or self.fileman).input_field,
            ),
        )

    def _get_children(self):
        children = ([self.fileman] if self.fileman_visible else []) \
            + list(self.views.values())
        return VSplit(
            children=children,
            padding_char=Border.VERTICAL,
            padding=1,
            padding_style='#ffff00'
        ) if len(children) > 0 else Window()  # VSplit([]) will raise Exception

    @property
    def current_view(self) -> Optional[SimpleView]:
        return self.views.get(self.shared_state['focused_view'])

    def set_focus(self, view_id: str) -> None:
        self.shared_state['focused_view'] = view_id
        # When creating a new_view then set_focus will be called immediately after
        # This will create a race-condition between app.focus("LOADING...") and the
        # "LOADING..." component being replaced by the actually content (SimpleView
        # starts a thread that listen on the RPC channel, which often takes "a while"
        # so wait for the app to be ready (is_dirty != None) before calling set_focus:
        threading.Thread(target=self._set_focus, args=(view_id, )).start()

    def _set_focus(self, view_id: str) -> None:
        # Break if multiple threads are competing for focus:
        while self.shared_state['focused_view'] == view_id:
            if current_view := self.current_view:
                if current_view.is_dirty is None:
                    sleep(.1)
                else:
                    self.app.layout.focus(current_view.input_field)
                    break

    def new_view(self, file_path: Optional[str] = None):
        channel = self.manager.Queue()
        self.rpc_channel.edit_request('new_view', {} if file_path is None else {'file_path': file_path}, channel)
        # Wait for 'view-id-X' identifier:
        view_id = channel.get()
        assert view_id not in self.shared_state['view_channels'], f"Duplicate view_id: {view_id} ({self.shared_state})"
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
