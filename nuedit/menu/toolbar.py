import logging

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import Container, ConditionalContainer, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .view import View


class Toolbar:
    def __init__(self, view: 'View'):
        self.view = view
        self.control = BufferControl(focus_on_click=False)

    def __pt_container__(self):
        status = ""
        show_xy = True
        # Doing: `self.view.global_view.shared_state['settings'].get('show_xy', True)``
        # Will raise: AttributeError: 'ForkAwareLocal' object has no attribute 'connection'
        # ?!

        if current_view := self.view.current_view:
            status = "{xy} | {file_path} {dirty}".format(
                xy=f'{current_view.xy}' if show_xy and current_view.xy else '',
                file_path=current_view.file_path,
                dirty='*' if current_view.is_dirty else ' ',
            )

        return VSplit([
            Window(content=self.control),
            Window(FormattedTextControl(text=status), width=len(status), style='fg:#888'),
        ], height=1, style='bg:#3200ff')

    def handler(self, buffer: Buffer):
        logging.debug(f"[Toolbar] handler got: {buffer.text}")
        return False  # <-- delete text
