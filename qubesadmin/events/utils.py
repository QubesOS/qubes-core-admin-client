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

''' Utilities for common events-based actions '''

import asyncio
import functools

import qubesadmin.events
import qubesadmin.exc



class Interrupt(Exception):
    '''Interrupt events processing'''


def interrupt_on_vm_shutdown(vm, subject, event):
    '''Interrupt events processing when given VM was shutdown'''
    # pylint: disable=unused-argument
    if event == 'connection-established':
        if vm.is_halted():
            raise Interrupt
    elif event == 'domain-shutdown' and vm == subject:
        raise Interrupt


def wait_for_domain_shutdown(vm, timeout):
    ''' Helper function to wait for domain shutdown.

    This function wait for domain shutdown, but do not initiate the shutdown
    itself.

    Note: you need to close event loop after calling this function.

    :param vm: QubesVM object to wait for shutdown on
    :param timeout: Timeout in seconds, use 0 for no timeout
    '''
    events = qubesadmin.events.EventsDispatcher(vm.app)
    loop = asyncio.get_event_loop()
    events.add_handler('domain-shutdown',
        functools.partial(interrupt_on_vm_shutdown, vm))
    events.add_handler('connection-established',
        functools.partial(interrupt_on_vm_shutdown, vm))
    events_task = asyncio.ensure_future(events.listen_for_events(),
        loop=loop)
    if timeout:
        # pylint: disable=no-member
        loop.call_later(timeout, events_task.cancel)
    try:
        loop.run_until_complete(events_task)
    except asyncio.CancelledError:
        raise qubesadmin.exc.QubesVMShutdownTimeout(
            'VM %s shutdown timeout expired', vm.name)
    except Interrupt:
        pass
