# -*- encoding: utf8 -*-
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
# with this program; if not, see <http://www.gnu.org/licenses/>.

"""qvm-start - start a domain"""
import asyncio
import sys

import qubesadmin.exc
import qubesadmin.tools
import qubesadmin.utils


parser = qubesadmin.tools.QubesArgumentParser(
    description="start a domain", vmname_nargs="+"
)

parser.add_argument(
    "--skip-if-running",
    action="store_true",
    default=False,
    help="Do not fail if the qube is already runnning",
)

parser_drive = parser.add_mutually_exclusive_group()

parser_drive.add_argument(
    "--drive",
    metavar="DRIVE",
    help="temporarily attach specified drive as CD/DVD or hard disk (can be"
    ' specified with prefix "hd:" or "cdrom:", default is cdrom)',
)

parser_drive.add_argument(
    "--hddisk",
    action=qubesadmin.utils.DriveAction,
    dest="drive",
    prefix="hd:",
    help="temporarily attach specified drive as hard disk",
)

parser_drive.add_argument(
    "--cdrom",
    metavar="IMAGE",
    action=qubesadmin.utils.DriveAction,
    dest="drive",
    prefix="cdrom:",
    help="temporarily attach specified drive as CD/DVD",
)

parser_drive.add_argument(
    "--install-windows-tools",
    action="store_const",
    dest="drive",
    default=False,
    const="cdrom:dom0:/usr/lib/qubes/qubes-windows-tools.iso",
    help="temporarily attach Windows tools CDROM to the domain",
)


async def run_async(args=None, app=None):
    # pylint: disable=missing-function-docstring
    args = parser.parse_args(args, app=app)
    exit_code = 0
    preflight = len(args.domains) > 1 and not args.skip_if_running
    if preflight:
        check_tasks = [
            asyncio.to_thread(qube.is_running) for qube in args.domains
        ]
        check_results = await asyncio.gather(
            *check_tasks, return_exceptions=True
        )
        start_domains = []
        for qube, is_running in zip(args.domains, check_results):
            if isinstance(is_running, BaseException):
                exit_code = 1
                parser.print_error(
                    "Starting qube failed: {}: {}".format(
                        qube.name, str(is_running)
                    )
                )
            elif is_running:
                exit_code = 1
                parser.print_error(
                    "Starting qube failed: {}: Domain is already running"
                    .format(qube.name)
                )
            else:
                start_domains.append(qube)
    else:
        start_domains = args.domains

    # The preflight above determines which qubes were running before this
    # command. Without a drive, admin.vm.Start is a no-op if a dependency has
    # started the qube in the meantime, so do not repeat the state request.
    check_if_running = not (preflight or args.skip_if_running)
    if args.drive:
        # Avoid attaching a temporary drive to an already-running qube.
        check_if_running = True
    tasks = [
        asyncio.to_thread(
            qubesadmin.utils.start_expert,
            domain=qube,
            skip_if_running=args.skip_if_running or preflight,
            drive=args.drive,
            check_if_running=check_if_running,
        )
        for qube in start_domains
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for qube, res in zip(start_domains, results):
        if isinstance(res, BaseException):
            exit_code = 1
            parser.print_error(
                "Starting qube failed: {}: {}".format(
                    qube.name, str(res)
                )
            )
    return exit_code


def main(args=None, app=None):
    """Main routine of :program:`qvm-start`.

    :param list args: Optional arguments to override those delivered from \
        command line.
    """
    return asyncio.run(run_async(args=args, app=app))


if __name__ == "__main__":
    sys.exit(main())
