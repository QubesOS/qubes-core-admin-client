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

'''qvm-service - Manage domain's services'''

from __future__ import print_function

import argparse
import sys

import qubesadmin
import qubesadmin.exc
import qubesadmin.tools

parser = qubesadmin.tools.QubesArgumentParser(
    vmname_nargs=1,
    argument_default=argparse.SUPPRESS,
    description='manage domain\'s services')

parser.add_argument('service', metavar='SERVICE',
    action='store', nargs='?',
    help='name of the feature')

parser.add_argument('value', metavar='VALUE',
    action='store', nargs='?',
    help='new value of the service (on/off)')

parser.add_argument('--unset', '--default', '--delete', '-D',
    dest='delete', default=False,
    action='store_true',
    help='unset service (default to VM preference)')

parser.add_argument('--list', '-l',
    dest='list',
    action='store_true',
    help='list services (default action)')

parser.add_argument('--enable', '-e',
    dest='value',
    action='store_const', const='1',
    help='enable service (same as setting "on" value)')

parser.add_argument('--disable', '-d',
    dest='value',
    action='store_const', const='0',
    help='disable service (same as setting "off" value)')

def parse_bool(value):
    '''Convert string value to bool according to well known representations

    It accepts (case-insensitive) ``'0'``, ``'no'`` and ``false`` as
        :py:obj:`False` and ``'1'``, ``'yes'`` and ``'true'`` as
        :py:obj:`True`.
    '''
    if isinstance(value, str):
        lcvalue = value.lower()
        if lcvalue in ('0', 'no', 'false', 'off'):
            return False
        if lcvalue in ('1', 'yes', 'true', 'on'):
            return True
        raise qubesadmin.exc.QubesValueError(
            'Invalid literal for boolean value: {!r}'.format(value))

    return bool(value)


def main(args=None, app=None):
    '''Main routine of :program:`qvm-features`.

    :param list args: Optional arguments to override those delivered from \
        command line.
    '''

    args = parser.parse_args(args, app=app)
    vm = args.domains[0]

    if not hasattr(args, 'service'):
        if args.delete:
            parser.error('--unset requires a feature')

        services = [(feat[len('service.'):],
            'on' if vm.features[feat] else 'off') for feat in
            vm.features if feat.startswith('service.')]
        qubesadmin.tools.print_table(services)

    elif args.delete:
        if hasattr(args, 'value'):
            parser.error('cannot both set and unset a value')
        try:
            del vm.features['service.' + args.service]
        except KeyError:
            pass
        except qubesadmin.exc.QubesException as err:
            parser.error_runtime(str(err))

    elif hasattr(args, 'value'):
        try:
            vm.features['service.' + args.service] = parse_bool(args.value)
        except qubesadmin.exc.QubesException as err:
            parser.error_runtime(str(err))

    else:
        try:
            print('on' if vm.features['service.' + args.service] else 'off')
            return 0
        except KeyError:
            return 1
        except qubesadmin.exc.QubesException as err:
            parser.error_runtime(str(err))

    return 0


if __name__ == '__main__':
    sys.exit(main())
