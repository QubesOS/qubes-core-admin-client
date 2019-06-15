#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010-2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015       Wojtek Porczyk <woju@invisiblethingslab.com>
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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

'''Parser for qvm-create'''

from __future__ import print_function

import argparse

import qubesadmin.toolparsers


def get_parser():
    '''Return argument parser for qvm-create'''
    parser = qubesadmin.toolparsers.QubesArgumentParser()

    parser.add_argument('--class', '-C', dest='cls',
        default='AppVM',
        help='specify the class of the new domain (default: %(default)s)')

    parser.add_argument('--standalone',
        action="store_true",
        help=' shortcut for --class StandaloneVM')

    parser.add_argument('--disp',
        action="store_true",
        help='alias for --class DispVM --label red')

    parser.add_argument('--property', '--prop',
        action=qubesadmin.toolparsers.PropertyAction,
        help='set domain\'s property, like "internal", "memory" or "vcpus"')

    parser.add_argument('--pool', '-p',
                        action='append',
                        metavar='VOLUME_NAME=POOL_NAME',
                        help='specify the pool to use for a volume')

    parser.add_argument('-P',
                        metavar='POOL_NAME',
                        dest='one_pool',
                        default='',
                        help='change all volume pools to specified pool')

    parser.add_argument('--template', '-t',
        action=qubesadmin.toolparsers.SinglePropertyAction,
        help='specify the TemplateVM to use')

    parser.add_argument('--label', '-l',
        action=qubesadmin.toolparsers.SinglePropertyAction,
        help='specify the label to use for the new domain'
            ' (e.g. red, yellow, green, ...)')

    parser.add_argument('--help-classes',
        action='store_true',
        help='List available classes and exit')

    parser_root = parser.add_mutually_exclusive_group()
    parser_root.add_argument('--root-copy-from', '-r', metavar='FILENAME',
        help='use provided root.img instead of default/empty one'
            ' (file will be COPIED)')
    parser_root.add_argument('--root-move-from', '-R', metavar='FILENAME',
        help='use provided root.img instead of default/empty one'
            ' (file will be MOVED)')

    # silently ignored
    parser_root.add_argument('--no-root',
        action='store_true', default=False,
        help=argparse.SUPPRESS)

    parser.add_argument('name', metavar='VMNAME',
        action=qubesadmin.toolparsers.SinglePropertyAction,
        nargs='?',
        help='name of the domain to create')

    return parser
