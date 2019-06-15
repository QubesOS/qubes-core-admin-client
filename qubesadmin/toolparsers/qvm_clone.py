# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
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

'''Parser for qvm-clone'''

from qubesadmin.toolparsers import QubesArgumentParser

def get_parser():
    '''Return argument parser for qvm-clone'''
    parser = QubesArgumentParser(description=__doc__, vmname_nargs=1)
    parser.add_argument('new_name',
                        metavar='NEWVM',
                        action='store',
                        help='name of the domain to create')

    parser.add_argument('--class', '-C', dest='cls',
        default=None,
        help='specify the class of the new domain (default: same as source)')

    parser.add_argument('--ignore-errors', action='store_true',
        default=False,
        help='log errors encountered during setting metadata'
             'but continue clone operation')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-P',
                        metavar='POOL',
                        dest='one_pool',
                        default='',
                        help='pool to use for the new domain')

    group.add_argument('-p',
                        '--pool',
                        action='append',
                        metavar='VOLUME=POOL',
                        help='specify the pool to use for the specific volume')
    return parser
