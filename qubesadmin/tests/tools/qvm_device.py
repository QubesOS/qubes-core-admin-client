# pylint: disable=protected-access

#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2017  Marek Marczykowski-Górecki
#                                       <marmarek@invisiblethingslab.com>
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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

# pylint: disable=missing-docstring

""" Tests for the `qvm-device` tool. """

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.device_protocol
import qubesadmin.tools.qvm_device


class TC_00_qvm_device(qubesadmin.tests.QubesTestCase):
    """ Tests the output logic of the qvm-device tool """

    def expected_device_call(
        self, vm, action, returned=b"0\0", klass="testclass"
    ):
        self.app.expected_calls[
            (vm, f"admin.vm.device.{klass}.{action}", None, None)
        ] = returned

    def setUp(self):
        super().setUp()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0test-vm1 class=AppVM state=Running\n'
            b'test-vm2 class=AppVM state=Running\n'
            b'test-vm3 class=AppVM state=Running\n')
        self.expected_device_call(
            'test-vm1', 'Available',
            b"0\0dev1 device_id='dead:beef:babe:u012345' "
            b"port_id='dev1' devclass='testclass' vendor='itl' "
            b"interfaces='u012345' product='test-device' "
            b"backend_domain='test-vm1'"
        )
        self.vm1 = self.app.domains['test-vm1']
        self.vm2 = self.app.domains['test-vm2']
        self.vm1_device = \
            self.app.domains['test-vm1'].devices['testclass']['dev1']

    def test_000_list_all(self):
        """
        List all exposed vm devices. No devices are connected to other domains.
        """
        self.expected_device_call(
            'test-vm2', 'Available',
            b"0\0dev2 port_id='dev2' devclass='testclass' vendor='? `'"
            b" product='test-device' backend_domain='test-vm2'"
        )
        self.expected_device_call('test-vm3', 'Available')

        self.expected_device_call('test-vm1', 'Attached')
        self.expected_device_call('test-vm2', 'Attached')
        self.expected_device_call('test-vm3', 'Attached')
        self.expected_device_call('test-vm1', 'Assigned')
        self.expected_device_call('test-vm2', 'Assigned')
        self.expected_device_call('test-vm3', 'Assigned')

        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['testclass', 'list'], app=self.app)
            self.assertEqual(
                [x.rstrip() for x in buf.getvalue().splitlines()],
                ['test-vm1:dev1  Audio: itl test-device',
                 'test-vm2:dev2  ?******: ? ` test-device']
            )

    def test_001_list_assigned_required(self):
        """
        List the device exposed by the `vm1` and assigned to the `vm3`.
        """
        # This shouldn't be listed
        self.expected_device_call(
            'test-vm2', 'Available',
            b"0\0dev2 device_id='serial' port_id='dev2' "
            b"devclass='testclass' backend_domain='test-vm2'\n")
        self.expected_device_call(
            'test-vm3', 'Available',
            b"0\0dev3 port_id='dev3' device_id='0000:0000::p000000' "
            b"devclass='testclass' backend_domain='test-vm3' "
            b"vendor='evil inc.' product='test-device-3'\n"
        )
        self.expected_device_call('test-vm1', 'Attached')
        self.expected_device_call('test-vm2', 'Attached')
        self.expected_device_call('test-vm3', 'Attached')
        self.expected_device_call('test-vm1', 'Assigned')
        self.expected_device_call(
            'test-vm2', 'Assigned',
            b"0\0test-vm1+dev1 port_id='dev1' devclass='testclass' "
            b"backend_domain='test-vm1' mode='required' _option='other option' "
            b"_extra_opt='yes'\n"
            b"test-vm3+dev3 device_id='0000:0000::p000000' port_id='dev3' "
            b"devclass='testclass' backend_domain='test-vm3' mode='required'\n"
        )
        self.expected_device_call(
            'test-vm3', 'Assigned',
            b"0\0test-vm1+dev1 port_id='dev1' devclass='testclass' "
            b"backend_domain='test-vm1' mode='required' _option='test option'\n"
        )

        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['testclass', 'list', '-s', 'test-vm3'], app=self.app)
            self.assertEqual(
                buf.getvalue(),
'test-vm1:dev1  any device                        '
'*test-vm2 (required: option=other option, extra_opt=yes), '
'*test-vm3 (required: option=test option)\n'
'test-vm3:dev3  0000:0000::p000000                *test-vm2 (required)\n'
'test-vm3:dev3  ?******: evil inc. test-device-3  \n'
            )

    def test_002_list_attach(self):
        """
        List the device exposed by the `vm1` and attached to the `vm3`.
        """
        # This shouldn't be listed
        self.expected_device_call(
            'test-vm2', 'Available',
            b"0\0dev2 port_id='dev1' devclass='testclass' "
            b"backend_domain='test-vm2'\n")
        self.expected_device_call('test-vm3', 'Available')
        self.expected_device_call('test-vm1', 'Attached')
        self.expected_device_call('test-vm2', 'Attached')
        self.expected_device_call(
            'test-vm3', 'Attached',
            b"0\0test-vm1+dev1 port_id='dev1' devclass='testclass' "
            b"backend_domain='test-vm1' mode='required'\n"
        )
        self.expected_device_call('test-vm1', 'Assigned')
        self.expected_device_call('test-vm2', 'Assigned')
        self.expected_device_call('test-vm3', 'Assigned')

        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['testclass', 'list', 'test-vm3'], app=self.app)
            self.assertEqual(
                buf.getvalue(),
                'test-vm1:dev1  Audio: itl test-device  '
                'test-vm3 (attached)\n'
            )

    def test_003_list_device_classes(self):
        """
        List the device exposed by the `vm1` and attached to the `vm3`.
        """
        self.app.expected_calls[
            ('dom0', 'admin.deviceclass.List', None, None)] = b"0\0pci\nusb\n"

        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['list-device-classes'], app=self.app)
            self.assertEqual(
                buf.getvalue(),
                'pci\nusb\n'
            )

    def test_004_list_pci_with_sbdf(self):
        """
        List PCI devices with SBDF info.
        """
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\0dom0 class=AdminVM state=Running\n"
        )
        self.app.domains.clear_cache()
        self.expected_device_call(
            "dom0",
            "Available",
            b"0\00000_14.0:0x8086:0xa0ed::p0c0330 "
            b"device_id='0x8086:0xa0ed::p0c0330' port_id='00_14.0' "
            b"devclass='pci' backend_domain='dom0' product='p1' vendor='v' "
            b"interfaces='p0c0330' _sbdf='0000:00:14.0'\n"
            b"00_1d.0-00_00.0:0x8086:0x2725::p028000 "
            b"device_id='0x8086:0x2725::p028000' port_id='00_1d.0-00_00.0' "
            b"devclass='pci' backend_domain='dom0' product='p2' vendor='v' "
            b"interfaces='p028000' _sbdf='0000:aa:00.0'\n",
            klass="pci",
        )
        self.expected_device_call("dom0", "Attached", b"0\0", klass="pci")

        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ["pci", "list", "--with-sbdf", "dom0"], app=self.app
            )
            self.assertEqual(
                [x.rstrip() for x in buf.getvalue().splitlines()],
                [
                    "dom0:00_14.0          0000:00:14.0  PCI_USB: v p1",
                    "dom0:00_1d.0-00_00.0  0000:aa:00.0  Network: v p2",
                ],
            )

    def test_010_attach(self):
        """ Test attach action """
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attach',
            'test-vm1+dev1+dead+beef+babe+u012345',
            b"device_id='dead:beef:babe:u012345' port_id='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' mode='manual' "
            b"frontend_domain='test-vm2'")] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'attach', 'test-vm2', 'test-vm1:dev1'], app=self.app)
        self.assertAllCalled()

    def test_011_attach_options(self):
        """ Test `read-only` attach option """
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attach',
            'test-vm1+dev1+dead+beef+babe+u012345',
            b"device_id='dead:beef:babe:u012345' port_id='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' mode='manual' "
            b"frontend_domain='test-vm2' _read-only='yes'")] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'attach', '-o', 'ro=True', 'test-vm2',
             'test-vm1:dev1'],
            app=self.app)
        self.assertAllCalled()

    def test_012_attach_invalid(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['testclass', 'attach', '-p', 'test-vm2', 'dev1'],
                    app=self.app)
            self.assertIn(
                'expected a backend vm, port id and [optional] device id',
                stderr.getvalue())
        self.assertAllCalled()

    def test_013_attach_invalid_device(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['testclass', 'attach', '-p', 'test-vm2',
                     'test-vm1:invalid'],
                    app=self.app)
            self.assertIn('doesn\'t expose testclass device',
                stderr.getvalue())
        self.assertAllCalled()

    def test_014_attach_invalid_backend(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['testclass', 'attach', '-p', 'test-vm2',
                     'no-such-vm:dev3'],
                    app=self.app)
            self.assertIn('no such backend vm!',
                stderr.getvalue())
        self.assertAllCalled()

    def test_020_detach(self):
        """ Test detach action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Detach',
             'test-vm1+dev1+dead+beef+babe+u012345', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'detach', 'test-vm2', 'test-vm1:dev1'], app=self.app)
        self.assertAllCalled()

    def test_021_detach_unknown(self):
        """ Test detach action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Detach',
             'test-vm1+dev7+0000+0000++_______', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'detach', 'test-vm2', 'test-vm1:dev7'], app=self.app)
        self.assertAllCalled()

    def test_022_detach_all(self):
        """ Test detach action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Attached', None, None)] = \
            b'0\0test-vm1+dev1\ntest-vm1+dev2\n'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Detach',
             'test-vm1+dev1+_', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Detach',
             'test-vm1+dev2+_', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'detach', 'test-vm2'], app=self.app)
        self.assertAllCalled()

    def test_030_assign(self):
        """ Test assign action """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign',
            'test-vm1+dev1+dead+beef+babe+u012345',
            b"device_id='dead:beef:babe:u012345' port_id='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"mode='auto-attach' frontend_domain='test-vm2'"
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.GetAll', None, None
        )] = b'2\0QubesDaemonNoResponseError\0\0err\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.Get', 'devices_denied', None
        )] = b'0\0default=False type=str '
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'assign', 'test-vm2', 'test-vm1:dev1'], app=self.app)
        self.assertAllCalled()

    def test_031_assign_required(self):
        """ Test assign as required """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign',
            'test-vm1+dev1+dead+beef+babe+u012345',
            b"device_id='dead:beef:babe:u012345' port_id='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' mode='required' "
            b"frontend_domain='test-vm2'"
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.GetAll', None, None
        )] = b'2\0QubesDaemonNoResponseError\0\0err\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.Get', 'devices_denied', None
        )] = b'0\0default=False type=str '
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'assign', '--required', 'test-vm2', 'test-vm1:dev1'],
            app=self.app)
        self.assertAllCalled()

    def test_032_assign_ask_and_options(self):
        """ Test `read-only` assign option """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign',
            'test-vm1+dev1+dead+beef+babe+u012345',
            b"device_id='dead:beef:babe:u012345' port_id='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"mode='ask-to-attach' frontend_domain='test-vm2' _read-only='yes'"
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.GetAll', None, None
        )] = b'2\0QubesDaemonNoResponseError\0\0err\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.Get', 'devices_denied', None
        )] = b'0\0default=False type=str '
        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['testclass', 'assign', '--ro', '--ask', 'test-vm2',
                 'test-vm1:dev1'],
                app=self.app)
            self.assertIn('Assigned.', buf.getvalue())
            self.assertIn('now restart domain', buf.getvalue())
        self.assertAllCalled()

    def test_033_assign_invalid(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['testclass', 'assign', 'test-vm2', 'dev1'],
                    app=self.app)
            self.assertIn(
                'expected a backend vm, port id and [optional] device id',
                stderr.getvalue())
        self.assertAllCalled()

    def test_034_assign_invalid_device(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            retcode = qubesadmin.tools.qvm_device.main(
                    ['testclass', 'assign', 'test-vm2', 'test-vm1:invalid'],
                    app=self.app)
            self.assertEqual(retcode, 1)
            self.assertIn("doesn't expose testclass device", stderr.getvalue())
        self.assertAllCalled()

    def test_035_assign_invalid_backend(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['testclass', 'assign', 'test-vm2', 'no-such-vm:dev3'],
                    app=self.app)
            self.assertIn('no such backend vm!', stderr.getvalue())
        self.assertAllCalled()

    def test_036_assign_port(self):
        """ Test assign action """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign',
            'test-vm1+dev1+_',
            b"device_id='*' port_id='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"mode='auto-attach' frontend_domain='test-vm2'"
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.GetAll', None, None
        )] = b'2\0QubesDaemonNoResponseError\0\0err\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.Get', 'devices_denied', None
        )] = b'0\0default=False type=str '
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'assign', 'test-vm2', 'test-vm1:dev1', '--port'],
            app=self.app)
        self.assertAllCalled()

    def test_037_assign_port_asterisk(self):
        """ Test assign action """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign',
            'test-vm1+dev1+_',
            b"device_id='*' port_id='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"mode='auto-attach' frontend_domain='test-vm2'"
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.GetAll', None, None
        )] = b'2\0QubesDaemonNoResponseError\0\0err\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.Get', 'devices_denied', None
        )] = b'0\0default=False type=str '
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'assign', 'test-vm2', 'test-vm1:dev1:*'],
            app=self.app)
        self.assertAllCalled()

    def test_038_assign_device_from_port(self):
        """ Test assign action """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign',
            'test-vm1+_+dead+beef+babe+u012345',
            b"device_id='dead:beef:babe:u012345' port_id='*' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"mode='auto-attach' frontend_domain='test-vm2'"
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.GetAll', None, None
        )] = b'2\0QubesDaemonNoResponseError\0\0err\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.Get', 'devices_denied', None
        )] = b'0\0default=False type=str '
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'assign', 'test-vm2', 'test-vm1:dev1', '--device'],
            app=self.app)
        self.assertAllCalled()

    def test_039_assign_explicit_device(self):
        """ Test assign action """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign',
            'test-vm1+dev1+cafe+cafe++0123456u654321',
            b"device_id='cafe:cafe::0123456u654321' port_id='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"mode='auto-attach' frontend_domain='test-vm2'"
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.GetAll', None, None
        )] = b'2\0QubesDaemonNoResponseError\0\0err\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.Get', 'devices_denied', None
        )] = b'0\0default=False type=str '
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'assign', 'test-vm2',
             'test-vm1:dev1:cafe:cafe::0123456u654321'], app=self.app)
        self.assertAllCalled()

    def test_040_assign_explicit_device_device_id(self):
        """ Test assign action """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign',
            'test-vm1+_+cafe+cafe++0123456u654321',
            b"device_id='cafe:cafe::0123456u654321' port_id='*' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"mode='auto-attach' frontend_domain='test-vm2'"
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.GetAll', None, None
        )] = b'2\0QubesDaemonNoResponseError\0\0err\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.Get', 'devices_denied', None
        )] = b'0\0default=False type=str '
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'assign', 'test-vm2',
             'test-vm1:dev1:cafe:cafe::0123456u654321', '--device'],
            app=self.app)
        self.assertAllCalled()

    def test_041_assign_denied_device(self):
        """ Test user warning """
        self.app.domains['test-vm2'].is_running = lambda: False
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign',
            'test-vm1+dev1+dead+beef+babe+u012345',
            b"device_id='dead:beef:babe:u012345' port_id='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"mode='ask-to-attach' frontend_domain='test-vm2'"
        )] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.GetAll', None, None
        )] = b'2\0QubesDaemonNoResponseError\0\0err\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.property.Get', 'devices_denied', None
        )] = b'0\0default=False type=str u012345*543210'
        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['testclass', 'assign', '--ask', 'test-vm2', 'test-vm1:dev1'],
                app=self.app)
            self.assertIn('Warning:', buf.getvalue())
        self.assertAllCalled()

    def test_050_unassign(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev1+dead+beef+babe+u012345', None)] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2', 'test-vm1:dev1'],
            app=self.app)
        self.assertAllCalled()

    def test_051_unassign_unknown(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev7+0000+0000++_______', None)] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2', 'test-vm1:dev7'],
            app=self.app)
        self.assertAllCalled()

    def test_052_unassign_port(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev1+_', None)] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2', 'test-vm1:dev1', '--port'],
            app=self.app)
        self.assertAllCalled()

    def test_053_unassign_device_from_port(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+_+dead+beef+babe+u012345', None)] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2', 'test-vm1:dev1', '--device'],
            app=self.app)
        self.assertAllCalled()

    def test_054_unassign_explicit_device(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev1+dead+beef+babe+u0123456', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2',
             'test-vm1:dev1:dead:beef:babe:u0123456'], app=self.app)
        self.assertAllCalled()

    def test_055_unassign_explicit_device_port(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev1+_', None)] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2',
             'test-vm1:dev1:dead:beef:babe:u0123456', '--port'], app=self.app)
        self.assertAllCalled()

    def test_056_unassign_explicit_device_id(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+_+cafe+cafe++0123456u654321', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2',
             'test-vm1:dev1:cafe:cafe::0123456u654321', '--device'],
            app=self.app)
        self.assertAllCalled()

    def test_057_unassign_all(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Assigned', None, None)] = \
            (b"0\0test-vm1+dev1 devclass='testclass'\n"
             b"test-vm1+dev2 devclass='testclass'\n")
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev1+_', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev2+_', None)] = b'0\0'
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attached', None, None
        )] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2'], app=self.app)
        self.assertAllCalled()

    def test_060_device_info(self):
        """ Test printing info about device """
        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['testclass', 'info', 'test-vm1:dev1'],
                app=self.app)
            self.assertIn('Audio: itl test-device\n'
                          'device ID: dead:beef:babe:u012345',
                          buf.getvalue())
        self.assertAllCalled()
