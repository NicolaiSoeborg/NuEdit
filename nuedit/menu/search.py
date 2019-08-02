import logging
import re

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import Container, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.key_binding import ConditionalKeyBindings
from prompt_toolkit.key_binding.key_bindings import KeyBindings
from prompt_toolkit.layout.processors import (
    AfterInput,
    BeforeInput,
    ShowLeadingWhiteSpaceProcessor,
    ShowTrailingWhiteSpaceProcessor
)

from .toolbar import Toolbar


class SearchToolbar(Toolbar):
    def __init__(self, view):
        super().__init__(view)
        self._find_idx = 0

        self.control = BufferControl(
            focus_on_click=True,
            key_bindings=self._get_kb(),
            include_default_input_processors=False,
            input_processors=[
                BeforeInput("Search: ", style="bold bg:#3200ff"),
                # AfterInput("Regex: [ ]", style="bold bg:#3200ff"),
                ShowLeadingWhiteSpaceProcessor(),
                ShowTrailingWhiteSpaceProcessor()
            ],
            buffer=Buffer(
                multiline=False,
                accept_handler=self.handler
            )
        )
        self.container = Window(
            content=self.control,
            height=1,
            style="bg:#3200ff",
        )

    def __pt_container__(self) -> Container:
        return self.container

    def handler(self, buffer: Buffer):
        regex = re.fullmatch(r'/(.+)/([gi]?)', buffer.text)

        found_result = [a for a in self.view.current_view.lines.annotations if a['type'] == 'find']
        if len(found_result) == 0:
            self.view.rpc_channel.edit('find', {
                'chars': regex.group(1) if regex else buffer.text,
                'case_sensitive': 'i' in regex.group(2) if regex else False,
                'regex': bool(regex),
                # 'whole_words' : False,
            })
            self._find_idx = 0
            return True  # <-- keep text

        assert len(found_result) == 1
        ranges = found_result[0]['ranges']
        start_line, start_col, end_line, end_col = ranges[self._find_idx % len(ranges)]
        self._find_idx += 1

        # Select current found result (start + select_extend to end):
        self.view.rpc_channel.edit('gesture', {
            'line': start_line,
            'col': start_col,
            'ty': {'select': {'granularity': 'point', 'multi': False}}
        })
        self.view.rpc_channel.edit('gesture', {
            'line': end_line,
            'col': end_col,
            'ty': {'select_extend': {'granularity': 'point', 'multi': False}}
        })

        # Then find next result:
        #self.view.rpc_channel.edit('find_next', {
        #    'wrap_around': 'g' in regex.group(2) if regex else False,
        #    'allow_same': True,
        #})
        return True  # <-- keep text

    def _get_kb(self):
        kb = KeyBindings()

        @kb.add('escape')
        def _(event):
            # if self.view.current_view.lines.has_selection:
            #    self.view.rpc_channel.edit('collapse_selections')
            # else:
            self.view.toolbar = Toolbar(self.view)  # Hide "Find: " and fix focus:
            self.view.app.layout.focus((self.view.current_view or self.view.fileman).input_field)

        return kb
