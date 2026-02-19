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

import io
import os
from unittest import mock

import asyncio

import qubesadmin.tests
import qubesadmin.tests.tools
from qubesadmin.tools import qvm_backup

class TC_00_qvm_backup(qubesadmin.tests.QubesTestCase):
    def test_000_write_backup_profile(self):
        args = qvm_backup.parser.parse_args(['/var/tmp'], app=self.app)
        profile = io.StringIO()
        qvm_backup.write_backup_profile(profile, args)
        expected_profile = (
            'compression: true\n'
            'destination_path: /var/tmp\n'
            'destination_vm: dom0\n'
            'include: null\n'
        )
        self.assertEqual(profile.getvalue(), expected_profile)

    def test_001_write_backup_profile_include(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0dom0 class=AdminVM state=Running\n' \
            b'vm1 class=AppVM state=Halted\n' \
            b'vm2 class=AppVM state=Halted\n' \
            b'vm3 class=AppVM state=Halted\n'
        args = qvm_backup.parser.parse_args(['/var/tmp', 'vm1', 'vm2'],
            app=self.app)
        profile = io.StringIO()
        qvm_backup.write_backup_profile(profile, args)
        expected_profile = (
            'compression: true\n'
            'destination_path: /var/tmp\n'
            'destination_vm: dom0\n'
            'include:\n'
            '- vm1\n'
            '- vm2\n'
        )
        self.assertEqual(profile.getvalue(), expected_profile)
        self.assertAllCalled()

    def test_002_write_backup_profile_exclude(self):
        args = qvm_backup.parser.parse_args([
            '-x', 'vm1', '-x', 'vm2', '/var/tmp'], app=self.app)
        profile = io.StringIO()
        qvm_backup.write_backup_profile(profile, args)
        expected_profile = (
            'compression: true\n'
            'destination_path: /var/tmp\n'
            'destination_vm: dom0\n'
            'exclude:\n'
            '- vm1\n'
            '- vm2\n'
            'include: null\n'
        )
        self.assertEqual(profile.getvalue(), expected_profile)

    def test_003_write_backup_with_passphrase(self):
        args = qvm_backup.parser.parse_args(['/var/tmp'], app=self.app)
        profile = io.StringIO()
        qvm_backup.write_backup_profile(profile, args, passphrase='test123')
        expected_profile = (
            'compression: true\n'
            'destination_path: /var/tmp\n'
            'destination_vm: dom0\n'
            'include: null\n'
            'passphrase_text: test123\n'
        )
        self.assertEqual(profile.getvalue(), expected_profile)

    def test_004_write_backup_profile_no_compress(self):
        args = qvm_backup.parser.parse_args(['--no-compress', '/var/tmp'],
            app=self.app)
        profile = io.StringIO()
        qvm_backup.write_backup_profile(profile, args)
        expected_profile = (
            'compression: false\n'
            'destination_path: /var/tmp\n'
            'destination_vm: dom0\n'
            'include: null\n'
        )
        self.assertEqual(profile.getvalue(), expected_profile)

    @mock.patch('qubesadmin.tools.qvm_backup.backup_profile_dir', '/tmp')
    @mock.patch('qubesadmin.tools.qvm_backup.input', create=True)
    @mock.patch('getpass.getpass')
    def test_010_main_save_profile_cancel(self, mock_getpass, mock_input):
        asyncio.set_event_loop(asyncio.new_event_loop())
        mock_input.return_value = 'n'
        mock_getpass.return_value = 'some password'
        self.app.qubesd_connection_type = 'socket'
        self.app.expected_calls[('dom0', 'admin.backup.Info', 'test-profile',
                None)] = \
            b'0\0backup summary'
        profile_path = '/tmp/test-profile.conf'
        try:
            qvm_backup.main(['--save-profile', 'test-profile', '/var/tmp'],
                app=self.app)
            expected_profile = (
                'compression: true\n'
                'destination_path: /var/tmp\n'
                'destination_vm: dom0\n'
                'include: null\n'
            )
            with open(profile_path, encoding="utf-8") as f_profile:
                self.assertEqual(expected_profile, f_profile.read())
        finally:
            os.unlink(profile_path)

    @mock.patch('qubesadmin.tools.qvm_backup.backup_profile_dir', '/tmp')
    @mock.patch('qubesadmin.tools.qvm_backup.input', create=True)
    @mock.patch('getpass.getpass')
    def test_011_main_save_profile_confirm(self, mock_getpass, mock_input):
        asyncio.set_event_loop(asyncio.new_event_loop())
        mock_input.return_value = 'y'
        mock_getpass.return_value = 'some password'
        self.app.qubesd_connection_type = 'socket'
        self.app.expected_calls[('dom0', 'admin.backup.Info', 'test-profile',
                None)] = \
            b'0\0backup summary'
        self.app.expected_calls[('dom0', 'admin.backup.Execute', 'test-profile',
                None)] = \
            b'0\0'
        profile_path = '/tmp/test-profile.conf'
        try:
            qvm_backup.main(['--save-profile', 'test-profile', '/var/tmp'],
                app=self.app)
            expected_profile = (
                'compression: true\n'
                'destination_path: /var/tmp\n'
                'destination_vm: dom0\n'
                'include: null\n'
                'passphrase_text: some password\n'
            )
            with open(profile_path, encoding="utf-8") as f_profile:
                self.assertEqual(expected_profile, f_profile.read())
        finally:
            os.unlink(profile_path)

    @mock.patch('qubesadmin.tools.qvm_backup.backup_profile_dir', '/tmp')
    @mock.patch('qubesadmin.tools.qvm_backup.input', create=True)
    @mock.patch('getpass.getpass')
    def test_012_main_existing_profile(self, mock_getpass, mock_input):
        asyncio.set_event_loop(asyncio.new_event_loop())
        mock_input.return_value = 'y'
        mock_getpass.return_value = 'some password'
        self.app.qubesd_connection_type = 'socket'
        self.app.expected_calls[('dom0', 'admin.backup.Info', 'test-profile',
                None)] = \
            b'0\0backup summary'
        self.app.expected_calls[('dom0', 'admin.backup.Execute', 'test-profile',
                None)] = \
            b'0\0'
        self.app.expected_calls[('dom0', 'admin.Events', None,
                None)] = \
            b'0\0'
        try:
            mock_events = mock.AsyncMock()
            patch = mock.patch(
                'qubesadmin.events.EventsDispatcher._get_events_reader',
                mock_events)
            patch.start()
            self.addCleanup(patch.stop)
            mock_events.side_effect = qubesadmin.tests.tools.MockEventsReader([
                b'1\0\0connection-established\0\0',
                b'1\0\0backup-progress\0backup_profile\0test-profile\0'
                b'progress\x000.25\0\0',
                ])
        except ImportError:
            pass

        qvm_backup.main(['--profile', 'test-profile'],
            app=self.app)
        self.assertFalse(os.path.exists('/tmp/test-profile.conf'))
        self.assertFalse(mock_getpass.called)

    @mock.patch('qubesadmin.tools.qvm_backup.backup_profile_dir', '/tmp')
    @mock.patch('qubesadmin.tools.qvm_backup.input', create=True)
    @mock.patch('getpass.getpass')
    def test_013_main_new_profile_vm(self, mock_getpass, mock_input):
        asyncio.set_event_loop(asyncio.new_event_loop())
        mock_input.return_value = 'y'
        mock_getpass.return_value = 'some password'
        self.app.qubesd_connection_type = 'qrexec'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qvm_backup.main(['-x', 'vm1', '/var/tmp'],
                app=self.app)
        expected_output = (
            'To perform the backup according to selected options, create '
            'backup profile (/tmp/profile_name.conf) in dom0 with following '
            'content:\n'
            'compression: true\n'
            'destination_path: /var/tmp\n'
            'destination_vm: dom0\n'
            'exclude:\n'
            '- vm1\n'
            'include: null\n'
            '# specify backup passphrase below\n'
            'passphrase_text: ...\n'
        )
        self.assertEqual(stdout.getvalue(), expected_output)

    @mock.patch('qubesadmin.tools.qvm_backup.backup_profile_dir', '/tmp')
    @mock.patch('qubesadmin.tools.qvm_backup.input', create=True)
    @mock.patch('getpass.getpass')
    def test_014_main_passphrase_file(self, mock_getpass, mock_input):
        asyncio.set_event_loop(asyncio.new_event_loop())
        mock_input.return_value = 'y'
        mock_getpass.return_value = 'some password'
        self.app.qubesd_connection_type = 'socket'
        self.app.expected_calls[('dom0', 'admin.backup.Info', 'test-profile',
                None)] = \
            b'0\0backup summary'
        self.app.expected_calls[('dom0', 'admin.backup.Execute', 'test-profile',
                None)] = \
            b'0\0'
        profile_path = '/tmp/test-profile.conf'
        try:
            stdin = io.StringIO()
            stdin.write('other passphrase\n')
            stdin.seek(0)
            with mock.patch('sys.stdin', stdin):
                qvm_backup.main(['--passphrase-file', '-', '--save-profile',
                    'test-profile', '/var/tmp'],
                    app=self.app)
            expected_profile = (
                'compression: true\n'
                'destination_path: /var/tmp\n'
                'destination_vm: dom0\n'
                'include: null\n'
                'passphrase_text: other passphrase\n'
            )
            with open(profile_path, encoding="utf-8") as f_profile:
                self.assertEqual(expected_profile, f_profile.read())
        finally:
            os.unlink(profile_path)

    def test_015_conflicting_args(self):
        with self.assertRaises(SystemExit):
            qvm_backup.main(['--profile', 'test-profile', '--compress'],
                app=self.app)
