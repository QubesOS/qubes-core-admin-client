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

import argparse
import asyncio
import sys

import qubesadmin.events.utils
import qubesadmin.tools
import qubesadmin.exc
from qubesadmin.utils import async_thread

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
    type=float,
    default=60,
    help="timeout after which domains are killed when using --wait"
    " (default: %(default)d)",
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


async def shutdown(
    args,
    domains: list[qubesadmin.vm.QubesVM],
    force: bool,
):
    """
    Asynchronously shutdown qubes and return qubes that failed to shutdown as
    well as failed with a timeout.
    """
    # pylint: disable=missing-docstring
    remnants, timedout = [], []
    tasks = [
        asyncio.wait_for(
            async_thread(qube.shutdown, force=force, wait=args.wait),
            timeout=args.timeout,
        )
        for qube in domains
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for qube, res in zip(domains, results):
        if not isinstance(res, BaseException):
            qube.log.info("Shutdown succeeded")
            continue
        remnants.append(qube)
        try:
            raise res
        except qubesadmin.exc.QubesVMNotStartedError:
            remnants.remove(qube)
        except qubesadmin.exc.QubesVMInUseError as e:
            qube.log.error("Shutdown error: (try --force): {}".format(e))
        except qubesadmin.exc.QubesVMShutdownTimeoutError as e:
            if args.wait:
                qube.log.error("Shutdown error: {}".format(e))
            else:
                qube.log.error("Shutdown error: (try qvm-kill): {}".format(e))
            timedout.append(qube)
        except TimeoutError:
            if args.wait:
                qube.log.error("Shutdown error: timed out")
            else:
                qube.log.error("Shutdown error: (try qvm-kill): timed out")
            timedout.append(qube)
        except qubesadmin.exc.QubesException as e:
            qube.log.error("Shutdown error: {}".format(e))
    return remnants, timedout


async def kill(domains: list[qubesadmin.vm.QubesVM]):
    """
    Asynchronously kill qubes and return qubes that failed to shutdown.
    """
    # pylint: disable=missing-docstring
    remnants = domains.copy()
    tasks = [async_thread(qube.kill) for qube in domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for qube, res in zip(domains, results):
        if not isinstance(res, BaseException):
            qube.log.info("Killing succeeded")
            remnants.remove(qube)
            continue
        try:
            raise res
        except qubesadmin.exc.QubesVMNotStartedError:
            remnants.remove(qube)
        except qubesadmin.exc.QubesException as e:
            qube.log.error("Kill error: {}".format(e))
    return remnants


async def main(args=None, app=None):
    # pylint: disable=missing-docstring
    args = parser.parse_args(args, app=app)
    force = args.force or (args.all_domains and not args.exclude)
    if args.dry_run:
        return
    domains = set(args.domains)

    remnants, timedout = await shutdown(args=args, force=force, domains=domains)
    if timedout:
        args.app.log.info(
            "Retrying shutdown of qubes that timed out: {}".format(
                ", ".join(qube.name for qube in timedout)
            )
        )
        remnants, timedout = await shutdown(
            args=args, force=force, domains=timedout
        )

    if timedout:
        args.app.log.info(
            "Killing timed out qubes: {}".format(
                ", ".join(qube.name for qube in timedout)
            )
        )
        remnants = await kill(domains=timedout)

    if not remnants:
        return
    parser.error_runtime(
        "Failed to shut down: {}".format(
            ", ".join(qube.name for qube in remnants)
        ),
        len(remnants),
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
