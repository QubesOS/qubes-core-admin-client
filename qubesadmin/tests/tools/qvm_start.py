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

import unittest.mock

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_start


class TC_00_qvm_start(qubesadmin.tests.QubesTestCase):
    def test_000_with_vm(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Start', None, None)] = b'0\x00'
        qubesadmin.tools.qvm_start.main(['some-vm'], app=self.app)
        self.assertAllCalled()

    def test_001_missing_vm(self):
        with self.assertRaises(SystemExit):
            with qubesadmin.tests.tools.StderrBuffer() as stderr:
                qubesadmin.tools.qvm_start.main([], app=self.app)
        self.assertIn('one of the arguments --all VMNAME is required',
            stderr.getvalue())
        self.assertAllCalled()

    def test_002_invalid_vm(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        with self.assertRaises(SystemExit):
            with qubesadmin.tests.tools.StderrBuffer() as stderr:
                qubesadmin.tools.qvm_start.main(['no-such-vm'], app=self.app)
        self.assertIn('no such domain', stderr.getvalue())
        self.assertAllCalled()

    def test_003_already_running(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Runnin'
        self.assertEqual(
            qubesadmin.tools.qvm_start.main(['some-vm'], app=self.app),
            1)
        self.assertAllCalled()

    def test_010_drive_cdrom(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Start', None, None)] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Assign', 'dom0+sr0+_',
             b"device_id='*' port_id='sr0' "
             b"devclass='block' backend_domain='dom0' mode='required' "
             b"frontend_domain='some-vm' _devtype='cdrom' "
             b"_read-only='True'")] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Unassign', 'dom0+sr0+_',
             None)] = b'0\x00'
        qubesadmin.tools.qvm_start.main(['--cdrom=dom0:sr0', 'some-vm'],
            app=self.app)
        self.assertAllCalled()

    def test_011_drive_disk(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Start', None, None)] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Assign', 'dom0+sdb1+_',
             b"device_id='*' port_id='sdb1' "
             b"devclass='block' backend_domain='dom0' mode='required' "
             b"frontend_domain='some-vm' _devtype='disk' "
             b"_read-only='False'")] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Unassign', 'dom0+sdb1+_',
             None)] = b'0\x00'
        qubesadmin.tools.qvm_start.main(['--hd=dom0:sdb1', 'some-vm'],
            app=self.app)
        self.assertAllCalled()

    def test_012_drive_disk(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Start', None, None)] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Assign', 'dom0+sdb1+_',
             b"device_id='*' port_id='sdb1' "
             b"devclass='block' backend_domain='dom0' mode='required' "
             b"frontend_domain='some-vm' _devtype='disk' "
             b"_read-only='False'")] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Unassign', 'dom0+sdb1+_',
             None)] = b'0\x00'
        qubesadmin.tools.qvm_start.main(['--drive=hd:dom0:sdb1', 'some-vm'],
            app=self.app)
        self.assertAllCalled()

    @unittest.mock.patch('subprocess.check_output')
    def test_013_drive_loop_local(self, mock_subprocess):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('dom0', 'admin.vm.device.block.Available', None, None)] = \
            b'0\x00loop12\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Start', None, None)] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Assign', 'dom0+loop12+_',
             b"device_id='*' port_id='loop12' "
             b"devclass='block' backend_domain='dom0' mode='required' "
             b"frontend_domain='some-vm' _devtype='cdrom' "
             b"_read-only='True'")] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Unassign', 'dom0+loop12+_', None
             )] = b'0\x00loop12\n'
        mock_subprocess.return_value = b"/dev/loop12"
        qubesadmin.tools.qvm_start.main([
            '--cdrom=dom0:/home/some/image.iso',
            'some-vm'],
            app=self.app)
        self.assertAllCalled()
        mock_subprocess.assert_called_once_with(
            ['sudo', 'losetup', '-f', '--show', '/home/some/image.iso'])

    def test_014_drive_loop_remote(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('other-vm', 'admin.vm.device.block.Available', None, None)] = \
            b'0\x00loop7\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Start', None, None)] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Assign', 'other-vm+loop7+_',
             b"device_id='*' port_id='loop7' "
             b"devclass='block' backend_domain='other-vm' mode='required' "
             b"frontend_domain='some-vm' _devtype='cdrom' "
             b"_read-only='True'")] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Unassign', 'other-vm+loop7+_',
             None)] = b'0\x00'
        self.app.expected_calls[
            ('other-vm', 'admin.vm.feature.CheckWithTemplate', 'vmexec',
             None)] = b'2\x00QubesFeatureNotFoundError\x00\x00' \
                      b'Feature \'vmexec\' not set\x00'

        with unittest.mock.patch.object(self.app.domains['other-vm'], 'run') \
                as mock_run:
            mock_run.return_value = (b'/dev/loop7', b'')
            qubesadmin.tools.qvm_start.main([
                '--cdrom=other-vm:/home/some image.iso',
                'some-vm'],
                app=self.app)
            mock_run.assert_called_once_with(
                'losetup -f --show \'/home/some image.iso\'',
                user='root')
        self.assertAllCalled()

    def test_015_drive_failed_start(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Assign', 'other-vm+loop7+_',
             b"device_id='*' port_id='loop7' "
             b"devclass='block' backend_domain='other-vm' mode='required' "
             b"frontend_domain='some-vm' _devtype='cdrom' "
             b"_read-only='True'")] = b'0\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Start', None, None)] = \
            b'2\x00QubesException\x00\x00An error occurred\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Detach',
            'other-vm+loop7+_', None)] = b'0\x00'
        qubesadmin.tools.qvm_start.main([
            '--cdrom=other-vm:loop7',
            'some-vm'],
            app=self.app)
        self.assertAllCalled()

    def test_016_drive_failed_attach(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n' \
            b'some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Halted'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.device.block.Assign', 'other-vm+loop7+_',
             b"device_id='*' port_id='loop7' "
             b"devclass='block' backend_domain='other-vm' mode='required' "
             b"frontend_domain='some-vm' _devtype='cdrom' "
             b"_read-only='True'")] = \
            b'2\x00QubesException\x00\x00An error occurred\x00'
        retcode = qubesadmin.tools.qvm_start.main([
            '--cdrom=other-vm:loop7',
            'some-vm'],
            app=self.app)
        self.assertEqual(retcode, 1)
        self.assertAllCalled()
