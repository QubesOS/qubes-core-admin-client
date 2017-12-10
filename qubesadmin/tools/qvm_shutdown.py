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

import asyncio

try:
    import qubesadmin.events.utils
    have_events = True
except ImportError:
    have_events = False
import qubesadmin.tools
import qubesadmin.exc

parser = qubesadmin.tools.QubesArgumentParser(
    description=__doc__, vmname_nargs='+')

parser.add_argument('--wait',
    action='store_true', default=False,
    help='wait for the VMs to shut down')

parser.add_argument('--timeout',
    action='store', type=float,
    default=60,
    help='timeout after which domains are killed when using --wait'
        ' (default: %(default)d)')


def main(args=None, app=None):  # pylint: disable=missing-docstring
    args = parser.parse_args(args, app=app)

    if have_events:
        loop = asyncio.get_event_loop()
    remaining_domains = args.domains
    for _ in range(len(args.domains)):
        this_round_domains = set(remaining_domains)
        if not this_round_domains:
            break
        remaining_domains = set()
        for vm in this_round_domains:
            try:
                vm.shutdown()
            except qubesadmin.exc.QubesVMNotRunningError:
                pass
            except qubesadmin.exc.QubesException as e:
                if not args.wait:
                    vm.log.error('Shutdown error: {}'.format(e))
                else:
                    remaining_domains.add(vm)
        if not args.wait:
            return len(remaining_domains)
        this_round_domains.difference_update(remaining_domains)
        if not this_round_domains:
            # no VM shutdown request succeed, no sense to try again
            break
        if have_events:
            try:
                # pylint: disable=no-member
                loop.run_until_complete(asyncio.wait_for(
                    qubesadmin.events.utils.wait_for_domain_shutdown(
                        sorted(this_round_domains)),
                    args.timeout))
            except asyncio.TimeoutError:
                for vm in this_round_domains:
                    try:
                        vm.kill()
                    except qubesadmin.exc.QubesVMNotStartedError:
                        # already shut down
                        pass
        else:
            timeout = args.timeout
            current_vms = list(sorted(this_round_domains))
            while timeout >= 0:
                current_vms = [vm for vm in current_vms
                    if vm.get_power_state() != 'Halted']
                if not current_vms:
                    break
                args.app.log.info('Waiting for shutdown ({}): {}'.format(
                    timeout, ', '.join([str(vm) for vm in current_vms])))
                time.sleep(1)
                timeout -= 1
            if current_vms:
                args.app.log.info(
                    'Killing remaining qubes: {}'
                    .format(', '.join([str(vm) for vm in current_vms])))
            for vm in current_vms:
                try:
                    vm.kill()
                except qubesadmin.exc.QubesVMNotStartedError:
                    # already shut down
                    pass

    if args.wait:
        if have_events:
            loop.close()
        return len([vm for vm in args.domains
            if vm.get_power_state() != 'Halted'])

if __name__ == '__main__':
    sys.exit(main())
