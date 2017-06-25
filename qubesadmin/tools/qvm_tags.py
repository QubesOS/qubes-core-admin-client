#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2010-2016  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2016       Wojtek Porczyk <woju@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

'''qvm-features - Manage domain's tags'''

from __future__ import print_function

import sys

import qubesadmin
import qubesadmin.tools

def mode_query(args):
    '''Query/list tags'''
    if not hasattr(args, 'tag') or args.tag is None:
        # list
        tags = list(sorted(args.domains[0].tags))
        if tags:
            print('\n'.join(tags))
    else:
        # real query
        if args.tag not in args.domains[0].tags:
            return 1
        print(args.tag)
    return 0


def mode_add(args):
    '''Add tag'''
    for tag in args.tag:
        args.domains[0].tags.add(tag)
    return 0


def mode_del(args):
    '''Delete tag'''
    for tag in args.tag:
        args.domains[0].tags.discard(tag)
    return 0


def get_parser():
    ''' Return qvm-tags tool command line parser '''
    parser = qubesadmin.tools.QubesArgumentParser(
        vmname_nargs=1,
        description='manage domain\'s tags')
    parser.register('action', 'parsers',
        qubesadmin.tools.AliasedSubParsersAction)

    sub_parsers = parser.add_subparsers(
        title='commands',
        description="For more information see qvm-tags command -h",
        dest='command')

    list_parser = sub_parsers.add_parser('list', aliases=('ls', 'l'),
        help='list tags')
    list_parser.add_argument('tag', nargs='?',
        action='store', default=None)
    list_parser.set_defaults(func=mode_query)

    add_parser = sub_parsers.add_parser('add', aliases=('a', 'set'),
        help='add tag')
    add_parser.add_argument('tag', nargs='+',
        action='store')
    add_parser.set_defaults(func=mode_add)

    del_parser = sub_parsers.add_parser('del', aliases=('d', 'unset', 'u'),
        help='add tag')
    del_parser.add_argument('tag', nargs=1,
        action='store')
    del_parser.set_defaults(func=mode_del)

    parser.set_defaults(func=mode_query)
    return parser


def main(args=None, app=None):
    '''Main routine of :program:`qvm-tags`.

    :param list args: Optional arguments to override those delivered from \
        command line.
    '''

    parser = get_parser()
    args = parser.parse_args(args, app=app)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
