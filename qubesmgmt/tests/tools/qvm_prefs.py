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

import qubesmgmt.tests
import qubesmgmt.tests.tools
import qubesmgmt.tools.qvm_prefs


class TC_00_qvm_prefs(qubesmgmt.tests.QubesTestCase):
    def test_000_list(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n'
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.property.List', None, None)] = \
            b'0\x00prop1\nprop2\n'
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.property.Get', 'prop1', None)] = \
            b'0\x00default=True type=str value1'
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.property.Get', 'prop2', None)] = \
            b'0\x00default=False type=str value2'
        with qubesmgmt.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0, qubesmgmt.tools.qvm_prefs.main([
                'dom0'], app=self.app))
        self.assertEqual(stdout.getvalue(),
            'prop1  D  value1\n'
            'prop2  -  value2\n')
        self.assertAllCalled()

    def test_001_no_vm(self):
        with self.assertRaises(SystemExit):
            qubesmgmt.tools.qvm_prefs.main([], app=self.app)
        self.assertAllCalled()

    def test_002_set_property(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n'
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.property.Set', 'default_user', b'testuser')] = \
            b'0\x00'
        self.assertEqual(0, qubesmgmt.tools.qvm_prefs.main([
            'dom0', 'default_user', 'testuser'], app=self.app))
        self.assertAllCalled()

    def test_003_invalid_property(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n'
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.property.Get', 'no_such_property', None)] = \
            b'2\x00AttributeError\x00\x00no_such_property\x00'
        with self.assertRaises(SystemExit):
            qubesmgmt.tools.qvm_prefs.main([
                'dom0', 'no_such_property'], app=self.app)
        self.assertAllCalled()

    def test_004_set_invalid_property(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n'
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.property.Set', 'no_such_property', b'value')] = \
            b'2\x00AttributeError\x00\x00no_such_property\x00'
        with self.assertRaises(SystemExit):
            qubesmgmt.tools.qvm_prefs.main([
                'dom0', 'no_such_property', 'value'], app=self.app)
        self.assertAllCalled()
