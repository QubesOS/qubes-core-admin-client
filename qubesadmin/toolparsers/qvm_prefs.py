# encoding=utf-8
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010-2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015       Wojtek Porczyk <woju@invisiblethingslab.com>
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

''' Parser for qvm-prefs.'''

from __future__ import print_function

import qubesadmin.toolparsers


def get_parser(vmname_nargs=1):
    '''Return argument parser for generic property-related tool'''
    parser = qubesadmin.toolparsers.QubesArgumentParser(
        vmname_nargs=vmname_nargs)

    parser.add_argument('--help-properties',
        action='store_true',
        help='list all available properties with short descriptions and exit')

    parser.add_argument('--hide-default',
        action='store_true',
        help='Do not show properties that are set to the default value.')

    parser.add_argument('--get', '-g',
        action='store_true',
        help='Ignored; for compatibility with older scripts.')

    parser.add_argument('--set', '-s',
        action='store_true',
        help='Ignored; for compatibility with older scripts.')

    parser.add_argument('property', metavar='PROPERTY',
        nargs='?',
        help='name of the property to show or change')

    parser_value = parser.add_mutually_exclusive_group()

    parser_value.add_argument('value', metavar='VALUE',
        nargs='?',
        help='new value of the property')

    parser.add_argument('--default', '-D',
        dest='delete',
        action='store_true',
        help='reset property to its default value')

    return parser
