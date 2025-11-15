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

import sys

try:
    import qubesadmin.events.utils

    have_events = True
except ImportError:
    have_events = False
import qubesadmin.tools
from qubesadmin.tools import qvm_start, qvm_shutdown

parser = qubesadmin.tools.QubesArgumentParser(
    description=__doc__, vmname_nargs="+"
)

parser.add_argument(
    "--timeout",
    action="store",
    type=float,
    help="timeout after which domains are killed before being restarted",
)


def main(args=None, app=None):  # pylint: disable=missing-docstring
    args = parser.parse_args(args, app=app)

    if not args.all_domains:
        # Check if user explicitly specified dom0 or unnamed DispVMs
        invalid_domains = [
            vm
            for vm in args.domains
            if vm.klass == "AdminVM"
            or (vm.klass == "DispVM" and vm.auto_cleanup)
        ]
        if invalid_domains:
            parser.error_runtime(
                "Can not restart: "
                + ", ".join(vm.name for vm in invalid_domains),
                "dom0 or unnamed DispVMs could not be restarted",
            )
        target_domains = args.domains
    else:
        # Only restart running, non-DispVM and not dom0 with --all option
        target_domains = [
            vm
            for vm in args.domains
            if vm.get_power_state() == "Running"
            and vm.klass != "AdminVM"
            and not (vm.klass == "DispVM" and vm.auto_cleanup)
        ]

    # Forcing shutdown to allow graceful restart of ServiceVMs
    shutdown_cmd = [vm.name for vm in target_domains] + ["--wait", "--force"]
    shutdown_cmd += ["--timeout", str(args.timeout)] if args.timeout else []
    shutdown_cmd += ["--quiet"] if args.quiet else []
    qvm_shutdown.main(shutdown_cmd, app=args.app)

    start_cmd = [vm.name for vm in target_domains]
    start_cmd += ["--quiet"] if args.quiet else []
    qvm_start.main(start_cmd, app=args.app)


if __name__ == "__main__":
    sys.exit(main())
