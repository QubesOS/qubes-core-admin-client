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
            b'0\x00test-vm class=AppVM state=running\n'
        self.assertEqual(
            list(self.app.domains.keys()),
            ['test-vm'])
        self.assertAllCalled()

    def test_001_getitem(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=running\n'
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
            b'0\x00test-vm class=AppVM state=running\n'
        self.assertIn('test-vm', self.app.domains)
        self.assertAllCalled()

        self.assertNotIn('test-non-existent', self.app.domains)
        self.assertAllCalled()

    def test_003_iter(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00test-vm class=AppVM state=running\n'
        self.assertEqual([vm.name for vm in self.app.domains], ['test-vm'])
        self.assertAllCalled()


