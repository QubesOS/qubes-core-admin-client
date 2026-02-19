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

# pylint: disable=missing-docstring

import os
import shutil
import socket
import subprocess
import unittest

import multiprocessing

from unittest import mock
from unittest.mock import call

import tempfile

import qubesadmin.exc
import qubesadmin.tests
import qubesadmin.events


class TC_00_VMCollection(qubesadmin.tests.QubesTestCase):
    def test_000_list(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.assertEqual(
            list(self.app.domains.keys()),
            ['test-vm'])
        self.assertAllCalled()

    def test_001_getitem(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
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
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.assertIn('test-vm', self.app.domains)
        self.assertAllCalled()

        self.assertNotIn('test-non-existent', self.app.domains)
        self.assertAllCalled()

    def test_003_iter(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.assertEqual([vm.name for vm in self.app.domains], ['test-vm'])
        self.assertAllCalled()

    def test_004_delitem(self):
        self.app.expected_calls[('test-vm', 'admin.vm.Remove', None, None)] = \
            b'0\x00'
        del self.app.domains['test-vm']
        self.assertAllCalled()

    def test_005_keys(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n'
        self.assertEqual(set(self.app.domains.keys()),
            {'test-vm', 'test-vm2'})
        self.assertAllCalled()

    def test_006_values(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n'
        values = self.app.domains.values()
        for obj in values:
            self.assertIsInstance(obj, qubesadmin.vm.QubesVM)
        self.assertEqual({vm.name for vm in values},
            {'test-vm', 'test-vm2'})
        self.assertAllCalled()

    def test_007_getitem_blind_mode(self):
        self.app.blind_mode = True
        try:
            vm = self.app.domains['test-vm']
            self.assertEqual(vm.name, 'test-vm')
        except KeyError:
            self.fail('VM not found in collection')
        self.assertAllCalled()

        with self.assertNotRaises(KeyError):
            vm = self.app.domains['test-non-existent']
        self.assertAllCalled()

    def test_008_in_blind_mode(self):
        self.app.blind_mode = True
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.assertIn('test-vm', self.app.domains)
        self.assertAllCalled()

        self.assertNotIn('test-non-existent', self.app.domains)
        self.assertAllCalled()

    def test_009_getitem_cache_class(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        try:
            vm = self.app.domains['test-vm']
            self.assertEqual(vm.name, 'test-vm')
            self.assertEqual(vm.klass, 'AppVM')
        except KeyError:
            self.fail('VM not found in collection')
        self.assertAllCalled()

    def test_010_getitem_cache_power_state(self):
        self.app.cache_enabled = True
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        try:
            vm = self.app.domains['test-vm']
            self.assertEqual(vm.name, 'test-vm')
            self.assertEqual(vm.klass, 'AppVM')
            self.assertEqual(vm.get_power_state(), 'Running')
        except KeyError:
            self.fail('VM not found in collection')
        self.assertAllCalled()

    def test_011_getitem_non_cache_power_state(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running mem=1024'
        try:
            vm = self.app.domains['test-vm']
            self.assertEqual(vm.name, 'test-vm')
            self.assertEqual(vm.klass, 'AppVM')
            self.assertEqual(vm.get_power_state(), 'Running')
        except KeyError:
            self.fail('VM not found in collection')
        self.assertAllCalled()

    def test_012_getitem_cached_object(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=Running\n'
        try:
            vm1 = self.app.domains['test-vm']
            vm2 = self.app.domains['test-vm']
            self.assertIs(vm1, vm2)
        except KeyError:
            self.fail('VM not found in collection')
        self.app.domains.clear_cache()
        # even after clearing the cache, the same instance should be returned
        # if the class haven't changed
        vm3 = self.app.domains['test-vm']
        self.assertIs(vm1, vm3)

        # change the class and expected different object
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=StandaloneVM state=Running\n'
        self.app.domains.clear_cache()
        vm4 = self.app.domains['test-vm']
        self.assertIsNot(vm1, vm4)
        self.assertAllCalled()



class TC_10_QubesBase(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.check_output_patch = mock.patch(
            'subprocess.check_output')
        self.check_output_mock = self.check_output_patch.start()

    def tearDown(self):
        self.check_output_patch.stop()
        super().tearDown()

    def test_010_new_simple(self):
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM', None,
                b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n'
        vm = self.app.add_new_vm('AppVM', 'new-vm', 'red')
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.klass, 'AppVM')
        self.assertAllCalled()

    def test_011_new_template(self):
        self.app.expected_calls[('dom0', 'admin.vm.Create.TemplateVM', None,
                b'name=new-template label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-template class=TemplateVM state=Running\n'
        vm = self.app.add_new_vm('TemplateVM', 'new-template', 'red')
        self.assertEqual(vm.name, 'new-template')
        self.assertEqual(vm.klass, 'TemplateVM')
        self.assertAllCalled()

    def test_012_new_template_based(self):
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'some-template', b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n'
        vm = self.app.add_new_vm('AppVM', 'new-vm', 'red', 'some-template')
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.klass, 'AppVM')
        self.assertAllCalled()

    def test_013_new_objects_params(self):
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'some-template', b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n' \
            b'some-template class=TemplateVM state=Running\n'
        vm = self.app.add_new_vm(self.app.get_vm_class('AppVM'), 'new-vm',
            self.app.get_label('red'), self.app.domains['some-template'])
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.klass, 'AppVM')
        self.assertAllCalled()

    def test_014_new_pool(self):
        self.app.expected_calls[('dom0', 'admin.vm.CreateInPool.AppVM', None,
                b'name=new-vm label=red pool=some-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n'
        vm = self.app.add_new_vm('AppVM', 'new-vm', 'red', pool='some-pool')
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.klass, 'AppVM')
        self.assertAllCalled()

    def test_015_new_pools(self):
        self.app.expected_calls[('dom0', 'admin.vm.CreateInPool.AppVM', None,
                b'name=new-vm label=red pool:private=some-pool '
                b'pool:volatile=other-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n'
        vm = self.app.add_new_vm('AppVM', 'new-vm', 'red',
            pools={'private': 'some-pool', 'volatile': 'other-pool'})
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.klass, 'AppVM')
        self.assertAllCalled()

    def test_016_new_template_based_default(self):
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            None, b'name=new-vm label=red')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Running\n'
        vm = self.app.add_new_vm('AppVM', 'new-vm', 'red',
            template=qubesadmin.DEFAULT)
        self.assertEqual(vm.name, 'new-vm')
        self.assertEqual(vm.klass, 'AppVM')
        self.assertAllCalled()

    def test_020_get_label(self):
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        label = self.app.get_label('red')
        self.assertEqual(label.name, 'red')
        self.assertAllCalled()

    def test_021_get_nonexistant_label(self):
        self.app.expected_calls[('dom0', 'admin.label.List', None, None)] = \
            b'0\x00red\nblue\n'
        with self.assertRaises(qubesadmin.exc.QubesLabelNotFoundError):
            self.app.get_label('green')
        self.assertAllCalled()

    def clone_setup_common_calls(self, src, dst):
        # have each property type with default=no, each special-cased,
        # and some with default=yes
        properties = {
            'label': 'default=False type=label red',
            'template': 'default=False type=vm test-template',
            'memory': 'default=False type=int 400',
            'kernel': 'default=False type=str 4.9.31',
            'netvm': 'default=False type=vm test-net',
            'virt_mode': 'default=False type=str hvm',
            'default_user': 'default=True type=str user',
        }
        self.app.expected_calls[
            (src, 'admin.vm.property.List', None, None)] = \
            b'0\0qid\nname\n' + \
            b'\n'.join(prop.encode() for prop in properties) + \
            b'\n'
        for prop, value in properties.items():
            self.app.expected_calls[
                (src, 'admin.vm.property.Get', prop, None)] = \
                b'0\0' + value.encode()
            # special cases handled by admin.vm.Create call
            if prop in ('label', 'template'):
                continue
            # default properties should not be set
            if 'default=True' in value:
                continue
            self.app.expected_calls[
                (dst, 'admin.vm.property.Set', prop,
                value.split()[-1].encode())] = b'0\0'

        # tags
        self.app.expected_calls[
            (src, 'admin.vm.tag.List', None, None)] = \
            b'0\0tag1\ntag2\n'
        self.app.expected_calls[
            (dst, 'admin.vm.tag.Set', 'tag1', None)] = b'0\0'
        self.app.expected_calls[
            (dst, 'admin.vm.tag.Set', 'tag2', None)] = b'0\0'

        # features
        self.app.expected_calls[
            (src, 'admin.vm.feature.List', None, None)] = \
            b'0\0feat1\nfeat2\n'
        self.app.expected_calls[
            (src, 'admin.vm.feature.Get', 'feat1', None)] = \
            b'0\0feat1-value with spaces'
        self.app.expected_calls[
            (src, 'admin.vm.feature.Get', 'feat2', None)] = \
            b'0\x001'
        self.app.expected_calls[
            (dst, 'admin.vm.feature.Set', 'feat1',
            b'feat1-value with spaces')] = b'0\0'
        self.app.expected_calls[
            (dst, 'admin.vm.feature.Set', 'feat2', b'1')] = b'0\0'

        # firewall
        rules = (
            b'action=drop dst4=192.168.0.0/24\n'
            b'action=accept\n'
        )
        self.app.expected_calls[
            (src, 'admin.vm.firewall.Get', None, None)] = \
            b'0\x00' + rules
        self.app.expected_calls[
            (dst, 'admin.vm.firewall.Set', None, rules)] = \
            b'0\x00'

        # notes
        self.app.expected_calls[
            (src, 'admin.vm.notes.Get', None, None)] = \
            b'0\0'

        # storage
        for vm in (src, dst):
            self.app.expected_calls[
                (vm, 'admin.vm.volume.Info', 'root', None)] = \
                b'0\x00pool=lvm\n' \
                b'vid=vm-' + vm.encode() + b'/root\n' \
                b'size=10737418240\n' \
                b'usage=2147483648\n' \
                b'rw=False\n' \
                b'internal=True\n' \
                b'source=vm-test-template/root\n' \
                b'save_on_stop=False\n' \
                b'snap_on_start=True\n'
            self.app.expected_calls[
                (vm, 'admin.vm.volume.Info', 'private', None)] = \
                b'0\x00pool=lvm\n' \
                b'vid=vm-' + vm.encode() + b'/private\n' \
                b'size=2147483648\n' \
                b'usage=214748364\n' \
                b'rw=True\n' \
                b'internal=True\n' \
                b'save_on_stop=True\n' \
                b'snap_on_start=False\n'
            self.app.expected_calls[
                (vm, 'admin.vm.volume.Info', 'volatile', None)] = \
                b'0\x00pool=lvm\n' \
                b'vid=vm-' + vm.encode() + b'/volatile\n' \
                b'size=10737418240\n' \
                b'usage=0\n' \
                b'rw=True\n' \
                b'internal=True\n' \
                b'source=None\n' \
                b'save_on_stop=False\n' \
                b'snap_on_start=False\n'
            self.app.expected_calls[
                (vm, 'admin.vm.volume.Info', 'kernel', None)] = \
                b'0\x00pool=linux-kernel\n' \
                b'vid=\n' \
                b'size=0\n' \
                b'usage=0\n' \
                b'rw=False\n' \
                b'internal=True\n' \
                b'source=None\n' \
                b'save_on_stop=False\n' \
                b'snap_on_start=False\n'
            self.app.expected_calls[
                (vm, 'admin.vm.volume.List', None, None)] = \
                b'0\x00root\nprivate\nvolatile\nkernel\n'
        self.app.expected_calls[
            (src, 'admin.vm.volume.CloneFrom', 'private', None)] = \
            b'0\x00token-private'
        self.app.expected_calls[
            (dst, 'admin.vm.volume.CloneTo', 'private', b'token-private')] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_pool_private', None)] = \
            b'0\0default=True type=str lvm'
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_pool_volatile', None)] = \
            b'0\0default=True type=str lvm'

    def test_030_clone(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        new_vm = self.app.clone_vm('test-vm', 'new-name')
        self.assertEqual(new_vm.name, 'new-name')
        self.check_output_mock.assert_called_once_with(
            ['qvm-appmenus', '--init', '--update',
                '--source', 'test-vm', 'new-name'],
            stderr=subprocess.STDOUT
        )
        self.assertAllCalled()

    def test_031_clone_object(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        new_vm = self.app.clone_vm(self.app.domains['test-vm'], 'new-name')
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()

    def test_032_clone_pool(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        for volume in ('root', 'private', 'volatile', 'kernel'):
            del self.app.expected_calls[
                'test-vm', 'admin.vm.volume.Info', volume, None]
        del self.app.expected_calls[
            'dom0', 'admin.property.Get', 'default_pool_private', None]
        del self.app.expected_calls[
            'dom0', 'admin.property.Get', 'default_pool_volatile', None]
        self.app.expected_calls[('dom0', 'admin.vm.CreateInPool.AppVM',
            'test-template',
            b'name=new-name label=red pool=some-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        new_vm = self.app.clone_vm('test-vm', 'new-name', pool='some-pool')
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()

    def test_033_clone_pools(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        for volume in ('root', 'private', 'volatile', 'kernel'):
            del self.app.expected_calls[
                'test-vm', 'admin.vm.volume.Info', volume, None]
        del self.app.expected_calls[
            'dom0', 'admin.property.Get', 'default_pool_private', None]
        del self.app.expected_calls[
            'dom0', 'admin.property.Get', 'default_pool_volatile', None]
        self.app.expected_calls[('dom0', 'admin.vm.CreateInPool.AppVM',
            'test-template',
            b'name=new-name label=red pool:private=some-pool '
            b'pool:volatile=other-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        new_vm = self.app.clone_vm('test-vm', 'new-name',
            pools={'private': 'some-pool', 'volatile': 'other-pool'})
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()

    def test_034_clone_class_change(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=StandaloneVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.Create.StandaloneVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        self.app.expected_calls[
            ('new-name', 'admin.vm.volume.Info', 'root', None)] = \
            b'0\x00pool=lvm\n' \
            b'vid=vm-new-name/root\n' \
            b'size=10737418240\n' \
            b'usage=2147483648\n' \
            b'rw=True\n' \
            b'internal=True\n' \
            b'source=None\n' \
            b'save_on_stop=True\n' \
            b'snap_on_start=False\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.CloneFrom', 'root', None)] = \
            b'0\x00token-root'
        self.app.expected_calls[
            ('new-name', 'admin.vm.volume.CloneTo', 'root', b'token-root')] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        new_vm = self.app.clone_vm('test-vm', 'new-name',
            new_cls='StandaloneVM')
        self.assertEqual(new_vm.name, 'new-name')
        self.assertEqual(new_vm.klass, 'StandaloneVM')
        self.assertAllCalled()

    def test_035_clone_fail(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.List', None, None)] = \
            b'0\0qid\nname\ntemplate\nlabel\nmemory\n'
        # simplify it a little, shouldn't get this far anyway
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'label', None)] = \
            b'0\0default=False type=label red'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'template', None)] = \
            b'0\0default=False type=vm test-template'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'memory', None)] = \
            b'0\0default=False type=int 400'
        self.app.expected_calls[
            ('new-name', 'admin.vm.property.Set', 'memory', b'400')] = \
            b'2\0QubesException\0\0something happened\0'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        self.app.expected_calls[('new-name', 'admin.vm.Remove', None, None)] = \
            b'0\x00'
        with self.assertRaises(qubesadmin.exc.QubesException):
            self.app.clone_vm('test-vm', 'new-name')
        self.assertAllCalled()

    def test_036_clone_ignore_errors_prop(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        self.app.expected_calls[
            ('new-name', 'admin.vm.property.Set', 'memory', b'400')] = \
            b'2\0QubesException\0\0something happened\0'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        new_vm = self.app.clone_vm('test-vm', 'new-name', ignore_errors=True)
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()

    def test_037_clone_ignore_errors_feature(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        self.app.expected_calls[
            ('new-name', 'admin.vm.feature.Set', 'feat2', b'1')] = \
            b'2\0QubesException\0\0something happened\0'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        new_vm = self.app.clone_vm('test-vm', 'new-name', ignore_errors=True)
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()

    def test_038_clone_ignore_errors_tag(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        self.app.expected_calls[
            ('new-name', 'admin.vm.tag.Set', 'tag1', None)] = \
            b'2\0QubesException\0\0something happened\0'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        new_vm = self.app.clone_vm('test-vm', 'new-name', ignore_errors=True)
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()

    def test_039_clone_ignore_errors_firewall(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        self.app.expected_calls[
            ('new-name', 'admin.vm.firewall.Set', None,
            b'action=drop dst4=192.168.0.0/24\naction=accept\n')] = \
            b'2\0QubesException\0\0something happened\0'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        new_vm = self.app.clone_vm('test-vm', 'new-name', ignore_errors=True)
        self.assertEqual(new_vm.name, 'new-name')
        self.assertAllCalled()

    def test_040_clone_ignore_errors_storage(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        self.app.expected_calls[
            ('new-name', 'admin.vm.volume.CloneTo', 'private',
            b'token-private')] = \
            b'2\0QubesException\0\0something happened\0'
        self.app.expected_calls[('new-name', 'admin.vm.Remove', None, None)] = \
            b'0\x00'
        del self.app.expected_calls[
            ('new-name', 'admin.vm.volume.Info', 'root', None)]
        del self.app.expected_calls[
            ('new-name', 'admin.vm.volume.Info', 'volatile', None)]
        with self.assertRaises(qubesadmin.exc.QubesException):
            self.app.clone_vm('test-vm', 'new-name', ignore_errors=True)
        self.assertAllCalled()

    def test_041_clone_fail_storage(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        self.app.expected_calls[
            ('new-name', 'admin.vm.volume.CloneTo', 'private',
            b'token-private')] = \
            b'2\0QubesException\0\0something happened\0'
        self.app.expected_calls[('new-name', 'admin.vm.Remove', None, None)] = \
            b'0\x00'
        del self.app.expected_calls[
            ('new-name', 'admin.vm.volume.Info', 'root', None)]
        del self.app.expected_calls[
            ('new-name', 'admin.vm.volume.Info', 'volatile', None)]
        with self.assertRaises(qubesadmin.exc.QubesException):
            self.app.clone_vm('test-vm', 'new-name')
        self.assertAllCalled()

    def test_042_clone_nondefault_pool(self):
        self.clone_setup_common_calls('test-vm', 'new-name')
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.Info', 'private', None)] = \
            b'0\x00pool=another\n' \
            b'vid=vm-test-vm/private\n' \
            b'size=2147483648\n' \
            b'usage=214748364\n' \
            b'rw=True\n' \
            b'internal=True\n' \
            b'save_on_stop=True\n' \
            b'snap_on_start=False\n'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.CreateInPool.AppVM',
            'test-template', b'name=new-name label=red pool:private=another')]\
            = b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b'0\0'
        new_vm = self.app.clone_vm('test-vm', 'new-name')
        self.assertEqual(new_vm.name, 'new-name')
        self.check_output_mock.assert_called_once_with(
            ['qvm-appmenus', '--init', '--update',
                '--source', 'test-vm', 'new-name'],
            stderr=subprocess.STDOUT
        )
        self.assertAllCalled()

    def test_043_clone_devices(self):
        self.clone_setup_common_calls('test-vm', 'new-name')

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-vm2 class=AppVM state=Halted\n' \
            b'test-vm3 class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'

        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'

        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = \
            b'0\0pci\n'

        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.pci.Assigned', None, None)] = \
            (b"0\0test-vm2+dev1 port_id='dev1' devclass='pci' "
             b"backend_domain='test-vm2' mode='required' "
             b"_ro='yes'\n"
             b"test-vm3+dev2 port_id='dev2' devclass='pci' "
             b"backend_domain='test-vm3' mode='required'\n")

        self.app.expected_calls[
            ('new-name', 'admin.vm.device.pci.Assign', 'test-vm2+dev1+_',
             b"device_id='*' port_id='dev1' "
             b"devclass='pci' backend_domain='test-vm2' mode='required' "
             b"frontend_domain='new-name' _ro='yes'")] = b'0\0'

        self.app.expected_calls[
            ('new-name', 'admin.vm.device.pci.Assign', 'test-vm3+dev2+_',
             b"device_id='*' port_id='dev2' "
             b"devclass='pci' backend_domain='test-vm3' mode='required' "
             b"frontend_domain='new-name'")] = b'0\0'

        new_vm = self.app.clone_vm('test-vm', 'new-name')
        self.assertEqual(new_vm.name, 'new-name')
        self.check_output_mock.assert_called_once_with(
            ['qvm-appmenus', '--init', '--update',
                '--source', 'test-vm', 'new-name'],
            stderr=subprocess.STDOUT
        )
        self.assertAllCalled()

    def test_044_clone_devices_fail(self):
        self.clone_setup_common_calls('test-vm', 'new-name')

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-vm2 class=AppVM state=Halted\n' \
            b'test-vm3 class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'

        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'

        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = \
            b'0\0pci\n'

        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.pci.Assigned', None, None)] = \
            (b"0\0test-vm2+dev1 port_id='dev1' devclass='pci' "
             b"backend_domain='test-vm2' mode='required' "
             b"_ro='yes'\n"
             b"test-vm3+dev2 port_id='dev2' devclass='pci' "
             b"backend_domain='test-vm3' mode='required'\n")

        self.app.expected_calls[
            ('new-name', 'admin.vm.device.pci.Assign', 'test-vm2+dev1+_',
             b"device_id='*' port_id='dev1' "
             b"devclass='pci' backend_domain='test-vm2' mode='required' "
             b"frontend_domain='new-name' _ro='yes'")] = b'0\0'

        self.app.expected_calls[
            ('new-name', 'admin.vm.device.pci.Assign', 'test-vm3+dev2+_',
             b"device_id='*' port_id='dev2' "
             b"devclass='pci' backend_domain='test-vm3' mode='required' "
             b"frontend_domain='new-name'")] = \
            b'2\0QubesException\0\0something happened\0'

        self.app.expected_calls[
            ('new-name', 'admin.vm.Remove', None, None)] = b'0\0'

        with self.assertRaises(qubesadmin.exc.QubesException):
            self.app.clone_vm('test-vm', 'new-name')

        self.assertAllCalled()

    def test_045_clone_notes_fail(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.notes.Get', None, None)] = \
            b'0\0Secret Note\0'
        self.app.expected_calls[
            ('new-name', 'admin.vm.notes.Set', None, b'Secret Note\0')] = \
            b'2\0QubesNotesException\0\0It was For Your Eyes Only!\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.List', None, None)] = \
            b'0\0qid\nname\ntemplate\nlabel\nmemory\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'label', None)] = \
            b'0\0default=False type=label red'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'template', None)] = \
            b'0\0default=False type=vm test-template'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.property.Get', 'memory', None)] = \
            b'0\0default=False type=int 400'
        self.app.expected_calls[
            ('new-name', 'admin.vm.property.Set', 'memory', b'400')] = \
            b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.List', None, None)] = \
            b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.List', None, None)] = \
            b'0\0'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-name class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n' \
            b'test-template class=TemplateVM state=Halted\n' \
            b'test-net class=AppVM state=Halted\n'
        self.app.expected_calls[('dom0', 'admin.vm.Create.AppVM',
            'test-template', b'name=new-name label=red')] = b'0\x00'
        self.app.expected_calls[('new-name', 'admin.vm.Remove', None, None)] = \
            b'0\x00'
        with self.assertRaises(qubesadmin.exc.QubesException):
            self.app.clone_vm('test-vm', 'new-name')
        self.assertAllCalled()

    def test_050_automatic_reset_cache(self):
        self.app.cache_enabled = True
        dispatcher = qubesadmin.events.EventsDispatcher(self.app)
        # first get few properties directly
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('vm1', 'admin.vm.property.GetAll', None, None)] = \
            b'0\0qid default=False type=int 1\n' \
            b'name default=False type=str vm1\n' \
            b'memory default=False type=int 400\n' \
            b'kernel default=False type=str 1.2.3\n'

        vm = self.app.domains['vm1']
        self.assertEqual(vm.memory, 400)
        self.assertEqual(vm.get_power_state(), 'Halted')
        self.assertAllCalled()
        # cache should be cleared when events connection is established
        dispatcher.handle(None, 'connection-established')
        self.app.actual_calls = []
        self.app.expected_calls[
            ('vm1', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running mem=400000 mem_static_max=400000 ' \
            b'cputime=0'
        self.app.expected_calls[
            ('vm1', 'admin.vm.property.GetAll', None, None)] = \
            b'0\0qid default=False type=int 1\n' \
            b'name default=False type=str vm1\n' \
            b'memory default=False type=int 500\n' \
            b'kernel default=False type=str 1.2.3\n'
        self.assertEqual(vm.memory, 500)
        self.assertEqual(vm.get_power_state(), 'Running')
        # should get the same instance
        self.assertIs(vm, self.app.domains['vm1'])
        self.assertAllCalled()
        self.app.actual_calls = []
        del self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)]
        del self.app.expected_calls[
            ('vm1', 'admin.vm.property.GetAll', None, None)]
        self.app.expected_calls[
            ('vm1', 'admin.vm.property.Get', 'memory', None)] = \
            b'0\0default=False type=int 600'
        # this one is cached already
        del self.app.expected_calls[
            ('vm1', 'admin.vm.CurrentState', None, None)]
        dispatcher.handle('vm1', 'property-set:memory',
            name='memory', newvalue='600', oldvalue='500')
        self.assertEqual(vm.memory, 600)
        self.assertEqual(vm.get_power_state(), 'Running')
        # update cached power state based on event
        dispatcher.handle('vm1', 'domain-shutdown')
        self.assertEqual(vm.get_power_state(), 'Halted')
        self.assertAllCalled()

    def test_051_space_in_vmname(self):
        with self.assertRaises(ValueError):
            self.app.add_new_vm('AppVM', 'VM Name with spaces', 'red')


class TC_20_QubesLocal(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.socket_dir = tempfile.mkdtemp()
        self.orig_sock = qubesadmin.config.QUBESD_SOCKET
        qubesadmin.config.QUBESD_SOCKET = os.path.join(self.socket_dir, 'sock')
        self.proc = None
        self.socket = None
        self.socket_pipe = None
        self.app = qubesadmin.app.QubesLocal()
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir)

    def listen_and_send(self, send_data):
        '''Listen on socket and send data in response.

        :param bytes send_data: data to send
        '''
        self.socket_pipe, child_pipe = multiprocessing.Pipe()
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(os.path.join(self.socket_dir, 'sock'))
        self.socket.listen(1)

        def worker(sock, pipe, send_data_):
            conn, _ = sock.accept()
            pipe.send(conn.makefile('rb').read())
            conn.sendall(send_data_)
            conn.close()
        self.proc = multiprocessing.Process(target=worker,
            args=(self.socket, child_pipe, send_data))
        self.proc.start()
        self.socket.close()

    def get_request(self):
        '''Get request sent to "qubesd" mock'''
        return self.socket_pipe.recv()

    def tearDown(self):
        qubesadmin.config.QUBESD_SOCKET = self.orig_sock
        if self.proc is not None:
            try:
                self.proc.terminate()
            except OSError:
                pass
        shutil.rmtree(self.socket_dir)
        super().tearDown()

    def test_000_qubesd_call(self):
        self.listen_and_send(b'0\0')
        self.app.qubesd_call('test-vm', 'some.method', 'arg1', b'payload')
        self.assertEqual(self.get_request(),
            b'some.method+arg1 dom0 name test-vm\0payload')

    def test_001_qubesd_call_none_arg(self):
        self.listen_and_send(b'0\0')
        self.app.qubesd_call('test-vm', 'some.method', None, b'payload')
        self.assertEqual(self.get_request(),
            b'some.method+ dom0 name test-vm\0payload')

    def test_002_qubesd_call_none_payload(self):
        self.listen_and_send(b'0\0')
        self.app.qubesd_call('test-vm', 'some.method', None, None)
        self.assertEqual(self.get_request(),
            b'some.method+ dom0 name test-vm\0')

    def test_003_qubesd_call_payload_stream(self):
        payload_input = os.path.join(self.tmpdir, 'payload-input')
        with open(payload_input, 'w+b') as payload_file:
            payload_file.write(b'some payload\n')
            payload_file.seek(0)

            self._call_test_service_with_payload_stream(
                payload_file, expected=b'some payload\n')

    def test_004_qubesd_call_payload_stream_proc(self):
        with subprocess.Popen(['echo', 'some payload'],
                              stdout=subprocess.PIPE) as echo:
            self._call_test_service_with_payload_stream(
                echo.stdout, expected=b'some payload\n')

    def test_005_qubesd_call_payload_stream_with_prefix(self):
        payload_input = os.path.join(self.tmpdir, 'payload-input')
        with open(payload_input, 'w+b') as payload_file:
            payload_file.write(b'some payload\n')
            payload_file.seek(0)

            self._call_test_service_with_payload_stream(
                payload_file, payload=b'first line\n',
                expected=b'first line\nsome payload\n')

    def _call_test_service_with_payload_stream(
            self, payload_stream, payload=None, expected=b''):
        service_path = os.path.join(self.tmpdir, 'test.service')
        with open(service_path, 'w', encoding="utf-8") as f_service:
            f_service.write(
                '#!/bin/bash\n'
                'env > {dir}/env\n'
                'echo "$@" > {dir}/args\n'
                'cat > {dir}/payload\n'
                'echo -en \'0\\0return-value\'\n'.format(dir=self.tmpdir))
        os.chmod(service_path, 0o755)

        with mock.patch('qubesadmin.config.QREXEC_SERVICES_DIR',
                        self.tmpdir):
            value = self.app.qubesd_call(
                'test-vm', 'test.service',
                'some-arg', payload=payload, payload_stream=payload_stream)
        self.assertEqual(value, b'return-value')
        self.assertTrue(os.path.exists(self.tmpdir + '/env'))
        with open(self.tmpdir + '/env', encoding="utf-8") as env:
            self.assertIn('QREXEC_REMOTE_DOMAIN=dom0\n', env)
            self.assertIn('QREXEC_REQUESTED_TARGET=test-vm\n', env)
        self.assertTrue(os.path.exists(self.tmpdir + '/args'))
        with open(self.tmpdir + '/args', encoding="utf-8") as args:
            self.assertEqual(args.read(), 'some-arg\n')
        self.assertTrue(os.path.exists(self.tmpdir + '/payload'))
        with open(self.tmpdir + '/payload', 'rb') as payload_f:
            self.assertEqual(payload_f.read(), expected)

    @mock.patch('os.isatty', lambda fd: fd == 2)
    def test_010_run_service(self):
        self.listen_and_send(b'0\0')
        with mock.patch('subprocess.Popen') as mock_proc:
            self.app.run_service('some-vm', 'service.name')
            mock_proc.assert_called_once_with([
                qubesadmin.config.QREXEC_CLIENT,
                '-d', 'some-vm', '-T', 'DEFAULT:QUBESRPC service.name+ dom0'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

        self.assertEqual(self.get_request(),
            b'admin.vm.Start+ dom0 name some-vm\0')

    def test_011_run_service_filter_esc(self):
        self.listen_and_send(b'0\0')
        with mock.patch('subprocess.Popen') as mock_proc:
            self.app.run_service('some-vm', 'service.name', filter_esc=True)
            mock_proc.assert_called_once_with([
                qubesadmin.config.QREXEC_CLIENT,
                '-d', 'some-vm', '-t', '-T',
                'DEFAULT:QUBESRPC service.name+ dom0'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

        self.assertEqual(self.get_request(),
            b'admin.vm.Start+ dom0 name some-vm\0')

    @mock.patch('os.isatty', lambda fd: fd == 2)
    def test_012_run_service_user(self):
        self.listen_and_send(b'0\0')
        with mock.patch('subprocess.Popen') as mock_proc:
            self.app.run_service('some-vm', 'service.name', user='user')
            mock_proc.assert_called_once_with([
                qubesadmin.config.QREXEC_CLIENT,
                '-d', 'some-vm', '-T',
                'user:QUBESRPC service.name+ dom0'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

        self.assertEqual(self.get_request(),
            b'admin.vm.Start+ dom0 name some-vm\0')

    def test_013_run_service_default_target(self):
        with self.assertRaises(ValueError):
            self.app.run_service('', 'service.name')


class TC_30_QubesRemote(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.proc_mock = mock.MagicMock()
        self.proc_mock.configure_mock(**{
            'return_value.returncode': 0,
            'return_value.__enter__.return_value': self.proc_mock.return_value,
        })
        self.proc_patch = mock.patch('subprocess.Popen', self.proc_mock)
        self.proc_patch.start()
        self.app = qubesadmin.app.QubesRemote()

    def set_proc_stdout(self, send_data):
        self.proc_mock.configure_mock(**{
            'return_value.communicate.return_value': (send_data, None)
        })

    def tearDown(self):
        self.proc_patch.stop()
        super().tearDown()

    def test_000_qubesd_call(self):
        self.set_proc_stdout(b'0\0')
        self.app.qubesd_call('test-vm', 'some.method', 'arg1', b'payload')
        # pylint: disable=unnecessary-dunder-call
        self.assertEqual(self.proc_mock.mock_calls, [
            mock.call([qubesadmin.config.QREXEC_CLIENT_VM, 'test-vm',
                'some.method+arg1'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE),
            mock.call().__enter__(),
            mock.call().communicate(b'payload'),
            mock.call().__exit__(None, None, None),
        ])

    def test_001_qubesd_call_none_arg(self):
        self.set_proc_stdout(b'0\0')
        self.app.qubesd_call('test-vm', 'some.method', None, b'payload')
        # pylint: disable=unnecessary-dunder-call
        self.assertEqual(self.proc_mock.mock_calls, [
            mock.call([qubesadmin.config.QREXEC_CLIENT_VM, 'test-vm',
                'some.method'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE),
            mock.call().__enter__(),
            mock.call().communicate(b'payload'),
            mock.call().__exit__(None, None, None),
        ])

    def test_002_qubesd_call_none_payload(self):
        self.set_proc_stdout(b'0\0')
        self.app.qubesd_call('test-vm', 'some.method', None, None)
        # pylint: disable=unnecessary-dunder-call
        self.assertEqual(self.proc_mock.mock_calls, [
            mock.call([qubesadmin.config.QREXEC_CLIENT_VM, 'test-vm',
                'some.method'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE),
            mock.call().__enter__(),
            mock.call().communicate(None),
            mock.call().__exit__(None, None, None),
        ])

    def test_003_qubesd_call_payload_stream(self):
        self.set_proc_stdout(b'0\0return-value')
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir)

        payload_input = os.path.join(tmpdir, 'payload-input')
        with open(payload_input, 'w+b') as payload_file:
            payload_file.write(b'some payload\n')
            payload_file.seek(0)

            value = self.app.qubesd_call('test-vm', 'some.method',
                'some-arg', payload_stream=payload_file)
        # pylint: disable=unnecessary-dunder-call
        self.assertListEqual(self.proc_mock.mock_calls, [
            mock.call(
                [qubesadmin.config.QREXEC_CLIENT_VM, 'test-vm',
                 'some.method+some-arg'],
                stdin=payload_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE),
            mock.call().__enter__(),
            mock.call().communicate(),
            mock.call().__exit__(None, None, None),
        ])
        self.assertEqual(value, b'return-value')

    def test_004_qubesd_call_payload_stream_with_prefix(self):
        self.set_proc_stdout(b'0\0return-value')
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir)

        payload_input = os.path.join(tmpdir, 'payload-input')
        with open(payload_input, 'w+b') as payload_file:
            payload_file.write(b'some payload\n')
            payload_file.seek(0)

            value = self.app.qubesd_call('test-vm', 'some.method',
                'some-arg', payload=b'first line\n',
                payload_stream=payload_file)
        # pylint: disable=unnecessary-dunder-call
        self.assertListEqual(self.proc_mock.mock_calls, [
            mock.call([qubesadmin.config.QREXEC_CLIENT_VM, 'test-vm',
                'some.method+some-arg'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE),
            mock.call().__enter__(),
            mock.call().stdin.write(b'first line\n'),
            mock.call().stdin.write(b'some payload\n'),
            mock.call().communicate(),
            mock.call().__exit__(None, None, None),
        ])
        self.assertEqual(value, b'return-value')

    @mock.patch('os.isatty', lambda fd: fd == 2)
    def test_010_run_service(self):
        self.app.run_service('some-vm', 'service.name')
        self.proc_mock.assert_called_once_with([
            qubesadmin.config.QREXEC_CLIENT_VM,
            '-T', 'some-vm', 'service.name'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

    @mock.patch('os.isatty', lambda fd: fd == 2)
    def test_011_run_service_filter_esc(self):
        self.app.run_service('some-vm', 'service.name', filter_esc=True)
        self.proc_mock.assert_called_once_with([
            qubesadmin.config.QREXEC_CLIENT_VM,
            '-t', '-T', 'some-vm', 'service.name'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

    @mock.patch('os.isatty', lambda fd: fd == 2)
    def test_012_run_service_user(self):
        with self.assertRaises(ValueError):
            self.app.run_service('some-vm', 'service.name', user='user')

    @mock.patch('os.isatty', lambda fd: fd == 2)
    def test_013_run_service_default_target(self):
        self.app.run_service('', 'service.name')
        self.proc_mock.assert_called_once_with([
            qubesadmin.config.QREXEC_CLIENT_VM,
            '-T', '', 'service.name'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

    @mock.patch('os.isatty', lambda fd: fd == 2)
    def test_014_run_service_no_autostart1(self):
        self.set_proc_stdout( b'0\x00power_state=Running')
        self.app.run_service('some-vm', 'service.name', autostart=False)
        # pylint: disable=unnecessary-dunder-call
        self.proc_mock.assert_has_calls([
            call([qubesadmin.config.QREXEC_CLIENT_VM,
                  'some-vm', 'admin.vm.CurrentState'],
                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE),
            call().__enter__(),
            call().communicate(None),
            call().__exit__(None, None, None),
            call([qubesadmin.config.QREXEC_CLIENT_VM,
                  '-T', 'some-vm', 'service.name'],
                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE),
        ])

    @mock.patch('os.isatty', lambda fd: fd == 2)
    def test_015_run_service_no_autostart2(self):
        self.set_proc_stdout( b'0\x00power_state=Halted')
        with self.assertRaises(qubesadmin.exc.QubesVMNotRunningError):
            self.app.run_service('some-vm', 'service.name', autostart=False)
        self.proc_mock.assert_called_once_with([
            qubesadmin.config.QREXEC_CLIENT_VM,
            'some-vm', 'admin.vm.CurrentState'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
