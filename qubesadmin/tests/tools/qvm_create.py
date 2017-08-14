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
import os
import tempfile

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
            self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
                None, b'name=new-vm label=red')] = b'0\x00'
            self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
                b'0\x00red\nblue\n'
            self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
                b'0\x00new-vm class=AppVM state=Halted\n'
            self.app.expected_calls[
                ('new-vm', 'admin.vm.volume.List', None, None)] = \
                b'0\x00root\nprivate\nvolatile\nkernel\n'
            self.app.expected_calls[
                ('new-vm', 'admin.vm.volume.Import', 'root', b'root data')] = \
                b'0\0'
            qubesadmin.tools.qvm_create.main(['-l', 'red',
                '--root-copy-from=' + root_file.name, 'new-vm'],
                app=self.app)
            self.assertAllCalled()
            self.assertTrue(os.path.exists(root_file.name))

    def test_006_root_move_from(self):
        with tempfile.NamedTemporaryFile(delete=False) as root_file:
            root_file.file.write(b'root data')
            root_file.file.flush()
            self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
                None, b'name=new-vm label=red')] = b'0\x00'
            self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
                b'0\x00red\nblue\n'
            self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
                b'0\x00new-vm class=AppVM state=Halted\n'
            self.app.expected_calls[
                ('new-vm', 'admin.vm.volume.List', None, None)] = \
                b'0\x00root\nprivate\nvolatile\nkernel\n'
            self.app.expected_calls[
                ('new-vm', 'admin.vm.volume.Import', 'root', b'root data')] = \
                b'0\0'
            qubesadmin.tools.qvm_create.main(['-l', 'red',
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
                    '--root-copy-from=' + root_file.name,
                    '--root-move-from=' + root_file.name,
                    'new-vm'],
                    app=self.app)
            self.assertAllCalled()
            self.assertTrue(os.path.exists(root_file.name))

    def test_008_root_invalid_path(self):
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_create.main(['-l', 'red',
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
