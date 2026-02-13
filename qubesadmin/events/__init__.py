# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

'''Event handling implementation, require Python >=3.5.2 for asyncio.'''

import asyncio
import fnmatch
import subprocess
import typing
from typing import Callable, Any
from asyncio import StreamWriter, StreamReader

import qubesadmin.config
import qubesadmin.exc
from qubesadmin.app import QubesBase
from qubesadmin.device_protocol import VirtualDevice, Port, UnknownDevice
from qubesadmin.vm import QubesVM

Handler: typing.TypeAlias\
    = Callable[[QubesVM | None, str, ...], Any]  # noqa: ANN401

class EventsDispatcher(object):
    ''' Events dispatcher, responsible for receiving events and calling
    appropriate handlers'''
    def __init__(self, app: QubesBase, api_method: str='admin.Events',
                 enable_cache: bool=True):
        """Initialize EventsDispatcher

        :param app :py:class:`qubesadmin.Qubes` object
        :param api_method Admin API method producing events
        :param enable_cache Enable caching (see below)

        Connecting :py:class:`EventsDispatcher` object to a
        :py:class:`qubesadmin.Qubes` implicitly enables caching. It is important
        to actually run the dispatcher (:py:meth:`listen_for_events`), otherwise
        the cache won't be updated. Alternatively, disable caching by setting
        :py:attr:`qubesadmin.Qubes.cache_enabled` property to `False`.
        """
        #: Qubes() object
        self.app = app

        self._api_method = api_method

        #: event handlers - dict of event -> handlers
        self.handlers = {}

        #: used to stop processing events
        self._reader_task = None

        if enable_cache:
            self.app.cache_enabled = True

    def add_handler(self, event: str, handler: Handler) -> None:
        '''Register handler for event

        Use '*' as event to register a handler for all events.

        Handler function is called with:
          * subject (VM object or None)
          * event name (str)
          * keyword arguments related to the event, if any - all values as str

        :param event Event name, or '*' for all events
        :param handler Handler function'''
        self.handlers.setdefault(event, set()).add(handler)

    def remove_handler(self, event: str, handler: Handler) -> None:
        '''Remove previously registered event handler

        :param event Event name
        :param handler Handler function
        '''
        self.handlers[event].remove(handler)

    async def _get_events_reader(self, vm: QubesVM | None =None)\
            -> tuple[asyncio.StreamReader, Callable]:
        '''Make connection to qubesd and return stream to read events from

        :param vm: Specific VM for which events should be handled, use None
        to handle events from all VMs (and non-VM objects)
        :return stream to read events from and a cleanup function
        (call it to terminate qubesd connection)'''
        if vm is not None:
            dest = vm.name
        else:
            dest = 'dom0'

        if self.app.qubesd_connection_type == 'socket':
            reader, writer = await asyncio.open_unix_connection(
                qubesadmin.config.QUBESD_SOCKET)
            writer.write(self._api_method.encode() + b'+ ')  # method+arg
            writer.write(b'dom0 ')  # source
            writer.write(b'name ' + dest.encode('ascii') + b'\0')  # dest
            writer.write_eof()

            def cleanup_func() -> None:
                '''Close connection to qubesd'''
                writer.close()
        elif self.app.qubesd_connection_type == 'qrexec':
            proc = await asyncio.create_subprocess_exec(
                'qrexec-client-vm', dest, self._api_method,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)

            typing.cast(StreamWriter, proc.stdin).write_eof()
            reader = typing.cast(StreamReader, proc.stdout)

            def cleanup_func() -> None:
                '''Close connection to qubesd'''
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
        else:
            raise NotImplementedError('Unsupported qubesd connection type: '
                                      + self.app.qubesd_connection_type)
        return reader, cleanup_func

    async def listen_for_events(self, vm: QubesVM | None=None,
                                reconnect: bool=True) -> None:
        '''
        Listen for events and call appropriate handlers.
        This function do not exit until manually terminated.

        This is coroutine.

        :param vm: Listen for events only for this VM, use None to listen for
            events about all VMs and not related to any particular VM.
        :param reconnect: should reconnect to qubesd if connection is
            interrupted?
        :rtype: None
        '''
        while True:
            try:
                self._reader_task = asyncio.create_task(
                    self._listen_for_events(vm))
                await self._reader_task
            except (OSError, qubesadmin.exc.QubesDaemonCommunicationError):
                pass
            except asyncio.CancelledError:
                break
            finally:
                self._reader_task = None
            if not reconnect:
                break
            self.app.log.warning(
                'Connection to qubesd terminated, reconnecting in {} '
                'seconds'.format(qubesadmin.config.QUBESD_RECONNECT_DELAY))
            # avoid busy-loop if qubesd is dead
            await asyncio.sleep(qubesadmin.config.QUBESD_RECONNECT_DELAY)

    async def _listen_for_events(self, vm: QubesVM | None=None) -> bool:
        '''
        Listen for events and call appropriate handlers.
        This function do not exit until manually terminated.

        This is coroutine.

        :param vm: Listen for events only for this VM, use None to listen for
        events about all VMs and not related to any particular VM.
        :return: True if any event was received, otherwise False
        :rtype: bool
        '''

        reader, cleanup_func = await self._get_events_reader(vm)
        try:
            some_event_received = False
            while not reader.at_eof():
                try:
                    event_header = await reader.readuntil(b'\0')
                    if event_header != b'1\0':
                        raise qubesadmin.exc.QubesDaemonCommunicationError(
                            'Non-event received on events connection: '
                            + repr(event_header))
                    subject = (await reader.readuntil(b'\0'))[:-1].decode(
                        'utf-8')
                    event = (await reader.readuntil(b'\0'))[:-1].decode(
                        'utf-8')
                    kwargs = {}
                    while True:
                        key = (await reader.readuntil(b'\0'))[:-1].decode(
                            'utf-8')
                        if not key:
                            break
                        value = (await reader.readuntil(b'\0'))[:-1].\
                            decode('utf-8')
                        kwargs[key] = value
                except BrokenPipeError:
                    break
                except asyncio.IncompleteReadError as err:
                    if err.partial == b'':
                        break
                    raise

                if not subject:
                    subject = None
                self.handle(subject, event, **kwargs)

                some_event_received = True
        finally:
            cleanup_func()
        return some_event_received

    def stop(self) -> None:
        """Stop currently running dispatcher"""
        if self._reader_task:
            self._reader_task.cancel()

    def handle(self, subject_name: str | None, event: str, **kwargs) -> None:
        """Call handlers for given event"""
        # pylint: disable=protected-access
        if subject_name:
            if event in ['property-set:name']:
                self.app.domains.clear_cache()
            try:
                subject = self.app.domains.get_blind(subject_name)
            except KeyError:
                return
        else:
            # handle cache refreshing on best-effort basis
            if event in ['domain-add', 'domain-delete']:
                vm = kwargs['vm']
                self.app.domains.clear_cache(invalidate_name=str(vm))
            subject = None
        # invalidate cache if needed; call it before other handlers
        # as those may want to use cached value
        if event.startswith('property-set:') or \
                event.startswith('property-reset:'):
            self.app._invalidate_cache(subject, event, **kwargs)
        elif event in ('domain-pre-start', 'domain-start', 'domain-shutdown',
                       'domain-paused', 'domain-unpaused',
                       'domain-start-failed'):
            self.app._update_power_state_cache(subject, event, **kwargs)
            subject.devices.clear_cache()
        elif event == 'connection-established':
            # on (re)connection, clear cache completely - we don't have
            # guarantee about not missing any events before this point
            self.app._invalidate_cache_all()
        elif event.split(":")[0] in (
            "device-assign",
            "device-unassign",
            "device-assignment-changed"
        ):
            devclass = event.split(":")[1]
            subject.devices[devclass]._assignment_cache = None
        elif event.split(":")[0] in (
            "device-attach",
            "device-detach",
            "device-removed"
        ):
            devclass = event.split(":")[1]
            subject.devices[devclass]._attachment_cache = None
        elif event.split(":")[0] in ("device-removed",):
            devclass = event.split(":")[1]
            try:
                subject.devices[devclass]._dev_cache[kwargs["port"]]
            except KeyError:
                pass

        handlers = [h_func for h_name, h_func_set in self.handlers.items()
                    for h_func in h_func_set
                    if fnmatch.fnmatch(event, h_name)]

        # skip deserializing parameters (which may make further Admin API calls)
        # if no handler is registered for the event
        if not handlers:
            return

        # deserialize known attributes
        if event.startswith('device-'):
            try:
                if 'device' in kwargs:
                    devclass = event.split(':', 1)[1]
                    device = VirtualDevice.from_str(
                        kwargs['device'],
                        devclass,
                        self.app.domains,
                        blind=True)
                    kwargs['device'] = device
                    if device.port_id != '*':
                        plugged = self.app.domains.get_blind(
                            device.backend_name).devices[
                            devclass][device.port_id]
                        if (not isinstance(plugged, UnknownDevice)
                            and plugged.device_id == device.device_id):
                            kwargs['device'] = plugged
            except (KeyError, ValueError):
                pass
            try:
                if 'port' in kwargs:
                    devclass = event.split(':', 1)[1]
                    kwargs['port'] = Port.from_str(
                        kwargs['port'], devclass, self.app.domains, blind=True)
            except (KeyError, ValueError):
                pass

        for handler in handlers:
            try:
                handler(subject, event, **kwargs)
            except:  # pylint: disable=bare-except
                self.app.log.exception(
                    'Failed to handle event: %s, %s, %s',
                    subject, event, kwargs)
