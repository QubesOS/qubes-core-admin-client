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

''' Shutdown a qube '''

from __future__ import print_function

import sys
import time

import qubesadmin.tools
import qubesadmin.exc

parser = qubesadmin.tools.QubesArgumentParser(
    description=__doc__, vmname_nargs='+')

parser.add_argument('--force',
    action='store_true', default=False,
    help='force operation, even if may damage other VMs (eg. shutdown of'
        ' network provider)')

parser.add_argument('--wait',
    action='store_true', default=False,
    help='wait for the VMs to shut down')

parser.add_argument('--timeout',
    action='store', type=float,
    default=60,
    help='timeout after which domains are killed when using --wait'
        ' (default: %d)')


def main(args=None, app=None):  # pylint: disable=missing-docstring
    args = parser.parse_args(args, app=app)

    for vm in args.domains:
        try:
            vm.shutdown(force=args.force)
        except qubesadmin.exc.QubesVMNotStartedError:
            pass

    if not args.wait:
        return

    timeout = args.timeout
    current_vms = list(sorted(args.domains))
    while timeout >= 0:
        current_vms = [vm for vm in current_vms
            if vm.get_power_state() != 'Halted']
        if not current_vms:
            return 0
        args.app.log.info('Waiting for shutdown ({}): {}'.format(
            timeout, ', '.join([str(vm) for vm in current_vms])))
        time.sleep(1)
        timeout -= 1

    args.app.log.info(
        'Killing remaining qubes: {}'
        .format(', '.join([str(vm) for vm in current_vms])))
    for vm in current_vms:
        vm.kill()


if __name__ == '__main__':
    sys.exit(main())
