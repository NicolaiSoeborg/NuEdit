from __future__ import annotations
import os

from typing import Callable, List
from pathlib import Path

from prompt_toolkit.application.current import get_app
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
from prompt_toolkit.layout.containers import Container, Window
from prompt_toolkit.key_binding import ConditionalKeyBindings
from prompt_toolkit.key_binding.key_bindings import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent as E
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.filters import Condition

# from prompt_toolkit.formatted_text import HTML
# from prompt_toolkit.completion import Completer, Completion
# class MyCustomCompleter(Completer):
#     def get_completions(self, document, complete_event):
#         yield Completion('completion3', start_position=0, style='class:special-completion')
#         yield Completion('completion4', start_position=0, display=HTML('<b>completion</b><ansired>1</ansired>'), style='bg:ansiyellow')


def get_filemanager_kb(lst: FileList, kb_active: Condition):
    kb = KeyBindings()

    @kb.add('up')
    def _(event: E) -> None:
        lst._selected_index = max(0, lst._selected_index - 1)

    @kb.add('down')
    def _(event: E) -> None:
        lst._selected_index = min(len(lst.values) - 1, lst._selected_index + 1)

    @kb.add('pageup')
    def _(event: E) -> None:
        w = event.app.layout.current_window
        lst._selected_index = max(0, lst._selected_index - len(w.render_info.displayed_lines))

    @kb.add('pagedown')
    def _(event: E) -> None:
        w = event.app.layout.current_window
        lst._selected_index = min(len(lst.values) - 1, lst._selected_index + len(w.render_info.displayed_lines))

    @kb.add('enter')
    def _(event: E) -> None:
        lst._handler(lst.selected)

    @kb.add('escape')
    def _(event: E) -> None:
        event.app.exit()

    @kb.add('<any>')
    def _(event: E) -> None:
        # We first check values after the selected value, then all values.
        for value in lst.values[lst._selected_index + 1:] + lst.values:
            if value.startswith(event.data):
                lst._selected_index = lst.values.index(value)
                return

    return ConditionalKeyBindings(kb, filter=kb_active)


class FileList:
    STYLE_FILE = ''
    STYLE_DIR = ''
    STYLE_OTHER = 'fg:red'

    def __init__(self, dir: Path, handler: Callable[[str], None], kb_active: Condition):
        self.values: List[str] = []
        self._styles = []
        for f in dir.iterdir():
            if f.is_file():
                self.values.append(f.name)
                self._styles.append(FileList.STYLE_FILE)
            elif f.is_dir():
                self.values.append(f.name + '/')
                self._styles.append(FileList.STYLE_DIR)
            elif f.is_symlink():
                self.values.append(f.name + ' -> ' + os.path.realpath(f))
                self._styles.append(FileList.STYLE_FILE)
            else:
                self.values.append(f.name + '|')
                self._styles.append(FileList.STYLE_OTHER)

        self._selected_index: int = 0
        self._handler = handler

        self.input_field = FormattedTextControl(
            self._get_text_fragments,
            show_cursor=False,
            key_bindings=get_filemanager_kb(self, kb_active),
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

    def _get_text_fragments(self):
        def mouse_handler(mouse_event: MouseEvent) -> None:
            if mouse_event.event_type == MouseEventType.MOUSE_UP:
                self._selected_index = mouse_event.position.y
                self._handler(self._selected_index)

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
    def __init__(self, view):
        self.view = view
        self.cwd = Path('.')
        cancel_button = Button(text="Exit", handler=self.exit_handler)

        self.filelist = FileList(self.cwd, view.new_view, Condition(lambda: view.fileman_visible))

        self.window = Dialog(
            title = "Browse files",
            body = HSplit([
                Label(text = f"Dir: {self.cwd}", dont_extend_height = True),
                self.filelist,
            ], padding = D(preferred=1, max=1)),
            buttons = [cancel_button],
            with_background = True)

    def __pt_container__(self) -> Container:
        return self.window

    @property
    def input_field(self):
        return self.filelist.input_field

    def exit_handler(self) -> None:
        if len(self.view.views) == 0:
            get_app().exit()
        else:
            self.view.fileman_visible = False
            self.view.set_focus(
                list(self.view.views.values())[0].view_id
            )
