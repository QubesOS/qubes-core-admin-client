# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
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

''' qvm-run parser'''
import os
import sys

import qubesadmin.toolparsers


def get_parser():
    parser = qubesadmin.toolparsers.QubesArgumentParser()

    parser.add_argument('--user', '-u', metavar='USER',
        help='run command in a qube as USER (available only from dom0)')

    parser.add_argument('--autostart', '--auto', '-a',
        action='store_true', default=True,
        help='option ignored, this is default')

    parser.add_argument('--no-autostart', '--no-auto', '-n',
        action='store_false', dest='autostart',
        help='do not autostart qube')

    parser.add_argument('--pass-io', '-p',
        action='store_true', dest='passio', default=False,
        help='pass stdio from remote program')

    parser.add_argument('--localcmd', metavar='COMMAND',
        help='with --pass-io, pass stdio to the given program')

    parser.add_argument('--gui',
        action='store_true', default=True,
        help='run the command with GUI (default on)')

    parser.add_argument('--no-gui', '--nogui',
        action='store_false', dest='gui',
        help='run the command without GUI')

    parser.add_argument('--colour-output', '--color-output', metavar='COLOUR',
        action='store', dest='color_output', default=None,
        help='mark the qube output with given ANSI colour (ie. "31" for red)')

    parser.add_argument('--colour-stderr', '--color-stderr', metavar='COLOUR',
        action='store', dest='color_stderr', default=None,
        help='mark the qube stderr with given ANSI colour (ie. "31" for red)')

    parser.add_argument('--no-colour-output', '--no-color-output',
        action='store_false', dest='color_output',
        help='disable colouring the stdio')

    parser.add_argument('--no-colour-stderr', '--no-color-stderr',
        action='store_false', dest='color_stderr',
        help='disable colouring the stderr')

    parser.add_argument('--filter-escape-chars',
        action='store_true', dest='filter_esc',
        default=os.isatty(sys.stdout.fileno()),
        help='filter terminal escape sequences (default if output is terminal)')

    parser.add_argument('--no-filter-escape-chars',
        action='store_false', dest='filter_esc',
        help='do not filter terminal escape sequences; DANGEROUS when output is a'
            ' terminal emulator')

    parser.add_argument('--service',
        action='store_true', dest='service',
        help='run a qrexec service (named by COMMAND) instead of shell command')

    target_parser = parser.add_mutually_exclusive_group()

    target_parser.add_argument('--dispvm', action='store', nargs='?',
        const=True, metavar='BASE_APPVM',
        help='start a service in new Disposable VM; '
             'optionally specify base AppVM for DispVM')
    target_parser.add_argument('VMNAME',
        nargs='?',
        action=qubesadmin.toolparsers.VmNameAction)

    # add those manually instead of vmname_args, because of mutually exclusive
    # group with --dispvm; parsing is still handled by QubesArgumentParser
    target_parser.add_argument('--all', action='store_true', dest='all_domains',
        help='run command on all running qubes')

    parser.add_argument('--exclude', action='append', default=[],
        help='exclude the qube from --all')

    parser.add_argument('cmd', metavar='COMMAND',
        help='command or service to run')

    return parser
