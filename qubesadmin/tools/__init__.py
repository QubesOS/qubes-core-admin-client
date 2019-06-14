# encoding=utf-8
#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015  Wojtek Porczyk <woju@invisiblethingslab.com>
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

'''Qubes' command line tools
'''

from __future__ import print_function

import subprocess
import sys

from qubesadmin.toolparsers import (VM_ALL, QubesAction, PropertyAction,
    SinglePropertyAction, VmNameAction, RunningVmNameAction, VolumeAction,
    VMVolumeAction, PoolsAction, QubesArgumentParser, SubParsersHelpAction,
    AliasedSubParsersAction, get_parser_for_command, VmNameGroup)

def print_table(table, stream=None):
    ''' Uses the unix column command to print pretty table.

        :param str text: list of lists/sets
    '''
    unit_separator = chr(31)
    cmd = ['column', '-t', '-s', unit_separator]
    text_table = '\n'.join([unit_separator.join(row) for row in table])
    text_table += '\n'

    if stream is None:
        stream = sys.stdout

    # for tests...
    if stream != sys.__stdout__:
        p = subprocess.Popen(cmd + ['-c', '80'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)
        p.stdin.write(text_table.encode())
        (out, _) = p.communicate()
        stream.write(str(out.decode()))
    else:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        p.communicate(text_table.encode())
