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

import qubesadmin.tests
import qubesadmin.tags

class TC_00_Tags(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n' \
            b'test-vm3 class=AppVM state=Running\n'
        self.vm = self.app.domains['test-vm']
        self.tags = qubesadmin.tags.Tags(self.vm)

    def test_000_list(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.List', None, None)] = \
            b'0\0tag1\ntag2\n'
        self.assertEqual(sorted(self.tags),
            ['tag1', 'tag2'])
        self.assertAllCalled()

    def test_010_get(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Get', 'tag1', None)] = \
            b'0\x001'
        self.assertIn('tag1', self.tags)
        self.assertAllCalled()

    def test_011_get_missing(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Get', 'tag1', None)] = \
            b'0\x000'
        self.assertNotIn('tag1', self.tags)
        self.assertAllCalled()

    def test_020_set(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Set', 'tag1', None)] = b'0\0'
        self.tags.add('tag1')
        self.assertAllCalled()

    def test_030_update(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Set', 'tag1', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Set', 'tag2', None)] = b'0\0'
        self.tags.update(['tag1', 'tag2'])
        self.assertAllCalled()

    def test_031_update_from_other(self):
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.tag.List', None, None)] = \
            b'0\0tag3\ntag4\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Set', 'tag3', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Set', 'tag4', None)] = b'0\0'
        self.tags.update(self.app.domains['test-vm2'].tags)
        self.assertAllCalled()

    def test_040_remove(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Remove', 'tag1', None)] = \
            b'0\0'
        self.tags.remove('tag1')
        self.assertAllCalled()

    def test_040_remove_missing(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Remove', 'tag1', None)] = \
            b'2\0QubesTagNotFoundError\0\0Tag not set for domain test-vm: ' \
            b'tag1\0'
        with self.assertRaises(KeyError):
            self.tags.remove('tag1')
        self.assertAllCalled()

    def test_050_discard(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Remove', 'tag1', None)] = \
            b'0\0'
        self.tags.discard('tag1')
        self.assertAllCalled()

    def test_051_discard_missing(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Remove', 'tag1', None)] = \
            b'2\0QubesTagNotFoundError\0\0Tag not set for domain test-vm: ' \
            b'tag1\0'
        self.tags.discard('tag1')
        self.assertAllCalled()
