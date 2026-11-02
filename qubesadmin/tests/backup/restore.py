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
from qubesadmin.backup.restore import BackupRestore, BackupCanceledError, \
    BACKUP_FILE_MAX_SIZE


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
                    300 * 1024 * 1024, {})
        # no total size limit, as the recorded size may be underestimated
        mock_retrieve.assert_called_once_with(
            ['vm1/', 'vm2/'], '46', 0, BACKUP_FILE_MAX_SIZE)

    def test_001_size_limits_ignored(self):
        self.restore.options.ignore_size_limit = True
        with mock.patch.object(self.restore, '_start_retrieval_process',
                side_effect=StopRestore) as mock_retrieve:
            with self.assertRaises(StopRestore):
                self.restore._restore_vm_data(['vm1/', 'vm2/'],
                    300 * 1024 * 1024, {})
        mock_retrieve.assert_called_once_with(['vm1/', 'vm2/'], '0', 0, 0)

    def test_010_retrieval_process_env(self):
        self.restore.backup_vm = mock.Mock()
        with mock.patch('subprocess.Popen') as mock_popen:
            self.restore._start_retrieval_process(['vm1/'], 46, 0,
                BACKUP_FILE_MAX_SIZE)
        self.assertEqual(mock_popen.call_args[0][0][0],
            '/usr/libexec/qubes/qfile-dom0-unpacker')
        env = mock_popen.call_args[1]['env']
        self.assertEqual(env['UPDATES_MAX_BYTES'], '0')
        self.assertEqual(env['UPDATES_MAX_FILES'], '46')
        self.assertEqual(env['UPDATES_MAX_BYTES_PER_FILE'],
            str(BACKUP_FILE_MAX_SIZE))

    def test_011_retrieval_process_env_header(self):
        self.restore.backup_vm = mock.Mock()
        with mock.patch('subprocess.Popen') as mock_popen:
            self.restore._start_retrieval_process(
                ['backup-header', 'backup-header.hmac'], 2, 1024 * 1024)
        env = mock_popen.call_args[1]['env']
        self.assertEqual(env['UPDATES_MAX_BYTES'], str(1024 * 1024))
        self.assertEqual(env['UPDATES_MAX_FILES'], '2')
        self.assertEqual(env['UPDATES_MAX_BYTES_PER_FILE'], '0')

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
