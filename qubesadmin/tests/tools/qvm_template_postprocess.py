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
import asyncio
import os
import subprocess
import tempfile
from unittest import mock
import qubesadmin.tests
import qubesadmin.tools.qvm_template_postprocess


class QubesLocalMock(qubesadmin.tests.QubesTest):
    def __init__(self):
        super(QubesLocalMock, self).__init__()
        self.__class__ = qubesadmin.app.QubesLocal

    qubesd_call = qubesadmin.tests.QubesTest.qubesd_call
    run_service = qubesadmin.tests.QubesTest.run_service

class TC_00_qvm_template_postprocess(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super(TC_00_qvm_template_postprocess, self).setUp()
        self.source_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        try:
            self.source_dir.cleanup()
        except FileNotFoundError:
            pass
        super(TC_00_qvm_template_postprocess, self).tearDown()

    def test_000_import_root_img_raw(self):
        root_img = os.path.join(self.source_dir.name, 'root.img')
        volume_data = b'volume data'
        with open(root_img, 'wb') as f:
            f.write(volume_data)

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[('test-vm', 'admin.vm.volume.List', None,
                None)] = \
            b'0\0root\nprivate\nvolatile\nkernel\n'
        self.app.expected_calls[('test-vm', 'admin.vm.volume.Resize', 'root',
                str(len(volume_data)).encode())] = \
            b'0\0'

        self.app.expected_calls[('test-vm', 'admin.vm.volume.Import', 'root',
            volume_data)] = b'0\0'
        vm = self.app.domains['test-vm']
        qubesadmin.tools.qvm_template_postprocess.import_root_img(
            vm, self.source_dir.name)
        self.assertAllCalled()

    def test_001_import_root_img_tar(self):
        root_img = os.path.join(self.source_dir.name, 'root.img')
        volume_data = b'volume data' * 1000
        with open(root_img, 'wb') as f:
            f.write(volume_data)

        subprocess.check_call(['tar', 'cf', 'root.img.tar', 'root.img'],
            cwd=self.source_dir.name)
        subprocess.check_call(['split', '-d', '-b', '1024', 'root.img.tar',
            'root.img.part.'], cwd=self.source_dir.name)
        os.unlink(root_img)

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[('test-vm', 'admin.vm.volume.List', None,
                None)] = \
            b'0\0root\nprivate\nvolatile\nkernel\n'
        self.app.expected_calls[('test-vm', 'admin.vm.volume.Resize', 'root',
                str(len(volume_data)).encode())] = \
            b'0\0'

        self.app.expected_calls[('test-vm', 'admin.vm.volume.Import', 'root',
            volume_data)] = b'0\0'
        vm = self.app.domains['test-vm']
        qubesadmin.tools.qvm_template_postprocess.import_root_img(
            vm, self.source_dir.name)
        self.assertAllCalled()

    def test_002_import_root_img_no_overwrite(self):
        self.app.qubesd_connection_type = 'socket'

        template_dir = os.path.join(self.source_dir.name, 'vm-templates',
            'test-vm')
        os.makedirs(template_dir)
        root_img = os.path.join(template_dir, 'root.img')
        volume_data = b'volume data'
        with open(root_img, 'wb') as f:
            f.write(volume_data)

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.List', None, None)] = \
            b'0\0root\nprivate\nvolatile\nkernel\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.Info', 'root', None)] = \
            b'0\0pool=default\nvid=vm-templates/test-vm/root\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.List', None, None)] = \
            b'0\0default\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.Info', 'default', None)] = \
            b'0\0driver=file\ndir_path=' + self.source_dir.name.encode() + b'\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.Resize', 'root',
                str(len(volume_data)).encode())] = \
            b'0\0'

        vm = self.app.domains['test-vm']
        qubesadmin.tools.qvm_template_postprocess.import_root_img(
            vm, template_dir)
        self.assertAllCalled()

    def test_010_import_appmenus(self):
        with open(os.path.join(self.source_dir.name,
                'vm-whitelisted-appmenus.list'), 'w') as f:
            f.write('org.gnome.Terminal.desktop\n')
            f.write('firefox.desktop\n')
        with open(os.path.join(self.source_dir.name,
                'whitelisted-appmenus.list'), 'w') as f:
            f.write('org.gnome.Terminal.desktop\n')
            f.write('org.gnome.Software.desktop\n')
            f.write('gnome-control-center.desktop\n')

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'

        vm = self.app.domains['test-vm']
        with mock.patch('subprocess.check_call') as mock_proc:
            qubesadmin.tools.qvm_template_postprocess.import_appmenus(
                vm, self.source_dir.name)
        self.assertEqual(mock_proc.mock_calls, [
            mock.call(['qvm-appmenus',
                '--set-default-whitelist=' + os.path.join(self.source_dir.name,
                    'vm-whitelisted-appmenus.list'), 'test-vm']),
            mock.call(['qvm-appmenus', '--set-whitelist=' + os.path.join(
                self.source_dir.name, 'whitelisted-appmenus.list'), 'test-vm']),
        ])
        self.assertAllCalled()

    @mock.patch('grp.getgrnam')
    @mock.patch('os.getuid')
    def test_011_import_appmenus_as_root(self, mock_getuid, mock_getgrnam):
        with open(os.path.join(self.source_dir.name,
                'vm-whitelisted-appmenus.list'), 'w') as f:
            f.write('org.gnome.Terminal.desktop\n')
            f.write('firefox.desktop\n')
        with open(os.path.join(self.source_dir.name,
                'whitelisted-appmenus.list'), 'w') as f:
            f.write('org.gnome.Terminal.desktop\n')
            f.write('org.gnome.Software.desktop\n')
            f.write('gnome-control-center.desktop\n')

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'

        mock_getuid.return_value = 0
        mock_getgrnam.configure_mock(**{
            'return_value.gr_mem.__getitem__.return_value': 'user'
        })

        vm = self.app.domains['test-vm']
        with mock.patch('subprocess.check_call') as mock_proc:
            qubesadmin.tools.qvm_template_postprocess.import_appmenus(
                vm, self.source_dir.name)
        self.assertEqual(mock_proc.mock_calls, [
            mock.call(['runuser', '-u', 'user', '--', 'env', 'DISPLAY=:0',
                'qvm-appmenus',
                '--set-default-whitelist=' + os.path.join(self.source_dir.name,
                    'vm-whitelisted-appmenus.list'), 'test-vm']),
            mock.call(['runuser', '-u', 'user', '--', 'env', 'DISPLAY=:0',
                'qvm-appmenus', '--set-whitelist=' + os.path.join(
                self.source_dir.name, 'whitelisted-appmenus.list'), 'test-vm']),
        ])
        self.assertAllCalled()

    @mock.patch('grp.getgrnam')
    @mock.patch('os.getuid')
    def test_012_import_appmenus_missing_user(self, mock_getuid, mock_getgrnam):
        with open(os.path.join(self.source_dir.name,
                'vm-whitelisted-appmenus.list'), 'w') as f:
            f.write('org.gnome.Terminal.desktop\n')
            f.write('firefox.desktop\n')
        with open(os.path.join(self.source_dir.name,
                'whitelisted-appmenus.list'), 'w') as f:
            f.write('org.gnome.Terminal.desktop\n')
            f.write('org.gnome.Software.desktop\n')
            f.write('gnome-control-center.desktop\n')

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'

        mock_getuid.return_value = 0
        mock_getgrnam.side_effect = KeyError

        vm = self.app.domains['test-vm']
        with mock.patch('subprocess.check_call') as mock_proc:
            qubesadmin.tools.qvm_template_postprocess.import_appmenus(
                vm, self.source_dir.name)
        self.assertEqual(mock_proc.mock_calls, [])
        self.assertAllCalled()

    def add_new_vm_side_effect(self, *args, **kwargs):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.domains.clear_cache()
        return self.app.domains['test-vm']

    @mock.patch('qubesadmin.tools.qvm_template_postprocess.import_appmenus')
    @mock.patch('qubesadmin.tools.qvm_template_postprocess.import_root_img')
    def test_020_post_install(self, mock_import_root_img,
            mock_import_appmenus):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0'
        self.app.add_new_vm = mock.Mock(side_effect=self.add_new_vm_side_effect)

        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Set', 'netvm', b'')] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Reset', 'netvm', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'qrexec', b'True')] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Start', None, None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Shutdown', None, None)] = b'0\0'

        if qubesadmin.tools.qvm_template_postprocess.have_events:
            patch_domain_shutdown = mock.patch(
                'qubesadmin.events.utils.wait_for_domain_shutdown')
            self.addCleanup(patch_domain_shutdown.stop)
            mock_domain_shutdown = patch_domain_shutdown.start()
        else:
            self.app.expected_calls[
                ('test-vm', 'admin.vm.List', None, None)] = \
                b'0\0test-vm class=TemplateVM state=Halted\n'

        ret = qubesadmin.tools.qvm_template_postprocess.main([
            '--really', 'post-install', 'test-vm', self.source_dir.name],
            app=self.app)
        self.assertEqual(ret, 0)
        self.app.add_new_vm.assert_called_once_with('TemplateVM',
            name='test-vm', label='black')
        mock_import_root_img.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name)
        mock_import_appmenus.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name)
        if qubesadmin.tools.qvm_template_postprocess.have_events:
            mock_domain_shutdown.assert_called_once_with(self.app.domains[
                'test-vm'], 60)
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.PostInstall', {}),
            ('test-vm', 'qubes.PostInstall', b''),
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template_postprocess.import_appmenus')
    @mock.patch('qubesadmin.tools.qvm_template_postprocess.import_root_img')
    def test_021_post_install_reinstall(self, mock_import_root_img,
            mock_import_appmenus):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.add_new_vm = mock.Mock()

        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Set', 'netvm', b'')] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Reset', 'netvm', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'qrexec', b'True')] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Start', None, None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Shutdown', None, None)] = b'0\0'

        if qubesadmin.tools.qvm_template_postprocess.have_events:
            patch_domain_shutdown = mock.patch(
                'qubesadmin.events.utils.wait_for_domain_shutdown')
            self.addCleanup(patch_domain_shutdown.stop)
            mock_domain_shutdown = patch_domain_shutdown.start()
        else:
            self.app.expected_calls[
                ('test-vm', 'admin.vm.List', None, None)] = \
                b'0\0test-vm class=TemplateVM state=Halted\n'

        ret = qubesadmin.tools.qvm_template_postprocess.main([
            '--really', 'post-install', 'test-vm', self.source_dir.name],
            app=self.app)
        self.assertEqual(ret, 0)
        self.assertFalse(self.app.add_new_vm.called)
        mock_import_root_img.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name)
        mock_import_appmenus.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name)
        if qubesadmin.tools.qvm_template_postprocess.have_events:
            mock_domain_shutdown.assert_called_once_with(self.app.domains[
                'test-vm'], 60)
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.PostInstall', {}),
            ('test-vm', 'qubes.PostInstall', b''),
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template_postprocess.import_appmenus')
    @mock.patch('qubesadmin.tools.qvm_template_postprocess.import_root_img')
    def test_022_post_install_skip_start(self, mock_import_root_img,
            mock_import_appmenus):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.add_new_vm = mock.Mock()

        if qubesadmin.tools.qvm_template_postprocess.have_events:
            patch_domain_shutdown = mock.patch(
                'qubesadmin.events.utils.wait_for_domain_shutdown')
            self.addCleanup(patch_domain_shutdown.stop)
            mock_domain_shutdown = patch_domain_shutdown.start()

        ret = qubesadmin.tools.qvm_template_postprocess.main([
            '--really', '--skip-start', 'post-install', 'test-vm',
            self.source_dir.name],
            app=self.app)
        self.assertEqual(ret, 0)
        self.assertFalse(self.app.add_new_vm.called)
        mock_import_root_img.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name)
        mock_import_appmenus.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name)
        if qubesadmin.tools.qvm_template_postprocess.have_events:
            self.assertFalse(mock_domain_shutdown.called)
        self.assertEqual(self.app.service_calls, [])
        self.assertAllCalled()

    def test_030_pre_remove(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[('test-vm', 'admin.vm.Remove', None, None)] = \
            b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'template', None)] = \
            b'2\0QubesNoSuchPropertyError\0\0invalid property \'template\' of ' \
            b'test-vm\0'

        ret = qubesadmin.tools.qvm_template_postprocess.main([
            '--really', 'pre-remove', 'test-vm',
            self.source_dir.name],
            app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(self.app.service_calls, [])
        self.assertAllCalled()

    def test_031_pre_remove_existing_appvm(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n' \
            b'test-vm2 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'template', None)] = \
            b'2\0QubesNoSuchPropertyError\0\0invalid property \'template\' of ' \
            b'test-vm\0'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.property.Get', 'template', None)] = \
            b'0\0default=no type=vm test-vm'

        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_template_postprocess.main([
                '--really', 'pre-remove', 'test-vm',
                self.source_dir.name],
                app=self.app)
        self.assertEqual(self.app.service_calls, [])
        self.assertAllCalled()

    def test_040_missing_really(self):
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_template_postprocess.main([
                'post-install', 'test-vm', self.source_dir.name],
                app=self.app)
        self.assertAllCalled()
