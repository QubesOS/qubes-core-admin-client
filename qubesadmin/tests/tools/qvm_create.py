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

import os
import tempfile
import unittest.mock
import subprocess

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_create


class TC_00_qvm_create(qubesadmin.tests.QubesTestCase):
    def test_000_just_appvm(self):
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM', None,
            b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n'
        qubesadmin.tools.qvm_create.main(['-l', 'red', 'new-vm'], app=self.app)
        self.assertAllCalled()

    def test_001_missing_vm(self):
        with self.assertRaises(SystemExit):
            with qubesadmin.tests.tools.StderrBuffer() as stderr:
                qubesadmin.tools.qvm_create.main(['-l', 'red'], app=self.app)
        self.assertIn('NAME', stderr.getvalue())
        self.assertAllCalled()

    def test_002_custom_template(self):
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'some-template', b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n'
        qubesadmin.tools.qvm_create.main(['-l', 'red', '-t',
            'some-template', 'new-vm'], app=self.app)
        self.assertAllCalled()

    def test_003_properties(self):
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            None, b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n'
        self.app.expected_calls[('new-vm', 'admin.vm.property.Set',
            'netvm', b'sys-whonix')] = b'0\x00'
        qubesadmin.tools.qvm_create.main(['-l', 'red', '--prop',
            'netvm=sys-whonix', 'new-vm'],
            app=self.app)
        self.assertAllCalled()

    def test_004_pool(self):
        self.app.expected_calls[('dom0', 'admin.vm.CreateInPool.AppVM',
            None, b'name=new-vm label=red pool=some-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n'
        qubesadmin.tools.qvm_create.main(['-l', 'red', '-P', 'some-pool',
            'new-vm'],
            app=self.app)
        self.assertAllCalled()

    def test_005_pools(self):
        self.app.expected_calls[('dom0', 'admin.vm.CreateInPool.AppVM',
            None, b'name=new-vm label=red pool:private=some-pool '
                  b'pool:volatile=other-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n'
        qubesadmin.tools.qvm_create.main(['-l', 'red', '--pool',
            'private=some-pool', '--pool', 'volatile=other-pool', 'new-vm'],
            app=self.app)
        self.assertAllCalled()

    def test_005_root_copy_from(self):
        with tempfile.NamedTemporaryFile() as root_file:
            root_file.file.write(b'root data')
            root_file.file.flush()
            self.app.expected_calls[('dom0', 'admin.vm.Create.StandaloneVM',
                None, b'name=new-vm label=red')] = b'0\x00'
            self.app.expected_calls[('dom0', 'admin.label.List', None,
                None)] = b'0\x00red\nblue\n'
            self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
                b'0\x00new-vm class=AppVM state=Halted\n'
            self.app.expected_calls[
                ('new-vm', 'admin.vm.volume.List', None, None)] = \
                b'0\x00root\nprivate\nvolatile\nkernel\n'
            self.app.expected_calls[
                ('new-vm', 'admin.vm.volume.ImportWithSize', 'root',
                 b'9\nroot data')] = b'0\0'
            qubesadmin.tools.qvm_create.main(['-l', 'red', '-C', 'StandaloneVM',
                '--root-copy-from=' + root_file.name, 'new-vm'],
                app=self.app)
            self.assertAllCalled()
            self.assertTrue(os.path.exists(root_file.name))

    def test_006_root_move_from(self):
        with tempfile.NamedTemporaryFile(delete=False) as root_file:
            root_file.file.write(b'root data')
            root_file.file.flush()
            self.app.expected_calls[('dom0', 'admin.vm.Create.StandaloneVM',
                None, b'name=new-vm label=red')] = b'0\x00'
            self.app.expected_calls[('dom0', 'admin.label.List', None,
                None)] = b'0\x00red\nblue\n'
            self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
                b'0\x00new-vm class=AppVM state=Halted\n'
            self.app.expected_calls[
                ('new-vm', 'admin.vm.volume.List', None, None)] = \
                b'0\x00root\nprivate\nvolatile\nkernel\n'
            self.app.expected_calls[
                ('new-vm', 'admin.vm.volume.ImportWithSize', 'root',
                 b'9\nroot data')] = b'0\0'
            qubesadmin.tools.qvm_create.main(['-l', 'red', '-C', 'StandaloneVM',
                '--root-move-from=' + root_file.name, 'new-vm'],
                app=self.app)
            self.assertAllCalled()
            self.assertFalse(os.path.exists(root_file.name))

    def test_007_root_move_copy_both(self):
        with tempfile.NamedTemporaryFile() as root_file:
            root_file.file.write(b'root data')
            root_file.file.flush()
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_create.main(['-l', 'red',
                    '-C', 'StandaloneVM',
                    '--root-copy-from=' + root_file.name,
                    '--root-move-from=' + root_file.name,
                    'new-vm'],
                    app=self.app)
            self.assertAllCalled()
            self.assertTrue(os.path.exists(root_file.name))

    def test_008_root_invalid_path(self):
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_create.main(['-l', 'red', '-C', 'StandaloneVM',
                '--root-copy-from=/invalid', 'new-vm'],
                app=self.app)
        self.assertAllCalled()

    def test_009_help_classes(self):
        self.app.expected_calls[('dom0', 'admin.vmclass.List',
            None, None)] = b'0\x00StandaloneVM\nAppVM\nTemplateVM\nDispVM\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_create.main(['--help-classes'],
                app=self.app)
            self.assertEqual(stdout.getvalue(),
                'AppVM\nDispVM\nStandaloneVM\nTemplateVM\n')
        self.assertAllCalled()

    @unittest.mock.patch('subprocess.check_output')
    def test_011_standalonevm(self, check_output_mock):
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00template class=TemplateVM state=Halted\n' \
            b'new-vm class=StandaloneVM state=Halted\n'
        self.app.expected_calls[
            ('template', 'admin.vm.property.Get', 'label', None)] = \
            b'0\x00default=False type=label blue'
        self.app.expected_calls[
            ('template', 'admin.vm.property.Get', 'vcpus', None)] = \
            b'0\x00default=False type=int 2'
        self.app.expected_calls[
            ('template', 'admin.vm.property.Get', 'kernel', None)] = \
            b'0\x00default=True type=str kernel-version'
        self.app.expected_calls[
            ('template', 'admin.vm.property.Get', 'memory', None)] = \
            b'0\x00default=True type=int 400'
        self.app.expected_calls[
            ('template', 'admin.vm.property.Get', 'template', None)] = \
            b'2\x00QubesNoSuchPropertyError\x00\x00No such property\x00'
        self.app.expected_calls[
            ('template', 'admin.vm.property.List', None, None)] = \
            b'0\x00name\n' \
            b'label\n' \
            b'vcpus\n' \
            b'kernel\n' \
            b'memory\n'
        self.app.expected_calls[
            ('template', 'admin.vm.tag.List', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('template', 'admin.vm.feature.List', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('template', 'admin.vm.firewall.Get', None, None)] = \
            b'0\x00'
        self.app.expected_calls[('dom0', 'admin.vm.Create.StandaloneVM', None,
            b'name=new-vm label=blue')] = b'0\x00'
        # TODO this is weird...
        self.app.expected_calls[
            ('new-vm', 'admin.vm.property.Set', 'label', b'red')] = \
            b'0\x00'
        self.app.expected_calls[
            ('new-vm', 'admin.vm.property.Set', 'vcpus', b'2')] = \
            b'0\x00'
        self.app.expected_calls[
            ('new-vm', 'admin.vm.firewall.Set', None, b'')] = \
            b'0\x00'
        self.app.expected_calls[
            ('template', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\nvolatile\nkernel\n'
        self.app.expected_calls[
            ('new-vm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\nvolatile\nkernel\n'
        self.app.expected_calls[
            ('new-vm', 'admin.vm.volume.Info', 'root', None)] = \
            b'0\x00' \
            b'snap_on_start=False\n' \
            b'save_on_stop=True\n' \
            b'pool=other-pool\n' \
            b'vid=new-vm-root\n' \
            b'rw=True\n' \
            b'size=2\n'
        self.app.expected_calls[
            ('new-vm', 'admin.vm.volume.Info', 'private', None)] = \
            b'0\x00' \
            b'snap_on_start=False\n' \
            b'save_on_stop=True\n' \
            b'pool=other-pool\n' \
            b'vid=new-vm-private\n' \
            b'rw=True\n' \
            b'size=2\n'
        self.app.expected_calls[
            ('new-vm', 'admin.vm.volume.Info', 'volatile', None)] = \
            b'0\x00' \
            b'snap_on_start=False\n' \
            b'save_on_stop=False\n' \
            b'pool=other-pool\n' \
            b'vid=new-vm-volatile\n' \
            b'rw=True\n' \
            b'size=2\n'
        self.app.expected_calls[
            ('new-vm', 'admin.vm.volume.Info', 'kernel', None)] = \
            b'0\x00' \
            b'snap_on_start=False\n' \
            b'save_on_stop=False\n' \
            b'pool=linux-kernel\n' \
            b'vid=kernel-version\n' \
            b'rw=False\n' \
            b'size=2\n'
        self.app.expected_calls[
            ('template', 'admin.vm.volume.CloneFrom', 'root', None)] = \
            b'0\0clone-cookie'
        self.app.expected_calls[
            ('template', 'admin.vm.notes.Get', None, None)] = \
            b'0\0'
        self.app.expected_calls[
            ('new-vm', 'admin.vm.volume.CloneTo', 'root', b'clone-cookie')] = \
            b'0\0'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        qubesadmin.tools.qvm_create.main(['-C', 'StandaloneVM',
            '-t', 'template', '-l', 'red', 'new-vm'],
            app=self.app)
        check_output_mock.assert_called_once_with(
            ['qvm-appmenus', '--init', '--update',
                '--source', 'template', 'new-vm'],
            stderr=subprocess.STDOUT)
        self.assertAllCalled()

    def test_012_invalid_label(self):
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        with self.assertRaises(SystemExit):
            with qubesadmin.tests.tools.StderrBuffer() as stderr:
                qubesadmin.tools.qvm_create.main(['-l', 'invalid', 'name'],
                    app=self.app)
        self.assertIn('red, blue', stderr.getvalue())
        self.assertAllCalled()

    def test_013_root_copy_from_template_based(self):
        with tempfile.NamedTemporaryFile() as root_file:
            root_file.file.write(b'root data')
            root_file.file.flush()
            with self.assertRaises(SystemExit):
                with qubesadmin.tests.tools.StderrBuffer() as stderr:
                    qubesadmin.tools.qvm_create.main(['-l', 'red',
                        '--root-copy-from=' + root_file.name, 'new-vm'],
                        app=self.app)
            self.assertIn('--root-copy-from', stderr.getvalue())
            self.assertAllCalled()

    def test_014_standalone_shortcut(self):
        self.app.expected_calls[('dom0', 'admin.vm.Create.StandaloneVM',
            None, b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=StandaloneVM state=Halted\n'
        qubesadmin.tools.qvm_create.main(
            ['-l', 'red', '--standalone', 'new-vm'],
            app=self.app)
        self.assertAllCalled()

    def test_015_disp_shortcut(self):
        self.app.expected_calls[('dom0', 'admin.vm.Create.DispVM',
            None, b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=DispVM state=Halted\n'
        qubesadmin.tools.qvm_create.main(['--disp', 'new-vm'],
            app=self.app)
        self.assertAllCalled()
