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
from qubesadmin.label import Label


class TC_00_Label(qubesadmin.tests.QubesTestCase):
    def test_000_list(self):
        self.app.expected_calls[
            ('dom0', 'admin.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        seen = set()
        for label in self.app.labels.values():
            self.assertNotIn(label.name, seen)
            seen.add(label.name)
        self.assertEqual(seen, {'green', 'red', 'black'})

    def test_001_list_names(self):
        self.app.expected_calls[
            ('dom0', 'admin.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        seen = set()
        for label in self.app.labels:
            self.assertNotIn(label, seen)
            seen.add(label)
        self.assertEqual(seen, {'green', 'red', 'black'})

    def test_002_list_keys(self):
        self.app.expected_calls[
            ('dom0', 'admin.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        seen = set()
        for label in self.app.labels.keys():
            self.assertNotIn(label, seen)
            seen.add(label)
        self.assertEqual(seen, {'green', 'red', 'black'})

    def test_003_list_items(self):
        self.app.expected_calls[
            ('dom0', 'admin.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        seen = set()
        for name, label in self.app.labels.items():
            self.assertEqual(name, label.name)
            self.assertNotIn(name, seen)
            seen.add(name)
        self.assertEqual(seen, {'green', 'red', 'black'})

    def test_010_get(self):
        self.app.expected_calls[
            ('dom0', 'admin.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        label = self.app.labels['green']
        self.assertIsInstance(label, Label)
        self.assertEqual(label.name, 'green')

    def test_011_get_color(self):
        self.app.expected_calls[
            ('dom0', 'admin.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        self.app.expected_calls[
            ('dom0', 'admin.label.Get', 'green', None)] = \
            b'0\x000x00FF00'
        label = self.app.labels['green']
        self.assertEqual(label.color, '0x00FF00')

    def test_012_get_index(self):
        self.app.expected_calls[
            ('dom0', 'admin.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        self.app.expected_calls[
            ('dom0', 'admin.label.Index', 'green', None)] = b'0\x003'
        label = self.app.labels['green']
        self.assertEqual(label.index, 3)

    def test_024_get_icon(self):
        self.app.expected_calls[
            ('dom0', 'admin.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        label = self.app.labels['green']
        self.assertEqual(label.icon, 'appvm-green')
