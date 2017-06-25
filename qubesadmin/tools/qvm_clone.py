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

from qubesadmin.tools import QubesArgumentParser

parser = QubesArgumentParser(description=__doc__, vmname_nargs=1)
parser.add_argument('new_name',
                    metavar='NEWVM',
                    action='store',
                    help='name of the domain to create')

parser.add_argument('--class', '-C', dest='cls',
    default=None,
    help='specify the class of the new domain (default: same as source)')

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


def main(args=None, app=None):
    ''' Clones an existing VM by copying all its disk files '''
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

    app.clone_vm(src_vm, new_name, new_cls=args.cls, pool=pool, pools=pools)

if __name__ == '__main__':
    sys.exit(main())
