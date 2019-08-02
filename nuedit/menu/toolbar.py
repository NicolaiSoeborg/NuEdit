import logging

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


class Toolbar:
    def __init__(self, view):
        self.view = view

        self.control = BufferControl(
            focus_on_click=False,
            # key_bindings=self._get_kb(),
            include_default_input_processors=False,
            input_processors=[
                # BeforeInput("Menu: ", style="bold bg:#3200ff"),
                # AfterInput("", style="bold bg:#3200ff"),
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
        logging.debug("[Toolbar] handler got: " + buffer.text)
        return False

    # def _get_kb(self):
    #    kb = KeyBindings()
    #
    #    @kb.add('escape')
    #    def _(event) -> None:
    #        logging.debug("[Toolbar] Change focus to {}".format(self.view.current_view or self.view.fileman))
    #        self.view.app.layout.focus((self.view.current_view or self.view.fileman).input_field)
    #     return kb
