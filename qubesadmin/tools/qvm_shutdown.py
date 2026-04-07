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

import asyncio

import qubesadmin.events.utils
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

parser.add_argument(
    '--force',
    action='store_true', default=False,
    help='force shutdown regardless of connected domains; use with caution')

parser.add_argument(
    '--dry-run',
    action='store_true', dest='dry_run', default=False,
    help='don\'t really shutdown or kill the domains; useful with --wait')


def failed_domains(vms):
    '''Find the domains that have not successfully been shut down'''

    # DispVM might have been deleted before we check them, so NA is acceptable.
    return [vm for vm in vms
            if not (vm.get_power_state() == 'Halted'
                or (vm.klass == 'DispVM' and vm.get_power_state() == 'NA'))]

def main(args=None, app=None):  # pylint: disable=missing-docstring
    args = parser.parse_args(args, app=app)

    force = args.force or (args.all_domains and not args.exclude)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    remaining_domains = set(args.domains)
    for _ in range(len(args.domains)):
        if not remaining_domains:
            break
        shutdown_failed = set()
        if not args.dry_run:
            for vm in remaining_domains:
                try:
                    vm.shutdown(force=force)
                except qubesadmin.exc.QubesVMNotStartedError:
                    pass
                except qubesadmin.exc.QubesException as e:
                    if not args.wait:
                        vm.log.error('Shutdown error: {}'.format(e))
                    shutdown_failed.add(vm)
        if not args.wait:
            if shutdown_failed:
                parser.error_runtime(
                    'Failed to shut down: ' +
                    ', '.join(vm.name for vm in shutdown_failed),
                    len(shutdown_failed))
            return
        awaiting = remaining_domains - shutdown_failed
        remaining_domains = shutdown_failed
        if not awaiting:
            # no VM shutdown request succeeded, no sense to try again
            break

        try:
            # pylint: disable=no-member
            loop.run_until_complete(asyncio.wait_for(
                qubesadmin.events.utils.wait_for_domain_shutdown(
                    awaiting), args.timeout))
        except (TimeoutError, asyncio.TimeoutError):
            if not args.dry_run:
                current_vms = failed_domains(awaiting)
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
                    except qubesadmin.exc.QubesException as e:
                        parser.error_runtime(e)

    loop.close()
    failed = failed_domains(args.domains)
    if failed:
        parser.error_runtime(
            'Failed to shut down: ' +
            ', '.join(vm.name for vm in failed),
            len(failed))


if __name__ == '__main__':
    sys.exit(main())
