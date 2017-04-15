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
import subprocess

import qubesmgmt.config
import qubesmgmt.exc


class EventsDispatcher(object):
    ''' Events dispatcher, responsible for receiving events and calling
    appropriate handlers'''
    def __init__(self, app):
        '''Initialize EventsDispatcher'''
        #: Qubes() object
        self.app = app

        #: event handlers - dict of event -> handlers
        self.handlers = {}

    def add_handler(self, event, handler):
        '''Register handler for event

        Use '*' as event to register a handler for all events.

        Handler function is called with:
          * subject (VM object or None)
          * event name (str)
          * keyword arguments related to the event, if any - all values as str

        :param event Event name, or '*' for all events
        :param handler Handler function'''
        self.handlers.setdefault(event, set()).add(handler)

    def remove_handler(self, event, handler):
        '''Remove previously registered event handler

        :param event Event name
        :param handler Handler function
        '''
        self.handlers[event].remove(handler)

    @asyncio.coroutine
    def _get_events_reader(self, vm=None) -> (asyncio.StreamReader, callable):
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
            reader, writer = yield from asyncio.open_unix_connection(
                qubesmgmt.config.QUBESD_SOCKET)
            writer.write(b'dom0\0')  # source
            writer.write(b'mgmt.Events\0')  # method
            writer.write(dest.encode('ascii') + b'\0')  # dest
            writer.write(b'\0')  # arg
            writer.write_eof()

            def cleanup_func():
                '''Close connection to qubesd'''
                writer.close()
        elif self.app.qubesd_connection_type == 'qrexec':
            proc = yield from asyncio.create_subprocess_exec(
                ['qrexec-client-vm', dest, 'mgmt.Events'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)

            proc.stdin.write_eof()
            reader = proc.stdout

            def cleanup_func():
                '''Close connection to qubesd'''
                proc.kill()
        else:
            raise NotImplementedError('Unsupported qubesd connection type: '
                                      + self.app.qubesd_connection_type)
        return reader, cleanup_func

    @asyncio.coroutine
    def listen_for_events(self, vm=None, reconnect=True):
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
                yield from self._listen_for_events(vm)
            except ConnectionRefusedError:
                pass
            if not reconnect:
                break
            self.app.log.warning(
                'Connection to qubesd terminated, reconnecting in {} '
                'seconds'.format(qubesmgmt.config.QUBESD_RECONNECT_DELAY))
            # avoid busy-loop if qubesd is dead
            yield from asyncio.sleep(qubesmgmt.config.QUBESD_RECONNECT_DELAY)

    @asyncio.coroutine
    def _listen_for_events(self, vm=None):
        '''
        Listen for events and call appropriate handlers.
        This function do not exit until manually terminated.

        This is coroutine.

        :param vm: Listen for events only for this VM, use None to listen for
        events about all VMs and not related to any particular VM.
        :return: True if any event was received, otherwise False
        :rtype: bool
        '''

        reader, cleanup_func = yield from self._get_events_reader(vm)
        try:
            some_event_received = False
            while not reader.at_eof():
                try:
                    event_data = yield from reader.readuntil(b'\0\0')
                    if event_data == b'1\0\0':
                        # event with non-VM subject contains \0\0 inside of
                        # event, need to receive rest of the data
                        event_data += yield from reader.readuntil(b'\0\0')
                except asyncio.IncompleteReadError as err:
                    if err.partial == b'':
                        break
                    else:
                        raise

                if not event_data.startswith(b'1\0'):
                    raise qubesmgmt.exc.QubesDaemonCommunicationError(
                        'Non-event received on events connection: '
                        + repr(event_data))
                event_data = event_data.decode('utf-8')
                _, subject, event, *kwargs = event_data.split('\0')
                # convert list to dict, remove last empty entry
                kwargs = dict(zip(kwargs[:-2:2], kwargs[1:-2:2]))
                self.handle(subject, event, **kwargs)

                some_event_received = True
        finally:
            cleanup_func()
        return some_event_received

    def handle(self, subject, event, **kwargs):
        '''Call handlers for given event'''
        if subject:
            subject = self.app.domains[subject]
        else:
            subject = None
        for handler in self.handlers.get(event, []):
            handler(subject, event, **kwargs)
        for handler in self.handlers.get('*', []):
            handler(subject, event, **kwargs)
