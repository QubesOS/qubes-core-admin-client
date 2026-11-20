# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
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

import tempfile
from unittest import mock

import qubesadmin.exc
import qubesadmin.tests
from qubesadmin.backup import BackupVM
from qubesadmin.backup.restore import BackupRestore, BackupCanceledError


class StopRestore(Exception):
    pass


class TC_00_BackupRestore(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=R1732
        self.addCleanup(tmpdir.cleanup)
        patches = [
            mock.patch.object(BackupRestore, '_retrieve_backup_header'),
            mock.patch.object(BackupRestore, '_process_qubes_xml'),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.restore = BackupRestore(self.app, '/backup/location', None,
            'qubes', tmpdir=tmpdir.name)
        self.restore.header_data.version = 4

    def test_000_size_limits(self):
        with mock.patch.object(self.restore, '_start_retrieval_process',
                side_effect=StopRestore) as mock_retrieve:
            with self.assertRaises(StopRestore):
                self.restore._restore_vm_data(['vm1/', 'vm2/'],
                    300 * 1024 * 1024, 4000 * 1024 * 1024, {})
        # 4000 MiB of volumes, + 10% + 10 MiB per qube
        mock_retrieve.assert_called_once_with(
            ['vm1/', 'vm2/'], '128', 4420 * 1024 * 1024)

    def test_001_size_limits_ignored(self):
        self.restore.options.ignore_size_limit = True
        with mock.patch.object(self.restore, '_start_retrieval_process',
                side_effect=StopRestore) as mock_retrieve:
            with self.assertRaises(StopRestore):
                self.restore._restore_vm_data(['vm1/', 'vm2/'],
                    300 * 1024 * 1024, 4000 * 1024 * 1024, {})
        mock_retrieve.assert_called_once_with(['vm1/', 'vm2/'], '0', 0)

    def test_002_max_size(self):
        vm = BackupVM()
        vm.size = '1000'
        vm.max_size = 5000
        self.assertEqual(BackupRestore.VMToRestore(vm).max_size, 5000)
        # no volume sizes (dom0, old backup format): use the recorded size
        vm.max_size = 0
        self.assertEqual(BackupRestore.VMToRestore(vm).max_size, 1000)

    def restore_do_with_error(self, error):
        patches = [
            mock.patch.object(self.restore, 'check_disk_space'),
            mock.patch.object(self.restore, 'restore_info_verify',
                side_effect=lambda info: info),
            mock.patch.object(self.restore, '_restore_vms_metadata'),
            mock.patch.object(self.restore, '_restore_vm_data',
                side_effect=error),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.restore.restore_do({})

    def test_020_restore_do_extract_error(self):
        with self.assertRaisesRegex(qubesadmin.exc.QubesException,
                'Error extracting data.*retrieved backup exceed'):
            self.restore_do_with_error(qubesadmin.exc.QubesException(
                'retrieved backup exceed size or file count limit'))

    def test_021_restore_do_extract_error_verify_only(self):
        self.restore.options.verify_only = True
        with self.assertRaisesRegex(qubesadmin.exc.QubesException,
                '^some error$'):
            self.restore_do_with_error(
                qubesadmin.exc.QubesException('some error'))

    def test_022_restore_do_canceled(self):
        self.restore.canceled = True
        with self.assertRaises(BackupCanceledError):
            self.restore_do_with_error(
                BackupCanceledError('Restore canceled'))

    def test_023_restore_do_success(self):
        self.restore_do_with_error(None)
