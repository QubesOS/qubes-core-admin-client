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
import functools
import os
import signal
import tempfile
import unittest.mock
import re
import asyncio

import qubesadmin.tests
import qubesadmin.tools.qvm_start_daemon
from  qubesadmin.tools.qvm_start_daemon import GUI_DAEMON_OPTIONS
import qubesadmin.vm


class TC_00_qvm_start_gui(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super(TC_00_qvm_start_gui, self).setUp()
        self.launcher = \
            qubesadmin.tools.qvm_start_daemon.DAEMONLauncher(self.app, ["guivm"])

    @unittest.mock.patch('subprocess.check_output')
    def test_000_kde_args(self, proc_mock):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'label', None)] = \
            b'0\x00default=False type=label red'

        proc_mock.side_effect = [
            b'KWIN_RUNNING = 0x1\n',
            b'access control enabled, only authorized clients can connect\n'
            b'SI:localuser:root\n'
            b'SI:localuser:' + os.environ['USER'].encode() + b'\n',
        ]

        args = self.launcher.kde_guid_args(self.app.domains['test-vm'])
        self.launcher.kde = True
        self.assertEqual(args, ['-T', '-p',
                                '_KDE_NET_WM_COLOR_SCHEME=s:' +
                                os.path.expanduser(
                                    '~/.local/share/qubes-kde/red.colors')])

        self.assertAllCalled()

    def setup_common_args(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n' \
            b'gui-vm class=AppVM state=Running'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'label', None)] = \
            b'0\x00default=False type=label red'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'debug', None)] = \
            b'0\x00default=False type=bool False'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'guivm', None)] = \
            b'0\x00default=False type=vm gui-vm'
        self.app.expected_calls[
            ('dom0', 'admin.label.Get', 'red', None)] = \
            b'0\x000xff0000'
        self.app.expected_calls[
            ('dom0', 'admin.label.Index', 'red', None)] = \
            b'0\x001'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'rpc-clipboard', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'

        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'xid', None)] = \
            b'0\x00default=99 type=int 99'

        for name, _kind in GUI_DAEMON_OPTIONS:
            self.app.expected_calls[
                ('test-vm', 'admin.vm.feature.Get',
                 'gui-' + name.replace('_', '-'), None)] = \
                b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'

            self.app.expected_calls[
                ('gui-vm', 'admin.vm.feature.Get',
                 'gui-default-' + name.replace('_', '-'), None)] = \
                b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'

    def run_common_args(self):
        with unittest.mock.patch.object(
                self.launcher, 'kde_guid_args') as kde_mock, \
             unittest.mock.patch.object(
                 self.launcher, 'write_guid_config') as write_config_mock:
            kde_mock.return_value = []

            args = self.launcher.common_guid_args(self.app.domains['test-vm'])

        self.assertEqual(len(write_config_mock.mock_calls), 1)

        config_args = write_config_mock.mock_calls[0][1]
        self.assertEqual(config_args[0], '/var/run/qubes/guid-conf.99')
        config = config_args[1]

        # Strip comments and empty lines
        config = re.sub(r'^#.*\n', '', config)
        config = re.sub(r'^\n', '', config)

        self.assertAllCalled()
        return args, config

    def test_010_common_args(self):
        self.setup_common_args()

        args, config = self.run_common_args()
        self.assertEqual(args, [
            '/usr/bin/qubes-guid', '-N', 'test-vm',
            '-c', '0xff0000',
            '-i', '/usr/share/icons/hicolor/128x128/devices/appvm-red.png',
            '-l', '1', '-q',
            '-C', '/var/run/qubes/guid-conf.99',
        ])

        self.assertEqual(config, '''\
global: {
}
''')

    def test_011_common_args_debug(self):
        self.setup_common_args()
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'debug', None)] = \
            b'0\x00default=False type=bool True'

        args, config = self.run_common_args()
        self.assertEqual(args, [
            '/usr/bin/qubes-guid', '-N', 'test-vm',
            '-c', '0xff0000',
            '-i', '/usr/share/icons/hicolor/128x128/devices/appvm-red.png',
            '-l', '1', '-v', '-v',
            '-C', '/var/run/qubes/guid-conf.99',
        ])
        self.assertEqual(config, '''\
global: {
}
''')

    def test_012_common_args_rpc_clipboard(self):
        self.setup_common_args()
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'rpc-clipboard', None)] = \
            b'0\x001'

        args, config = self.run_common_args()

        self.assertEqual(args,  [
            '/usr/bin/qubes-guid', '-N', 'test-vm',
            '-c', '0xff0000',
            '-i', '/usr/share/icons/hicolor/128x128/devices/appvm-red.png',
            '-l', '1', '-q', '-Q',
            '-C', '/var/run/qubes/guid-conf.99',
        ])
        self.assertEqual(config, '''\
global: {
}
''')

    def test_013_common_args_guid_config(self):
        self.setup_common_args()

        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Get',
             'gui-allow-fullscreen', None)] = \
                 b'0\x001'
        # The template will not be asked for this feature
        del self.app.expected_calls[
            ('gui-vm', 'admin.vm.feature.Get',
             'gui-default-allow-fullscreen', None)]

        self.app.expected_calls[
            ('gui-vm', 'admin.vm.feature.Get',
             'gui-default-secure-copy-sequence', None)] = \
                 b'0\x00Ctrl-Alt-Shift-c'

        _args, config = self.run_common_args()
        self.assertEqual(config, '''\
global: {
  allow_fullscreen = true;
  secure_copy_sequence = "Ctrl-Alt-Shift-c";
}
''')

    @unittest.mock.patch('asyncio.create_subprocess_exec')
    def test_020_start_gui_for_vm(self, proc_mock):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'xid', None)] = \
            b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'virt_mode', None)] = \
            b'0\x00default=False type=str pv'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'no-monitor-layout', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'
        with unittest.mock.patch.object(self.launcher,
                                        'common_guid_args', lambda vm: []), \
             unittest.mock.patch.object(qubesadmin.tools.qvm_start_daemon,
                                        'get_monitor_layout',
                                        unittest.mock.Mock(
                                            return_value=['1600 900 0 0\n'])):
            loop.run_until_complete(self.launcher.start_gui_for_vm(
                self.app.domains['test-vm']))
            # common arguments dropped for simplicity
            proc_mock.assert_called_once_with('-d', '3000')

        self.assertAllCalled()

    @unittest.mock.patch('asyncio.create_subprocess_exec')
    def test_021_start_gui_for_vm_hvm(self, proc_mock):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'xid', None)] = \
            b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'stubdom_xid', None)] = \
            b'0\x00default=False type=int 3001'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'virt_mode', None)] = \
            b'0\x00default=False type=str hvm'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'debug', None)] = \
            b'0\x00default=False type=bool False'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'no-monitor-layout', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'
        with unittest.mock.patch.object(self.launcher,
                                        'common_guid_args', lambda vm: []), \
            unittest.mock.patch.object(qubesadmin.tools.qvm_start_daemon,
                                       'get_monitor_layout',
                                       unittest.mock.Mock(
                                           return_value=['1600 900 0 0\n'])):
            loop.run_until_complete(self.launcher.start_gui_for_vm(
                self.app.domains['test-vm']))
            # common arguments dropped for simplicity
            proc_mock.assert_called_once_with('-d', '3000', '-n')

        self.assertAllCalled()

    def test_022_start_gui_for_vm_hvm_stubdom(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'xid', None)] = \
            b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'stubdom_xid', None)] = \
            b'0\x00default=False type=int 3001'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'virt_mode', None)] = \
            b'0\x00default=False type=str hvm'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'debug', None)] = \
            b'0\x00default=False type=bool False'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'no-monitor-layout', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'
        pidfile = tempfile.NamedTemporaryFile()
        pidfile.write(b'1234\n')
        pidfile.flush()
        self.addCleanup(pidfile.close)

        patch_proc = unittest.mock.patch('asyncio.create_subprocess_exec')
        patch_monitor_layout = unittest.mock.patch.object(
            qubesadmin.tools.qvm_start_daemon,
            'get_monitor_layout',
            unittest.mock.Mock(return_value=['1600 900 0 0\n']))
        patch_args = unittest.mock.patch.object(self.launcher,
                                                'common_guid_args',
                                                lambda vm: [])
        patch_pidfile = unittest.mock.patch.object(self.launcher,
                                                   'guid_pidfile',
                                                   lambda vm: pidfile.name)
        try:
            mock_proc = patch_proc.start()
            patch_args.start()
            patch_pidfile.start()
            patch_monitor_layout.start()
            loop.run_until_complete(self.launcher.start_gui_for_vm(
                self.app.domains['test-vm']))
            # common arguments dropped for simplicity
            mock_proc.assert_called_once_with(
                '-d', '3000', '-n', '-K', '1234')
        finally:
            unittest.mock.patch.stopall()

        self.assertAllCalled()

    def test_030_start_gui_for_stubdomain(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'xid', None)] = \
            b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'stubdom_xid', None)] = \
            b'0\x00default=False type=int 3001'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate', 'gui', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate', 'gui-emulated',
             None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'
        with unittest.mock.patch('asyncio.create_subprocess_exec') as proc_mock:
            with unittest.mock.patch.object(self.launcher,
                                            'common_guid_args', lambda vm: []):
                loop.run_until_complete(self.launcher.start_gui_for_stubdomain(
                    self.app.domains['test-vm']))
                # common arguments dropped for simplicity
                proc_mock.assert_called_once_with('-d', '3001', '-t', '3000')

        self.assertAllCalled()

    def test_031_start_gui_for_stubdomain_forced(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'xid', None)] = \
            b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'stubdom_xid', None)] = \
            b'0\x00default=False type=int 3001'
        # self.app.expected_calls[
        #    ('test-vm', 'admin.vm.feature.CheckWithTemplate', 'gui', None)] = \
        #    b'0\x00'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate', 'gui-emulated',
             None)] = \
            b'0\x001'
        with unittest.mock.patch('asyncio.create_subprocess_exec') as proc_mock:
            with unittest.mock.patch.object(self.launcher,
                                            'common_guid_args', lambda vm: []):
                loop.run_until_complete(self.launcher.start_gui_for_stubdomain(
                    self.app.domains['test-vm']))
                # common arguments dropped for simplicity
                proc_mock.assert_called_once_with('-d', '3001', '-t', '3000')

        self.assertAllCalled()

    async def mock_coroutine(self, mock, *args, **kwargs):
        mock(*args, **kwargs)

    def test_040_start_gui(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n' \
            b'gui-vm class=AppVM state=Running'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate', 'gui', None)] = \
            b'0\x00True'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'no-monitor-layout', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'virt_mode', None)] = \
            b'0\x00default=False type=str hvm'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'xid', None)] = \
            b'0\x00default=False type=int 3000'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'stubdom_xid', None)] = \
            b'0\x00default=False type=int 3001'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'guivm', None)] = \
            b'0\x00default=False type=vm gui-vm'

        self.app._local_name = 'gui-vm'
        vm = self.app.domains['test-vm']
        mock_start_vm = unittest.mock.Mock()
        mock_start_stubdomain = unittest.mock.Mock()
        patch_start_vm = unittest.mock.patch.object(
            self.launcher, 'start_gui_for_vm', functools.partial(
                self.mock_coroutine, mock_start_vm))
        patch_start_stubdomain = unittest.mock.patch.object(
            self.launcher, 'start_gui_for_stubdomain', lambda vm_, force:
            self.mock_coroutine(mock_start_stubdomain, vm_))
        try:
            patch_start_vm.start()
            patch_start_stubdomain.start()
            loop.run_until_complete(self.launcher.start_gui(vm))
            mock_start_vm.assert_called_once_with(vm, monitor_layout=None)
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
        proc_mock().__enter__.return_value = proc_mock()
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
        self.assertEqual(qubesadmin.tools.qvm_start_daemon.get_monitor_layout(),
                         ['1920 1200 0 0\n'])

    @unittest.mock.patch('subprocess.Popen')
    def test_051_get_monitor_layout_multiple(self, proc_mock):
        proc_mock().__enter__.return_value = proc_mock()
        proc_mock().stdout = b'''Screen 0: minimum 8 x 8, current 2880 x 1024, maximum 32767 x 32767
LVDS1 connected 1600x900+0+0 (normal left inverted right x axis y axis)
VGA1 connected 1280x1024+1600+0 (normal left inverted right x axis y axis)
'''.splitlines()
        self.assertEqual(qubesadmin.tools.qvm_start_daemon.get_monitor_layout(),
                         ['1600 900 0 0\n', '1280 1024 1600 0\n'])

    @unittest.mock.patch('subprocess.Popen')
    def test_052_get_monitor_layout_hidpi1(self, proc_mock):
        proc_mock().__enter__.return_value = proc_mock()
        proc_mock().stdout = b'''Screen 0: minimum 8 x 8, current 1920 x 1200, maximum 32767 x 32767
HDMI1 connected 2560x1920+0+0 (normal left inverted right x axis y axis) 372mm x 208mm
   1920x1200     60.00*+
'''.splitlines()
        dpi = 150
        self.assertEqual(qubesadmin.tools.qvm_start_daemon.get_monitor_layout(),
                         ['2560 1920 0 0 {} {}\n'.format(
                             int(2560 / dpi * 254 / 10),
                             int(1920 / dpi * 254 / 10))])

    @unittest.mock.patch('subprocess.Popen')
    def test_052_get_monitor_layout_hidpi2(self, proc_mock):
        proc_mock().__enter__.return_value = proc_mock()
        proc_mock().stdout = b'''Screen 0: minimum 8 x 8, current 1920 x 1200, maximum 32767 x 32767
HDMI1 connected 2560x1920+0+0 (normal left inverted right x axis y axis) 310mm x 174mm
   1920x1200     60.00*+
'''.splitlines()
        dpi = 200
        self.assertEqual(qubesadmin.tools.qvm_start_daemon.get_monitor_layout(),
                         ['2560 1920 0 0 {} {}\n'.format(
                             int(2560 / dpi * 254 / 10),
                             int(1920 / dpi * 254 / 10))])

    @unittest.mock.patch('subprocess.Popen')
    def test_052_get_monitor_layout_hidpi3(self, proc_mock):
        proc_mock().__enter__.return_value = proc_mock()
        proc_mock().stdout = b'''Screen 0: minimum 8 x 8, current 1920 x 1200, maximum 32767 x 32767
HDMI1 connected 2560x1920+0+0 (normal left inverted right x axis y axis) 206mm x 116mm
   1920x1200     60.00*+
'''.splitlines()
        dpi = 300
        self.assertEqual(qubesadmin.tools.qvm_start_daemon.get_monitor_layout(),
                         ['2560 1920 0 0 {} {}\n'.format(
                             int(2560 / dpi * 254 / 10),
                             int(1920 / dpi * 254 / 10))])

    def test_060_send_monitor_layout(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'no-monitor-layout', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'

        vm = self.app.domains['test-vm']
        mock_run_service = unittest.mock.Mock(spec={})
        patch_run_service = unittest.mock.patch.object(
            qubesadmin.vm.QubesVM, 'run_service_for_stdio',
            mock_run_service)
        patch_run_service.start()
        self.addCleanup(patch_run_service.stop)
        monitor_layout = ['1920 1080 0 0\n']
        loop.run_until_complete(self.launcher.send_monitor_layout(
            vm, layout=monitor_layout, startup=True))
        mock_run_service.assert_called_once_with(
            'qubes.SetMonitorLayout', autostart=False, input=b'1920 1080 0 0\n')
        self.assertAllCalled()

    def test_061_send_monitor_layout_exclude(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'no-monitor-layout', None)] = \
            b'0\x00True'

        vm = self.app.domains['test-vm']
        mock_run_service = unittest.mock.Mock()
        patch_run_service = unittest.mock.patch.object(
            qubesadmin.vm.QubesVM, 'run_service_for_stdio',
            mock_run_service)
        patch_run_service.start()
        self.addCleanup(patch_run_service.stop)
        monitor_layout = ['1920 1080 0 0\n']
        loop.run_until_complete(self.launcher.send_monitor_layout(
            vm, layout=monitor_layout, startup=True))
        self.assertFalse(mock_run_service.called)
        self.assertAllCalled()

    def test_062_send_monitor_layout_not_running(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'no-monitor-layout', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'

        vm = self.app.domains['test-vm']
        mock_run_service = unittest.mock.Mock()
        patch_run_service = unittest.mock.patch.object(
            qubesadmin.vm.QubesVM, 'run_service_for_stdio',
            mock_run_service)
        patch_run_service.start()
        self.addCleanup(patch_run_service.stop)
        monitor_layout = ['1920 1080 0 0\n']
        loop.run_until_complete(self.launcher.send_monitor_layout(
            vm, layout=monitor_layout, startup=True))
        self.assertFalse(mock_run_service.called)
        self.assertAllCalled()

    def test_063_send_monitor_layout_signal_existing(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'xid', None)] = \
            b'0\x00default=False type=int 123'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'stubdom_xid', None)] = \
            b'0\x00default=False type=int 124'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'no-monitor-layout', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'

        vm = self.app.domains['test-vm']
        self.addCleanup(unittest.mock.patch.stopall)

        with tempfile.NamedTemporaryFile() as pidfile:
            pidfile.write(b'1234\n')
            pidfile.flush()

            patch_guid_pidfile = unittest.mock.patch.object(
                self.launcher, 'guid_pidfile')
            mock_guid_pidfile = patch_guid_pidfile.start()
            mock_guid_pidfile.return_value = pidfile.name

            mock_kill = unittest.mock.patch('os.kill').start()

            monitor_layout = ['1920 1080 0 0\n']
            loop.run_until_complete(self.launcher.send_monitor_layout(
                vm, layout=monitor_layout, startup=False))
            self.assertEqual(mock_guid_pidfile.mock_calls,
                             [unittest.mock.call(123),
                              unittest.mock.call(124)])
            self.assertEqual(mock_kill.mock_calls,
                             [unittest.mock.call(1234, signal.SIGHUP),
                              unittest.mock.call(1234, signal.SIGHUP)])
        self.assertAllCalled()

    def test_070_send_monitor_layout_all(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.addCleanup(loop.close)

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n' \
            b'test-vm3 class=AppVM state=Running\n' \
            b'test-vm4 class=AppVM state=Halted\n' \
            b'gui-vm class=AppVM state=Running'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        self.app.expected_calls[
            ('test-vm3', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        self.app.expected_calls[
            ('test-vm4', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate',
             'gui', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.feature.CheckWithTemplate',
             'gui', None)] = \
            b'0\x00True'
        self.app.expected_calls[
            ('test-vm3', 'admin.vm.feature.CheckWithTemplate',
             'gui', None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('gui-vm', 'admin.vm.property.Get', 'guivm', None)] = \
            b'0\x00default=True type=vm '
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'guivm', None)] = \
            b'0\x00default=False type=vm gui-vm'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.property.Get', 'guivm', None)] = \
            b'0\x00default=False type=vm gui-vm'
        self.app.expected_calls[
            ('test-vm3', 'admin.vm.property.Get', 'guivm', None)] = \
            b'0\x00default=False type=vm gui-vm'
        self.app.expected_calls[
            ('test-vm4', 'admin.vm.property.Get', 'guivm', None)] = \
            b'0\x00default=False type=vm gui-vm'

        self.app._local_name = 'gui-vm'

        vm = self.app.domains['test-vm']
        vm2 = self.app.domains['test-vm2']

        self.addCleanup(unittest.mock.patch.stopall)

        mock_send_monitor_layout = unittest.mock.Mock()
        patch_send_monitor_layout = unittest.mock.patch.object(
            self.launcher, 'send_monitor_layout',
            functools.partial(self.mock_coroutine, mock_send_monitor_layout))
        patch_send_monitor_layout.start()
        monitor_layout = ['1920 1080 0 0\n']
        mock_get_monior_layout = unittest.mock.patch(
            'qubesadmin.tools.qvm_start_daemon.get_monitor_layout').start()
        mock_get_monior_layout.return_value = monitor_layout

        self.launcher.send_monitor_layout_all()
        loop.stop()
        loop.run_forever()

        # test-vm3 not called b/c feature 'gui' set to false
        # test-vm4 not called b/c not running
        self.assertCountEqual(mock_send_monitor_layout.mock_calls,
                              [unittest.mock.call(vm, monitor_layout),
                               unittest.mock.call(vm2, monitor_layout)])
        mock_get_monior_layout.assert_called_once_with()
        self.assertAllCalled()
