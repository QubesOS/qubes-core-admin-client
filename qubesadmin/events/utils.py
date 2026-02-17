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

""" Utilities for common events-based actions """

import functools
from typing import Iterable

import qubesadmin.events
import qubesadmin.exc
from qubesadmin.events import EventsDispatcher
from qubesadmin.vm import QubesVM


def interrupt_on_vm_shutdown(vms: set[QubesVM], dispatcher: EventsDispatcher,
                             subject: QubesVM, event: str) -> None:
    """Interrupt events processing when given VM was shutdown"""
    # pylint: disable=unused-argument
    if event == 'connection-established':
        for vm in sorted(vms):
            if vm.is_halted():
                vms.remove(vm)
    elif event == 'domain-shutdown' and subject in vms:
        vms.remove(subject)
    if not vms:
        dispatcher.stop()


async def wait_for_domain_shutdown(vms: Iterable[QubesVM]) -> None:
    """ Helper function to wait for domain shutdown.

    This function wait for domain shutdown, but do not initiate the shutdown
    itself.

    :param vms: QubesVM object collection to wait for shutdown on
    """
    if not vms:
        return
    app = list(vms)[0].app
    vms = set(vms)
    events = qubesadmin.events.EventsDispatcher(app, enable_cache=False)
    events.add_handler('domain-shutdown',
        functools.partial(interrupt_on_vm_shutdown, vms, events))
    events.add_handler('connection-established',
        functools.partial(interrupt_on_vm_shutdown, vms, events))
    await events.listen_for_events()
