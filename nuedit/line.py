from __future__ import annotations
import logging
from functools import partial
# from collections import deque

# from prompt_toolkit import ANSI('\x1b[31mhello \x1b[32mworld')
from prompt_toolkit.formatted_text import FormattedText  #, HTML('<u>underline</u>')
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType

from collections import namedtuple
FormattedLetter = namedtuple('FormattedLetter', ['style', 'letter', 'mouse_handler'])


def add_style(inst: FormattedLetter, style: str) -> FormattedLetter:
    return inst._replace(style=" ".join([inst.style, style]))


ClickInfo = namedtuple('ClickInfo', ['xy', 'count'])
last_click = ClickInfo((-1, -1), 0)


def mouse_handler(sview, xy: tuple, mouse_event: MouseEvent) -> None:
    global last_click
    if not sview.global_view.app.layout.has_focus(sview):
        sview.global_view.set_focus(sview.view_id)

    rpc_channel = sview.global_view.rpc_channel
    if mouse_event.event_type == MouseEventType.MOUSE_DOWN:
        if last_click.xy != xy:
            rpc_channel.edit('gesture', {
                'col': xy[0],
                'line': xy[1],
                'ty': {'select': {'granularity': 'point', 'multi': False}}
            }, sview.view_id)
    elif mouse_event.event_type == MouseEventType.MOUSE_UP:
        if last_click.xy == xy:
            if last_click.count == 1:
                rpc_channel.edit('gesture', {
                    'col': xy[0],
                    'line': xy[1],
                    'ty': {'select': {'granularity': 'word', 'multi': False}}
                }, sview.view_id)
            elif last_click.count == 2:
                rpc_channel.edit('gesture', {
                    'col': xy[0],
                    'line': xy[1],
                    'ty': {'select': {'granularity': 'line', 'multi': False}}
                }, sview.view_id)
            last_click = ClickInfo(last_click.xy, (last_click.count + 1) % 3)
        else:
            rpc_channel.edit('gesture', {
                'col': xy[0],
                'line': xy[1],
                'ty': {'select_extend': {'granularity': 'point', 'multi': False}}
            }, sview.view_id)
            last_click = ClickInfo(xy, 1)
    elif mouse_event.event_type == MouseEventType.SCROLL_UP:
        pass
    elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
        pass


class Line:
    def __init__(self, text='', ln=' ', valid=False, **kwargs):
        # newline = shared_settings['settings']['line_ending']
        self.text = text[:-1] + ' \n'  # add "secret last space" (when cursor in last line position)
        self.ln = ln
        self.valid = valid
        self.cursor = kwargs.get('cursor', [])
        self.styles = kwargs.get('styles', [])
        assert len(self.styles) % 3 == 0, "Styles should be a multiple of 3: {}".format(self)
        for k in kwargs.keys():
            assert hasattr(self, k), 'Unknown line property: {}'.format(k)

    def get_formatted(self, annotations: list, shared_styles: dict, sview):
        output = [
            FormattedLetter("", char, partial(mouse_handler, sview, (col+1, self.ln-1)))
            for col, char in enumerate(self.text)]

        # Add style
        n_styles = len(self.styles)
        last_end = 0
        for i in range(n_styles // 3):
            start_idx = self.styles[i] + last_end
            style_len = self.styles[i + 1]
            last_end = start_idx + style_len
            style_id = self.styles[i + 2]
            for j in range(start_idx, style_len):
                output[j] = add_style(output[j], shared_styles[style_id])

        # Add annotation
        for annotation in annotations:
            assert len(annotation['ranges']) == annotation['n'], "Bad annotation: {}".format(annotation)
            style = shared_styles[annotation['type']]

            for (start_line, start_col, end_line, end_col) in annotation['ranges']:

                # self.ln is 1 indexed:
                if start_line <= self.ln - 1 <= end_line:
                    #logging.debug("self.ln-1={}, start_line={}, start_col={}, end_line={}, end_col={}".format(self.ln-1, start_line, start_col, end_line, end_col))
                    start_idx = start_col if start_line == self.ln - 1 else 0
                    end_idx   = end_col   if end_line   == self.ln - 1 else len(output)
                    for i in range(start_idx, end_idx):
                        output[i] = add_style(output[i], style)

        # Add cursors
        for cursor in self.cursor:
            output[cursor] = add_style(
                output[cursor], shared_styles['cursor']
            )

        return output


class Lines(list):
    def __init__(self, shared_styles = {}, *args):
        super(Lines, self).__init__(*args)
        self.annotations = []
        self.shared_styles = shared_styles
        # TODO: speedup using deque?

    def apply(self, update) -> Lines:
        """ Apply 'update' and return result (self+update) """
        new_lines = Lines(shared_styles=self.shared_styles)
        new_lines.annotations = update['annotations']

        old_idx = 0
        for op in update['ops']:
            n = op['n']  # lines affected

            if op['op'] == 'copy':
                assert len(self[old_idx : old_idx + n]) == n, '{}[{} : {}+{}] != {}'.format(self, old_idx, old_idx, n, n)
                #new_lines = new_lines + self[old_idx : old_idx + n]
                for i in range(old_idx, old_idx + n):
                    new_lines.append(self[i])
                old_idx += n

            elif op['op'] == 'skip':
                old_idx += n

            elif op['op'] == 'invalidate':
                # TODO: logic below is "the correct way", but very slow for big files
                for _ in range(n):
                    new_lines.append(Line(valid=False))

            elif op['op'] == 'ins':
                assert len(op['lines']) == n
                for line in op['lines']:
                    new_lines.append(Line(**line, valid=True))

            elif op['op'] == 'update':
                assert len(op['lines']) == n
                old_idx += n
                logging.warning('Lines not currently used: update({})'.format(update))
                exit(0)  # Not currently used

            else:
                logging.warning('Lines not implemented: {}({})'.format(op, update))
                exit(0)

        assert type(new_lines) == Lines
        return new_lines

    @property
    def cursors(self):
        for line in filter(lambda l: l.valid, self):
            for cursor in line.cursor:
                yield (line.ln - 1, cursor)

    @property
    def has_selection(self):
        for ann in filter(lambda a: a['type'] == 'selection', self.annotations):
            for r in ann['ranges']:
                # "empty" ranges are used to mark cursors, check for non-empty ranges:
                if r[0] != r[2] or r[1] != r[3]:
                    return True
        return False

    def get_formatted(self, sview):
        output = []  # https://python-prompt-toolkit.readthedocs.io/en/master/pages/printing_text.html#style-text-tuples
        line_no = ""
        len_of_lineno_col = 0
        for line in filter(lambda l: l.valid, self):  # and line.ln >= topline
            output += line.get_formatted(self.annotations, self.shared_styles, sview)
            line_no += str(line.ln) + '\n'
            len_of_lineno_col = line.ln

        return FormattedText(output), line_no, len(str(len_of_lineno_col))
