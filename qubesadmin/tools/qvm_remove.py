#
# The Qubes OS Project, http://www.qubes-os.org
#
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

''' Remove domains from the system '''

import sys

import qubesadmin.exc
from qubesadmin.tools import QubesArgumentParser

parser = QubesArgumentParser(description=__doc__,
                             want_app=True,
                             vmname_nargs='+')
parser.add_argument("--force", "-f", action="store_true", dest="no_confirm",
    default=False, help="Do not prompt for confirmation")



def main(args=None, app=None):  # pylint: disable=missing-docstring
    args = parser.parse_args(args, app=app)
    go_ahead = ""
    if not args.no_confirm:
        print("This will completely remove the selected VM(s)...")
        for vm in args.domains:
            print(" ", vm.name)
        go_ahead = input("Are you sure? [y/N] ").upper()

    if args.no_confirm or go_ahead == "Y":
        for vm in args.domains:
            try:
                del args.app.domains[vm.name]
            except qubesadmin.exc.QubesException as e:
                parser.error_runtime(e)
        retcode = 0
    else:
        print("Remove cancelled.")
        retcode = 1
    return retcode



if __name__ == '__main__':
    sys.exit(main())
