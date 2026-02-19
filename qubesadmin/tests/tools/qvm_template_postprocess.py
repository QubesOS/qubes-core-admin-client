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

import argparse
import asyncio
import os
import subprocess
import tempfile
from unittest import mock
import qubesadmin.tests
import qubesadmin.tools.qvm_template_postprocess
from qubesadmin.exc import QubesException


class QubesLocalMock(qubesadmin.tests.QubesTest):
    def __init__(self):
        super().__init__()
        self.__class__ = qubesadmin.app.QubesLocal

    qubesd_call = qubesadmin.tests.QubesTest.qubesd_call
    run_service = qubesadmin.tests.QubesTest.run_service

class TC_00_qvm_template_postprocess(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        # pylint: disable=consider-using-with
        self.source_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        try:
            self.source_dir.cleanup()
        except FileNotFoundError:
            pass
        super().tearDown()

    def test_000_import_root_img_raw(self):
        root_img = os.path.join(self.source_dir.name, 'root.img')
        volume_data = b'volume data'
        with open(root_img, 'wb') as f_root:
            f_root.write(volume_data)

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[('test-vm', 'admin.vm.volume.List', None,
                None)] = \
            b'0\0root\nprivate\nvolatile\nkernel\n'

        self.app.expected_calls[(
            'test-vm', 'admin.vm.volume.ImportWithSize', 'root',
            str(len(volume_data)).encode() + b'\n' + volume_data)] = b'0\0'
        vm = self.app.domains['test-vm']
        qubesadmin.tools.qvm_template_postprocess.import_root_img(
            vm, self.source_dir.name)
        self.assertAllCalled()

    def test_001_import_root_img_tar_pre_mar_2024(self):
        root_img = os.path.join(self.source_dir.name, 'root.img')
        volume_data = b'volume data' * 1000
        with open(root_img, 'wb') as f_root:
            f_root.write(volume_data)

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

        self.app.expected_calls[(
            'test-vm', 'admin.vm.volume.ImportWithSize', 'root',
            str(len(volume_data)).encode() + b'\n' + volume_data)] = b'0\0'
        vm = self.app.domains['test-vm']
        try:
            qubesadmin.tools.qvm_template_postprocess.import_root_img(
                vm, self.source_dir.name)
        except QubesException as e:
            assert str(e).startswith(
                'template.rpm symlink not found for multi-part image')
        else:
            assert False

    def test_001_import_root_img_tar(self):
        root_img = os.path.join(self.source_dir.name, 'root.img')
        volume_data = b'volume data' * 1000
        with open(root_img, 'wb') as f_root:
            f_root.write(volume_data)

        subprocess.check_call(['tar', 'cf', 'root.img.tar', 'root.img'],
            cwd=self.source_dir.name)
        subprocess.check_call(['split', '-d', '-b', '1024', 'root.img.tar',
            'root.img.part.'], cwd=self.source_dir.name)
        os.unlink(root_img)

        spec = os.path.join(self.source_dir.name, 'template.spec')
        with open(spec, 'w', encoding="utf-8") as f_spec:
            f_spec.writelines((
                '%define _rpmdir %{expand:%%(pwd)}/build\n',
                'Name: test\n',
                'Summary: testing\n',
                'License: none\n',
                'Version: 6.6.6\n',
                'Release: 44\n',

                '%description\n',
                'test\n',

                '%prep\n',
                'mkdir -p $RPM_BUILD_ROOT\n',
                'mv %{expand:%%(pwd)}/root.img.part.* $RPM_BUILD_ROOT\n',
                'dd',
                ' if=$RPM_BUILD_ROOT/root.img.part.00',
                ' count=1',
                ' of=%{expand:%%(pwd)}/root.img.part.00\n',
                'ln -s',
                ' %{expand:%%(pwd)}/build/i386/test-6.6.6-44.i386.rpm',
                ' %{expand:%%(pwd)}/template.rpm\n',

                '%files\n',
                '/root.img.part.*\n',
            ))
        subprocess.check_call([
                'rpmbuild', '-bb', '--rmspec', '--target', 'i386-redhat-linux',
                '--clean', '-D', f'_topdir {self.source_dir.name}', spec
            ],
            cwd=self.source_dir.name,
            stdout=subprocess.DEVNULL)

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[('test-vm', 'admin.vm.volume.List', None,
                None)] = \
            b'0\0root\nprivate\nvolatile\nkernel\n'

        self.app.expected_calls[(
            'test-vm', 'admin.vm.volume.ImportWithSize', 'root',
            str(len(volume_data)).encode() + b'\n' + volume_data)] = b'0\0'
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
        with open(root_img, 'wb') as f_root:
            f_root.write(volume_data)

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.List', None, None)] = \
            b'0\0root\nprivate\nvolatile\nkernel\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.Info', 'root', None)] = \
            b'0\x00pool=default\n' \
            b'vid=vm-templates/test-vm/root\n' \
            b'size=10737418240\n' \
            b'usage=0\n' \
            b'rw=True\n' \
            b'source=\n' \
            b'save_on_stop=True\n' \
            b'snap_on_start=False\n' \
            b'revisions_to_keep=3\n' \
            b'is_outdated=False\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.List', None, None)] = \
            b'0\0default\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.Info', 'default', None)] = \
            b'0\0driver=file\ndir_path=' + self.source_dir.name.encode() + b'\n'

        vm = self.app.domains['test-vm']
        qubesadmin.tools.qvm_template_postprocess.import_root_img(
            vm, template_dir)
        self.assertAllCalled()

    def test_005_reset_private_img(self):
        self.app.qubesd_connection_type = 'socket'

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.List', None, None)] = \
            b'0\0root\nprivate\nvolatile\nkernel\n'
        self.app.expected_calls[('test-vm', 'admin.vm.volume.Clear', 'private',
                                 None)] = b'0\0'

        vm = self.app.domains['test-vm']
        qubesadmin.tools.qvm_template_postprocess.reset_private_img(vm)
        self.assertAllCalled()

    def test_010_import_appmenus(self):
        default_menu_items = [
            'org.gnome.Terminal.desktop',
            'firefox.desktop']
        menu_items = [
            'org.gnome.Terminal.desktop',
            'org.gnome.Software.desktop',
            'gnome-control-center.desktop']
        netvm_menu_items = [
            'org.gnome.Terminal.desktop',
            'nm-connection-editor.desktop']
        with open(os.path.join(self.source_dir.name,
                'vm-whitelisted-appmenus.list'), 'w',
                encoding="utf-8") as f_list:
            for entry in default_menu_items:
                f_list.write(entry + '\n')
        with open(os.path.join(self.source_dir.name,
                'whitelisted-appmenus.list'), 'w',
                encoding="utf-8") as f_list:
            for entry in menu_items:
                f_list.write(entry + '\n')
        with open(os.path.join(self.source_dir.name,
                'netvm-whitelisted-appmenus.list'), 'w',
                encoding="utf-8") as f_list:
            for entry in netvm_menu_items:
                f_list.write(entry + '\n')

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Set',
            'default-menu-items',
            ' '.join(default_menu_items).encode())] = b'0\0'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Set',
            'menu-items',
            ' '.join(menu_items).encode())] = b'0\0'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Set',
            'netvm-menu-items',
            ' '.join(netvm_menu_items).encode())] = b'0\0'

        vm = self.app.domains['test-vm']
        with mock.patch('subprocess.check_call') as mock_proc:
            qubesadmin.tools.qvm_template_postprocess.import_appmenus(
                vm, self.source_dir.name, skip_generate=False)
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
        default_menu_items = [
            'org.gnome.Terminal.desktop',
            'firefox.desktop']
        menu_items = [
            'org.gnome.Terminal.desktop',
            'org.gnome.Software.desktop',
            'gnome-control-center.desktop']
        netvm_menu_items = [
            'org.gnome.Terminal.desktop',
            'nm-connection-editor.desktop']
        with open(os.path.join(self.source_dir.name,
                'vm-whitelisted-appmenus.list'), 'w',
                encoding="utf-8") as f_list:
            for entry in default_menu_items:
                f_list.write(entry + '\n')
        with open(os.path.join(self.source_dir.name,
                'whitelisted-appmenus.list'), 'w',
                encoding="utf-8") as f_list:
            for entry in menu_items:
                f_list.write(entry + '\n')
        with open(os.path.join(self.source_dir.name,
                'netvm-whitelisted-appmenus.list'), 'w',
                encoding="utf-8") as f_list:
            for entry in netvm_menu_items:
                f_list.write(entry + '\n')
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Set',
            'default-menu-items',
            ' '.join(default_menu_items).encode())] = b'0\0'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Set',
            'menu-items',
            ' '.join(menu_items).encode())] = b'0\0'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Set',
            'netvm-menu-items',
            ' '.join(netvm_menu_items).encode())] = b'0\0'

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'

        mock_getuid.return_value = 0
        mock_getgrnam.configure_mock(**{
            'return_value.gr_mem.__getitem__.return_value': 'user'
        })

        vm = self.app.domains['test-vm']
        with mock.patch('subprocess.check_call') as mock_proc:
            qubesadmin.tools.qvm_template_postprocess.import_appmenus(
                vm, self.source_dir.name, skip_generate=False)
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
                'vm-whitelisted-appmenus.list'), 'w',
                encoding="utf-8") as f_list:
            f_list.write('org.gnome.Terminal.desktop\n')
            f_list.write('firefox.desktop\n')
        with open(os.path.join(self.source_dir.name,
                'whitelisted-appmenus.list'), 'w',
                encoding="utf-8") as f_list:
            f_list.write('org.gnome.Terminal.desktop\n')
            f_list.write('org.gnome.Software.desktop\n')
            f_list.write('gnome-control-center.desktop\n')

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'

        mock_getuid.return_value = 0
        mock_getgrnam.side_effect = KeyError

        vm = self.app.domains['test-vm']
        with mock.patch('subprocess.check_call') as mock_proc:
            qubesadmin.tools.qvm_template_postprocess.import_appmenus(
                vm, self.source_dir.name, skip_generate=False)
        self.assertEqual(mock_proc.mock_calls, [])
        self.assertAllCalled()

    def add_new_vm_side_effect(self, *_args, **_kwargs):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.domains.clear_cache()
        return self.app.domains['test-vm']

    async def wait_for_shutdown(self, vm):
        pass

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
            ('test-vm', 'admin.vm.property.Set', 'installed_by_rpm', b'True')] \
            = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Reset', 'netvm', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'qrexec', b'1')] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Start', None, None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Shutdown', None, None)] = b'0\0'

        if qubesadmin.tools.qvm_template_postprocess.have_events:
            patch_domain_shutdown = mock.patch(
                'qubesadmin.events.utils.wait_for_domain_shutdown')
            self.addCleanup(patch_domain_shutdown.stop)
            mock_domain_shutdown = patch_domain_shutdown.start()
            mock_domain_shutdown.side_effect = self.wait_for_shutdown
        else:
            self.app.expected_calls[
                ('test-vm', 'admin.vm.List', None, None)] = \
                b'0\0test-vm class=TemplateVM state=Halted\n'

        asyncio.set_event_loop(asyncio.new_event_loop())
        ret = qubesadmin.tools.qvm_template_postprocess.main([
            '--really', 'post-install', 'test-vm', self.source_dir.name],
            app=self.app)
        self.assertEqual(ret, 0)
        self.app.add_new_vm.assert_called_once_with('TemplateVM',
            name='test-vm', label='black', pool=None)
        mock_import_root_img.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name)
        mock_import_appmenus.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name, skip_generate=True)
        if qubesadmin.tools.qvm_template_postprocess.have_events:
            mock_domain_shutdown.assert_called_once_with([self.app.domains[
                'test-vm']])
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.PostInstall', {}),
            ('test-vm', 'qubes.PostInstall', b''),
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template_postprocess.import_appmenus')
    @mock.patch('qubesadmin.tools.qvm_template_postprocess.import_root_img')
    @mock.patch('qubesadmin.tools.qvm_template_postprocess.reset_private_img')
    def test_021_post_install_reinstall(self, mock_reset_private_img,
            mock_import_root_img, mock_import_appmenus):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.add_new_vm = mock.Mock()

        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Set', 'netvm', b'')] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Set', 'installed_by_rpm', b'True')] \
            = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Reset', 'netvm', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'qrexec', b'1')] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Start', None, None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Shutdown', None, None)] = b'0\0'

        if qubesadmin.tools.qvm_template_postprocess.have_events:
            patch_domain_shutdown = mock.patch(
                'qubesadmin.events.utils.wait_for_domain_shutdown')
            self.addCleanup(patch_domain_shutdown.stop)
            mock_domain_shutdown = patch_domain_shutdown.start()
            mock_domain_shutdown.side_effect = self.wait_for_shutdown
        else:
            self.app.expected_calls[
                ('test-vm', 'admin.vm.List', None, None)] = \
                b'0\0test-vm class=TemplateVM state=Halted\n'

        asyncio.set_event_loop(asyncio.new_event_loop())
        ret = qubesadmin.tools.qvm_template_postprocess.main([
            '--really', 'post-install', 'test-vm', self.source_dir.name],
            app=self.app)
        self.assertEqual(ret, 0)
        self.assertFalse(self.app.add_new_vm.called)
        mock_import_root_img.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name)
        mock_reset_private_img.assert_called_once_with(self.app.domains[
            'test-vm'])
        mock_import_appmenus.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name, skip_generate=True)
        if qubesadmin.tools.qvm_template_postprocess.have_events:
            mock_domain_shutdown.assert_called_once_with([self.app.domains[
                'test-vm']])
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.PostInstall', {}),
            ('test-vm', 'qubes.PostInstall', b''),
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template_postprocess.import_appmenus')
    @mock.patch('qubesadmin.tools.qvm_template_postprocess.import_root_img')
    @mock.patch('qubesadmin.tools.qvm_template_postprocess.reset_private_img')
    def test_022_post_install_skip_start(self, mock_reset_private_img,
            mock_import_root_img, mock_import_appmenus):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Set', 'installed_by_rpm', b'True')] \
            = b'0\0'
        self.app.add_new_vm = mock.Mock()

        if qubesadmin.tools.qvm_template_postprocess.have_events:
            patch_domain_shutdown = mock.patch(
                'qubesadmin.events.utils.wait_for_domain_shutdown')
            self.addCleanup(patch_domain_shutdown.stop)
            mock_domain_shutdown = patch_domain_shutdown.start()
            mock_domain_shutdown.side_effect = self.wait_for_shutdown

        asyncio.set_event_loop(asyncio.new_event_loop())
        ret = qubesadmin.tools.qvm_template_postprocess.main([
            '--really', '--skip-start', 'post-install', 'test-vm',
            self.source_dir.name],
            app=self.app)
        self.assertEqual(ret, 0)
        self.assertFalse(self.app.add_new_vm.called)
        mock_import_root_img.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name)
        mock_reset_private_img.assert_called_once_with(self.app.domains[
            'test-vm'])
        mock_import_appmenus.assert_called_once_with(self.app.domains[
            'test-vm'], self.source_dir.name, skip_generate=False)
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
            ('test-vm', 'admin.vm.property.Set', 'installed_by_rpm', b'False')]\
            = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'template', None)] = \
            b'2\0QubesNoSuchPropertyError\0\0invalid property ' \
            b'\'template\' of test-vm\0'

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
            b'2\0QubesNoSuchPropertyError\0\0invalid property ' \
            b'\'template\' of test-vm\0'
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

    def test_050_template_config(self):
        template_config = """gui=1
qrexec=1
linux-stubdom=1
net.fake-ip=192.168.1.100
net.fake-netmask=255.255.255.0
net.fake-gateway=192.168.1.1
virt-mode=hvm
kernel=
"""
        template_conf = os.path.join(self.source_dir.name, 'template.conf')
        with open(template_conf, 'w', encoding="utf-8") as f_conf:
            f_conf.write(template_config)
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[(
            'test-vm', 'admin.vm.feature.Set', 'gui', b'1')] = b'0\0'
        self.app.expected_calls[(
            'test-vm', 'admin.vm.feature.Set', 'qrexec', b'1')] = b'0\0'
        self.app.expected_calls[(
            'test-vm', 'admin.vm.feature.Set', 'linux-stubdom', b'1')] = b'0\0'
        self.app.expected_calls[(
            'test-vm', 'admin.vm.feature.Set', 'net.fake-ip',
            b'192.168.1.100')] = b'0\0'
        self.app.expected_calls[(
            'test-vm', 'admin.vm.feature.Set', 'net.fake-netmask',
            b'255.255.255.0')] = b'0\0'
        self.app.expected_calls[(
            'test-vm', 'admin.vm.feature.Set', 'net.fake-gateway',
            b'192.168.1.1')] = b'0\0'
        self.app.expected_calls[(
            'test-vm', 'admin.vm.property.Set', 'virt_mode', b'hvm')] = b'0\0'
        self.app.expected_calls[(
            'test-vm', 'admin.vm.property.Set', 'kernel', b'')] = b'0\0'

        vm = self.app.domains['test-vm']
        args = argparse.Namespace(
            allow_pv=False,
        )
        qubesadmin.tools.qvm_template_postprocess.import_template_config(
            args, template_conf, vm)
        self.assertAllCalled()

    def test_051_template_config_invalid(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        vm = self.app.domains['test-vm']
        args = argparse.Namespace(
            allow_pv=False,
        )
        with self.subTest('invalid feature value'):
            template_config = "gui=false\n"
            template_conf = os.path.join(self.source_dir.name, 'template.conf')
            with open(template_conf, 'w', encoding="utf-8") as f_conf:
                f_conf.write(template_config)
            qubesadmin.tools.qvm_template_postprocess.import_template_config(
                args, template_conf, vm)

        with self.subTest('invalid feature name'):
            template_config = "invalid=1\n"
            template_conf = os.path.join(self.source_dir.name, 'template.conf')
            with open(template_conf, 'w', encoding="utf-8") as f_conf:
                f_conf.write(template_config)
            qubesadmin.tools.qvm_template_postprocess.import_template_config(
                args, template_conf, vm)

        with self.subTest('invalid ip'):
            template_config = "net.fake-ip=1.2.3.4.5\n"
            template_conf = os.path.join(self.source_dir.name, 'template.conf')
            with open(template_conf, 'w', encoding="utf-8") as f_conf:
                f_conf.write(template_config)
            qubesadmin.tools.qvm_template_postprocess.import_template_config(
                args, template_conf, vm)

        with self.subTest('invalid virt-mode'):
            template_config = "virt-mode=invalid\n"
            template_conf = os.path.join(self.source_dir.name, 'template.conf')
            with open(template_conf, 'w', encoding="utf-8") as f_conf:
                f_conf.write(template_config)
            qubesadmin.tools.qvm_template_postprocess.import_template_config(
                args, template_conf, vm)

        with self.subTest('invalid kernel'):
            template_config = "kernel=1.2.3.4.5\n"
            template_conf = os.path.join(self.source_dir.name, 'template.conf')
            with open(template_conf, 'w', encoding="utf-8") as f_conf:
                f_conf.write(template_config)
            qubesadmin.tools.qvm_template_postprocess.import_template_config(
                args, template_conf, vm)
        self.assertAllCalled()

    def test_052_template_config_virt_mode_pv(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        vm = self.app.domains['test-vm']
        args = argparse.Namespace(
            allow_pv=False,
        )
        with self.subTest('not allowed'):
            template_config = "virt-mode=pv\n"
            template_conf = os.path.join(self.source_dir.name, 'template.conf')
            with open(template_conf, 'w', encoding="utf-8") as f_conf:
                f_conf.write(template_config)
            qubesadmin.tools.qvm_template_postprocess.import_template_config(
                args, template_conf, vm)
        with self.subTest('allowed'):
            args = argparse.Namespace(
                allow_pv=True,
            )
            self.app.expected_calls[(
                'test-vm', 'admin.vm.property.Set', 'virt_mode',
                b'pv')] = b'0\0'
            template_config = "virt-mode=pv\n"
            template_conf = os.path.join(self.source_dir.name, 'template.conf')
            with open(template_conf, 'w', encoding="utf-8") as f_conf:
                f_conf.write(template_config)
            qubesadmin.tools.qvm_template_postprocess.import_template_config(
                args, template_conf, vm)
        self.assertAllCalled()
