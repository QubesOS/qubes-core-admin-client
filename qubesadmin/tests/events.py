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

# pylint: disable=missing-docstring,protected-access


import socket
import subprocess
import asyncio
import unittest
import unittest.mock

import qubesadmin.tests
import qubesadmin.events
from qubesadmin.device_protocol import VirtualDevice, Port


class TC_00_Events(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.app = unittest.mock.MagicMock()
        self.dispatcher = qubesadmin.events.EventsDispatcher(self.app)

    def test_000_handler_specific(self):
        handler = unittest.mock.Mock()
        self.dispatcher.add_handler('some-event', handler)
        self.dispatcher.handle('', 'some-event', arg1='value1')
        handler.assert_called_once_with(None, 'some-event', arg1='value1')
        handler.reset_mock()
        self.dispatcher.handle('test-vm', 'some-event', arg1='value1')
        handler.assert_called_once_with(
            self.app.domains.get_blind('test-vm'), 'some-event', arg1='value1')
        handler.reset_mock()
        self.dispatcher.handle('', 'other-event', arg1='value1')
        self.assertFalse(handler.called)
        self.dispatcher.remove_handler('some-event', handler)
        self.dispatcher.handle('', 'some-event', arg1='value1')
        self.assertFalse(handler.called)

    def test_001_handler_glob(self):
        handler = unittest.mock.Mock()
        self.dispatcher.add_handler('*', handler)
        self.dispatcher.handle('', 'some-event', arg1='value1')
        handler.assert_called_once_with(None, 'some-event', arg1='value1')
        handler.reset_mock()
        self.dispatcher.handle('test-vm', 'some-event', arg1='value1')
        handler.assert_called_once_with(
            self.app.domains.get_blind('test-vm'), 'some-event', arg1='value1')
        handler.reset_mock()
        self.dispatcher.handle('', 'other-event', arg1='value1')
        handler.assert_called_once_with(None, 'other-event', arg1='value1')
        handler.reset_mock()
        self.dispatcher.remove_handler('*', handler)
        self.dispatcher.handle('', 'some-event', arg1='value1')
        self.assertFalse(handler.called)

    def test_002_handler_glob_partial(self):
        handler = unittest.mock.Mock()
        self.dispatcher.add_handler('some-*', handler)
        self.dispatcher.handle('', 'some-event', arg1='value1')
        handler.assert_called_once_with(None, 'some-event', arg1='value1')
        handler.reset_mock()
        self.dispatcher.handle('test-vm', 'some-event', arg1='value1')
        handler.assert_called_once_with(
            self.app.domains.get_blind('test-vm'), 'some-event', arg1='value1')
        handler.reset_mock()
        self.dispatcher.handle('', 'other-event', arg1='value1')
        self.assertFalse(handler.called)
        handler.reset_mock()
        self.dispatcher.remove_handler('some-*', handler)
        self.dispatcher.handle('', 'some-event', arg1='value1')
        self.assertFalse(handler.called)

    def test_003_handler_error(self):
        handler = unittest.mock.Mock()
        self.dispatcher.add_handler('some-event', handler)
        handler2 = unittest.mock.Mock(side_effect=AssertionError)
        self.dispatcher.add_handler('some-event', handler2)
        # should catch the exception
        self.dispatcher.handle('', 'some-event', arg1='value1')
        handler.assert_called_once_with(None, 'some-event', arg1='value1')
        handler2.assert_called_once_with(None, 'some-event', arg1='value1')

    async def mock_get_events_reader(self, stream, cleanup_func, expected_vm,
            vm=None):
        self.assertEqual(expected_vm, vm)
        return stream, cleanup_func

    async def send_events(self, stream, events):
        for event in events:
            stream.feed_data(event)
            await asyncio.sleep(0.01)
        stream.feed_eof()

    def test_010_listen_for_events(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stream = asyncio.StreamReader()
        cleanup_func = unittest.mock.Mock()
        self.dispatcher._get_events_reader = \
            lambda vm=None: self.mock_get_events_reader(stream, cleanup_func,
                None, vm)
        handler = unittest.mock.Mock()
        self.dispatcher.add_handler('some-event', handler)
        events = [
            b'1\0\0some-event\0arg1\0value1\0\0',
            b'1\0some-vm\0some-event\0arg1\0value1\0\0',
            b'1\0some-vm\0some-event\0arg_without_value\0\0arg2\0value\0\0',
            b'1\0some-vm\0other-event\0\0',
        ]
        asyncio.ensure_future(self.send_events(stream, events))
        loop.run_until_complete(self.dispatcher.listen_for_events(
            reconnect=False))
        self.assertEqual(handler.mock_calls, [
            unittest.mock.call(None, 'some-event', arg1='value1'),
            unittest.mock.call(
                self.app.domains.get_blind('some-vm'), 'some-event',
                arg1='value1'),
            unittest.mock.call(
                self.app.domains.get_blind('some-vm'), 'some-event',
                arg_without_value='', arg2='value'),
        ])
        cleanup_func.assert_called_once_with()
        loop.close()

    def mock_open_unix_connection(self, expected_path, sock, path):
        self.assertEqual(expected_path, path)
        return asyncio.open_connection(sock=sock)

    def read_all(self, sock):
        buf = b''
        for data in iter(lambda: sock.recv(4096), b''):
            buf += data
        return buf

    def test_020_get_events_reader_local(self):
        self.app.qubesd_connection_type = 'socket'
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sock1, sock2 = socket.socketpair()
        with unittest.mock.patch('asyncio.open_unix_connection',
                lambda path: self.mock_open_unix_connection(
                    qubesadmin.config.QUBESD_SOCKET, sock1, path)):
            task = asyncio.ensure_future(self.dispatcher._get_events_reader())
            reader = asyncio.ensure_future(loop.run_in_executor(None,
                self.read_all, sock2))
            loop.run_until_complete(asyncio.wait([task, reader]))
            self.assertEqual(reader.result(),
                b'admin.Events+ dom0 name dom0\0')
            self.assertIsInstance(task.result()[0], asyncio.StreamReader)
            cleanup_func = task.result()[1]
            cleanup_func()
            sock2.close()

        # run socket cleanup functions
        loop.stop()
        loop.run_forever()
        loop.close()

    def test_021_get_events_reader_local_vm(self):
        self.app.qubesd_connection_type = 'socket'
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sock1, sock2 = socket.socketpair()
        vm = unittest.mock.Mock()
        vm.name = 'test-vm'
        with unittest.mock.patch('asyncio.open_unix_connection',
                lambda path: self.mock_open_unix_connection(
                    qubesadmin.config.QUBESD_SOCKET, sock1, path)):
            task = asyncio.ensure_future(self.dispatcher._get_events_reader(vm))
            reader = asyncio.ensure_future(loop.run_in_executor(None,
                self.read_all, sock2))
            loop.run_until_complete(asyncio.wait([task, reader]))
            self.assertEqual(reader.result(),
                b'admin.Events+ dom0 name test-vm\0')
            self.assertIsInstance(task.result()[0], asyncio.StreamReader)
            cleanup_func = task.result()[1]
            cleanup_func()
            sock2.close()

        # run socket cleanup functions
        loop.stop()
        loop.run_forever()
        loop.close()

    async def mock_coroutine(self, mock, *args, **kwargs):
        return mock(*args, **kwargs)

    def test_022_get_events_reader_remote(self):
        self.app.qubesd_connection_type = 'qrexec'
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mock_proc = unittest.mock.Mock()
        with unittest.mock.patch('asyncio.create_subprocess_exec',
                lambda *args, **kwargs: self.mock_coroutine(mock_proc,
                    *args, **kwargs)):
            task = asyncio.ensure_future(self.dispatcher._get_events_reader())
            loop.run_until_complete(task)
            self.assertEqual(mock_proc.mock_calls, [
                unittest.mock.call('qrexec-client-vm', 'dom0',
                    'admin.Events', stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE),
                unittest.mock.call().stdin.write_eof()
            ])
            self.assertEqual(task.result()[0], mock_proc().stdout)
            cleanup_func = task.result()[1]
            cleanup_func()
            unittest.mock.call().kill.assert_called_once_with()

        loop.close()

    def test_023_get_events_reader_remote_vm(self):
        self.app.qubesd_connection_type = 'qrexec'
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mock_proc = unittest.mock.Mock()
        vm = unittest.mock.Mock()
        vm.name = 'test-vm'
        with unittest.mock.patch('asyncio.create_subprocess_exec',
                lambda *args, **kwargs: self.mock_coroutine(mock_proc,
                    *args, **kwargs)):
            task = asyncio.ensure_future(self.dispatcher._get_events_reader(vm))
            loop.run_until_complete(task)
            self.assertEqual(mock_proc.mock_calls, [
                unittest.mock.call('qrexec-client-vm', 'test-vm',
                    'admin.Events', stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE),
                unittest.mock.call().stdin.write_eof()
            ])
            self.assertEqual(task.result()[0], mock_proc().stdout)
            cleanup_func = task.result()[1]
            cleanup_func()
            unittest.mock.call().kill.assert_called_once_with()

        loop.close()

    def test_030_events_device(self):
        handler = unittest.mock.Mock()
        self.dispatcher.add_handler('device-attach:test', handler)
        self.dispatcher.handle('test-vm', 'device-attach:test',
            device='test-vm2:dev:id', options='{}')
        vm = self.app.domains.get_blind('test-vm')
        self.app.domains.get_blind('test-vm2').devices = {
            'test': {'dev': VirtualDevice(
                Port(self.app.domains.get_blind('test-vm2'),"dev", "test"),
                device_id="id")}}
        dev = self.app.domains.get_blind('test-vm2').devices['test']['dev']
        handler.assert_called_once_with(vm, 'device-attach:test', device=dev,
            options='{}')
