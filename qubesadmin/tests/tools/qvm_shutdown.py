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

# pylint: disable=missing-docstring

import asyncio
import unittest.mock

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_shutdown


class TC_00_qvm_shutdown(qubesadmin.tests.QubesTestCase):
    def test_000_with_vm(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', None, None)] = b'0\x00'
        qubesadmin.tools.qvm_shutdown.main(['some-vm'], app=self.app)
        self.assertAllCalled()

    def test_001_missing_vm(self):
        with self.assertRaises(SystemExit):
            with qubesadmin.tests.tools.StderrBuffer() as stderr:
                qubesadmin.tools.qvm_shutdown.main([], app=self.app)
        self.assertIn('one of the arguments --all VMNAME is required',
            stderr.getvalue())
        self.assertAllCalled()

    def test_002_invalid_vm(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        with self.assertRaises(SystemExit):
            with qubesadmin.tests.tools.StderrBuffer() as stderr:
                qubesadmin.tools.qvm_shutdown.main(['no-such-vm'], app=self.app)
        self.assertIn('no such domain', stderr.getvalue())
        self.assertAllCalled()

    def test_003_not_running(self):
        # TODO: some option to ignore this error?
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', None, None)] = \
            b'2\x00QubesVMNotStartedError\x00\x00Domain is powered off: ' \
            b'some-vm\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Halted\n'
        qubesadmin.tools.qvm_shutdown.main(['some-vm'], app=self.app)
        self.assertAllCalled()

    def test_004_multiple_vms(self):
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Shutdown', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        qubesadmin.tools.qvm_shutdown.main(['some-vm', 'other-vm'],
                                           app=self.app)
        self.assertAllCalled()

    @unittest.skipUnless(qubesadmin.tools.qvm_shutdown.have_events,
        'Events not present')
    def test_010_wait(self):
        '''test --wait option'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_events = unittest.mock.AsyncMock()
        patch = unittest.mock.patch(
            'qubesadmin.events.EventsDispatcher._get_events_reader',
            mock_events)
        patch.start()
        self.addCleanup(patch.stop)
        mock_events.side_effect = qubesadmin.tests.tools.MockEventsReader([
            b'1\0\0connection-established\0\0',
            b'1\0some-vm\0domain-shutdown\0\0',
            ])

        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            [b'0\x00power_state=Running'] + \
            [b'0\x00power_state=Halted']
        qubesadmin.tools.qvm_shutdown.main(['--wait', 'some-vm'], app=self.app)
        self.assertAllCalled()

    @unittest.skipUnless(qubesadmin.tools.qvm_shutdown.have_events,
        'Events not present')
    def test_012_wait_all(self):
        '''test --wait option, with multiple VMs'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_events = unittest.mock.AsyncMock()
        patch = unittest.mock.patch(
            'qubesadmin.events.EventsDispatcher._get_events_reader',
            mock_events)
        patch.start()
        self.addCleanup(patch.stop)
        mock_events.side_effect = qubesadmin.tests.tools.MockEventsReader([
            b'1\0\0connection-established\0\0',
            b'1\0sys-net\0domain-shutdown\0\0',
            b'1\0some-vm\0domain-shutdown\0\0',
            b'1\0other-vm\0domain-shutdown\0\0',
            ])

        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'force', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Shutdown', 'force', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.Shutdown', 'force', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'sys-net class=AppVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('other-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        qubesadmin.tools.qvm_shutdown.main(['--wait', '--all'], app=self.app)
        self.assertAllCalled()

    @unittest.skipUnless(qubesadmin.tools.qvm_shutdown.have_events,
        'Events not present')
    def test_015_wait_all_kill_timeout(self):
        '''test --wait option, with multiple VMs and killing on timeout'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_events = unittest.mock.AsyncMock()
        patch = unittest.mock.patch(
            'qubesadmin.events.EventsDispatcher._get_events_reader',
            mock_events)
        patch.start()
        self.addCleanup(patch.stop)
        mock_events.side_effect = qubesadmin.tests.tools.MockEventsReader([
            b'1\0\0connection-established\0\0',
            b'1\0sys-net\0domain-shutdown\0\0',
            ])

        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'force', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Kill', None, None)] = \
            b'2\x00QubesVMNotStartedError\x00\x00Domain is powered off\x00'
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Shutdown', 'force', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Kill', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.Shutdown', 'force', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.Kill', None, None)] = \
            b'2\x00QubesVMNotStartedError\x00\x00Domain is powered off\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'sys-net class=AppVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = [
            b'0\x00power_state=Running',
            b'0\x00power_state=Running',
        ]
        self.app.expected_calls[
            ('other-vm', 'admin.vm.CurrentState', None, None)] = [
            b'0\x00power_state=Running',
            b'0\x00power_state=Running',
        ]
        self.app.expected_calls[
            ('sys-net', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        with self.assertRaisesRegex(SystemExit, '2'):
            qubesadmin.tools.qvm_shutdown.main(
                ['--wait', '--all', '--timeout=1'], app=self.app)
        self.assertAllCalled()
