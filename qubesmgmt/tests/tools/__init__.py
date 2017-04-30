# encoding=utf-8
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


import io
import sys


class StdoutBuffer(object):
    def __init__(self):
        self.orig_stdout = None
        if sys.version_info[0] >= 3:
            self.stdout = io.StringIO()
        else:
            self.stdout = io.BytesIO()

    def __enter__(self):
        self.orig_stdout = sys.stdout
        sys.stdout = self.stdout
        return self.stdout

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.orig_stdout
        return False


class StderrBuffer(object):
    def __init__(self):
        self.orig_stderr = None
        if sys.version_info[0] >= 3:
            self.stderr = io.StringIO()
        else:
            self.stderr = io.BytesIO()

    def __enter__(self):
        self.orig_stderr = sys.stderr
        sys.stderr = self.stderr
        return self.stderr

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr = self.orig_stderr
        return False
