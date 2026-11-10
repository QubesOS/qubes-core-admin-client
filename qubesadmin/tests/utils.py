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

import qubesadmin.tests
import qubesadmin.utils


class TestVMUsage(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()

        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n' \
            b'template1 class=TemplateVM state=Halted\n' \
            b'template2 class=TemplateVM state=Running\n' \
            b'vm2 class=AppVM state=Running\n' \
            b'sys-net class=AppVM state=Running\n' \
            b'sys-firewall class=AppVM state=Running\n' \
            b'test-dvm class=AppVM state=Running\n' \
            b'disp1 class=DispVM state=Running\n' \
            b'disp2 class=DispVM state=Running\n'

        self.global_properties = ['default_dispvm', 'default_netvm',
                                  'default_guivm', 'default_audiovm',
                                  'default_template', 'clockvm', 'updatevm',
                                  'management_dispvm']

        for prop in self.global_properties:
            self.app.expected_calls[
                ('dom0', 'admin.property.Get', prop, None)] = \
                b'0\x00default=True type=vm vm2'

        self.vms = [
            'vm1', 'vm2', 'sys-net', 'sys-firewall', 'template1', 'template2',
            'test-dvm', 'disp1', 'disp2',
        ]

        self.vm_properties = [
            'template', 'netvm', 'guivm', 'audiovm', 'default_dispvm',
            'management_dispvm'
        ]

        for vm in self.vms:
            self.app.expected_calls[
                (vm, 'admin.vm.property.Get', 'is_preload', None)
            ] = b'2\0QubesNoSuchPropertyError\0\0invalid property\0'
            for prop in self.vm_properties:
                if not prop.startswith('template') or \
                        not vm.startswith('template'):
                    self.app.expected_calls[
                        (vm, 'admin.vm.property.Get', prop, None)] = \
                        b'0\x00default=False type=vm template1'
                else:
                    self.app.expected_calls[
                        (vm, 'admin.vm.property.Get', prop, None)] = \
                        b'2\0QubesNoSuchPropertyError\0\0invalid property\0'


    def test_00_only_global(self):
        result = qubesadmin.utils.vm_dependencies(self.app,
                                                  self.app.domains['vm2'])

        self.assertListEqual(result,
                             [(None, prop) for prop in self.global_properties],
                             "Incorrect global properties listed.")

    def test_01_only_vm(self):
        result = qubesadmin.utils.vm_dependencies(
            self.app, self.app.domains['template1'])

        self.assertSetEqual(
            set(result),
            {(vm, prop) for vm in self.vms for prop in self.vm_properties
                 if (not vm.startswith('template')
                     or not prop.startswith(
                            'template')) and vm != 'template1'},
            "Incorrect VM properties listed.")

    def test_02_empty(self):
        result = qubesadmin.utils.vm_dependencies(self.app,
                                                  self.app.domains['vm1'])

        self.assertListEqual(result, [], "Incorrect use found.")

    def test_03_access_error(self):
        self.app.expected_calls[
            ('dom0', 'admin.property.Get', 'default_dispvm', None)] = b''

        result = qubesadmin.utils.vm_dependencies(self.app,
                                                  self.app.domains['vm1'])

        self.assertListEqual(result, [], "Incorrect use found.")

    def test_04_defaults(self):
        self.app.expected_calls[
            ('vm2', 'admin.vm.property.Get', 'netvm', None)] = \
            b'0\x00default=True type=vm sys-net'

        self.app.expected_calls[
            ('vm1', 'admin.vm.property.Get', 'netvm', None)] = \
            b'0\x00default=False type=vm sys-net'

        result = qubesadmin.utils.vm_dependencies(self.app,
                                                  self.app.domains['sys-net'])

        self.assertListEqual(result, [(self.app.domains['vm1'], 'netvm')])

    def test_05_preloaded_disposables(self):
        self.app.expected_calls[
            ('disp1', 'admin.vm.property.Get', 'template', None)
        ] = b'0\x00default=False type=vm test-dvm'
        self.app.expected_calls[
            ('disp2', 'admin.vm.property.Get', 'template', None)
        ] = b'0\x00default=False type=vm test-dvm'
        self.app.expected_calls[
            ('disp1', 'admin.vm.property.Get', 'is_preload', None)
        ] = b'0\x00default=False type=bool False'
        self.app.expected_calls[
            ('disp2', 'admin.vm.property.Get', 'is_preload', None)
        ] = b'0\x00default=False type=bool True'

        result = qubesadmin.utils.vm_dependencies(
            self.app, self.app.domains['test-dvm']
        )
        self.assertListEqual(
            result, [(self.app.domains['disp1'], 'template')]
        )


class TestVMExecEncode(qubesadmin.tests.QubesTestCase):
    def test_00_encode(self):
        self.assertEqual(
            qubesadmin.utils.encode_for_vmexec(['ls', '-a', '+x']),
            'ls+--a+-2Bx')
        self.assertEqual(
            qubesadmin.utils.encode_for_vmexec(
                ['touch', '/home/user/.profile']),
            'touch+-2Fhome-2Fuser-2F.profile')
