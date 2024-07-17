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
import qubesadmin.device_protocol


serialized_test_device = (
    b"0\0dev1 ident='dev1' devclass='test' vendor='itl' product='test-device' "
    b"manufacturer='itl' backend_domain='test-vm' interfaces='?******' ")


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
        self.assertIsInstance(dev, qubesadmin.device_protocol.DeviceInfo)
        self.assertEqual(dev.backend_domain, self.vm)
        self.assertEqual(dev.ident, 'dev1')
        self.assertEqual(
            dev.description, '?******: unknown vendor unknown test device')
        self.assertEqual(dev.data, {})
        self.assertEqual(str(dev), 'test-vm:dev1')
        self.assertAllCalled()

    def test_001_available_desc(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Available', None, None)] = \
            serialized_test_device + b'\n'
        devices = list(self.vm.devices['test'].get_exposed_devices())
        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertIsInstance(dev, qubesadmin.device_protocol.DeviceInfo)
        self.assertEqual(dev.backend_domain, self.vm)
        self.assertEqual(dev.ident, 'dev1')
        self.assertEqual(dev.description, '?******: itl test-device')
        self.assertEqual(dev.data, {})
        self.assertEqual(str(dev), 'test-vm:dev1')

    def test_002_available_options(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Available', None, None)] = \
            serialized_test_device + b"_ro='True' _other='123'\n"
        devices = list(self.vm.devices['test'].get_exposed_devices())
        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertIsInstance(dev, qubesadmin.device_protocol.DeviceInfo)
        self.assertEqual(dev.backend_domain, self.vm)
        self.assertEqual(dev.ident, 'dev1')
        self.assertEqual(dev.description, '?******: itl test-device')
        self.assertEqual(dev.data, {'ro': 'True', 'other': '123'})
        self.assertEqual(str(dev), 'test-vm:dev1')
        self.assertAllCalled()

    def test_010_getitem(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Available', None, None)] = \
            serialized_test_device + b"\n"
        dev = self.vm.devices['test']['dev1']
        self.assertIsInstance(dev, qubesadmin.device_protocol.DeviceInfo)
        self.assertEqual(dev.backend_domain, self.vm)
        self.assertEqual(dev.ident, 'dev1')
        self.assertEqual(dev.description, '?******: itl test-device')
        self.assertEqual(dev.data, {})
        self.assertEqual(str(dev), 'test-vm:dev1')
        self.assertAllCalled()

    def test_011_getitem_missing(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Available', None, None)] = \
            serialized_test_device + b"\n"
        dev = self.vm.devices['test']['dev2']
        self.assertIsInstance(dev, qubesadmin.device_protocol.UnknownDevice)
        self.assertEqual(dev.backend_domain, self.vm)
        self.assertEqual(dev.ident, 'dev2')
        self.assertEqual(dev.description,
                         '?******: unknown vendor unknown test device')
        self.assertEqual(dev.data, {})
        self.assertEqual(str(dev), 'test-vm:dev2')
        self.assertAllCalled()

    def test_020_attach(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attach', 'test-vm2+dev1',
             b"required='no' attach_automatically='no' ident='dev1' "
             b"devclass='test' backend_domain='test-vm2' "
             b"frontend_domain='test-vm'")] = \
            b'0\0'
        assign = qubesadmin.device_protocol.DeviceAssignment(
            qubesadmin.device_protocol.Port(
                self.app.domains['test-vm2'], 'dev1', devclass='test',))
        self.vm.devices['test'].attach(assign)
        self.assertAllCalled()

    def test_021_attach_options(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attach', 'test-vm2+dev1',
             b"required='no' attach_automatically='no' ident='dev1' "
             b"devclass='test' backend_domain='test-vm2' "
             b"frontend_domain='test-vm' _ro='True' "
             b"_something='value'")] = b'0\0'
        assign = qubesadmin.device_protocol.DeviceAssignment(
            qubesadmin.device_protocol.Port(
                self.app.domains['test-vm2'], 'dev1', devclass='test'))
        assign.options['ro'] = True
        assign.options['something'] = 'value'
        self.vm.devices['test'].attach(assign)
        self.assertAllCalled()

    def test_022_attach_required(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attach', 'test-vm2+dev1',
             b"required='yes' attach_automatically='yes' ident='dev1' "
             b"devclass='test' backend_domain='test-vm2' "
             b"frontend_domain='test-vm'")] = b'0\0'
        assign = qubesadmin.device_protocol.DeviceAssignment(
            qubesadmin.device_protocol.Port(
                self.app.domains['test-vm2'], 'dev1', devclass='test'),
            attach_automatically=True, required=True)
        self.vm.devices['test'].attach(assign)
        self.assertAllCalled()

    def test_023_attach_required_options(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attach', 'test-vm2+dev1',
             b"required='yes' attach_automatically='yes' ident='dev1' "
             b"devclass='test' backend_domain='test-vm2' "
             b"frontend_domain='test-vm' _ro='True'")] = b'0\0'
        assign = qubesadmin.device_protocol.DeviceAssignment(
            qubesadmin.device_protocol.Port(
                self.app.domains['test-vm2'], 'dev1', devclass='test'),
            attach_automatically=True, required=True)
        assign.options['ro'] = True
        self.vm.devices['test'].attach(assign)
        self.assertAllCalled()

    def test_030_detach(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Detach', 'test-vm2+dev1',
             None)] = b'0\0'
        assign = qubesadmin.device_protocol.DeviceAssignment(
            qubesadmin.device_protocol.Port(
                self.app.domains['test-vm2'], 'dev1', devclass='test'))
        self.vm.devices['test'].detach(assign)
        self.assertAllCalled()

    def test_040_dedicated(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attached', None, None)] = \
            (b"0\0test-vm2+dev1 backend_domain='test-vm2' ident='dev1' "
             b"attach_automatically='no' required='no' devclass='test' "
             b"frontend_domain='test-vm'\n")
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Assigned', None, None)] = \
            (b"0\0test-vm3+dev2 backend_domain='test-vm3' devclass='test' "
             b"ident='dev2' attach_automatically='yes' required='yes' "
             b"frontend_domain='test-vm'\n")
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev1 description=desc\n'
        self.app.expected_calls[
            ('test-vm3', 'admin.vm.device.test.Available', None, None)] = \
            b'0\0dev2 description=desc\n'
        dedicated = sorted(list(
            self.vm.devices['test'].get_dedicated_devices()))
        self.assertEqual(len(dedicated), 2)
        self.assertIsInstance(dedicated[0], qubesadmin.device_protocol.DeviceAssignment)
        self.assertEqual(dedicated[0].backend_domain,
                         self.app.domains['test-vm2'])
        self.assertEqual(dedicated[0].ident, 'dev1')
        self.assertEqual(dedicated[0].frontend_domain,
                         self.app.domains['test-vm'])
        self.assertEqual(dedicated[0].options, {})
        self.assertEqual(dedicated[0].devclass, 'test')
        self.assertEqual(dedicated[0].device,
                         self.app.domains['test-vm2'].devices['test']['dev1'])

        self.assertIsInstance(dedicated[1], qubesadmin.device_protocol.DeviceAssignment)
        self.assertEqual(dedicated[1].backend_domain,
                         self.app.domains['test-vm3'])
        self.assertEqual(dedicated[1].ident, 'dev2')
        self.assertEqual(dedicated[1].frontend_domain,
                         self.app.domains['test-vm'])
        self.assertEqual(dedicated[1].options, {})
        self.assertEqual(dedicated[1].devclass, 'test')
        self.assertEqual(dedicated[1].device,
                         self.app.domains['test-vm3'].devices['test']['dev2'])

        self.assertAllCalled()

    def test_041_assignments_options(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attached', None, None)] = \
            (b"0\0test-vm2+dev1 backend_domain='test-vm2' ident='dev1' "
             b"attach_automatically='no' required='no' devclass='test' "
             b"frontend_domain='test-vm' _ro='True'\n")
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Assigned', None, None)] = \
            (b"0\0test-vm3+dev2 backend_domain='test-vm3' devclass='test' "
             b"ident='dev2' attach_automatically='yes' required='yes' "
             b"frontend_domain='test-vm' _ro='False'\n")
        assigns = sorted(list(
            self.vm.devices['test'].get_dedicated_devices()))
        self.assertEqual(len(assigns), 2)
        self.assertIsInstance(assigns[0], qubesadmin.device_protocol.DeviceAssignment)
        self.assertEqual(assigns[0].backend_domain,
                         self.app.domains['test-vm2'])
        self.assertEqual(assigns[0].ident, 'dev1')
        self.assertEqual(assigns[0].frontend_domain,
                         self.app.domains['test-vm'])
        self.assertEqual(assigns[0].options, {'ro': 'True'})
        self.assertEqual(assigns[0].required, False)
        self.assertEqual(assigns[0].devclass, 'test')

        self.assertIsInstance(assigns[1], qubesadmin.device_protocol.DeviceAssignment)
        self.assertEqual(assigns[1].backend_domain,
                         self.app.domains['test-vm3'])
        self.assertEqual(assigns[1].ident, 'dev2')
        self.assertEqual(assigns[1].frontend_domain,
                         self.app.domains['test-vm'])
        self.assertEqual(assigns[1].options, {'ro': 'False'})
        self.assertEqual(assigns[1].required, True)
        self.assertEqual(assigns[1].devclass, 'test')

        self.assertAllCalled()

    def test_050_required(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Assigned', None, None)] = \
            (b"0\0test-vm2+dev1 backend_domain='test-vm2' ident='dev1' "
             b"attach_automatically='no' required='no'\n"
             b"test-vm3+dev2 backend_domain='test-vm3' "
             b"ident='dev2' attach_automatically='yes' required='yes'\n")
        devs = list(self.vm.devices['test'].get_assigned_devices(
            required_only=True))
        self.assertEqual(len(devs), 1)
        self.assertIsInstance(devs[0], qubesadmin.device_protocol.DeviceAssignment)
        self.assertEqual(devs[0].backend_domain, self.app.domains['test-vm3'])
        self.assertEqual(devs[0].ident, 'dev2')
        self.assertAllCalled()

    def test_060_attached(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Attached', None, None)] = \
            (b"0\0test-vm2+dev1 backend_domain='test-vm2' ident='dev1' "
             b"attach_automatically='no' required='no'\n"
             b"test-vm3+dev2 backend_domain='test-vm3' ident='dev2' "
             b"attach_automatically='yes' required='no'\n")
        devs = list(self.vm.devices['test'].get_attached_devices())
        self.assertEqual(len(devs), 2)
        self.assertIsInstance(devs[0], qubesadmin.device_protocol.DeviceAssignment)
        self.assertEqual(devs[0].backend_domain, self.app.domains['test-vm2'])
        self.assertEqual(devs[0].ident, 'dev1')
        self.assertIsInstance(devs[1], qubesadmin.device_protocol.DeviceAssignment)
        self.assertEqual(devs[1].backend_domain, self.app.domains['test-vm3'])
        self.assertEqual(devs[1].ident, 'dev2')
        self.assertAllCalled()

    def test_070_update_assignment(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Set.assignment', 'test-vm2+dev1',
             b'True')] = b'0\0'
        dev = qubesadmin.device_protocol.DeviceAssignment(
            qubesadmin.device_protocol.Port(
                self.app.domains['test-vm2'], devclass='test', ident='dev1'))
        self.vm.devices['test'].update_assignment(dev, True)
        self.assertAllCalled()

    def test_071_update_assignment_false(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Set.assignment', 'test-vm2+dev1',
             b'False')] = b'0\0'
        dev = qubesadmin.device_protocol.DeviceAssignment(
            qubesadmin.device_protocol.Port(
                self.app.domains['test-vm2'], devclass='test', ident='dev1'))
        self.vm.devices['test'].update_assignment(dev, False)
        self.assertAllCalled()

    def test_072_update_assignment_none(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.device.test.Set.assignment', 'test-vm2+dev1',
             b'None')] = b'0\0'
        dev = qubesadmin.device_protocol.DeviceAssignment(
            qubesadmin.device_protocol.Port(
                self.app.domains['test-vm2'], devclass='test', ident='dev1'))
        self.vm.devices['test'].update_assignment(dev, None)
        self.assertAllCalled()

    def test_073_list(self):
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = \
            b'0\x00block\nmic\nusb\n'
        seen = set()
        for devclass in self.app.domains['test-vm'].devices:
            self.assertNotIn(devclass, seen)
            seen.add(devclass)
        self.assertEqual(seen, {'block', 'mic', 'usb'})
