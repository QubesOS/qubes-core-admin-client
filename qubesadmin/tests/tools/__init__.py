#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2015  Marek Marczykowski-Górecki
#                                       <marmarek@invisiblethingslab.com>
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
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

# pylint: disable=missing-docstring

import io
import sys

import asyncio


class StdoutBuffer:
    def __init__(self):
        self.orig_stdout = None
        self.stdout = io.StringIO()

    def __enter__(self):
        self.orig_stdout = sys.stdout
        sys.stdout = self.stdout
        return self.stdout

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.orig_stdout
        return False


class StderrBuffer:
    def __init__(self):
        self.orig_stderr = None
        self.stderr = io.StringIO()

    def __enter__(self):
        self.orig_stderr = sys.stderr
        sys.stderr = self.stderr
        return self.stderr

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr = self.orig_stderr
        return False

class MockEventsReader:
    def __init__(self, events, delay=0.05):
        self.events = events
        self.delay = delay
        self.current_event = None

    def at_eof(self):
        return not bool(self.events)

    async def readuntil(self, delim):
        if not self.current_event:
            if not self.events:
                raise asyncio.IncompleteReadError(b'', delim)
            await asyncio.sleep(self.delay)
            self.current_event = self.events.pop(0)
        data, rest = self.current_event.split(delim, 1)
        self.current_event = rest
        return data + delim

    def __call__(self, vm=None):
        return self, (lambda: None)
