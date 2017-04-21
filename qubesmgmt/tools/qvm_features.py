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

'''qvm-features - Manage domain's features'''

from __future__ import print_function

import sys

import qubesmgmt
import qubesmgmt.tools

parser = qubesmgmt.tools.QubesArgumentParser(
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


def main(args=None, app=None):
    '''Main routine of :program:`qvm-features`.

    :param list args: Optional arguments to override those delivered from \
        command line.
    '''

    args = parser.parse_args(args, app=app)
    vm = args.domains[0]

    if args.feature is None:
        if args.delete:
            parser.error('--unset requires a feature')

        features = [(feat, vm.features[feat]) for feat in vm.features]
        qubesmgmt.tools.print_table(features)

    elif args.delete:
        if args.value is not None:
            parser.error('cannot both set and unset a value')
        try:
            del vm.features[args.feature]
        except KeyError:
            pass

    elif args.value is None:
        try:
            print(vm.features[args.feature])
            return 0
        except KeyError:
            return 1
    else:
        vm.features[args.feature] = args.value

    return 0


if __name__ == '__main__':
    sys.exit(main())
