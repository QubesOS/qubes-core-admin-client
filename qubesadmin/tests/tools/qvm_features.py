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
import qubesadmin.tools.qvm_features


class TC_00_qvm_features(qubesadmin.tests.QubesTestCase):
    def test_000_list(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.List', None, None)] = \
            b'0\x00feature1\nfeature2\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Get', 'feature1', None)] = \
            b'0\x00value1'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Get', 'feature2', None)] = \
            b'0\x00value2 with spaces'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_features.main(['some-vm'], app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'feature1  value1\n'
                'feature2  value2 with spaces\n')
        self.assertAllCalled()

    def test_001_set(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Set',
             'feature3', b'value of feature')] = b'0\x00'
        self.assertEqual(
            qubesadmin.tools.qvm_features.main(['some-vm', 'feature3',
                'value of feature'],
                app=self.app),
            0)
        self.assertAllCalled()

    def test_002_get(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Get', 'feature3', None)] = \
            b'0\x00value2 with spaces'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_features.main(['some-vm', 'feature3'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'value2 with spaces\n')
        self.assertAllCalled()

    def test_003_del(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Remove', 'feature4', None)] = \
            b'0\x00'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_features.main(['--unset', 'some-vm',
                    'feature4'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                '')
        self.assertAllCalled()
