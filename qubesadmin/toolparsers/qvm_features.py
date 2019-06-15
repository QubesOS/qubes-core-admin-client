# coding=utf-8
#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2010-2016  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2016       Wojtek Porczyk <woju@invisiblethingslab.com>
# Copyright (C) 2017       Marek Marczykowski-Górecki
#                                           <marmarek@invisiblethingslab.com>
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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

'''Parser for qvm-features'''

from __future__ import print_function

import qubesadmin.toolparsers

def get_parser():
    '''Return argument parser for qvm-features'''
    parser = qubesadmin.toolparsers.QubesArgumentParser(
        vmname_nargs=1,
        description='manage domain\'s features')

    parser.add_argument('feature', metavar='FEATURE',
        action='store', nargs='?',
        help='name of the feature')

    parser.add_argument('value', metavar='VALUE',
        action='store', nargs='?',
        help='new value of the feature')

    parser.add_argument('--unset', '--default', '--delete', '-D',
        dest='delete',
        action='store_true',
        help='unset the feature')

    return parser
