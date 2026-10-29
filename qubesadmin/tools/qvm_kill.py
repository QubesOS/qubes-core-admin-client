# encoding=utf-8
#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015  Wojtek Porczyk <woju@invisiblethingslab.com>
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

'''Immediately terminate a qube without a graceful shutdown sequence.'''


import asyncio
import sys

import qubesadmin.exc
import qubesadmin.tools
import qubesadmin.tools.qvm_shutdown

parser = qubesadmin.tools.QubesArgumentParser(
    description='immediately terminate a qube without a graceful shutdown'
                ' sequence',
    vmname_nargs='+')


async def run_async(args=None, app=None):
    # pylint: disable=missing-docstring
    args = parser.parse_args(args, app=app)
    failed = await qubesadmin.utils.kill(domains=args.domains)
    if not failed:
        return 0
    for qube, exc in failed.items():
        parser.print_error("Failed to kill: {}: {}".format(qube, exc))
    raise SystemExit(len(failed))


def main(args=None, app=None):
    # pylint: disable=missing-docstring
    return asyncio.run(run_async(args=args, app=app))


if __name__ == '__main__':
    sys.exit(main())
