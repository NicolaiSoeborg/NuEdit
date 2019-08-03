import logging

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import Container, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl


class Toolbar:
    def __init__(self, view):
        self.view = view

        self.control = BufferControl(
            focus_on_click=False,
            include_default_input_processors=False,
            input_processors=[],
            buffer=Buffer(
                multiline=False,
                accept_handler=self.handler
            )
        )
        self.container = Window(
            content=self.control,
            height=1, style="bg:#3200ff",
        )

    def __pt_container__(self) -> Container:
        return self.container

    def handler(self, buffer: Buffer):
        logging.debug("[Toolbar] handler got: " + buffer.text)
        return False  # <-- delete text
