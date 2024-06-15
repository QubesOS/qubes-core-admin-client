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

""" Tests for the `qvm-device` tool. """

import unittest.mock as mock
import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.device_protocol
import qubesadmin.tools.qvm_device


class TC_00_qvm_device(qubesadmin.tests.QubesTestCase):
    """ Tests the output logic of the qvm-device tool """

    def expected_device_call(self, vm, action, returned=b"0\0"):
        self.app.expected_calls[
            (vm, f'admin.vm.device.testclass.{action}', None, None)] = returned

    def setUp(self):
        super(TC_00_qvm_device, self).setUp()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\0test-vm1 class=AppVM state=Running\n'
            b'test-vm2 class=AppVM state=Running\n'
            b'test-vm3 class=AppVM state=Running\n')
        self.expected_device_call(
            'test-vm1', 'Available',
            b"0\0dev1 ident='dev1' devclass='testclass' vendor='itl'"
            b" product='test-device' backend_domain='test-vm1'"
        )
        self.vm1 = self.app.domains['test-vm1']
        self.vm2 = self.app.domains['test-vm2']
        self.vm1_device = self.app.domains['test-vm1'].devices['testclass']['dev1']

    def test_000_list_all(self):
        """
        List all exposed vm devices. No devices are connected to other domains.
        """
        self.expected_device_call(
            'test-vm2', 'Available',
            b"0\0dev2 ident='dev2' devclass='testclass' vendor='? `'"
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
                ['test-vm1:dev1  ?******: itl test-device',
                 'test-vm2:dev2  ?******: ? ` test-device']
            )

    def test_001_list_assigned_required(self):
        """
        List the device exposed by the `vm1` and assigned to the `vm3`.
        """
        # This shouldn't be listed
        self.expected_device_call(
            'test-vm2', 'Available',
            b"0\0dev2 ident='dev1' devclass='testclass' backend_domain='test-vm2'\n")
        self.expected_device_call('test-vm3', 'Available')
        self.expected_device_call('test-vm1', 'Attached')
        self.expected_device_call('test-vm2', 'Attached')
        self.expected_device_call('test-vm3', 'Attached')
        self.expected_device_call('test-vm1', 'Assigned')
        self.expected_device_call('test-vm2', 'Assigned')
        self.expected_device_call(
            'test-vm3', 'Assigned',
            b"0\0test-vm1+dev1 ident='dev1' devclass='testclass' "
            b"backend_domain='test-vm1' attach_automatically='yes' "
            b"required='yes'\n"
        )

        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['testclass', 'list', 'test-vm3'], app=self.app)
            self.assertEqual(
                buf.getvalue(),
                'test-vm1:dev1  ?******: itl test-device  test-vm3\n'
            )

    def test_002_list_attach(self):
        """
        List the device exposed by the `vm1` and attached to the `vm3`.
        """
        # This shouldn't be listed
        self.expected_device_call(
            'test-vm2', 'Available',
            b"0\0dev2 ident='dev1' devclass='testclass' backend_domain='test-vm2'\n")
        self.expected_device_call('test-vm3', 'Available')
        self.expected_device_call('test-vm1', 'Attached')
        self.expected_device_call('test-vm2', 'Attached')
        self.expected_device_call(
            'test-vm3', 'Attached',
            b"0\0test-vm1+dev1 ident='dev1' devclass='testclass' "
            b"backend_domain='test-vm1' attach_automatically='yes' "
            b"required='yes'\n"
        )
        self.expected_device_call('test-vm1', 'Assigned')
        self.expected_device_call('test-vm2', 'Assigned')
        self.expected_device_call('test-vm3', 'Assigned')

        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['testclass', 'list', 'test-vm3'], app=self.app)
            self.assertEqual(
                buf.getvalue(),
                'test-vm1:dev1  ?******: itl test-device  test-vm3\n'
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

    def test_010_attach(self):
        """ Test attach action """
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attach', 'test-vm1+dev1',
            b"required='no' attach_automatically='no' ident='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"frontend_domain='test-vm2'")] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'attach', 'test-vm2', 'test-vm1:dev1'], app=self.app)
        self.assertAllCalled()

    def test_011_attach_options(self):
        """ Test `read-only` attach option """
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Attach', 'test-vm1+dev1',
            b"required='no' attach_automatically='no' ident='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"frontend_domain='test-vm2' _read-only='yes'")] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'attach', '-o', 'ro=True', 'test-vm2', 'test-vm1:dev1'],
            app=self.app)
        self.assertAllCalled()

    def test_012_attach_invalid(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['testclass', 'attach', '-p', 'test-vm2', 'dev1'],
                    app=self.app)
            self.assertIn('expected a backend vm & device id',
                stderr.getvalue())
        self.assertAllCalled()

    def test_013_attach_invalid_device(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['testclass', 'attach', '-p', 'test-vm2', 'test-vm1:invalid'],
                    app=self.app)
            self.assertIn('doesn\'t expose testclass device',
                stderr.getvalue())
        self.assertAllCalled()

    def test_014_attach_invalid_backend(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['testclass', 'attach', '-p', 'test-vm2', 'no-such-vm:dev3'],
                    app=self.app)
            self.assertIn('no backend vm',
                stderr.getvalue())
        self.assertAllCalled()

    def test_020_detach(self):
        """ Test detach action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Detach',
             'test-vm1+dev1', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'detach', 'test-vm2', 'test-vm1:dev1'], app=self.app)
        self.assertAllCalled()

    def test_021_detach_unknown(self):
        """ Test detach action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Detach',
             'test-vm1+dev7', None)] = b'0\0'
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
             'test-vm1+dev1', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Detach',
             'test-vm1+dev2', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'detach', 'test-vm2'], app=self.app)
        self.assertAllCalled()

    def test_030_assign(self):
        """ Test assign action """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign', 'test-vm1+dev1',
            b"required='no' attach_automatically='yes' ident='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"frontend_domain='test-vm2' _identity='0000:0000::?******'"
        )] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'assign', 'test-vm2', 'test-vm1:dev1'], app=self.app)
        self.assertAllCalled()

    def test_031_assign_required(self):
        """ Test assign as required """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign', 'test-vm1+dev1',
            b"required='yes' attach_automatically='yes' ident='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"frontend_domain='test-vm2' _identity='0000:0000::?******'"
        )] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'assign', '--required', 'test-vm2', 'test-vm1:dev1'], app=self.app)
        self.assertAllCalled()

    def test_032_assign_options(self):
        """ Test `read-only` assign option """
        self.app.domains['test-vm2'].is_running = lambda: True
        self.app.expected_calls[(
            'test-vm2', 'admin.vm.device.testclass.Assign', 'test-vm1+dev1',
            b"required='no' attach_automatically='yes' ident='dev1' "
            b"devclass='testclass' backend_domain='test-vm1' "
            b"frontend_domain='test-vm2' _read-only='yes' "
            b"_identity='0000:0000::?******'")] = b'0\0'
        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['testclass', 'assign', '--ro', 'test-vm2', 'test-vm1:dev1'],
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
            self.assertIn('expected a backend vm & device id',
                stderr.getvalue())
        self.assertAllCalled()

    def test_034_assign_invalid_device(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['testclass', 'assign', 'test-vm2', 'test-vm1:invalid'],
                    app=self.app)
            self.assertIn('doesn\'t expose testclass device', stderr.getvalue())
        self.assertAllCalled()

    def test_035_assign_invalid_backend(self):
        """ Test attach action """
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['testclass', 'assign', 'test-vm2', 'no-such-vm:dev3'],
                    app=self.app)
            self.assertIn('no backend vm', stderr.getvalue())
        self.assertAllCalled()

    def test_040_unassign(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev1', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2', 'test-vm1:dev1'], app=self.app)
        self.assertAllCalled()

    def test_041_unassign_unknown(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev7', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2', 'test-vm1:dev7'], app=self.app)
        self.assertAllCalled()

    def test_042_unassign_all(self):
        """ Test unassign action """
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Assigned', None, None)] = \
            (b"0\0test-vm1+dev1 devclass='testclass'\n"
             b"test-vm1+dev2 devclass='testclass'\n")
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev1', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.device.testclass.Unassign',
             'test-vm1+dev2', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['testclass', 'unassign', 'test-vm2'], app=self.app)
        self.assertAllCalled()

