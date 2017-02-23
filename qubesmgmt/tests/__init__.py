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
import unittest

import qubesmgmt
import qubesmgmt.app


class QubesTest(qubesmgmt.app.QubesBase):
    expected_calls = None
    actual_calls = None

    def __init__(self):
        super(QubesTest, self).__init__()
        #: expected calls and saved replies for them
        self.expected_calls = {}
        #: actual calls made
        self.actual_calls = []

    def qubesd_call(self, dest, method, arg=None, payload=None):
        call_key = (dest, method, arg, payload)
        self.actual_calls.append(call_key)
        if call_key not in self.expected_calls:
            raise AssertionError('Unexpected call {!r}'.format(call_key))
        return_data = self.expected_calls[call_key]
        return self._parse_qubesd_response(return_data)


class QubesTestCase(unittest.TestCase):
    def setUp(self):
        super(QubesTestCase, self).setUp()
        self.app = QubesTest()

    def assertAllCalled(self):
        self.assertEqual(
            set(self.app.expected_calls.keys()),
            set(self.app.actual_calls))