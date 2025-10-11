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

"""Remove domains from the system"""

import sys

import qubesadmin.exc
from qubesadmin.tools import QubesArgumentParser
import qubesadmin.utils

parser = QubesArgumentParser(description=__doc__, vmname_nargs="+")
parser.add_argument(
    "--force",
    "-f",
    action="store_true",
    dest="no_confirm",
    default=False,
    help="Do not prompt for confirmation",
)


def main(args=None, app=None):  # pylint: disable=missing-docstring
    args = parser.parse_args(args, app=app)
    go_ahead = ""

    if "dom0" in args.domains:
        print("Domain 'dom0' cannot be removed.", file=sys.stderr)
        return 1

    if args.all_domains and not (args.no_confirm or args.exclude):
        print(
            "WARNING!!! Removing all domains may leave your system in an "
            "unrecoverable state!",
            file=sys.stderr,
        )
        go_ahead_remove_all = input("Are you certain? [N/IKNOWWHATIAMDOING]")
        if not go_ahead_remove_all == "IKNOWWHATIAMDOING":
            print("Remove cancelled.", file=sys.stderr)
            return 1

    if not args.no_confirm:
        print(
            "This will completely remove the selected VM(s)...", file=sys.stderr
        )
        for vm in args.domains:
            print(" ", vm.name)
        go_ahead = input("Are you sure? [y/N] ").upper()

    if args.no_confirm or go_ahead == "Y":
        for vm in args.domains:
            try:
                del args.app.domains[vm.name]
            except qubesadmin.exc.QubesVMInUseError as e:
                dependencies = qubesadmin.utils.vm_dependencies(vm.app, vm)
                # Check qubes.app::domain-pre-delete for logic.
                preloads = [
                    (holder, prop)
                    for holder, prop in dependencies
                    if holder
                    and getattr(holder, "is_preload", False)
                    and (
                        prop == "template"
                        or (
                            prop == "default_dispvm"
                            and getattr(holder, "template", None) == vm
                        )
                    )
                ]
                dependencies = list(set(dependencies) - set(preloads))
                if dependencies:
                    print(
                        "VM {} cannot be removed. It is in use as:".format(
                            vm.name
                        ),
                        file=sys.stderr,
                    )
                    for holder, prop in dependencies:
                        if holder:
                            print(
                                " - {} for {}".format(prop, holder.name),
                                file=sys.stderr,
                            )
                        else:
                            print(
                                " - global property {}".format(prop),
                                file=sys.stderr,
                            )
                # Display the original message as well
                parser.error_runtime(e)
            except qubesadmin.exc.QubesException as e:
                parser.error_runtime(e)
        retcode = 0
    else:
        print("Remove cancelled.", file=sys.stderr)
        retcode = 1
    return retcode


if __name__ == "__main__":
    sys.exit(main())
