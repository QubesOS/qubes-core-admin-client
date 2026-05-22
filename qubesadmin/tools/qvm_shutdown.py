# encoding=utf-8
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010-2016  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2011-2016  Marek Marczykowski-Górecki
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

"""Shutdown a qube"""

from __future__ import print_function

import asyncio
import sys
from warnings import warn

import qubesadmin.tools
import qubesadmin.exc

parser = qubesadmin.tools.QubesArgumentParser(
    description=__doc__, vmname_nargs="+"
)

parser.add_argument(
    "--wait",
    action="store_true",
    default=False,
    help="wait for the VMs to shut down",
)

parser.add_argument(
    "--timeout",
    action="store",
    help="Deprecated, use --wait instead. Setting this option will enable "
    "--wait",
)

parser.add_argument(
    "--force",
    action="store_true",
    default=False,
    help="shut down even if other qubes depend on this one (e.g. as NetVM"
    " or AudioVM); does not affect how the qube itself is shut down;"
    " use with caution",
)

parser.add_argument(
    "--dry-run",
    action="store_true",
    dest="dry_run",
    default=False,
    help="don't really shutdown or kill the domains; useful with --wait",
)


async def shutdown(domains, **shutdown_kwargs):
    # pylint: disable=missing-function-docstring
    failed = await qubesadmin.utils.shutdown(domains=domains, **shutdown_kwargs)
    used = {
        qube: exc
        for qube, exc in failed.items()
        if isinstance(exc, qubesadmin.exc.QubesVMInUseError)
    }
    timedout = {
        qube: exc
        for qube, exc in failed.items()
        if isinstance(exc, qubesadmin.exc.QubesVMShutdownTimeoutError)
    }
    unhandled = {
        qube: exc
        for qube, exc in failed.items()
        if qube not in used and qube not in timedout
    }
    return unhandled, used, timedout


async def run_async(args=None, app=None):
    # pylint: disable=missing-docstring
    args = parser.parse_args(args, app=app)
    if args.dry_run:
        return
    if args.timeout:
        warn(
            "Call to deprecated --timeout option, use --wait instead",
            FutureWarning,
        )
        args.wait = True
    args.force = args.force or (args.all_domains and not args.exclude)
    shutdown_kwargs = {
        "force": args.force,
        "wait": args.wait,
    }

    unhandled, used, timedout = await shutdown(
        domains=args.domains, **shutdown_kwargs
    )
    unhandled_retry = {}
    timedout_retry = {}
    if used:
        old_failed = unhandled, used, timedout
        parser.print_error(
            "Retrying shutdown of qubes that were in use for {} time(s)".format(
                len(used)
            )
        )
    for _ in range(len(used)):
        parser.print_error(
            "Retrying shutdown of qubes that were in use: {}".format(
                ", ".join(qube.name for qube in used)
            )
        )
        failed = await shutdown(domains=used, **shutdown_kwargs)
        unhandled_retry, used, timedout_retry = failed
        if not failed:
            break
        if old_failed:
            len_failed = sum(len(item) for item in failed)
            len_old_failed = sum(len(item) for item in old_failed)
            if len_failed == len_old_failed:
                break
        old_failed = failed

    unhandled.update(unhandled_retry)
    timedout.update(timedout_retry)

    # Retry timed out only once, as it can take a long time, 60s by default.
    if timedout:
        parser.print_error(
            "Retrying shutdown of qubes that timed out: {}".format(
                ", ".join(qube.name for qube in timedout)
            )
        )
        unhandled, used, timedout = await shutdown(
            domains=timedout, **shutdown_kwargs
        )

    if timedout:
        parser.print_error(
            "Killing timed out qubes: {}".format(
                ", ".join(qube.name for qube in timedout)
            )
        )
        timedout = await qubesadmin.utils.kill(domains=timedout)

    for item in [unhandled, used, timedout]:
        for qube, exc in item.items():
            parser.print_error(
                "Failed to shut down: {}: {}".format(qube.name, str(exc))
            )

    exit_code = len(unhandled) + len(used) + len(timedout)
    if exit_code == 0:
        return
    raise SystemExit(exit_code)


def main(args=None, app=None):
    # pylint: disable=missing-docstring
    asyncio.run(run_async(args=args, app=app))


if __name__ == "__main__":
    sys.exit(main())
