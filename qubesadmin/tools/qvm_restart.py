# encoding=utf-8
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010-2016  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2011-2025  Marek Marczykowski-Górecki
#                                              <marmarek@invisiblethingslab.com>
# Copyright (C) 2016       Wojtek Porczyk <woju@invisiblethingslab.com>
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

"""Restart a qube / qubes"""

import asyncio
import sys

import qubesadmin.tools
import qubesadmin.utils


parser = qubesadmin.tools.QubesArgumentParser(
    description="restart domain(s)", vmname_nargs="+"
)
parser.add_argument(
    "--force","-f",
    action="store_true",
    default=False,
    help="restart even if other qubes depend on selected qubes, e.g. as "
    "NetVM or AudioVM; does not affect how the qube itself is shut down; "
    "use with caution."
)
parser.add_argument(
    "--start","-s",
    action="store_true",
    default=False,
    help="start selected domains if they are down. By default only restart "
    "running domains."
)


def report_failure(data):
    """Report failures as a table of `qube_name "reason"`. Returns a list of
    strings with trailing newlines, ready for output in a single print call.

    :param data: Information to report; a dictionary of:
                 {qubesadmin.vm.QubesVM: str or Exception}
    """
    nwidth = str(len(max(
        (vm.name for vm in data),
        key=len
    )))
    output = [
        ("{:>" + nwidth + "} REASON\n").format("NAME")
    ]
    for vm in data:
        output.append(
            ("{:>" + nwidth + "} \"{}\"\n").format(vm.name,data[vm])
        )
    return output


def main(args=None, app=None):
    """Main function of qvm-restart. See `qvm-restart --help` or 
    execute this function with args=["--help"] for more information
    """
    args = parser.parse_args(args, app=app)
    args.force = args.force or (args.all_domains and not args.exclude)
    target_domains = args.domains
    invalid_domains = []

    if args.all_domains:
        target_domains = [
            vm for vm in target_domains
            if not (vm.klass == 'DispVM' and vm.auto_cleanup)
        ]
    else:
        invalid_domains = [
            vm for vm in args.domains
            if vm.name == 'dom0'
            or (vm.klass == 'DispVM' and vm.auto_cleanup)
        ]

    if invalid_domains:
        parser.error_runtime(
            "Can not restart: "
            + ", ".join(vm.name for vm in invalid_domains) +
            "\nRefusing to shut down dom0 and unnamed DispVMs;"
            " Ensure data is saved and shut down manually."
        )

    if not args.start:
        target_domains = [
            vm for vm in target_domains
            if vm.get_power_state() == "Running"
        ]

    failed = {}
    failed['shutdown'] = asyncio.run(
        qubesadmin.utils.shutdown(
            domains=target_domains, force=args.force, wait=True
        )
    )
    if failed['shutdown']:
        parser.print_error(
            "Failed to restart domains:\n",
            *report_failure(failed['shutdown']),
            end=""
        )


    failed['start'] = asyncio.run(
        qubesadmin.utils.start(
            domains=[
                vm for vm in target_domains if vm not in failed['shutdown']
            ]
        )
    )
    if failed['start']:
        parser.print_error(
            "Failed to start domains back up:\n",
            *report_failure(failed['start']),
            end=""
        )

    if failed['start'] or failed['shutdown']:
        return 75


if __name__ == "__main__":
    sys.exit(main())
