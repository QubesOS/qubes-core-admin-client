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

    force = args.force or bool(args.all_domains)

    if have_events:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    remaining_domains = args.domains
    for _ in range(len(args.domains)):
        this_round_domains = set(remaining_domains)
        if not this_round_domains:
            break
        remaining_domains = set()
        if not args.dry_run:
            for vm in this_round_domains:
                try:
                    vm.shutdown(force=force)
                except qubesadmin.exc.QubesVMNotStartedError:
                    pass
                except qubesadmin.exc.QubesException as e:
                    if not args.wait:
                        vm.log.error(f'Shutdown error: {e}')
                    else:
                        remaining_domains.add(vm)
        if not args.wait:
            if remaining_domains:
                parser.error_runtime(
                    'Failed to shut down: ' +
                    ', '.join(vm.name for vm in remaining_domains),
                    len(remaining_domains))
            return
        this_round_domains.difference_update(remaining_domains)
        if not this_round_domains:
            # no VM shutdown request succeed, no sense to try again
            break
        if have_events:
            try:
                # pylint: disable=no-member
                loop.run_until_complete(asyncio.wait_for(
                    qubesadmin.events.utils.wait_for_domain_shutdown(
                        this_round_domains),
                    args.timeout))
            except TimeoutError:
                if not args.dry_run:
                    for vm in this_round_domains:
                        try:
                            vm.kill()
                        except qubesadmin.exc.QubesVMNotStartedError:
                            # already shut down
                            pass
                        except qubesadmin.exc.QubesException as e:
                            parser.error_runtime(e)
        else:
            timeout = args.timeout
            current_vms = list(sorted(this_round_domains))
            while timeout >= 0:
                current_vms = failed_domains(current_vms)
                if not current_vms:
                    break
                args.app.log.info('Waiting for shutdown ({}): {}'.format(
                    timeout, ', '.join([str(vm) for vm in current_vms])))
                time.sleep(1)
                timeout -= 1
            if not args.dry_run:
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

    if args.wait:
        if have_events:
            loop.close()
        failed = failed_domains(args.domains)
        if failed:
            parser.error_runtime(
                'Failed to shut down: ' +
                ', '.join(vm.name for vm in failed),
                len(failed))


if __name__ == '__main__':
    sys.exit(main())
