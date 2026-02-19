#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

# pylint: disable=missing-docstring

import qubesadmin.features
import qubesadmin.tests


class TC_00_Features(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n' \
            b'test-vm3 class=AppVM state=Running\n'
        self.vm = self.app.domains['test-vm']
        self.features = qubesadmin.features.Features(self.vm)

    def test_000_list(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.List', None, None)] = \
            b'0\0feature1\nfeature2\n'
        self.assertEqual(sorted(self.vm.features.keys()),
            ['feature1', 'feature2'])
        self.assertAllCalled()

    def test_010_get(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Get', 'feature1', None)] = \
            b'0\0value1'
        self.assertEqual(self.vm.features['feature1'], 'value1')
        self.assertAllCalled()

    def test_011_get_none(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Get', 'feature1', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00feature1\x00'
        with self.assertRaises(KeyError):
            # pylint: disable=pointless-statement
            self.vm.features['feature1']
        self.assertAllCalled()

    def test_012_get_none(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Get', 'feature1', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00feature1\x00'
        with self.assertRaises(KeyError):
            self.vm.features.get('feature1', self.vm.features.NO_DEFAULT)
        self.assertAllCalled()

    def test_013_get_default(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Get', 'feature1', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00feature1\x00'
        self.assertEqual(self.vm.features.get('feature1', 'other'), 'other')
        self.assertAllCalled()

    def test_020_set(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'feature1', b'value')] = \
            b'0\0'
        self.vm.features['feature1'] = 'value'
        self.assertAllCalled()

    def test_021_set_bool(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'feature1', b'1')] = \
            b'0\0'
        self.vm.features['feature1'] = True
        self.assertAllCalled()

    def test_022_set_bool_false(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'feature1', b'')] = \
            b'0\0'
        self.vm.features['feature1'] = False
        self.assertAllCalled()
