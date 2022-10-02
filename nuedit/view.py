from __future__ import annotations
import logging
from operator import length_hint
import threading
import multiprocessing as mp
from collections import OrderedDict
from time import time, sleep
from typing import Any, Dict, List, Optional

from prompt_toolkit import Application
from prompt_toolkit.clipboard import InMemoryClipboard
from prompt_toolkit.formatted_text import FormattedText  #, HTML('<u>underline</u>')
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import DynamicContainer, Container, Window, HSplit, VSplit
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.output.color_depth import ColorDepth
from prompt_toolkit.widgets import HorizontalLine, VerticalLine
from prompt_toolkit.widgets.base import Border

from .XiChannel import XiChannel
from .line_cache import LineCache
from .keybinding import get_view_kb
from .filemanager import Filemanager
from .menu import Toolbar


class SimpleView:
    def __init__(self, file_path: Optional[str], channel: XiChannel, view_id: str, global_view: GlobalView):
        self.file_path = file_path
        self.view_id = view_id
        self.global_view = global_view
        self._debug_update_timer = time()

        self.config: dict[str, Any] = {}  # font size, word wrap, line ending, etc
        self.undo_stack = [('close_view', {'view_id': view_id})]
        self.is_dirty: Optional[bool] = None

        self.line_cache = LineCache(global_view)
        self.input_field = Window(
            content=FormattedTextControl(
                key_bindings=get_view_kb(self.global_view),
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
        #    self.rpc_channel.edit('scroll', {int(columns), int(rows)}, self.view_id)
        #    #        'width': int(columns),  # <-- TODO: in pixels
        #    #        'height': int(rows)     # .input_field.width, ?
        #    logging.debug("[RESIZE] {} {} | w/h:{}/{}".format(signum, frame, columns, rows))
        #    proc.close()
        #signal.signal(signal.SIGWINCH, _resizeHandler)
        #_resizeHandler(None, None)

    def __pt_container__(self) -> Container:
        return self.input_field

    def _bg_worker(self, channel):
        try:
            while True:
                (method, params) = channel.get()
                logging.debug(f"[SimpleView] _bg_worker: {method=} {params=}")
                if method == 'kill':
                    break
                elif hasattr(self, f'rpc_{method}'):
                    getattr(self, f'rpc_{method}')(**params)
                else:
                    logging.warning(f"[SimpleView] Unknown method: {method}")
        except Exception as ex:
            logging.warning("[SimpleView] Got exception: ", ex)

    # Commands from Xi below
    def rpc_language_changed(self, language_id: str):
        # {"method":"language_changed","params":{"language_id":"Plain Text","view_id":"view-id-1"}}
        pass

    def rpc_available_plugins(self, plugins: list):
        self.config['plugins'] = plugins

    def rpc_config_changed(self, changes: dict):
        # {'changes': {'auto_indent': True, 'autodetect_whitespace': True, 'font_face': 'InconsolataGo', 'font_size': 14, 'line_ending': '\n', 'plugin_search_path': [], 'save_with_newline': True, 'scroll_past_end': False, 'surrounding_pairs': [['"', '"'], ["'", "'"], ['{', '}'], ['[', ']']], 'tab_size': 4, 'translate_tabs_to_spaces': True, 'use_tab_stops': True, 'word_wrap': False, 'wrap_width': 0}}
        self.config.update(changes)

    def rpc_update(self, update: dict):
        self._debug_update_timer = time()
        self.is_dirty = not update['pristine']
        self.line_cache.apply_update(update)

        len_of_lineno_col = len(str(self.line_cache.max_ln))
        self.lineNo.content = FormattedTextControl(text='\n'.join(
            str(l.ln).rjust(len_of_lineno_col, ' ') if l else '?'*len_of_lineno_col
            for l in self.line_cache.lines
        ))
        self.lineNo.width = len_of_lineno_col

        # Redraw
        # https://python-prompt-toolkit.readthedocs.io/en/master/pages/printing_text.html#style-text-tuples
        output = []
        for line in self.line_cache.lines:
            logging.debug(f'[SimpleView] {line.text=}')
            if line:
                for style_text_pair in line.get_style_text_pairs(self.line_cache.annotations):
                    logging.debug(f'[SimpleView] {style_text_pair=}')
                    output.append(style_text_pair)
            else:
                output.append(('', '\n'))
        self.input_field.content = FormattedTextControl(
            show_cursor=False,
            text=FormattedText(output)
        )

        self.global_view.app.invalidate()  # <-- redraw content
        logging.debug("[SimpleView] Update + redraw took {:.5f}s".format(time() - self._debug_update_timer))

    def rpc_scroll_to(self, col: int, line: int):
        pass  # "frontend should scroll its cursor to the given line and column."

    def rpc_find_status(self, queries: list):
        pass  # for query in queries:


class GlobalView:
    def __init__(self, manager: mp.managers.SyncManager, shared_state: dict, rpc_channel: XiChannel):
        self.manager = manager
        self.shared_state = shared_state
        self.rpc_channel = rpc_channel

        self.fileman = Filemanager(self)
        self.fileman_visible = True

        self.toolbar = Toolbar(self)

        self.views: dict[str, SimpleView] = OrderedDict()

        self.app: Application = Application(
            full_screen=True,
            mouse_support=shared_state['settings'].get('mouse_support', False),
            color_depth=ColorDepth.DEPTH_24_BIT,
            clipboard=InMemoryClipboard(),
            enable_page_navigation_bindings=False,
            # key_bindings=get_filemanager_kb()
            key_bindings=get_view_kb(self),
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
        logging.debug(f"[View] set_focus({view_id=})")
        self.shared_state['focused_view'] = view_id
        # When creating a new_view then set_focus will be called immediately after
        # This will create a race-condition between app.focus("LOADING...") and the
        # "LOADING..." component being replaced by the actually content (SimpleView
        # starts a thread that listen on the RPC channel, which often takes "a while"
        # so wait for the app to be ready (is_dirty != None) before calling set_focus:
        threading.Thread(target=self._set_focus, args=(view_id, )).start()

    def _set_focus(self, view_id: str) -> None:
        # Break if multiple threads are competing for focus:
        logging.debug(f"[View] _set_focus({view_id=}) should eq {self.shared_state['focused_view']}")
        while self.shared_state['focused_view'] == view_id:
            if current_view := self.current_view:
                if current_view.is_dirty is None:
                    sleep(.1)
                else:
                    logging.debug(f"[View] _set_focus({view_id=}) setting focus! {self.app}.focus({current_view=})")
                    self.app.layout.focus(current_view.input_field)
                    break
            logging.debug(f"[View] _set_focus({view_id=}) waiting for {current_view=} (is_dirty)")

    def new_view(self, file_path: Optional[str] = None):
        channel = self.manager.Queue()
        self.rpc_channel.put('new_view', {} if file_path is None else {'file_path': file_path}, result=channel)
        # Wait for 'view-id-X' identifier:
        view_id = channel.get()
        assert view_id not in self.shared_state['view_channels'], f"Duplicate view_id: {view_id} ({self.shared_state})"
        self.shared_state['view_channels'][view_id] = channel
        self.views[view_id] = SimpleView(file_path, channel, view_id, self)
        self.set_focus(view_id)

    def close_view(self, view_id: str):
        self.rpc_channel.put('close_view', {'view_id': view_id})
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
