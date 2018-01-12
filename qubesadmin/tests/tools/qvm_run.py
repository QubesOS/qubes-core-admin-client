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

import io
import os
import unittest.mock

import subprocess
import sys

import qubesadmin.tests
import qubesadmin.tools.qvm_run


class TC_00_qvm_run(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        if sys.stdout is not sys.__stdout__ or \
                sys.stderr is not sys.__stderr__:
            self.skipTest('qvm-run change behavior on redirected stdout/stderr')
        super(TC_00_qvm_run, self).setUp()

    def default_filter_esc(self):
        return os.isatty(sys.stdout.fileno())

    def test_000_run_single(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        ret = qubesadmin.tools.qvm_run.main(
            ['--no-gui', 'test-vm', 'command'],
            app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {
                'localcmd': None,
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'user': None,
            }),
            ('test-vm', 'qubes.VMShell', b'command; exit\n')
        ])
        self.assertAllCalled()

    def test_001_run_multiple(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n' \
            b'test-vm3 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm2 class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm3', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm3 class=AppVM state=Halted\n'
        ret = qubesadmin.tools.qvm_run.main(
            ['--no-gui', '--all', 'command'],
            app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {
                'localcmd': None,
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'user': None,
            }),
            ('test-vm', 'qubes.VMShell', b'command; exit\n'),
            ('test-vm2', 'qubes.VMShell', {
                'localcmd': None,
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'user': None,
            }),
            ('test-vm2', 'qubes.VMShell', b'command; exit\n')
        ])
        self.assertAllCalled()

    @unittest.expectedFailure
    def test_002_passio(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        echo = subprocess.Popen(['echo', 'some-data'], stdout=subprocess.PIPE)
        with unittest.mock.patch('sys.stdin', echo.stdout):
            ret = qubesadmin.tools.qvm_run.main(
                ['--no-gui', '--pass-io', 'test-vm', 'command'],
                app=self.app)

        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {
                'filter_esc': self.default_filter_esc(),
                'localcmd': None,
                'stdout': None,
                'stderr': None,
                'user': None,
            }),
            ('test-vm', 'qubes.VMShell', b'command; exit\nsome-data\n')
        ])
        self.assertAllCalled()

    @unittest.expectedFailure
    def test_002_color_output(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        stdout = io.StringIO()
        echo = subprocess.Popen(['echo', 'some-data'], stdout=subprocess.PIPE)
        with unittest.mock.patch('sys.stdin', echo.stdout):
            with unittest.mock.patch('sys.stdout', stdout):
                ret = qubesadmin.tools.qvm_run.main(
                    ['--no-gui', '--filter-esc', '--pass-io', 'test-vm',
                        'command'],
                    app=self.app)

        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {
                'filter_esc': True,
                'localcmd': None,
                'stdout': None,
                'stderr': None,
                'user': None,
            }),
            ('test-vm', 'qubes.VMShell', b'command; exit\nsome-data\n')
        ])
        self.assertEqual(stdout.getvalue(), '\033[0;31m\033[0m')
        stdout.close()
        self.assertAllCalled()

    @unittest.expectedFailure
    def test_003_no_color_output(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        stdout = io.StringIO()
        echo = subprocess.Popen(['echo', 'some-data'], stdout=subprocess.PIPE)
        with unittest.mock.patch('sys.stdin', echo.stdout):
            with unittest.mock.patch('sys.stdout', stdout):
                ret = qubesadmin.tools.qvm_run.main(
                    ['--no-gui', '--pass-io', '--no-color-output',
                        'test-vm', 'command'],
                    app=self.app)

        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {
                'filter_esc': self.default_filter_esc(),
                'localcmd': None,
                'stdout': None,
                'stderr': None,
                'user': None,
            }),
            ('test-vm', 'qubes.VMShell', b'command; exit\nsome-data\n')
        ])
        self.assertEqual(stdout.getvalue(), '')
        stdout.close()
        self.assertAllCalled()

    @unittest.expectedFailure
    def test_004_no_filter_esc(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        stdout = io.StringIO()
        echo = subprocess.Popen(['echo', 'some-data'], stdout=subprocess.PIPE)
        with unittest.mock.patch('sys.stdin', echo.stdout):
            with unittest.mock.patch('sys.stdout', stdout):
                ret = qubesadmin.tools.qvm_run.main(
                    ['--no-gui', '--pass-io', '--no-filter-esc',
                        'test-vm', 'command'],
                    app=self.app)

        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {
                'filter_esc': False,
                'localcmd': None,
                'stdout': None,
                'stderr': None,
                'user': None,
            }),
            ('test-vm', 'qubes.VMShell', b'command; exit\nsome-data\n')
        ])
        self.assertEqual(stdout.getvalue(), '')
        stdout.close()
        self.assertAllCalled()

    def test_005_localcmd(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        ret = qubesadmin.tools.qvm_run.main(
            ['--no-gui', '--pass-io', '--localcmd', 'local-command',
                'test-vm', 'command'],
            app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {
                'localcmd': 'local-command',
                'stdout': None,
                'stderr': None,
                'user': None,
            }),
            ('test-vm', 'qubes.VMShell', b'command; exit\n')
        ])
        self.assertAllCalled()

    def test_006_run_single_with_gui(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'default_user', None)] = \
            b'0\x00default=yes type=str user'
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        ret = qubesadmin.tools.qvm_run.main(
            ['test-vm', 'command'],
            app=self.app)
        self.assertEqual(ret, 0)
        # make sure we have the same instance below
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.WaitForSession', {
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
            }),
            ('test-vm', 'qubes.WaitForSession', b'user'),
            ('test-vm', 'qubes.VMShell', {
                'localcmd': None,
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'user': None,
            }),
            ('test-vm', 'qubes.VMShell', b'command; exit\n')
        ])
        self.assertAllCalled()

    def test_007_run_service_with_gui(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'default_user', None)] = \
            b'0\x00default=yes type=str user'
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        ret = qubesadmin.tools.qvm_run.main(
            ['--service', 'test-vm', 'service.name'],
            app=self.app)
        self.assertEqual(ret, 0)
        # make sure we have the same instance below
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.WaitForSession', {
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
            }),
            ('test-vm', 'qubes.WaitForSession', b'user'),
            ('test-vm', 'service.name', {
                'localcmd': None,
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'user': None,
            }),
            ('test-vm', 'service.name', b''),
        ])
        self.assertAllCalled()

    def test_008_dispvm_remote(self):
        ret = qubesadmin.tools.qvm_run.main(
            ['--dispvm', '--service', 'test.service'], app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('$dispvm', 'test.service', {
                'localcmd': None,
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'user': None,
            }),
            ('$dispvm', 'test.service', b''),
        ])
        self.assertAllCalled()

    def test_009_dispvm_remote_specific(self):
        ret = qubesadmin.tools.qvm_run.main(
            ['--dispvm=test-vm', '--service', 'test.service'], app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('$dispvm:test-vm', 'test.service', {
                'localcmd': None,
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'user': None,
            }),
            ('$dispvm:test-vm', 'test.service', b''),
        ])
        self.assertAllCalled()

    def test_010_dispvm_local(self):
        self.app.qubesd_connection_type = 'socket'
        self.app.expected_calls[
            ('dom0', 'admin.vm.CreateDisposable', None, None)] = \
            b'0\0disp123'
        self.app.expected_calls[('disp123', 'admin.vm.Kill', None, None)] = \
            b'0\0'
        self.app.expected_calls[
            ('disp123', 'admin.vm.property.Get', 'qrexec_timeout', None)] = \
            b'0\0default=yes type=int 30'
        ret = qubesadmin.tools.qvm_run.main(
            ['--dispvm', '--service', 'test.service'], app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('disp123', 'test.service', {
                'localcmd': None,
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'user': None,
                'connect_timeout': 30,
            }),
            ('disp123', 'test.service', b''),
        ])
        self.assertAllCalled()

    def test_011_dispvm_local_specific(self):
        self.app.qubesd_connection_type = 'socket'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CreateDisposable', None, None)] = \
            b'0\0disp123'
        self.app.expected_calls[('disp123', 'admin.vm.Kill', None, None)] = \
            b'0\0'
        self.app.expected_calls[
            ('disp123', 'admin.vm.property.Get', 'qrexec_timeout', None)] = \
            b'0\0default=yes type=int 30'
        ret = qubesadmin.tools.qvm_run.main(
            ['--dispvm=test-vm', '--service', 'test.service'], app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('disp123', 'test.service', {
                'localcmd': None,
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'user': None,
                'connect_timeout': 30,
            }),
            ('disp123', 'test.service', b''),
        ])
        self.assertAllCalled()

    def test_012_exclude(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n' \
            b'test-vm3 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm3', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm3 class=AppVM state=Halted\n'
        ret = qubesadmin.tools.qvm_run.main(
            ['--no-gui', '--all', '--exclude', 'test-vm2', 'command'],
            app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {
                'localcmd': None,
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'user': None,
            }),
            ('test-vm', 'qubes.VMShell', b'command; exit\n'),
        ])
        self.assertAllCalled()

    def test_013_no_autostart(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n' \
            b'test-vm3 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('test-vm3', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm3 class=AppVM state=Halted\n'
        ret = qubesadmin.tools.qvm_run.main(
            ['--no-gui', '--no-autostart', 'test-vm3', 'command'],
            app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [])
        self.assertAllCalled()
