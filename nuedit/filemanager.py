from __future__ import annotations
import logging

from typing import Callable, List
from pathlib import Path

# from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout.containers import HSplit
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.widgets import (
    Button,
    Dialog,
    Label,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.layout.containers import DynamicContainer, Container, Window
from prompt_toolkit.key_binding import ConditionalKeyBindings
from prompt_toolkit.key_binding.key_bindings import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent as E
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.filters import Condition

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .view import View

# from prompt_toolkit.formatted_text import HTML
# from prompt_toolkit.completion import Completer, Completion
# class MyCustomCompleter(Completer):
#     def get_completions(self, document, complete_event):
#         yield Completion('completion3', start_position=0, style='class:special-completion')
#         yield Completion('completion4', start_position=0, display=HTML('<b>completion</b><ansired>1</ansired>'), style='bg:ansiyellow')


class FileList:
    STYLE_FILE = ''
    STYLE_DIR = ''
    STYLE_OTHER = 'fg:red'

    def __init__(self, fm: Filemanager, handler: Callable[[str], None]):
        self.fm = fm
        self.values: List[str] = ['../']
        self._styles = [FileList.STYLE_DIR]
        self._selected_index: int = 0
        self._file_handler = handler

        for f in fm.cwd.iterdir():
            if f.is_file():
                self.values.append(f.name)
                self._styles.append(FileList.STYLE_FILE)
            elif f.is_dir():
                self.values.append(f.name + '/')
                self._styles.append(FileList.STYLE_DIR)
            # elif f.is_symlink():
            #    self.values.append(f.name + ' -> ' + os.path.realpath(f))
            #    self._styles.append(FileList.STYLE_SYMLINK)
            else:
                self.values.append(f.name + '|')
                self._styles.append(FileList.STYLE_OTHER)

        self.input_field = FormattedTextControl(
            self._get_text_fragments,
            show_cursor=False,
            key_bindings=self._get_filemanager_kb(fm),
            focusable=True)

        self.window = Window(
            content=self.input_field,
            cursorline=True,
            right_margins=[
                ScrollbarMargin(display_arrows=True),
            ],
            dont_extend_height=True)

    def __pt_container__(self) -> Container:
        return self.window

    @property
    def selected(self) -> str:
        return self.values[self._selected_index]

    def _on_enter(self):
        logging.debug(f"[FM] Selected: {self.selected}")
        if self.selected.endswith('/'):
            logging.debug(f"[FM] Changing dir: {self.selected}")
            self.fm.change_dir(Path(self.selected))
        elif self.selected.endswith('|'):
            logging.warning(f"[FM] TODO handle: {self.selected}")
            pass  # can't open PIPEs and other weird types
        else:
            logging.debug(f"[FM] Opening: {self.selected}")
            # assert callable(self._file_handler)
            self._file_handler(self.selected)

    def _get_filemanager_kb(self, fm: Filemanager):
        kb_active = Condition(lambda: fm.view.fileman_visible)
        kb = KeyBindings()

        @kb.add('up')
        def _(event: E) -> None:
            self._selected_index = max(0, self._selected_index - 1)

        @kb.add('down')
        def _(event: E) -> None:
            self._selected_index = min(len(self.values) - 1, self._selected_index + 1)

        @kb.add('pageup')
        def _(event: E) -> None:
            w = event.app.layout.current_window
            assert w.render_info
            self._selected_index = max(0, self._selected_index - len(w.render_info.displayed_lines))

        @kb.add('pagedown')
        def _(event: E) -> None:
            w = event.app.layout.current_window
            assert w.render_info
            self._selected_index = min(len(self.values) - 1, self._selected_index + len(w.render_info.displayed_lines))

        @kb.add('enter')
        def _(event: E) -> None:
            self._on_enter()

        @kb.add('escape')
        def _(event: E) -> None:
            fm.view.app.layout.focus(fm.cancel_button)

        @kb.add('<any>')
        def _(event: E) -> None:
            # We first check values after the selected value, then all values.
            for value in self.values[self._selected_index + 1:] + self.values:
                if value.startswith(event.data):
                    self._selected_index = self.values.index(value)
                    return

        return ConditionalKeyBindings(kb, filter=kb_active)

    def _get_text_fragments(self):
        def mouse_handler(mouse_event: MouseEvent) -> None:
            if mouse_event.event_type == MouseEventType.MOUSE_UP:
                self._selected_index = mouse_event.position.y
                self._on_enter()

        result = []
        for i, value in enumerate(self.values):
            if i == self._selected_index:
                result.append(('[SetCursorPosition]', ''))
            result.extend(to_formatted_text(value, style=self._styles[i]))
            result.append(('', '\n'))

        # Add mouse handler to all fragments.
        for i in range(len(result)):
            result[i] = (result[i][0], result[i][1], mouse_handler)

        result.pop()  # Remove last newline.
        return result


class Filemanager:
    def __init__(self, view: 'View'):
        self.view = view
        self.cwd: Path = Path('./').resolve()
        self.cancel_button = Button(text="Exit", handler=self.exit_handler)

        self.filelist = FileList(self, view.new_view)

        self.window = Dialog(
            title = "Browse files",
            body = DynamicContainer(lambda: HSplit([
                Label(text = f"Dir: {self.cwd}", dont_extend_height = True),
                self.filelist,
            ], padding = D(preferred=1, max=1))),
            buttons = [self.cancel_button],
            with_background = True)

    def __pt_container__(self):
        return self.window

    @property
    def input_field(self):
        return self.filelist.input_field

    def change_dir(self, new_dir: Path):
        self.cwd = self.cwd.joinpath(new_dir)
        self.filelist = FileList(self, self.view.new_view)  # recreate to use new self.cwd
        self.view.app.invalidate()  # fix focus

    def exit_handler(self) -> None:
        logging.debug("[FileMan] exit_handler")
        if len(self.view.views) == 0:
            logging.debug("[FileMan] Calling app.exit()")
            self.view.app.exit()
        else:
            self.view.fileman_visible = False
            self.view.set_focus(
                list(self.view.views.values())[0].view_id
            )
