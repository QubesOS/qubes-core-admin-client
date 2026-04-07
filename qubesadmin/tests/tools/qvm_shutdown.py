# -*- encoding: utf-8 -*-
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
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'sys-net class=AppVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = [
            b'0\x00power_state=Running',
            b'0\x00power_state=Running',
            b'0\x00power_state=Running',
        ]
        self.app.expected_calls[
            ('other-vm', 'admin.vm.CurrentState', None, None)] = [
            b'0\x00power_state=Running',
            b'0\x00power_state=Running',
            b'0\x00power_state=Running',
        ]
        self.app.expected_calls[
            ('sys-net', 'admin.vm.CurrentState', None, None)] = [
            b'0\x00power_state=Halted',
            b'0\x00power_state=Halted',
            b'0\x00power_state=Halted',
        ]
        with self.assertRaisesRegex(SystemExit, '2'):
            qubesadmin.tools.qvm_shutdown.main(
                ['--wait', '--all', '--timeout=1'], app=self.app)
        self.assertAllCalled()

    def test_016_all_exclude_noforce(self):
        '''test --all --exclude does NOT imply --force'''
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        qubesadmin.tools.qvm_shutdown.main(['--all', '--exclude', 'other-vm'],
                                           app=self.app)
        self.assertAllCalled()

    def test_017_all_exclude_force_explicit(self):
        '''test --all --exclude --force DOES imply --force'''
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'force', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        qubesadmin.tools.qvm_shutdown.main(['--all', '--exclude', 'other-vm',
                                            '--force'],
                                           app=self.app)
        self.assertAllCalled()

    def test_005_force(self):
        '''test --force sends force flag to shutdown call'''
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'force', None)] = b'0\x00'
        qubesadmin.tools.qvm_shutdown.main(
            ['--force', 'some-vm'], app=self.app)
        self.assertAllCalled()

    def test_006_dry_run(self):
        '''test --dry-run skips shutdown calls'''
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        qubesadmin.tools.qvm_shutdown.main(
            ['--dry-run', 'some-vm'], app=self.app)
        self.assertAllCalled()

    def test_011_wait_retry(self):
        '''test --wait retries VMs whose shutdown request failed'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_events = unittest.mock.AsyncMock()
        patch = unittest.mock.patch(
            'qubesadmin.events.EventsDispatcher._get_events_reader',
            mock_events)
        patch.start()
        self.addCleanup(patch.stop)
        mock_events.side_effect = qubesadmin.tests.tools.MockEventsReader([
            # round 1: wait for some-vm
            b'1\0\0connection-established\0\0',
            b'1\0some-vm\0domain-shutdown\0\0',
            # round 2: wait for other-vm
            b'1\0\0connection-established\0\0',
            b'1\0other-vm\0domain-shutdown\0\0',
            ])

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', None, None)] = \
            b'0\x00'
        # other-vm fails first attempt, succeeds on retry
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Shutdown', None, None)] = [
            b'2\x00QubesException\x00\x00Shutdown refused\x00',
            b'0\x00',
        ]
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = [
            b'0\x00power_state=Running',
            b'0\x00power_state=Halted',
        ]
        self.app.expected_calls[
            ('other-vm', 'admin.vm.CurrentState', None, None)] = [
            b'0\x00power_state=Running',
            b'0\x00power_state=Halted',
        ]
        qubesadmin.tools.qvm_shutdown.main(
            ['--wait', 'some-vm', 'other-vm'], app=self.app)
        self.assertAllCalled()

    def test_013_wait_all_shutdown_fail(self):
        '''test --wait exits with error when all shutdown requests fail'''
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', None, None)] = \
            b'2\x00QubesException\x00\x00Shutdown refused\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_shutdown.main(
                ['--wait', 'some-vm'], app=self.app)
        self.assertAllCalled()

    def test_016_wait_kill_exception(self):
        '''test --wait timeout where kill raises QubesException'''
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
            ])

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Kill', None, None)] = \
            b'2\x00QubesException\x00\x00Kill failed\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = [
            b'0\x00power_state=Running',
            b'0\x00power_state=Running',
        ]
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_shutdown.main(
                ['--wait', '--timeout=1', 'some-vm'], app=self.app)
        self.assertAllCalled()

    def test_017_wait_dispvm_na(self):
        '''test --wait treats DispVM with NA power state as shut down'''
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
            b'1\0disp123\0domain-shutdown\0\0',
            ])

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00disp123 class=DispVM state=Running\n'
        self.app.expected_calls[
            ('disp123', 'admin.vm.Shutdown', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('disp123', 'admin.vm.CurrentState', None, None)] = [
            b'0\x00power_state=Running',
            # failed_domains: first get_power_state() != 'Halted',
            # then klass == 'DispVM' triggers second get_power_state()
            b'0\x00power_state=NA',
            b'0\x00power_state=NA',
        ]
        qubesadmin.tools.qvm_shutdown.main(
            ['--wait', 'disp123'], app=self.app)
        self.assertAllCalled()
