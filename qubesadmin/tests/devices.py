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

import qubesadmin.tests
import qubesadmin.devices


class TC_00_DeviceCollection(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super(TC_00_DeviceCollection, self).setUp()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n' \
            b'test-vm3 class=AppVM state=Running\n'
        self.vm = self.app.domains['test-vm']

    def test_000_available(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev1\n'
        devices = list(self.vm.devices['test'].get_exposed_devices())
        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertIsInstance(dev, qubesadmin.devices.DeviceInfo)
        self.assertEqual(dev.backend_domain, self.vm)
        self.assertEqual(dev.ident, 'dev1')
        self.assertEqual(
            dev.description, 'unknown test device (unknown vendor)')
        self.assertEqual(dev.data, {})
        self.assertEqual(str(dev), 'test-vm:dev1')
        self.assertAllCalled()

    def test_001_available_desc(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev1 description=This is description\n'
        devices = list(self.vm.devices['test'].get_exposed_devices())
        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertIsInstance(dev, qubesadmin.devices.DeviceInfo)
        self.assertEqual(dev.backend_domain, self.vm)
        self.assertEqual(dev.ident, 'dev1')
        self.assertEqual(dev.description, 'This is description')
        self.assertEqual(dev.data, {})
        self.assertEqual(str(dev), 'test-vm:dev1')

    def test_002_available_options(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev1 ro=True other=123 description=This is description\n'
        devices = list(self.vm.devices['test'].get_exposed_devices())
        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertIsInstance(dev, qubesadmin.devices.DeviceInfo)
        self.assertEqual(dev.backend_domain, self.vm)
        self.assertEqual(dev.ident, 'dev1')
        self.assertEqual(dev.description, 'This is description')
        self.assertEqual(dev.data, {'ro': 'True', 'other': '123'})
        self.assertEqual(str(dev), 'test-vm:dev1')
        self.assertAllCalled()

    def test_010_getitem(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev1 description=This is description\n'
        dev = self.vm.devices['test']['dev1']
        self.assertIsInstance(dev, qubesadmin.devices.DeviceInfo)
        self.assertEqual(dev.backend_domain, self.vm)
        self.assertEqual(dev.ident, 'dev1')
        self.assertEqual(dev.description, 'This is description')
        self.assertEqual(dev.data, {})
        self.assertEqual(str(dev), 'test-vm:dev1')
        self.assertAllCalled()

    def test_011_getitem_missing(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev1 description=This is description\n'
        dev = self.vm.devices['test']['dev2']
        self.assertIsInstance(dev, qubesadmin.devices.UnknownDevice)
        self.assertEqual(dev.backend_domain, self.vm)
        self.assertEqual(dev.ident, 'dev2')
        self.assertEqual(dev.description, 'Unknown device')
        self.assertEqual(dev.data, {})
        self.assertEqual(str(dev), 'test-vm:dev2')
        self.assertAllCalled()

    def test_020_attach(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attach', 'test-vm2+dev1',
             b'')] = \
            b'0\0'
        assign = qubesadmin.devices.DeviceAssignment(
            self.app.domains['test-vm2'], 'dev1')
        self.vm.devices['test'].attach(assign)
        self.assertAllCalled()

    def test_021_attach_options(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attach', 'test-vm2+dev1',
             b'ro=True something=value')] = b'0\0'
        assign = qubesadmin.devices.DeviceAssignment(
            self.app.domains['test-vm2'], 'dev1')
        assign.options['ro'] = True
        assign.options['something'] = 'value'
        self.vm.devices['test'].attach(assign)
        self.assertAllCalled()

    def test_022_attach_required(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attach', 'test-vm2+dev1',
             b'required=True')] = b'0\0'
        assign = qubesadmin.devices.DeviceAssignment(
            self.app.domains['test-vm2'], 'dev1', required=True)
        self.vm.devices['test'].attach(assign)
        self.assertAllCalled()

    def test_023_attach_required_options(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attach', 'test-vm2+dev1',
             b'required=True ro=True')] = b'0\0'
        assign = qubesadmin.devices.DeviceAssignment(
            self.app.domains['test-vm2'], 'dev1', required=True)
        assign.options['ro'] = True
        self.vm.devices['test'].attach(assign)
        self.assertAllCalled()

    def test_030_detach(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Detach', 'test-vm2+dev1',
             None)] = b'0\0'
        assign = qubesadmin.devices.DeviceAssignment(
            self.app.domains['test-vm2'], 'dev1')
        self.vm.devices['test'].detach(assign)
        self.assertAllCalled()

    def test_040_assignments(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attached', None, None)] = \
            b'0\0test-vm2+dev1\n' \
            b'test-vm3+dev2\n'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev1 description=desc\n'
        self.app.expected_calls[
            ('test-vm3', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev2 description=desc\n'
        assigns = list(self.vm.devices['test'].get_dedicated_devices())
        self.assertEqual(len(assigns), 2)
        self.assertIsInstance(assigns[0], qubesadmin.devices.DeviceAssignment)
        self.assertEqual(assigns[0].backend_domain,
                         self.app.domains['test-vm2'])
        self.assertEqual(assigns[0].ident, 'dev1')
        self.assertEqual(assigns[0].frontend_domain,
                         self.app.domains['test-vm'])
        self.assertEqual(assigns[0].options, {})
        self.assertEqual(assigns[0].devclass, 'test')
        self.assertEqual(assigns[0].device,
                         self.app.domains['test-vm2'].devices['test']['dev1'])

        self.assertIsInstance(assigns[1], qubesadmin.devices.DeviceAssignment)
        self.assertEqual(assigns[1].backend_domain,
                         self.app.domains['test-vm3'])
        self.assertEqual(assigns[1].ident, 'dev2')
        self.assertEqual(assigns[1].frontend_domain,
                         self.app.domains['test-vm'])
        self.assertEqual(assigns[1].options, {})
        self.assertEqual(assigns[1].devclass, 'test')
        self.assertEqual(assigns[1].device,
                         self.app.domains['test-vm3'].devices['test']['dev2'])

        self.assertAllCalled()

    def test_041_assignments_options(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attached', None, None)] = \
            b'0\0test-vm2+dev1 ro=True\n' \
            b'test-vm3+dev2 ro=False required=True\n'
        assigns = list(self.vm.devices['test'].get_dedicated_devices())
        self.assertEqual(len(assigns), 2)
        self.assertIsInstance(assigns[0], qubesadmin.devices.DeviceAssignment)
        self.assertEqual(assigns[0].backend_domain,
                         self.app.domains['test-vm2'])
        self.assertEqual(assigns[0].ident, 'dev1')
        self.assertEqual(assigns[0].frontend_domain,
                         self.app.domains['test-vm'])
        self.assertEqual(assigns[0].options, {'ro': 'True'})
        self.assertEqual(assigns[0].required, False)
        self.assertEqual(assigns[0].devclass, 'test')

        self.assertIsInstance(assigns[1], qubesadmin.devices.DeviceAssignment)
        self.assertEqual(assigns[1].backend_domain,
                         self.app.domains['test-vm3'])
        self.assertEqual(assigns[1].ident, 'dev2')
        self.assertEqual(assigns[1].frontend_domain,
                         self.app.domains['test-vm'])
        self.assertEqual(assigns[1].options, {'ro': 'False'})
        self.assertEqual(assigns[1].required, True)
        self.assertEqual(assigns[1].devclass, 'test')

        self.assertAllCalled()

    def test_041_assignments_required(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.List', None, None)] = \
            b'0\0test-vm2+dev1\n' \
            b'test-vm3+dev2 required=True\n'
        assigns = list(self.vm.devices['test'].get_assignet_devices(
            required_only=True))
        self.assertEqual(len(assigns), 1)
        self.assertIsInstance(assigns[0], qubesadmin.devices.DeviceAssignment)
        self.assertEqual(assigns[0].backend_domain,
                         self.app.domains['test-vm3'])
        self.assertEqual(assigns[0].ident, 'dev2')
        self.assertEqual(assigns[0].frontend_domain,
                         self.app.domains['test-vm'])
        self.assertEqual(assigns[0].options, {})
        self.assertEqual(assigns[0].required, True)
        self.assertEqual(assigns[0].devclass, 'test')
        self.assertAllCalled()

    def test_042_assignments_non_required(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.List', None, None)] = \
            b'0\0test-vm2+dev1\n' \
            b'test-vm3+dev2 required=True\n'
        assigns = list(self.vm.devices['test'].get_assigned_devices(
            required_only=False))
        self.assertEqual(len(assigns), 1)
        self.assertIsInstance(assigns[0], qubesadmin.devices.DeviceAssignment)
        self.assertEqual(assigns[0].backend_domain,
                         self.app.domains['test-vm2'])
        self.assertEqual(assigns[0].ident, 'dev1')
        self.assertEqual(assigns[0].frontend_domain,
                         self.app.domains['test-vm'])
        self.assertEqual(assigns[0].options, {})
        self.assertEqual(assigns[0].required, False)
        self.assertAllCalled()

    def test_050_required(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Assigned', None, None)] = \
            b'0\0test-vm2+dev1\n' \
            b'test-vm3+dev2 required=True\n'
        self.app.expected_calls[
            ('test-vm3', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev2\n'
        devs = list(self.vm.devices['test'].get_assigned_devices(
            required_only=True))
        self.assertEqual(len(devs), 1)
        self.assertIsInstance(devs[0], qubesadmin.devices.DeviceInfo)
        self.assertEqual(devs[0].backend_domain, self.app.domains['test-vm3'])
        self.assertEqual(devs[0].ident, 'dev2')
        self.assertAllCalled()

    def test_060_attached(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attached', None, None)] = \
            b'0\0test-vm2+dev1\n' \
            b'test-vm3+dev2\n'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev1\n'
        self.app.expected_calls[
            ('test-vm3', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev2\n'
        devs = list(self.vm.devices['test'].get_attached_devices())
        self.assertEqual(len(devs), 2)
        self.assertIsInstance(devs[0], qubesadmin.devices.DeviceInfo)
        self.assertEqual(devs[0].backend_domain, self.app.domains['test-vm2'])
        self.assertEqual(devs[0].ident, 'dev1')
        self.assertIsInstance(devs[1], qubesadmin.devices.DeviceInfo)
        self.assertEqual(devs[1].backend_domain, self.app.domains['test-vm3'])
        self.assertEqual(devs[1].ident, 'dev2')
        self.assertAllCalled()

    def test_070_update_assignment(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Set.assignment', 'test-vm2+dev1',
             b'True')] = b'0\0'
        dev = qubesadmin.devices.DeviceAssignment(
            self.app.domains['test-vm2'], devclass='test', ident='dev1')
        self.vm.devices['test'].update_assignment(dev, True)
        self.assertAllCalled()

    def test_071_update_assignment_false(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Set.assignment', 'test-vm2+dev1',
             b'False')] = b'0\0'
        dev = qubesadmin.devices.DeviceAssignment(
            self.app.domains['test-vm2'], devclass='test', ident='dev1')
        self.vm.devices['test'].update_assignment(dev, None)  # TODO: false
        self.assertAllCalled()

    def test_072_list(self):
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = \
            b'0\x00block\nmic\nusb\n'
        seen = set()
        for devclass in self.app.domains['test-vm'].devices:
            self.assertNotIn(devclass, seen)
            seen.add(devclass)
        self.assertEqual(seen, {'block', 'mic', 'usb'})
