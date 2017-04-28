# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

import qubesmgmt.tests


class TC_00_VMCollection(qubesmgmt.tests.QubesTestCase):
    def test_000_list(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.assertEqual(
            list(self.app.domains.keys()),
            ['test-vm'])
        self.assertAllCalled()

    def test_001_getitem(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        try:
            vm = self.app.domains['test-vm']
            self.assertEqual(vm.name, 'test-vm')
        except KeyError:
            self.fail('VM not found in collection')
        self.assertAllCalled()

        with self.assertRaises(KeyError):
            vm = self.app.domains['test-non-existent']
        self.assertAllCalled()

    def test_002_in(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.assertIn('test-vm', self.app.domains)
        self.assertAllCalled()

        self.assertNotIn('test-non-existent', self.app.domains)
        self.assertAllCalled()

    def test_003_iter(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.assertEqual([vm.name for vm in self.app.domains], ['test-vm'])
        self.assertAllCalled()

    def test_004_delitem(self):
        self.app.expected_calls[('test-vm', 'mgmt.vm.Remove', None, None)] = \
            b'0\x00'
        del self.app.domains['test-vm']
        self.assertAllCalled()


class TC_10_QubesBase(qubesmgmt.tests.QubesTestCase):
    def test_010_new_simple(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.Create.AppVM', None,
                b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n'
        vm = self.app.add_new_vm('AppVM', 'new-vm', 'red')
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.__class__.__name__, 'AppVM')
        self.assertAllCalled()

    def test_011_new_template(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.Create.TemplateVM', None,
                b'name=new-template label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-template class=TemplateVM state=Running\n'
        vm = self.app.add_new_vm('TemplateVM', 'new-template', 'red')
        self.assertEqual(vm.name, 'new-template')
        self.assertEqual(vm.__class__.__name__, 'TemplateVM')
        self.assertAllCalled()

    def test_012_new_template_based(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.Create.AppVM',
            'some-template', b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n'
        vm = self.app.add_new_vm('AppVM', 'new-vm', 'red', 'some-template')
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.__class__.__name__, 'AppVM')
        self.assertAllCalled()

    def test_013_new_objects_params(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.Create.AppVM',
            'some-template', b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n' \
            b'some-template class=TemplateVM state=Running\n'
        vm = self.app.add_new_vm(self.app.get_vm_class('AppVM'), 'new-vm',
            self.app.get_label('red'), self.app.domains['some-template'])
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.__class__.__name__, 'AppVM')
        self.assertAllCalled()

    def test_014_new_pool(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.CreateInPool.AppVM', None,
                b'name=new-vm label=red pool=some-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n'
        vm = self.app.add_new_vm('AppVM', 'new-vm', 'red', pool='some-pool')
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.__class__.__name__, 'AppVM')
        self.assertAllCalled()

    def test_015_new_pools(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.CreateInPool.AppVM', None,
                b'name=new-vm label=red pool:private=some-pool '
                b'pool:volatile=other-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n'
        vm = self.app.add_new_vm('AppVM', 'new-vm', 'red',
            pools={'private': 'some-pool', 'volatile': 'other-pool'})
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.__class__.__name__, 'AppVM')
        self.assertAllCalled()

    def test_020_get_label(self):
        self.app.expected_calls[('dom0', 'mgmt.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        label = self.app.get_label('red')
        self.assertEqual(label.name, 'red')
        self.assertAllCalled()

    def test_030_clone(self):
        self.app.expected_calls[('test-vm', 'mgmt.vm.Clone', None,
            b'name=new-name')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        new_vm = self.app.clone_vm('test-vm', 'new-name')
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()

    def test_031_clone_object(self):
        self.app.expected_calls[('test-vm', 'mgmt.vm.Clone', None,
            b'name=new-name')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        new_vm = self.app.clone_vm(self.app.domains['test-vm'], 'new-name')
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()

    def test_032_clone_pool(self):
        self.app.expected_calls[('test-vm', 'mgmt.vm.CloneInPool', None,
            b'name=new-name pool=some-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        new_vm = self.app.clone_vm('test-vm', 'new-name', pool='some-pool')
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()

    def test_033_clone_pools(self):
        self.app.expected_calls[('test-vm', 'mgmt.vm.CloneInPool', None,
            b'name=new-name pool:private=some-pool '
            b'pool:volatile=other-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        new_vm = self.app.clone_vm('test-vm', 'new-name',
            pools={'private': 'some-pool', 'volatile': 'other-pool'})
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()
