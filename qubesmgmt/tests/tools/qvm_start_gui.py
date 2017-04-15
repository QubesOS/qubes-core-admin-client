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
import os
import tempfile
import unittest.mock

import asyncio

import qubesmgmt.tests
import qubesmgmt.tools.qvm_start_gui


class TC_00_qvm_start_gui(qubesmgmt.tests.QubesTestCase):
    def setUp(self):
        super(TC_00_qvm_start_gui, self).setUp()
        self.launcher = qubesmgmt.tools.qvm_start_gui.GUILauncher(self.app)

    @unittest.mock.patch('subprocess.check_output')
    def test_000_kde_args(self, proc_mock):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'label', None)] = \
                b'0\x00default=False type=label red'
        self.app.expected_calls[
            ('dom0', 'mgmt.label.List', None, None)] = \
            b'0\x00red\n'

        proc_mock.side_effect = [
            b'KWIN_RUNNING = 0x1\n',
            b'access control enabled, only authorized clients can connect\n'
            b'SI:localuser:root\n'
            b'SI:localuser:' + os.getlogin().encode() + b'\n',
        ]

        args = self.launcher.kde_guid_args(self.app.domains['test-vm'])
        self.assertEqual(args, ['-T', '-p',
            '_KDE_NET_WM_COLOR_SCHEME=s:' +
            os.path.expanduser('~/.local/share/qubes-kde/red.colors')])

        self.assertAllCalled()

    @unittest.mock.patch('subprocess.check_output')
    def test_001_kde_args_none(self, proc_mock):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'

        proc_mock.side_effect = [b'']

        args = self.launcher.kde_guid_args(self.app.domains['test-vm'])
        self.assertEqual(args, [])

        self.assertAllCalled()

    def test_010_common_args(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'label', None)] = \
                b'0\x00default=False type=label red'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'debug', None)] = \
                b'0\x00default=False type=bool False'
        self.app.expected_calls[
            ('dom0', 'mgmt.label.List', None, None)] = \
            b'0\x00red\n'
        self.app.expected_calls[
            ('dom0', 'mgmt.label.Get', 'red', None)] = \
            b'0\x000xff0000'
        self.app.expected_calls[
            ('dom0', 'mgmt.label.Index', 'red', None)] = \
            b'0\x001'

        with unittest.mock.patch.object(self.launcher, 'kde_guid_args') as \
                kde_mock:
            kde_mock.return_value = []

            args = self.launcher.common_guid_args(self.app.domains['test-vm'])
            self.assertEqual(args, [
                '/usr/bin/qubes-guid', '-N', 'test-vm',
                '-c', '0xff0000',
                '-i', '/usr/share/icons/hicolor/128x128/devices/appvm-red.png',
                '-l', '1', '-q'])

        self.assertAllCalled()

    def test_011_common_args_debug(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'label', None)] = \
                b'0\x00default=False type=label red'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'debug', None)] = \
                b'0\x00default=False type=bool True'
        self.app.expected_calls[
            ('dom0', 'mgmt.label.List', None, None)] = \
            b'0\x00red\n'
        self.app.expected_calls[
            ('dom0', 'mgmt.label.Get', 'red', None)] = \
            b'0\x000xff0000'
        self.app.expected_calls[
            ('dom0', 'mgmt.label.Index', 'red', None)] = \
            b'0\x001'

        with unittest.mock.patch.object(self.launcher, 'kde_guid_args') as \
                kde_mock:
            kde_mock.return_value = []

            args = self.launcher.common_guid_args(self.app.domains['test-vm'])
            self.assertEqual(args, [
                '/usr/bin/qubes-guid', '-N', 'test-vm',
                '-c', '0xff0000',
                '-i', '/usr/share/icons/hicolor/128x128/devices/appvm-red.png',
                '-l', '1', '-v', '-v'])

        self.assertAllCalled()

    @unittest.mock.patch('asyncio.create_subprocess_exec')
    def test_020_start_gui_for_vm(self, proc_mock):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'xid', None)] = \
                b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'hvm', None)] = \
                b'0\x00default=False type=bool False'
        with unittest.mock.patch.object(self.launcher,
                'common_guid_args', lambda vm: []):
            self.launcher.start_gui_for_vm(self.app.domains['test-vm'])
            # common arguments dropped for simplicity
            proc_mock.assert_called_once_with('-d', '3000')

        self.assertAllCalled()

    @unittest.mock.patch('asyncio.create_subprocess_exec')
    def test_021_start_gui_for_vm_hvm(self, proc_mock):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'xid', None)] = \
                b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'stubdom_xid', None)] = \
                b'0\x00default=False type=int 3001'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'hvm', None)] = \
                b'0\x00default=False type=bool True'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'debug', None)] = \
                b'0\x00default=False type=bool False'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.feature.CheckWithTemplate', 'rpc-clipboard',
            None)] = \
                b'0\x00True'
        with unittest.mock.patch.object(self.launcher,
                'common_guid_args', lambda vm: []):
            self.launcher.start_gui_for_vm(self.app.domains['test-vm'])
            # common arguments dropped for simplicity
            proc_mock.assert_called_once_with('-d', '3000', '-n', '-Q')

        self.assertAllCalled()

    def test_022_start_gui_for_vm_hvm_stubdom(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'xid', None)] = \
                b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'stubdom_xid', None)] = \
                b'0\x00default=False type=int 3001'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'hvm', None)] = \
                b'0\x00default=False type=bool True'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'debug', None)] = \
                b'0\x00default=False type=bool False'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.feature.CheckWithTemplate', 'rpc-clipboard',
            None)] = \
                b'0\x00True'
        pidfile = tempfile.NamedTemporaryFile()
        pidfile.write(b'1234\n')
        pidfile.flush()
        self.addCleanup(pidfile.close)

        patch_proc = unittest.mock.patch('asyncio.create_subprocess_exec')
        patch_args = unittest.mock.patch.object(self.launcher,
            'common_guid_args', lambda vm: [])
        patch_pidfile = unittest.mock.patch.object(self.launcher,
            'guid_pidfile', lambda vm: pidfile.name)
        try:
            mock_proc = patch_proc.start()
            patch_args.start()
            patch_pidfile.start()
            self.launcher.start_gui_for_vm(self.app.domains['test-vm'])
            # common arguments dropped for simplicity
            mock_proc.assert_called_once_with(
                '-d', '3000', '-n', '-Q', '-K', '1234')
        finally:
            unittest.mock.patch.stopall()

        self.assertAllCalled()

    def test_030_start_gui_for_stubdomain(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'xid', None)] = \
                b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'stubdom_xid', None)] = \
                b'0\x00default=False type=int 3001'
        with unittest.mock.patch('asyncio.create_subprocess_exec') as proc_mock:
            with unittest.mock.patch.object(self.launcher,
                    'common_guid_args', lambda vm: []):
                self.launcher.start_gui_for_stubdomain(
                    self.app.domains['test-vm'])
                # common arguments dropped for simplicity
                proc_mock.assert_called_once_with('-d', '3001', '-t', '3000')

        self.assertAllCalled()

    @asyncio.coroutine
    def mock_coroutine(self, mock, *args):
        mock(*args)

    def test_040_start_gui(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.feature.CheckWithTemplate', 'gui', None)] = \
            b'0\x00True'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.feature.CheckWithTemplate',
            'no-monitor-layout', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'hvm', None)] = \
                b'0\x00default=False type=bool True'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'xid', None)] = \
                b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.property.Get', 'stubdom_xid', None)] = \
                b'0\x00default=False type=int 3001'

        vm = self.app.domains['test-vm']
        mock_start_vm = unittest.mock.Mock()
        mock_start_stubdomain = unittest.mock.Mock()
        patch_start_vm = unittest.mock.patch.object(
            self.launcher, 'start_gui_for_vm', lambda vm_:
            self.mock_coroutine(mock_start_vm, vm_))
        patch_start_stubdomain = unittest.mock.patch.object(
            self.launcher, 'start_gui_for_stubdomain', lambda vm_:
            self.mock_coroutine(mock_start_stubdomain, vm_))
        try:
            patch_start_vm.start()
            patch_start_stubdomain.start()
            loop.run_until_complete(self.launcher.start_gui(vm))
            mock_start_vm.assert_called_once_with(vm)
            mock_start_stubdomain.assert_called_once_with(vm)
        finally:
            unittest.mock.patch.stopall()

    def test_041_start_gui_running(self):
        # simulate existing pidfiles, should not start processes
        self.skipTest('todo')

    def test_042_start_gui_pvh(self):
        # PVH - no stubdomain
        self.skipTest('todo')

    @unittest.mock.patch('subprocess.Popen')
    def test_050_get_monitor_layout1(self, proc_mock):
        proc_mock().stdout = b'''Screen 0: minimum 8 x 8, current 1920 x 1200, maximum 32767 x 32767
HDMI1 connected 1920x1200+0+0 (normal left inverted right x axis y axis) 518mm x 324mm
   1920x1200     59.95*+
   1920x1080     60.00    50.00    59.94
   1920x1080i    60.00    50.00    59.94
   1600x1200     60.00
   1680x1050     59.88
   1280x1024     60.02
   1440x900      59.90
   1280x960      60.00
   1280x720      60.00    50.00    59.94
   1024x768      60.00
   800x600       60.32
   720x576       50.00
   720x480       60.00    59.94
   720x480i      60.00    59.94
   640x480       60.00    59.94
HDMI2 disconnected (normal left inverted right x axis y axis)
VGA1 disconnected (normal left inverted right x axis y axis)
VIRTUAL1 disconnected (normal left inverted right x axis y axis)
'''.splitlines()
        self.assertEqual(qubesmgmt.tools.qvm_start_gui.get_monitor_layout(),
            ['1920 1200 0 0\n'])

    @unittest.mock.patch('subprocess.Popen')
    def test_051_get_monitor_layout_multiple(self, proc_mock):
        proc_mock().stdout = b'''Screen 0: minimum 8 x 8, current 2880 x 1024, maximum 32767 x 32767
LVDS1 connected 1600x900+0+0 (normal left inverted right x axis y axis)
VGA1 connected 1280x1024+1600+0 (normal left inverted right x axis y axis)
'''.splitlines()
        self.assertEqual(qubesmgmt.tools.qvm_start_gui.get_monitor_layout(),
            ['1600 900 0 0\n', '1280 1024 1600 0\n'])

    @unittest.mock.patch('subprocess.Popen')
    def test_052_get_monitor_layout_hidpi1(self, proc_mock):
        proc_mock().stdout = b'''Screen 0: minimum 8 x 8, current 1920 x 1200, maximum 32767 x 32767
HDMI1 connected 2560x1920+0+0 (normal left inverted right x axis y axis) 372mm x 208mm
   1920x1200     60.00*+
'''.splitlines()
        dpi = 150
        self.assertEqual(qubesmgmt.tools.qvm_start_gui.get_monitor_layout(),
            ['2560 1920 0 0 {} {}\n'.format(
                int(2560/dpi*254/10), int(1920/dpi*254/10))])

    @unittest.mock.patch('subprocess.Popen')
    def test_052_get_monitor_layout_hidpi2(self, proc_mock):
        proc_mock().stdout = b'''Screen 0: minimum 8 x 8, current 1920 x 1200, maximum 32767 x 32767
HDMI1 connected 2560x1920+0+0 (normal left inverted right x axis y axis) 310mm x 174mm
   1920x1200     60.00*+
'''.splitlines()
        dpi = 200
        self.assertEqual(qubesmgmt.tools.qvm_start_gui.get_monitor_layout(),
            ['2560 1920 0 0 {} {}\n'.format(
                int(2560/dpi*254/10), int(1920/dpi*254/10))])

    @unittest.mock.patch('subprocess.Popen')
    def test_052_get_monitor_layout_hidpi3(self, proc_mock):
        proc_mock().stdout = b'''Screen 0: minimum 8 x 8, current 1920 x 1200, maximum 32767 x 32767
HDMI1 connected 2560x1920+0+0 (normal left inverted right x axis y axis) 206mm x 116mm
   1920x1200     60.00*+
'''.splitlines()
        dpi = 300
        self.assertEqual(qubesmgmt.tools.qvm_start_gui.get_monitor_layout(),
            ['2560 1920 0 0 {} {}\n'.format(
                int(2560/dpi*254/10), int(1920/dpi*254/10))])
