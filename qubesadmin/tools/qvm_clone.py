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

''' Clone a domain '''

import sys

import qubesadmin.exc
from qubesadmin.toolparsers.qvm_clone import get_parser


def main(args=None, app=None):
    ''' Clones an existing VM by copying all its disk files '''
    parser = get_parser()
    args = parser.parse_args(args, app=app)
    app = args.app
    src_vm = args.domains[0]
    new_name = args.new_name

    pool = None
    pools = {}
    if args.one_pool:
        pool = args.one_pool
    elif hasattr(args, 'pool') and args.pool:
        for pool_vol in args.pool:
            try:
                volume_name, pool_name = pool_vol.split('=')
                pools[volume_name] = pool_name
            except ValueError:
                parser.error(
                    'Pool argument must be of form: -P volume_name=pool_name')

    try:
        app.clone_vm(src_vm, new_name, new_cls=args.cls, pool=pool, pools=pools,
                     ignore_errors=args.ignore_errors)
    except qubesadmin.exc.QubesException as e:
        parser.error_runtime(e)

if __name__ == '__main__':
    sys.exit(main())
