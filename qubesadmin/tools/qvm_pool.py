# pylint: disable=too-few-public-methods

#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
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

'''Manages Qubes pools and their options'''

from __future__ import print_function

import argparse
import sys

import qubesadmin
import qubesadmin.exc
import qubesadmin.storage
import qubesadmin.tools


class _Info(qubesadmin.tools.PoolsAction):
    ''' Action for argument parser that displays pool info and exits. '''

    def __init__(self, option_strings, help='print pool info and exit',
                 **kwargs):
        # pylint: disable=redefined-builtin
        super(_Info, self).__init__(option_strings, help=help, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, 'command', 'info')
        super(_Info, self).__call__(parser, namespace, values, option_string)


def pool_info(pool):
    ''' Prints out pool name and config '''
    data = [("name", pool.name)]
    data += [i for i in sorted(pool.config.items()) if i[0] != 'name']
    qubesadmin.tools.print_table(data)


def list_pools(app):
    ''' Prints out all known pools and their drivers '''
    result = [('NAME', 'DRIVER')]
    for pool in app.pools.values():
        result += [(pool.name, pool.driver)]
    qubesadmin.tools.print_table(result)


class _Remove(argparse.Action):
    ''' Action for argument parser that removes a pool '''

    def __init__(self, option_strings, dest=None, default=None, metavar=None):
        super(_Remove, self).__init__(option_strings=option_strings,
                                      dest=dest,
                                      metavar=metavar,
                                      default=default,
                                      help='remove pool')

    def __call__(self, parser, namespace, name, option_string=None):
        setattr(namespace, 'command', 'remove')
        setattr(namespace, 'name', name)


class _Add(argparse.Action):
    ''' Action for argument parser that adds a pool. '''

    def __init__(self, option_strings, dest=None, default=None, metavar=None):
        super(_Add, self).__init__(option_strings=option_strings,
                                   dest=dest,
                                   metavar=metavar,
                                   default=default,
                                   nargs=2,
                                   help='add pool')

    def __call__(self, parser, namespace, values, option_string=None):
        name, driver = values
        setattr(namespace, 'command', 'add')
        setattr(namespace, 'name', name)
        setattr(namespace, 'driver', driver)


class _Options(argparse.Action):
    ''' Action for argument parser that parsers options. '''

    def __init__(self, option_strings, dest, default, metavar='options'):
        super(_Options, self).__init__(
            option_strings=option_strings,
            dest=dest,
            metavar=metavar,
            default=default,
            help='comma-separated list of driver options')

    def __call__(self, parser, namespace, options, option_string=None):
        setattr(namespace, 'options',
                dict([option.split('=', 1) for option in options.split(',')]))


def get_parser():
    ''' Parses the provided args '''
    parser = qubesadmin.tools.QubesArgumentParser(description=__doc__)
    parser.add_argument('-o', action=_Options, dest='options', default={})
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-l',
                       '--list',
                       dest='command',
                       const='list',
                       action='store_const',
                       help='list all pools and exit (default action)')
    group.add_argument('-i', '--info', metavar='POOLNAME', dest='pools',
                       action=_Info, default=[])
    group.add_argument('-a',
                       '--add',
                       action=_Add,
                       dest='command',
                       metavar=('NAME', 'DRIVER'))
    group.add_argument('-r', '--remove', metavar='NAME', action=_Remove)
    group.add_argument('--help-drivers',
                       dest='command',
                       const='list-drivers',
                       action='store_const',
                       help='list all drivers with their options and exit')
    return parser


def main(args=None, app=None):
    '''Main routine of :program:`qvm-pools`.

    :param list args: Optional arguments to override those delivered from \
        command line.
    '''
    parser = get_parser()
    try:
        args = parser.parse_args(args, app=app)
    except qubesadmin.exc.QubesException as e:
        parser.print_error(str(e))
        return 1

    if args.command is None or args.command == 'list':
        list_pools(args.app)
    elif args.command == 'list-drivers':
        result = [('DRIVER', 'OPTIONS')]
        for driver in sorted(args.app.pool_drivers):
            params = args.app.pool_driver_parameters(driver)
            driver_options = ', '.join(params)
            result += [(driver, driver_options)]
        qubesadmin.tools.print_table(result)
    elif args.command == 'add':
        try:
            args.app.add_pool(name=args.name, driver=args.driver,
                **args.options)
        except qubesadmin.exc.QubesException as e:
            parser.error('failed to add pool %s: %s\n' % (args.name, str(e)))
    elif args.command == 'remove':
        try:
            args.app.remove_pool(args.name)
        except KeyError:
            parser.print_error('no such pool %s\n' % args.name)
    elif args.command == 'info':
        for pool in args.pools:
            pool_info(pool)
    return 0


if __name__ == '__main__':
    sys.exit(main())
