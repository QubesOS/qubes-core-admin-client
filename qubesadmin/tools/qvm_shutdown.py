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


async def shutdown(args, domains: list[qubesadmin.vm.QubesVM]):
    """
    Asynchronously shutdown qubes and return qubes that failed to shutdown
    because and the client can't handle, as well as qubes that were in use
    while --force was not provided, as well as timed out.
    """
    # pylint: disable=missing-docstring
    unhandled, used, timedout = [], [], []
    tasks = [
        asyncio.to_thread(qube.shutdown, force=args.force, wait=args.wait)
        for qube in domains
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for qube, res in zip(domains, results):
        if not isinstance(res, BaseException):
            qube.log.info("Shutdown succeeded")
            continue
        try:
            raise res
        except qubesadmin.exc.QubesVMNotStartedError:
            pass
        except qubesadmin.exc.QubesVMInUseError as e:
            if args.wait:
                qube.log.error("Shutdown error: {}".format(e))
            else:
                qube.log.error("Shutdown error: (try --force): {}".format(e))
            used.append(qube)
        except qubesadmin.exc.QubesVMShutdownTimeoutError as e:
            if args.wait:
                qube.log.error("Shutdown error: {}".format(e))
            else:
                qube.log.error("Shutdown error: (try qvm-kill): {}".format(e))
            timedout.append(qube)
        except qubesadmin.exc.QubesException as e:
            qube.log.error("Shutdown error: {}".format(e))
            unhandled.append(qube)
    return unhandled, used, timedout


async def kill(domains: list[qubesadmin.vm.QubesVM]):
    """
    Asynchronously kill qubes and return qubes that failed to shutdown.
    """
    # pylint: disable=missing-docstring
    unhandled = domains.copy()
    tasks = [asyncio.to_thread(qube.kill) for qube in domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for qube, res in zip(domains, results):
        if not isinstance(res, BaseException):
            qube.log.info("Killing succeeded")
            unhandled.remove(qube)
            continue
        try:
            raise res
        except qubesadmin.exc.QubesVMNotStartedError:
            unhandled.remove(qube)
        except qubesadmin.exc.QubesException as e:
            qube.log.error("Kill error: {}".format(e))
    return unhandled


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

    unhandled, used, timedout = await shutdown(args=args, domains=args.domains)
    unhandled_retry = []
    timedout_retry = []
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
        failed = await shutdown(args=args, domains=used)
        unhandled_retry, used, timedout_retry = failed
        if not failed:
            break
        if old_failed:
            len_failed = sum(len(item) for item in failed)
            len_old_failed = sum(len(item) for item in old_failed)
            if len_failed == len_old_failed:
                break
        old_failed = failed

    unhandled.extend(qube for qube in unhandled_retry if qube not in unhandled)
    timedout.extend(qube for qube in timedout_retry if qube not in timedout)

    # Retry timed out only once, as it can take a long time, 60s by default.
    if timedout:
        parser.print_error(
            "Retrying shutdown of qubes that timed out: {}".format(
                ", ".join(qube.name for qube in timedout)
            )
        )
        unhandled, used, timedout = await shutdown(args=args, domains=timedout)

    if timedout:
        parser.print_error(
            "Killing timed out qubes: {}".format(
                ", ".join(qube.name for qube in timedout)
            )
        )
        unhandled = await kill(domains=timedout)

    if not unhandled and not used and not timedout:
        return

    if unhandled:
        parser.print_error(
            "Failed to shut down for unknown reason: {}".format(
                ", ".join(qube.name for qube in unhandled)
            )
        )
    if used:
        parser.print_error(
            "Failed to shut down because it's in use: {}".format(
                ", ".join(qube.name for qube in used)
            )
        )
    if timedout:
        parser.print_error(
            "Failed to shut down because of time out: {}".format(
                ", ".join(qube.name for qube in timedout)
            )
        )
    raise SystemExit(len(unhandled + used + timedout))


def main(args=None, app=None):
    # pylint: disable=missing-docstring
    asyncio.run(run_async(args=args, app=app))


if __name__ == "__main__":
    sys.exit(main())
