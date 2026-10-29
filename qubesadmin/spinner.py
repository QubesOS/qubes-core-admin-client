#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2017  Wojtek Porczyk <woju@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#

'''Qubes CLI spinner

A novice asked the master: “In the east there is a great tree-structure that
men call 'Corporate Headquarters'. It is bloated out of shape with vice
presidents and accountants. It issues a multitude of memos, each saying 'Go,
Hence!' or 'Go, Hither!' and nobody knows what is meant. Every year new names
are put onto the branches, but all to no avail. How can such an unnatural
entity be?"

The master replied: “You perceive this immense structure and are disturbed that
it has no rational purpose. Can you not take amusement from its endless
gyrations? Do you not enjoy the untroubled ease of programming beneath its
sheltering branches? Why are you bothered by its uselessness?”

(Geoffrey James, “The Tao of Programming”, 7.1)
'''

import curses
import io
import itertools
import typing
from typing import IO

CHARSET: str = '-\\|/'
ENTERPRISE_CHARSET: str = CHARSET * 4 + '-._.-^' * 2

class AbstractSpinner:
    '''The base class for all Spinners

    :param stream: file-like object with ``.write()`` method
    :param str charset: the sequence of characters to display

    The spinner should be used as follows:
        1. exactly one call to :py:meth:`show()`
        2. zero or more calls to :py:meth:`update()`
        3. exactly one call to :py:meth:`hide()`
    '''
    def __init__(self, stream: IO, charset: str=CHARSET):
        self.stream = stream
        self.charset = itertools.cycle(charset)

    def show(self, prompt: str) -> None:
        '''Show the spinner, with a prompt

        :param str prompt: prompt, like "please wait"
        '''
        raise NotImplementedError()

    def hide(self) -> None:
        '''Hide the spinner and the prompt'''
        raise NotImplementedError()

    def update(self) -> None:
        '''Show next spinner character'''
        raise NotImplementedError()


class DummySpinner(AbstractSpinner):
    '''Dummy spinner, does not do anything'''
    def show(self, prompt: str) -> None:
        pass

    def hide(self) -> None:
        pass

    def update(self) -> None:
        pass


class QubesSpinner(AbstractSpinner):
    '''Basic spinner

    This spinner uses standard ASCII control characters'''
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hidelen = 0
        self.cub1 = '\b'

    def show(self, prompt: str) -> None:
        self.hidelen = len(prompt) + 2
        self.stream.write(f'{prompt} {next(self.charset)}')
        self.stream.flush()

    def hide(self) -> None:
        self.stream.write('\r' + ' ' * self.hidelen + '\r')
        self.stream.flush()

    def update(self) -> None:
        self.stream.write(self.cub1 + next(self.charset))
        self.stream.flush()


class QubesSpinnerEnterpriseEdition(QubesSpinner):
    '''Enterprise spinner

    This is tty- and terminfo-aware spinner. Recommended.
    '''
    def __init__(self, stream: IO, charset: str | None=None):
        # our Enterprise logic follows
        self.stream_isatty = stream.isatty()
        if charset is None:
            charset = ENTERPRISE_CHARSET if self.stream_isatty else '.'

        super().__init__(stream, charset)

        if self.stream_isatty:
            try:
                curses.setupterm()
                self.has_terminfo = True
                self.cub1 = typing.cast(bytes, curses.tigetstr('cub1')).decode()
            except (curses.error, io.UnsupportedOperation):
                # we are in very non-Enterprise environment
                self.has_terminfo = False
        else:
            self.cub1 = ''

    def hide(self) -> None:
        if self.stream_isatty:
            hideseq = '\r' + ' ' * self.hidelen + '\r'
            if self.has_terminfo:
                hideseq_l = typing.cast(
                    tuple[bytes, bytes],
                    (curses.tigetstr('cr'), curses.tigetstr('clr_eol')))
                if all(seq is not None for seq in hideseq_l):
                    hideseq = ''.join(seq.decode() for seq in hideseq_l)
        else:
            hideseq = '\n'

        self.stream.write(hideseq)
        self.stream.flush()
