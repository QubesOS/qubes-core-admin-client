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
from collections import Counter

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_shutdown


def _in_use(*names):
    '''qubesd reply for QubesVMInUseError, as raised by the NetVM
    ``domain-pre-shutdown`` guard.'''
    return (
        b'2\x00QubesVMInUseError\x00\x00'
        b'There are other VMs connected to this VM: '
        + ', '.join(names).encode() + b'\x00'
    )


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

        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'wait', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        qubesadmin.tools.qvm_shutdown.main(['--wait', 'some-vm'], app=self.app)
        self.assertAllCalled()

    def test_012_wait_all(self):
        '''test --wait option, with multiple VMs'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'force+wait', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Shutdown', 'force+wait', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.Shutdown', 'force+wait', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'sys-net class=AppVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        qubesadmin.tools.qvm_shutdown.main(['--wait', '--all'], app=self.app)
        self.assertAllCalled()

    def test_015_wait_all_kill_timeout(self):
        '''test --wait option, with multiple VMs and killing on timeout'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'force+wait', None)] = \
            b'2\x00QubesVMShutdownTimeoutError\x00\x00Shutdown timed out\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Kill', None, None)] = \
            b'2\x00QubesVMNotStartedError\x00\x00Domain is powered off\x00'
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Shutdown', 'force+wait', None)] = \
            b'2\x00QubesVMShutdownTimeoutError\x00\x00Shutdown timed out\x00'
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Kill', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.Shutdown', 'force+wait', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'sys-net class=AppVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        qubesadmin.tools.qvm_shutdown.main(['--wait', '--all'], app=self.app)
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

    def test_011_wait_retry_simple(self):
        '''test --wait retries VMs whose shutdown request failed'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'wait', None)] = \
            b'0\x00'
        # other-vm fails first attempt, succeeds on retry
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Shutdown', 'wait', None)] = [
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
            b'0\x00',
        ]
        qubesadmin.tools.qvm_shutdown.main(
            ['--wait', 'some-vm', 'other-vm'], app=self.app)
        self.assertAllCalled()

    def test_011_wait_retry_once_succeed(self):
        '''test --wait retry quits early if none fail'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\x00'
            b'some-vm class=AppVM state=Running\n'
            b'other-vm class=AppVM state=Running\n'
            b'another-vm class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'wait', None)] = [
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
            b'0\x00'
        ]
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Shutdown', 'wait', None)] = [
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
            b'0\x00',
        ]
        self.app.expected_calls[
            ('another-vm', 'admin.vm.Shutdown', 'wait', None)] = [
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
            b'0\x00',
        ]
        qubesadmin.tools.qvm_shutdown.main(
            ['--wait', 'some-vm', 'other-vm', 'another-vm'], app=self.app)
        self.assertAllCalled()

    def test_011_wait_retry_once_fail(self):
        '''test --wait retry quits early if none succeed'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\x00'
            b'some-vm class=AppVM state=Running\n'
            b'other-vm class=AppVM state=Running\n'
            b'another-vm class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'wait', None)] = [
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
        ]
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Shutdown', 'wait', None)] = [
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
        ]
        self.app.expected_calls[
            ('another-vm', 'admin.vm.Shutdown', 'wait', None)] = [
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
        ]
        with self.assertRaises(SystemExit) as cmg:
            qubesadmin.tools.qvm_shutdown.main(
                ['--wait', 'some-vm', 'other-vm', 'another-vm'], app=self.app)
        self.assertEqual(cmg.exception.code, 3)
        self.assertAllCalled()

    def test_011_wait_retry_as_many_as_in_use(self):
        '''test --wait retries VMs whose shutdown request failed as many as
        there were used qubes'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        # some-vm fails first attempt, succeeds on retry
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'wait', None)] = [
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00', \
            b'0\x00'
        ]
        # other-vm fails first and second attempt, succeeds on retry
        self.app.expected_calls[
            ('other-vm', 'admin.vm.Shutdown', 'wait', None)] = [
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00', \
            b'2\x00QubesVMInUseError\x00\x00Denied as qube is in use\x00',
            b'0\x00',
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
            ('some-vm', 'admin.vm.Shutdown', 'wait', None)] = \
            b'2\x00QubesException\x00\x00Shutdown refused\x00'
        with self.assertRaises(SystemExit) as cmg:
            qubesadmin.tools.qvm_shutdown.main(
                ['--wait', 'some-vm'], app=self.app)
        self.assertEqual(cmg.exception.code, 1)
        self.assertAllCalled()

    def test_014_timeout_deprecated_means_wait(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'wait', None)] = \
            b'2\x00QubesVMShutdownTimeoutError\x00\x00Shutdown timed out\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Kill', None, None)] = \
            b'2\x00QubesException\x00\x00Kill failed\x00'
        with self.assertRaises(SystemExit) as cmg:
            qubesadmin.tools.qvm_shutdown.main(
                ['--timeout=3', 'some-vm'], app=self.app)
        self.assertEqual(cmg.exception.code, 1)
        self.assertAllCalled()

    def test_016_wait_kill_exception(self):
        '''test --wait timeout where kill raises QubesException'''
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Shutdown', 'wait', None)] = \
            b'2\x00QubesVMShutdownTimeoutError\x00\x00Shutdown timed out\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Kill', None, None)] = \
            b'2\x00QubesException\x00\x00Kill failed\x00'
        with self.assertRaises(SystemExit) as cmg:
            qubesadmin.tools.qvm_shutdown.main(
                ['--wait', 'some-vm'], app=self.app)
        self.assertEqual(cmg.exception.code, 1)
        self.assertAllCalled()

    def test_018_wait_netvm_chain(self):
        '''--wait drains a three-level NetVM chain (qubes-issues#10860)

        The reported command, ``qvm-shutdown sys-net sys-firewall
        sys-whonix``, is modelled with scripted replies for a chain where
        ``sys-net`` provides network to ``sys-firewall``, which provides
        network to ``sys-whonix``.  Each provider's first attempt is
        refused with ``QubesVMInUseError`` and a later attempt is accepted,
        which exercises the client's retry path over the whole chain -
        including its retry-count boundary, as ``sys-net`` is accepted only
        on the client's last permitted retry pass.

        This is a client unit test with *scripted* server replies, not a
        live server lifecycle test.  Replies are fixed per (qube, attempt)
        and returned immediately: the mock does not simulate shutdown
        timing, and it does not check that a dependent has actually halted
        before its provider succeeds.  The test therefore covers only the
        client side - that ``--wait`` retries the chain to completion and
        that every shutdown request carries the ``wait`` argument - and it
        does not independently verify real server-side shutdown ordering or
        lifecycle.
        '''
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00' \
            b'sys-net class=AppVM state=Running\n' \
            b'sys-firewall class=AppVM state=Running\n' \
            b'sys-whonix class=AppVM state=Running\n'
        # Scripted replies, one consumed per attempt.  sys-whonix is the end
        # of the chain, so its first attempt is accepted.
        self.app.expected_calls[
            ('sys-whonix', 'admin.vm.Shutdown', 'wait', None)] = b'0\x00'
        # sys-firewall: refused once, accepted on the retry.
        self.app.expected_calls[
            ('sys-firewall', 'admin.vm.Shutdown', 'wait', None)] = [
            _in_use('sys-whonix'), b'0\x00']
        # sys-net: refused twice, accepted on the third attempt.
        self.app.expected_calls[
            ('sys-net', 'admin.vm.Shutdown', 'wait', None)] = [
            _in_use('sys-firewall'), _in_use('sys-firewall'), b'0\x00']
        # A failed shutdown exits non-zero (raises SystemExit); returning
        # without one means the client ended with no failed qubes.
        qubesadmin.tools.qvm_shutdown.main(
            ['--wait', 'sys-net', 'sys-firewall', 'sys-whonix'], app=self.app)
        self.assertAllCalled()
        # Every qube is attempted once per pass, so the retry counts follow
        # the scripted chain depth: 1, 2 and 3 attempts.  Order *within* a
        # pass is concurrent (asyncio.to_thread), so these per-qube counts -
        # not a global call sequence - are what can be asserted reliably.
        self.assertEqual(
            Counter(
                dest
                for dest, method, _arg, _payload in self.app.actual_calls
                if method == 'admin.vm.Shutdown'
            ),
            {'sys-whonix': 1, 'sys-firewall': 2, 'sys-net': 3},
        )
