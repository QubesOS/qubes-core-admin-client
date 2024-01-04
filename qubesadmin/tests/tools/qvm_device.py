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

''' Tests for the `qvm-device` tool. '''

import unittest.mock as mock
import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.devices
import qubesadmin.tools.qvm_device


class TC_00_qvm_device(qubesadmin.tests.QubesTestCase):
    ''' Tests the output logic of the qvm-device tool '''
    def setUp(self):
        super(TC_00_qvm_device, self).setUp()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm1 class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n' \
            b'test-vm3 class=AppVM state=Running\n'
        self.app.expected_calls[('test-vm1', 'admin.vm.device.test.Available',
            None, None)] = \
            b'0\0dev1 description=Description here\n'
        self.vm1 = self.app.domains['test-vm1']
        self.vm2 = self.app.domains['test-vm2']
        self.vm1_device = self.app.domains['test-vm1'].devices['test']['dev1']

    def test_000_list_all(self):
        ''' List all exposed vm devices. No devices are attached to other
            domains.
        '''
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.Available',
            None, None)] = \
            b'0\0dev2 description=Description here2\n'
        self.app.expected_calls[('test-vm3', 'admin.vm.device.test.Available',
            None, None)] = \
            b'0\0'

        self.app.expected_calls[('test-vm1', 'admin.vm.device.test.List',
            None, None)] = b'0\0'
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.List',
            None, None)] = b'0\0'
        self.app.expected_calls[('test-vm3', 'admin.vm.device.test.List',
            None, None)] = b'0\0'

        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['test', 'list'], app=self.app)
            self.assertEqual(
                [x.rstrip() for x in buf.getvalue().splitlines()],
                ['test-vm1:dev1  Description here',
                 'test-vm2:dev2  Description here2']
            )

    def test_001_list_required_attach(self):  # TODO
        """ Attach the device exposed by the `vm1` to the `vm3` persistently.
        """
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.Available',
            None, None)] = \
            b'0\0dev2 description=Description here2\n'
        self.app.expected_calls[('test-vm3', 'admin.vm.device.test.Available',
            None, None)] = \
            b'0\0'
        self.app.expected_calls[('test-vm1', 'admin.vm.device.test.List',
            None, None)] = b'0\0'
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.List',
            None, None)] = b'0\0'
        self.app.expected_calls[('test-vm3', 'admin.vm.device.test.List',
            None, None)] = \
            b'0\0test-vm1+dev1 required=True\n'

        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['test', 'list', 'test-vm3'], app=self.app)
            self.assertEqual(
                buf.getvalue(),
                'test-vm1:dev1  Description here  test-vm3\n'
            )

    def test_002_list_list_temp_attach(self):
        ''' Attach the device exposed by the `vm1` to the `vm3`
            non-persistently.
        '''
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.Available',
            None, None)] = \
            b'0\0dev2 description=Description here2\n'
        self.app.expected_calls[('test-vm3', 'admin.vm.device.test.Available',
            None, None)] = \
            b'0\0'

        self.app.expected_calls[('test-vm1', 'admin.vm.device.test.List',
            None, None)] = b'0\0'
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.List',
            None, None)] = b'0\0'
        self.app.expected_calls[('test-vm3', 'admin.vm.device.test.List',
            None, None)] = \
            b'0\0test-vm1+dev1\n'

        with qubesadmin.tests.tools.StdoutBuffer() as buf:
            qubesadmin.tools.qvm_device.main(
                ['test', 'list', 'test-vm3'], app=self.app)
            self.assertEqual(
                buf.getvalue(),
                'test-vm1:dev1  Description here  test-vm3\n'
            )

    def test_010_attach(self):
        ''' Test attach action '''
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.Attach',
            'test-vm1+dev1', b'')] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['test', 'attach', 'test-vm2', 'test-vm1:dev1'], app=self.app)
        self.assertAllCalled()

    def test_011_attach_options(self):
        ''' Test attach action '''
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.Attach',
            'test-vm1+dev1', b'ro=True')] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['test', 'attach', '-o', 'ro=True', 'test-vm2', 'test-vm1:dev1'],
            app=self.app)
        self.assertAllCalled()

    def test_011_attach_required(self):
        ''' Test attach action '''
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.Attach',
            'test-vm1+dev1', b'required=True')] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['test', 'attach', '-p', 'test-vm2', 'test-vm1:dev1'],
            app=self.app)
        self.assertAllCalled()

    def test_012_attach_invalid(self):
        ''' Test attach action '''
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['test', 'attach', '-p', 'test-vm2', 'dev1'],
                    app=self.app)
            self.assertIn('expected a backend vm & device id',
                stderr.getvalue())
        self.assertAllCalled()

    def test_013_attach_invalid2(self):
        ''' Test attach action '''
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['test', 'attach', '-p', 'test-vm2', 'test-vm1:invalid'],
                    app=self.app)
            self.assertIn('doesn\'t expose device',
                stderr.getvalue())
        self.assertAllCalled()

    def test_014_attach_invalid3(self):
        ''' Test attach action '''
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_device.main(
                    ['test', 'attach', '-p', 'test-vm2', 'no-such-vm:dev3'],
                    app=self.app)
            self.assertIn('no backend vm',
                stderr.getvalue())
        self.assertAllCalled()

    def test_020_detach(self):
        ''' Test detach action '''
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.Detach',
            'test-vm1+dev1', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['test', 'detach', 'test-vm2', 'test-vm1:dev1'], app=self.app)
        self.assertAllCalled()

    def test_021_detach_unknown(self):
        ''' Test detach action '''
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.Detach',
            'test-vm1+dev7', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['test', 'detach', 'test-vm2', 'test-vm1:dev7'], app=self.app)
        self.assertAllCalled()

    def test_022_detach_all(self):
        ''' Test detach action '''
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.List',
            None, None)] = \
            b'0\0test-vm1+dev1\ntest-vm1+dev2\n'
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.Detach',
            'test-vm1+dev1', None)] = b'0\0'
        self.app.expected_calls[('test-vm2', 'admin.vm.device.test.Detach',
            'test-vm1+dev2', None)] = b'0\0'
        qubesadmin.tools.qvm_device.main(
            ['test', 'detach', 'test-vm2'], app=self.app)
        self.assertAllCalled()

