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
import qubesadmin.tools
import qubesadmin.tools.qvm_pool_legacy


def list_drivers(args):
    ''' Lists all drivers with their options '''
    result = [('DRIVER', 'OPTIONS')]
    for driver in sorted(args.app.pool_drivers):
        params = args.app.pool_driver_parameters(driver)
        driver_options = ', '.join(params)
        result += [(driver, driver_options)]
    qubesadmin.tools.print_table(result)


def list_pools(args):
    ''' Lists all available pools '''
    result = [('NAME', 'DRIVER')]
    for pool in args.app.pools.values():
        result += [(pool.name, pool.driver)]
    qubesadmin.tools.print_table(result)


def info_pools(args):
    ''' Prints info about the specified pools '''
    data = []
    for idx, pool in enumerate(args.pools):
        data += [("", "")] if idx > 0 else []
        data += [("name", pool.name)]
        data += [i for i in sorted(pool.config.items()) if i[0] != 'name']
    qubesadmin.tools.print_table(data)


def add_pool(args):
    ''' Adds a new pool '''
    options = dict(opt.split('=', 1) for opt in args.option or [])
    try:
        args.app.add_pool(name=args.pool_name, driver=args.driver, **options)
    except qubesadmin.exc.QubesException as e:
        raise qubesadmin.exc.QubesException('Failed to add pool %s: %s\n',
                                            args.pool_name, str(e))


def remove_pools(args):
    ''' Removes the specified pools '''
    errors = []
    for pool_name in args.pool_names:
        try:
            args.app.remove_pool(pool_name)
        except KeyError:
            errors.append('No such pool %s\n' % pool_name)
        except qubesadmin.exc.QubesException as e:
            errors.append(
                'Failed to remove pool %s: %s\n' % (pool_name, str(e)))
    if errors:
        raise qubesadmin.exc.QubesException('\n'.join(errors))


def set_pool(args):
    ''' Modifies driver options for a pool '''
    options = (opt.split('=', 1) for opt in args.option or [])
    pool = args.app.pools[args.pool_name]
    errors = []
    for opt, value in options:
        if not hasattr(type(pool), opt):
            errors.append(
                'Setting option %s is not supported for pool %s\n' % (
                    opt, pool.name))
        try:
            setattr(pool, opt, value)
        except qubesadmin.exc.QubesException as e:
            errors.append('Failed to set option %s for pool %s: %s\n' % (
                opt, pool.name, str(e)))
    if errors:
        raise qubesadmin.exc.QubesException('\n'.join(errors))


def init_list_parser(sub_parsers):
    ''' Adds 'list' action related options '''
    l_parser = sub_parsers.add_parser(
        'list', aliases=('l', 'ls'), help='List all available pools')
    l_parser.set_defaults(func=list_pools)


def init_info_parser(sub_parsers):
    ''' Adds 'info' action related options '''
    i_parser = sub_parsers.add_parser(
        'info', aliases=('i',), help='Print info about the specified pools')
    i_parser.add_argument(metavar='POOL_NAME', dest='pools',
                          action=qubesadmin.tools.PoolsAction)
    i_parser.set_defaults(func=info_pools)


def init_add_parser(sub_parsers):
    ''' Adds 'add' action related options '''
    a_parser = sub_parsers.add_parser(
        'add', aliases=('a',), help='Add a new pool')
    a_parser.add_argument(metavar='POOL_NAME', dest='pool_name')
    a_parser.add_argument(metavar='DRIVER', dest='driver')
    a_parser.add_argument('--option', '-o', action='append',
                          help="Set option for the driver in opt=value form"
                               "(can be specified multiple times) --"
                               "see `man qvm-pool` for details")
    a_parser.set_defaults(func=add_pool)


def init_remove_parser(sub_parsers):
    ''' Adds 'remove' action related options '''
    r_parser = sub_parsers.add_parser(
        'remove', aliases=('r', 'rm'), help='Remove the specified pools')
    r_parser.add_argument(metavar='POOL_NAME', dest='pool_names', nargs='+')
    r_parser.set_defaults(func=remove_pools)


def init_set_parser(sub_parsers):
    ''' Adds 'set' action related options '''
    s_parser = sub_parsers.add_parser(
        'set', aliases=('s',), help='Modify driver options for a pool')
    s_parser.add_argument(metavar='POOL_NAME', dest='pool_name')
    s_parser.add_argument('--option', '-o', action='append',
                          help="Set option for the driver in opt=value form"
                               "(can be specified multiple times) --"
                               "see `man qvm-pool` for details")
    s_parser.set_defaults(func=set_pool)


def get_parser():
    ''' Creates :py:class:`argparse.ArgumentParser` suitable for
        :program:`qvm-pool`.
    '''
    parser = qubesadmin.tools.QubesArgumentParser(description=__doc__,
                                                  want_app=True)
    parser.register('action', 'parsers',
                    qubesadmin.tools.AliasedSubParsersAction)

    sub_parsers = parser.add_subparsers(
        title='commands', dest='command',
        description="For more information see qvm-pool <command> -h")

    d_parser = sub_parsers.add_parser(
        'drivers', aliases=('d',), help='List all drivers with their options')
    d_parser.set_defaults(func=list_drivers)

    init_list_parser(sub_parsers)
    init_info_parser(sub_parsers)
    init_add_parser(sub_parsers)
    init_remove_parser(sub_parsers)
    init_set_parser(sub_parsers)

    # default action
    parser.set_defaults(func=list_pools)

    return parser


def uses_legacy_options(args, app):
    ''' Checks if legacy options and used, and invokes the legacy tool '''
    parser = argparse.ArgumentParser(description=__doc__,
                                     usage=argparse.SUPPRESS)

    parser.add_argument('-a', '--add',
                        dest='has_legacy_options', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('-i', '--info',
                        dest='has_legacy_options', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('-l', '--list',
                        dest='has_legacy_options', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('-r', '--remove',
                        dest='has_legacy_options', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('-s', '--set',
                        dest='has_legacy_options', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--help-drivers',
                        dest='has_legacy_options', action='store_true',
                        help=argparse.SUPPRESS)

    parsed_args, _ = parser.parse_known_args(args)
    if parsed_args.has_legacy_options:
        qubesadmin.tools.qvm_pool_legacy.main(args, app)
        return True
    return False


def main(args=None, app=None):
    '''Main routine of :program:`qvm-pool`.'''
    if uses_legacy_options(args, app):
        return 0

    parser = get_parser()
    args = parser.parse_args(args, app=app)

    try:
        args.func(args)
    except qubesadmin.exc.QubesException as e:
        parser.error_runtime(str(e))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
