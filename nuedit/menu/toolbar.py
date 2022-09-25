import logging

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import Container, ConditionalContainer, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl


class Toolbar:
    def __init__(self, view):
        self.view = view

        self.control = BufferControl(focus_on_click=False)

    def __pt_container__(self):
        status = ""
        if self.view.current_view:
            status = "| {}{}".format(
                self.view.current_view.file_path,
                '*' if self.view.current_view.is_dirty else ' ',
            )

        return VSplit([
            Window(content=self.control),
            Window(FormattedTextControl(text=status), width=len(status), style='fg:#888'),
        ], height=1, style='bg:#3200ff')

    def handler(self, buffer: Buffer):
        logging.debug(f"[Toolbar] handler got: {buffer.text}")
        return False  # <-- delete text
