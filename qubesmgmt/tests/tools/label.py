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
from qubesmgmt.label import Label


class TC_00_Label(qubesmgmt.tests.QubesTestCase):
    def test_000_list(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        seen = set()
        for label in self.app.labels:
            self.assertNotIn(label.name, seen)
            seen.add(label.name)
        self.assertEqual(seen, set(['green', 'red', 'black']))

    def test_010_get(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        label = self.app.labels['green']
        self.assertIsInstance(label, Label)
        self.assertEqual(label.name, 'green')

    def test_011_get_color(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.label.List', None, None)] = \
            b'0\x00green\nred\nblack\n'
        self.app.expected_calls[
            ('dom0', 'mgmt.label.Get', 'green', None)] = \
            b'0\x000x00FF00'
        label = self.app.labels['green']
        self.assertEqual(label.color, '0x00FF00')

