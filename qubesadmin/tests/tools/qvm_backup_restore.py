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

# pylint: disable=missing-docstring,protected-access

import itertools
from unittest import mock

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_backup_restore
from qubesadmin.backup import BackupVM
from qubesadmin.backup.restore import BackupRestore
from qubesadmin.backup.dispvm import RestoreInDisposableVM


class TC_00_qvm_backup_restore(qubesadmin.tests.QubesTestCase):
    @mock.patch('qubesadmin.tools.qvm_backup_restore.input', create=True)
    @mock.patch('getpass.getpass')
    @mock.patch('qubesadmin.tools.qvm_backup_restore.BackupRestore')
    def test_000_simple(self, mock_backup, mock_getpass, mock_input):
        mock_getpass.return_value = 'testpass'
        mock_input.return_value = 'Y'
        vm1 = BackupVM()
        vm1.name = 'test-vm'
        vm1.backup_path = 'path/in/backup'
        vm1.template = None
        vm1.klass = 'StandaloneVM'
        vm1.label = 'red'
        mock_restore_info = {
            1: BackupRestore.VMToRestore(vm1),
        }
        mock_backup.configure_mock(**{
            'return_value.get_restore_summary.return_value': '',
            'return_value.get_restore_info.return_value': mock_restore_info,
        })
        with mock.patch('qubesadmin.tools.qvm_backup_restore.handle_broken') \
                as mock_handle_broken:
            qubesadmin.tools.qvm_backup_restore.main(['/some/path'],
                app=self.app)
            mock_handle_broken.assert_called_once_with(
                self.app, mock.ANY, mock_restore_info)
        mock_backup.assert_called_once_with(
            self.app, '/some/path', None, 'testpass',
            force_compression_filter=None, location_is_service=False)
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_backup_restore.input', create=True)
    @mock.patch('getpass.getpass')
    @mock.patch('qubesadmin.tools.qvm_backup_restore.BackupRestore')
    def test_001_selected_vms(self, mock_backup, mock_getpass, mock_input):
        mock_getpass.return_value = 'testpass'
        mock_input.return_value = 'Y'
        vm1 = BackupVM()
        vm1.name = 'test-vm'
        vm1.backup_path = 'path/in/backup'
        vm1.template = None
        vm1.klass = 'StandaloneVM'
        vm1.label = 'red'
        vm2 = BackupVM()
        vm2.name = 'test-vm2'
        vm2.backup_path = 'path/in/backup2'
        vm2.template = None
        vm2.klass = 'StandaloneVM'
        vm2.label = 'red'
        mock_restore_info = {
            1: BackupRestore.VMToRestore(vm1),
            2: BackupRestore.VMToRestore(vm2),
        }
        exclude_list = []
        mock_backup.configure_mock(**{
            'return_value.get_restore_summary.return_value': '',
            'return_value.options.exclude': exclude_list,
            'return_value.get_restore_info.return_value': mock_restore_info,
        })
        qubesadmin.tools.qvm_backup_restore.main(['/some/path', 'test-vm'],
            app=self.app)
        mock_backup.assert_called_once_with(
            self.app, '/some/path', None, 'testpass',
            force_compression_filter=None, location_is_service=False)
        self.assertEqual(mock_backup.return_value.options.exclude, ['test-vm2'])
        self.assertAllCalled()

    def test_010_handle_broken_no_problems(self):
        vm1 = BackupVM()
        vm1.name = 'test-vm'
        vm1.backup_path = 'path/in/backup'
        vm1.template = None
        vm1.klass = 'StandaloneVM'
        vm1.label = 'red'
        mock_restore_info = {
            1: BackupRestore.VMToRestore(vm1),
        }
        mock_args = mock.Mock()
        mock_args.verify_only = False
        self.app.log = mock.Mock()
        qubesadmin.tools.qvm_backup_restore.handle_broken(
            self.app, mock_args, mock_restore_info)
        self.assertEqual(self.app.log.mock_calls, [
            mock.call.info(
                'The above VMs will be copied and added to your system.'),
            mock.call.info(
                'Existing VMs will NOT be removed.'),
        ])

    def assertAppropriateLogging(self, missing_name, action):
        '''
        :param missing_name: NetVM or TemplateVM
        :param action: 'skip_broken', 'ignore_missing'
        :return:
        '''

        expected_calls = [
            mock.call.info(
                'The above VMs will be copied and added to your system.'),
            mock.call.info(
                'Existing VMs will NOT be removed.'),
            mock.call.warning(
                '*** One or more {}s are missing on the host! ***'.format(
                    missing_name)),
        ]
        if action == 'skip_broken':
            expected_calls.append(
                mock.call.warning(
                    'Skipping broken entries: VMs that depend on missing {}s '
                    'will NOT be restored.'.format(missing_name))
            )
        elif action == 'ignore_missing':
            expected_calls.append(
                mock.call.warning(
                    'Ignoring missing entries: VMs that depend on missing '
                    '{}s will have default value assigned.'.format(
                        missing_name))
            )
        self.assertEqual(self.app.log.mock_calls, expected_calls)


    def test_011_handle_broken_missing_template(self):
        vm1 = BackupVM()
        vm1.name = 'test-vm'
        vm1.backup_path = 'path/in/backup'
        vm1.template = 'not-existing-template'
        vm1.klass = 'AppVM'
        vm1.label = 'red'
        mock_restore_info = {
            1: BackupRestore.VMToRestore(vm1),
        }
        mock_restore_info[1].problems.add(
            BackupRestore.VMToRestore.MISSING_TEMPLATE)
        with self.subTest('skip_broken'):
            mock_args = mock.Mock()
            mock_args.skip_broken = True
            mock_args.verify_only = False
            self.app.log = mock.Mock()
            qubesadmin.tools.qvm_backup_restore.handle_broken(
                self.app, mock_args, mock_restore_info)
            self.assertAppropriateLogging('TemplateVM', 'skip_broken')
        with self.subTest('ignore_missing'):
            mock_args = mock.Mock()
            mock_args.skip_broken = False
            mock_args.ignore_missing = True
            mock_args.verify_only = False
            self.app.log = mock.Mock()
            qubesadmin.tools.qvm_backup_restore.handle_broken(
                self.app, mock_args, mock_restore_info)
            self.assertAppropriateLogging('TemplateVM', 'ignore_missing')
        with self.subTest('error'):
            mock_args = mock.Mock()
            mock_args.skip_broken = False
            mock_args.ignore_missing = False
            mock_args.verify_only = False
            self.app.log = mock.Mock()
            with self.assertRaises(qubesadmin.exc.QubesException):
                qubesadmin.tools.qvm_backup_restore.handle_broken(
                    self.app, mock_args, mock_restore_info)
            self.assertAppropriateLogging('TemplateVM', 'error')

    def test_012_handle_broken_missing_netvm(self):
        vm1 = BackupVM()
        vm1.name = 'test-vm'
        vm1.backup_path = 'path/in/backup'
        vm1.netvm = 'not-existing-netvm'
        vm1.klass = 'StandaloneVM'
        vm1.label = 'red'
        mock_restore_info = {
            1: BackupRestore.VMToRestore(vm1),
        }
        mock_restore_info[1].problems.add(
            BackupRestore.VMToRestore.MISSING_NETVM)
        with self.subTest('skip_broken'):
            mock_args = mock.Mock()
            mock_args.skip_broken = True
            mock_args.verify_only = False
            self.app.log = mock.Mock()
            qubesadmin.tools.qvm_backup_restore.handle_broken(
                self.app, mock_args, mock_restore_info)
            self.assertAppropriateLogging('NetVM', 'skip_broken')
        with self.subTest('ignore_missing'):
            mock_args = mock.Mock()
            mock_args.skip_broken = False
            mock_args.ignore_missing = True
            mock_args.verify_only = False
            self.app.log = mock.Mock()
            qubesadmin.tools.qvm_backup_restore.handle_broken(
                self.app, mock_args, mock_restore_info)
            self.assertAppropriateLogging('NetVM', 'ignore_missing')
        with self.subTest('error'):
            mock_args = mock.Mock()
            mock_args.skip_broken = False
            mock_args.ignore_missing = False
            mock_args.verify_only = False
            self.app.log = mock.Mock()
            with self.assertRaises(qubesadmin.exc.QubesException):
                qubesadmin.tools.qvm_backup_restore.handle_broken(
                    self.app, mock_args, mock_restore_info)
            self.assertAppropriateLogging('NetVM', 'error')

    def test_100_restore_in_dispvm_parser(self):
        """Verify if qvm-backup-restore tool options matches un-parser
        for paranoid restore mode"""
        parser = qubesadmin.tools.qvm_backup_restore.parser
        actions = parser._get_optional_actions()
        options_tool = set(
            itertools.chain(*(a.option_strings for a in actions)))

        options_parser = set(itertools.chain(
            *(o.opts for o in RestoreInDisposableVM.arguments.values())))
        self.assertEqual(options_tool, options_parser)
