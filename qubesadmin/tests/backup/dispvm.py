#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2019 Marek Marczykowski-Górecki
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

import datetime
import tempfile
import unittest
import unittest.mock
from unittest.mock import call

import subprocess

import qubesadmin.tests
from qubesadmin.tools import qvm_backup_restore
from qubesadmin.backup.dispvm import RestoreInDisposableVM


class TC_00_RestoreInDispVM(qubesadmin.tests.QubesTestCase):

    def test_000_prepare_inner_args(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
        )
        argv = ['--verbose', '--skip-broken', '--skip-dom0-home',
                '--dest-vm', 'testvm',
                '--compression-filter', 'gzip', '/backup/location']
        args = qvm_backup_restore.parser.parse_args(argv)
        obj = RestoreInDisposableVM(self.app, args)
        obj.storage_access_id = 'abc'
        reconstructed_argv = obj.prepare_inner_args()
        expected_argv = argv[:-1] + \
                        ['--location-is-service', 'qubes.RestoreById+abc']
        self.assertCountEqual(expected_argv, reconstructed_argv)

    def test_001_prepare_inner_args_exclude(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
        )
        argv = ['--exclude', 'vm1', '--exclude', 'vm2',
                '/backup/location']
        args = qvm_backup_restore.parser.parse_args(argv)
        print(repr(args))
        obj = RestoreInDisposableVM(self.app, args)
        obj.storage_access_id = 'abc'
        reconstructed_argv = obj.prepare_inner_args()
        expected_argv = argv[:-1] + \
                        ['--location-is-service', 'qubes.RestoreById+abc']
        self.assertCountEqual(expected_argv, reconstructed_argv)

    def test_002_prepare_inner_args_pass_file(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
        )
        argv = ['--passphrase-file=/tmp/some/file',
                '/backup/location']
        args = qvm_backup_restore.parser.parse_args(argv)
        print(repr(args))
        obj = RestoreInDisposableVM(self.app, args)
        obj.storage_access_id = 'abc'
        reconstructed_argv = obj.prepare_inner_args()
        expected_argv = ['--passphrase-file', '/tmp/some/file',
                         '--location-is-service', 'qubes.RestoreById+abc']
        self.assertEqual(expected_argv, reconstructed_argv)

    def test_003_prepare_inner_args_auto_close(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
        )
        argv = ['--auto-close', '/backup/location']
        args = qvm_backup_restore.parser.parse_args(argv)
        print(repr(args))
        obj = RestoreInDisposableVM(self.app, args)
        obj.storage_access_id = 'abc'
        reconstructed_argv = obj.prepare_inner_args()
        expected_argv = ['--location-is-service', 'qubes.RestoreById+abc']
        self.assertEqual(expected_argv, reconstructed_argv)

    def test_010_clear_old_tags(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
        )
        for tag in ('backup-restore-mgmt',
                    'backup-restore-in-progress',
                    'backup-restore-storage'):
            self.app.expected_calls[
                ('dom0', 'admin.vm.tag.Remove', tag, None)] = \
                b'2\x00QubesTagNotFoundError\x00\x00Tag not found\x00'
            self.app.expected_calls[
                ('fedora-25', 'admin.vm.tag.Remove', tag, None)] = b'0\0'
            self.app.expected_calls[
                ('testvm', 'admin.vm.tag.Remove', tag, None)] = b'0\0'

        args = unittest.mock.Mock(appvm='testvm')
        obj = RestoreInDisposableVM(self.app, args)
        obj.clear_old_tags()
        self.assertAllCalled()

    @unittest.mock.patch('subprocess.check_call')
    def test_020_create_dispvm(self, mock_check_call):
        # pylint: disable=unused-argument
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
            b'mgmt-dvm class=AppVM state=Halted\n'
            # this should be only after creating...
            b'disp-backup-restore class=DispVM state=Halted\n'
        )
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'management_dispvm', None)] =  \
            b'0\0default=False type=vm mgmt-dvm'
        self.app.expected_calls[
            ('dom0', 'admin.vm.Create.DispVM', 'mgmt-dvm',
             b'name=disp-backup-restore label=red')] = b'0\0'
        self.app.expected_calls[
            ('disp-backup-restore', 'admin.vm.property.Set', 'auto_cleanup',
             b'True')] =  \
            b'0\0'
        self.app.expected_calls[
            ('disp-backup-restore', 'admin.vm.feature.Set',
             'tag-created-vm-with',
             b'backup-restore-in-progress')] =  \
            b'0\0'
        args = unittest.mock.Mock(appvm='dom0')
        obj = RestoreInDisposableVM(self.app, args)
        obj.create_dispvm()
        self.assertAllCalled()

    @unittest.mock.patch('subprocess.check_call')
    @unittest.mock.patch('os.uname')
    def test_030_transfer_pass_file(self, mock_uname, mock_check_call):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'testvm class=AppVM state=Running\n'
        )
        mock_uname.return_value = ('Linux', 'dom0', '5.0.0', '#1', 'x86_64')
        args = unittest.mock.Mock(appvm='testvm')
        obj = RestoreInDisposableVM(self.app, args)
        obj.dispvm = unittest.mock.Mock(default_user='user2')
        new_path = obj.transfer_pass_file('/some/path')
        self.assertEqual(new_path, '/home/user2/QubesIncoming/dom0/path')
        mock_check_call.assert_called_once_with(
            ['qvm-copy-to-vm', 'disp-backup-restore', '/some/path'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        self.assertAllCalled()

    def test_040_register_backup_source(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'backup-storage class=AppVM state=Running\n'
        )
        self.app.expected_service_calls[
            ('backup-storage', 'qubes.RegisterBackupLocation')] = \
            b'someid\nsomething that should not be read'
        self.app.expected_calls[
            ('backup-storage', 'admin.vm.tag.Set', 'backup-restore-storage',
             None)] = b'0\0'

        args = unittest.mock.Mock(backup_location='/backup/path',
                                  appvm='backup-storage')
        obj = RestoreInDisposableVM(self.app, args)
        obj.dispvm = unittest.mock.Mock(default_user='user2')
        obj.register_backup_source()
        self.assertEqual(obj.storage_access_id, 'someid')
        self.assertEqual(self.app.service_calls, [
            ('backup-storage', 'qubes.RegisterBackupLocation',
             {'stdin':subprocess.PIPE, 'stdout':subprocess.PIPE}),
            ('backup-storage', 'qubes.RegisterBackupLocation',
             b'/backup/path\n'),
        ])
        self.assertAllCalled()

    def test_050_invalidate_backup_access(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'backup-storage class=AppVM state=Running\n'
        )
        self.app.expected_calls[
            ('backup-storage', 'admin.vm.tag.Remove', 'backup-restore-storage',
             None)] = b'0\0'

        args = unittest.mock.Mock(backup_location='/backup/path',
                                  appvm='backup-storage')
        obj = RestoreInDisposableVM(self.app, args)
        obj.storage_access_proc = unittest.mock.Mock()
        obj.invalidate_backup_access()
        self.assertEqual(obj.storage_access_proc.mock_calls, [
            call.stdin.close(),
            call.wait(),
        ])
        self.assertAllCalled()

    @unittest.mock.patch('datetime.date')
    def test_060_finalize_tags(self, mock_date):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
            b'disp-backup-restore class=DispVM state=Running\n'
            b'restored1 class=AppVM state=Halted\n'
            b'restored2 class=AppVM state=Halted\n'
        )
        self.app.expected_calls[
            ('dom0', 'admin.vm.tag.Get', 'backup-restore-in-progress',
             None)] = b'0\x000'
        self.app.expected_calls[
            ('fedora-25', 'admin.vm.tag.Get', 'backup-restore-in-progress',
             None)] = b'0\x000'
        self.app.expected_calls[
            ('disp-backup-restore', 'admin.vm.tag.Get',
             'backup-restore-in-progress',
             None)] = b'0\x000'
        self.app.expected_calls[
            ('restored1', 'admin.vm.tag.Get', 'backup-restore-in-progress',
             None)] = b'0\x001'
        self.app.expected_calls[
            ('restored1', 'admin.vm.tag.List', None, None)] = \
            b'0\0backup-restore-in-progress\n' \
            b'restored-from-backup-12345678\n' \
            b'created-by-disp-backup-restore\n'
        self.app.expected_calls[
            ('restored1', 'admin.vm.tag.Remove', 'backup-restore-in-progress',
             None)] = b'0\0'
        self.app.expected_calls[
            ('restored2', 'admin.vm.tag.Get', 'backup-restore-in-progress',
             None)] = b'0\x001'
        self.app.expected_calls[
            ('restored2', 'admin.vm.tag.List', None, None)] = \
            b'0\0backup-restore-in-progress\n' \
            b'created-by-disp-backup-restore\n'
        self.app.expected_calls[
            ('restored2', 'admin.vm.tag.Set',
             'restored-from-backup-at-2019-10-01',
             None)] = b'0\0'
        self.app.expected_calls[
            ('restored2', 'admin.vm.tag.Remove', 'backup-restore-in-progress',
             None)] = b'0\0'

        mock_date.today.return_value = datetime.date.fromisoformat('2019-10-01')
        mock_date.strftime.return_value = '2019-10-01'
        args = unittest.mock.Mock(backup_location='/backup/path',
                                  appvm=None)
        obj = RestoreInDisposableVM(self.app, args)
        obj.finalize_tags()
        self.assertAllCalled()

    def test_070_sanitize_log(self):
        sanitized = RestoreInDisposableVM.sanitize_log(b'sample message')
        self.assertEqual(sanitized, b'sample message')
        sanitized = RestoreInDisposableVM.sanitize_log(
            b'sample message\nmultiline\n')
        self.assertEqual(sanitized, b'sample message\nmultiline\n')
        sanitized = RestoreInDisposableVM.sanitize_log(
            b'\033[0;33m\xff\xfe\x80')
        self.assertEqual(sanitized, b'.[0;33m...')

    def test_080_extract_log(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
        )
        args = unittest.mock.Mock(backup_location='/backup/path',
                                  appvm=None)
        obj = RestoreInDisposableVM(self.app, args)
        obj.dispvm = unittest.mock.Mock()
        obj.dispvm.run_with_args.return_value = b'this is a log', None
        backup_log = obj.extract_log()
        obj.dispvm.run_with_args.assert_called_once_with(
            'cat', '/var/tmp/backup-restore.log',
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL)
        self.assertEqual(backup_log, b'this is a log')

    def test_100_run(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
        )
        args = unittest.mock.Mock(backup_location='/backup/path',
            pass_file=None,
            appvm=None)
        obj = RestoreInDisposableVM(self.app, args)
        methods = ['create_dispvm', 'clear_old_tags', 'register_backup_source',
                   'prepare_inner_args', 'extract_log', 'finalize_tags']
        for m in methods:
            setattr(obj, m, unittest.mock.Mock())
        obj.extract_log.return_value = b'Some logs\nexit code: 0\n'
        obj.transfer_pass_file = unittest.mock.Mock()
        obj.prepare_inner_args.return_value = ['args']
        obj.terminal_app = ('terminal',)
        obj.dispvm = unittest.mock.Mock()
        with tempfile.NamedTemporaryFile() as tmp:
            with unittest.mock.patch('qubesadmin.backup.dispvm.LOCKFILE',
                    tmp.name):
                obj.run()

        # pylint: disable=no-member
        for m in methods:
            self.assertEqual(len(getattr(obj, m).mock_calls), 1)
        self.assertEqual(obj.dispvm.mock_calls, [
            call.start(),
            call.run('command -v qvm-backup-restore'),
            call.run_service_for_stdio('qubes.WaitForSession'),
            call.tags.add('backup-restore-mgmt'),
            call.run_with_args('terminal', 'qvm-backup-restore', 'args',
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL),
            call.tags.discard('backup-restore-mgmt'),
            call.kill()
        ])
        obj.transfer_pass_file.assert_not_called()

    def test_101_run_pass_file(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
        )
        args = unittest.mock.Mock(backup_location='/backup/path',
            pass_file='/some/path',
            appvm=None)
        obj = RestoreInDisposableVM(self.app, args)
        methods = ['create_dispvm', 'clear_old_tags', 'register_backup_source',
                   'prepare_inner_args', 'extract_log', 'finalize_tags',
                   'transfer_pass_file']
        for m in methods:
            setattr(obj, m, unittest.mock.Mock())
        obj.extract_log.return_value = b'Some logs\nexit code: 0\n'
        obj.prepare_inner_args.return_value = ['args']
        obj.terminal_app = ('terminal',)
        obj.dispvm = unittest.mock.Mock()
        with tempfile.NamedTemporaryFile() as tmp:
            with unittest.mock.patch('qubesadmin.backup.dispvm.LOCKFILE',
                    tmp.name):
                obj.run()

        # pylint: disable=no-member
        for m in methods:
            self.assertEqual(len(getattr(obj, m).mock_calls), 1)
        self.assertEqual(obj.dispvm.mock_calls, [
            call.start(),
            call.run('command -v qvm-backup-restore'),
            call.run_service_for_stdio('qubes.WaitForSession'),
            call.tags.add('backup-restore-mgmt'),
            call.run_with_args('terminal', 'qvm-backup-restore', 'args',
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL),
            call.tags.discard('backup-restore-mgmt'),
            call.kill()
        ])

    def test_102_run_error(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
        )
        args = unittest.mock.Mock(backup_location='/backup/path',
            pass_file=None,
            appvm=None)
        obj = RestoreInDisposableVM(self.app, args)
        methods = ['create_dispvm', 'clear_old_tags', 'register_backup_source',
                   'prepare_inner_args', 'extract_log', 'finalize_tags']
        for m in methods:
            setattr(obj, m, unittest.mock.Mock())
        obj.extract_log.return_value = b'Some error\nexit code: 1\n'
        obj.transfer_pass_file = unittest.mock.Mock()
        obj.prepare_inner_args.return_value = ['args']
        obj.terminal_app = ('terminal',)
        obj.dispvm = unittest.mock.Mock()
        with tempfile.NamedTemporaryFile() as tmp:
            with unittest.mock.patch('qubesadmin.backup.dispvm.LOCKFILE',
                    tmp.name):
                with self.assertRaises(qubesadmin.exc.BackupRestoreError):
                    obj.run()
        # pylint: disable=no-member
        for m in methods:
            self.assertEqual(len(getattr(obj, m).mock_calls), 1)
        self.assertEqual(obj.dispvm.mock_calls, [
            call.start(),
            call.run('command -v qvm-backup-restore'),
            call.run_service_for_stdio('qubes.WaitForSession'),
            call.tags.add('backup-restore-mgmt'),
            call.run_with_args('terminal', 'qvm-backup-restore', 'args',
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL),
            call.tags.discard('backup-restore-mgmt'),
            call.kill()
        ])
        obj.transfer_pass_file.assert_not_called()

    def test_103_missing_package(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0dom0 class=AdminVM state=Running\n'
            b'fedora-25 class=TemplateVM state=Halted\n'
        )
        args = unittest.mock.Mock(backup_location='/backup/path',
            pass_file=None,
            appvm=None)
        obj = RestoreInDisposableVM(self.app, args)
        methods = ['create_dispvm', 'clear_old_tags', 'register_backup_source',
                   'finalize_tags']
        for m in methods:
            setattr(obj, m, unittest.mock.Mock())
        obj.transfer_pass_file = unittest.mock.Mock()
        obj.dispvm = unittest.mock.Mock()
        obj.dispvm.run = unittest.mock.Mock()
        obj.dispvm.run.side_effect = subprocess.CalledProcessError(
            '1',
            'command -v qvm-backup-restore',
        )
        with tempfile.NamedTemporaryFile() as tmp:
            with unittest.mock.patch('qubesadmin.backup.dispvm.LOCKFILE',
                    tmp.name):
                with self.assertRaises(qubesadmin.exc.QubesException):
                    obj.run()
        # pylint: disable=no-member
        for m in methods:
            self.assertEqual(len(getattr(obj, m).mock_calls), 1)
        self.assertEqual(obj.dispvm.mock_calls, [
            call.start(),
            call.run('command -v qvm-backup-restore'),
            call.tags.discard('backup-restore-mgmt'),
            call.kill()
        ])
        obj.transfer_pass_file.assert_not_called()
