from __future__ import annotations
from collections import deque
import logging
from multiprocessing.managers import DictProxy
from typing import Any, Iterator, Literal, Optional, Tuple, TypedDict
# from collections import deque

# from prompt_toolkit import ANSI('\x1b[31mhello \x1b[32mworld')
from prompt_toolkit.layout.containers import Container, Window
#from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from .keybinding import get_view_kb

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .view import GlobalView

class AnnotationSet(TypedDict):
    type: Literal['find', 'selection']
    ranges: list[Tuple[int, int, int, int]]  # actually it is a list of lists, start_line, start_col, end_line, end_col
    payloads: Optional[list[Any]]  # None or e.g. [{'id': 1}, {'id': 1}, {'id': 1}]
    n: int  # number of ranges

class SingleLine:
    def __init__(self, text: str, ln: int = 0, cursor: list[int] = [], styles: list = []) -> None:
        self.text = text
        self.ln = ln
        self.cursor = cursor
        self.styles = styles

    def get_style_text_pairs(self, annotations: AnnotationSet) -> Iterator[Tuple[str, str]]:
        """ Returns (style, text) pairs """
        logging.debug(f"get_style_text_pairs: {self.cursor=} {self.styles=} {self.text=}")

        # pass from global
        shared_state = {'styles': {
            'cursor': 'reverse underline',
            0: 'reverse',
            1: 'fg:ansiyellow bg:black',
        }}

        # Idé: lav par af (start, end, type) pairs og iter over zip()
        #pairs: list[Tuple[int, int, str]] = []  # (start, length, style)
        dumb_poc = {}

        # Add style:
        n_styles = len(self.styles)
        last_end = 0
        for i in range(n_styles // 3):
            start_idx = self.styles[i] + last_end
            style_len = self.styles[i + 1]
            style_id = self.styles[i + 2]
            last_end = start_idx + style_len
            #pairs.append((start_idx, style_len, shared_state['styles'][style_id]))
            for asd in range(style_len): dumb_poc[start_idx+asd] = shared_state['styles'][style_id]

        for ann in annotations:
            ...

        for cursor in self.cursor:
            #pairs.append((cursor, 1, shared_state['styles']['cursor']))
            dumb_poc[cursor] = shared_state['styles']['cursor']

        # Keep track of overlapping styles
        # E.g. [text [selected[cursor]___] ]
        #applied_styles = []
        #while len(pairs) > 1:
        #    (start_idx, style_len, style) = pairs.pop(0)
        #assert len(pairs) == 1
        #(start_idx, style_len, style) = pairs.pop()
        #yield (style, self.text[start_idx:])  # todo: apply other styles

        for i, c in enumerate(self.text):
            yield (dumb_poc.get(i, ''), c)

        # Dette virker:
        # txt_style = ''  # '#44ff00 italic'
        # if len(self.cursor) == 0:
        #     yield (txt_style, self.text)
        # else:
        #     pos = 0
        #     for cursor in self.cursor:
        #         yield (txt_style, self.text[pos:cursor])
        #         yield (cursor_style, self.text[cursor:cursor+1])
        #         pos = cursor + 1
        #     yield (txt_style, self.text[pos:])

    @property
    def is_wrapped(self):
        return False  # todo

class LineCache:
    def __init__(self, global_view: 'GlobalView'):
        self.annotations: list[AnnotationSet] = []
        self.global_view = global_view
        self.shared_styles: DictProxy[str, Any] = global_view.shared_state['styles']

        self.invalid_before = 0
        self.invalid_after = 0
        self.lines: list[Optional[SingleLine]] = []  # deque() ?

    def apply_update(self, update: dict) -> None:
        """Apply 'update' and return result (self+update)
        https://xi-editor.io/xi-editor/docs/frontend-protocol.html#update
        TODO: typeddict from https://xi-editor.io/xi-editor/docs/frontend-protocol.html#update <-- struct
        """
        self.annotations = update['annotations']

        index = 0
        new_lines: list[Optional[SingleLine]] = []
        new_invalid_before = 0
        new_invalid_after = 0

        for op in update['ops']:
            n = op['n']  # lines affected

            if op['op'] == 'copy':
                if index < self.invalid_before:
                    invalid = min(n, self.invalid_before - index)
                    new_invalid_before, new_invalid_after = self._add_invalid(new_lines, new_invalid_before, new_invalid_after, invalid)
                    n -= invalid
                    index += invalid
                number = op["ln"]
                if n > 0 and index < self.invalid_before + len(self.lines):
                    line = self.lines[index - self.invalid_before]
                    if line == None or line.is_wrapped:  # type: ignore
                        number += 1
                while n > 0 and index < self.invalid_before + len(self.lines):
                    line = self.lines[index - self.invalid_before]
                    if line and not line.is_wrapped:
                        line.ln = number
                        number += 1
                    new_invalid_before, new_invalid_after = self._add_line(new_lines, new_invalid_before, new_invalid_after, line)
                    n -= 1
                    index += 1
                new_invalid_before, new_invalid_after = self._add_invalid(new_lines, new_invalid_before, new_invalid_after, n)
                index += n
            elif op['op'] == 'skip':
                index += n
            elif op['op'] == 'invalidate':
                new_invalid_before, new_invalid_after = self._add_invalid(new_lines, new_invalid_before, new_invalid_after, n)
            elif op['op'] == 'ins':
                for json_line in op["lines"]:
                    line = SingleLine(**json_line)
                    new_invalid_before, new_invalid_after = self._add_line(new_lines, new_invalid_before, new_invalid_after, line)
            elif op['op'] == 'update':
                for json_line in op["lines"]:
                    if line := self.lines[index - self.invalid_before]:
                        for prop in json_line:
                            assert hasattr(line, prop), f'Line does not have {prop=} ({json_line=})'
                            setattr(line, prop, json_line[prop])
                    new_invalid_before, new_invalid_after = self._add_line(new_lines, new_invalid_before, new_invalid_after, line)
                    index += 1
            else:
                logging.warning(f'Lines not implemented: {op}({update})')

        # Save new state
        self.lines = new_lines
        self.invalid_after = new_invalid_after
        self.invalid_before = new_invalid_before

    def _add_line(self, lines: list[Optional[SingleLine]], invalid_before: int, invalid_after: int, line: Optional[SingleLine]) -> Tuple[int, int]:
        if line is None:
            return self._add_invalid(lines, invalid_before, invalid_after, 1)

        lines.extend([None]*invalid_after)
        invalid_after = 0
        lines.append(line)
        return invalid_before, invalid_after

    def _add_invalid(self, lines: list[Optional[SingleLine]], invalid_before: int, invalid_after: int, n: int) -> Tuple[int, int]:
        if len(lines) == 0:
            invalid_before += n
        else:
            invalid_after += n
        return invalid_before, invalid_after

    @property
    def max_ln(self) -> int:
        """ Used to calculate the size of "line no" col """
        return max([l.ln for l in self.lines if l])

    @property
    def cursors(self):
        self.lines
        for line in self.lines:
            if line:
                for cursor in line.cursor:
                    yield (line.ln - 1, cursor)

    @property
    def has_selection(self):
        match self.annotations:
            case {'type': 'selection', 'ranges': [ranges]}:
                return any(r[0] != r[2] or r[1] != r[3] for r in ranges)
        return False
