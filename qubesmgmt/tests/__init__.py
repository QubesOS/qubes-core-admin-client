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

import io

import qubesmgmt
import qubesmgmt.app


class TestVM(object):
    def __init__(self, name, **kwargs):
        self.name = name
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_power_state(self):
        return getattr(self, 'power_state', 'Running')

    def __str__(self):
        return self.name

    def __lt__(self, other):
        if isinstance(other, TestVM):
            return self.name < other.name
        return NotImplemented


class TestVMCollection(dict):
    def __iter__(self):
        return iter(self.values())


class TestProcess(object):
    def __init__(self, input_callback=None, stdout=None, stderr=None):
        self.input_callback = input_callback
        self.stdin = io.BytesIO()
        # don't let anyone close it, before we get the value
        self.stdin_close = self.stdin.close
        if self.input_callback:
            self.stdin.close = (
                lambda: self.input_callback(self.stdin.getvalue()))
        else:
            self.stdin.close = lambda: None
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = 0

    def communicate(self, input=None):
        self.stdin.write(input)
        self.stdin.close()
        self.stdin_close()
        return self.stdout, self.stderr

    def wait(self):
        self.stdin_close()
        return 0

class QubesTest(qubesmgmt.app.QubesBase):
    expected_calls = None
    actual_calls = None
    service_calls = None

    def __init__(self):
        super(QubesTest, self).__init__()
        #: expected calls and saved replies for them
        self.expected_calls = {}
        #: actual calls made
        self.actual_calls = []
        #: rpc service calls
        self.service_calls = []

    def qubesd_call(self, dest, method, arg=None, payload=None):
        call_key = (dest, method, arg, payload)
        self.actual_calls.append(call_key)
        if call_key not in self.expected_calls:
            raise AssertionError('Unexpected call {!r}'.format(call_key))
        return_data = self.expected_calls[call_key]
        return self._parse_qubesd_response(return_data)

    def run_service(self, dest, service, **kwargs):
        self.service_calls.append((dest, service, kwargs))
        return TestProcess(lambda input: self.service_calls.append((dest,
            service, input)))


class QubesTestCase(unittest.TestCase):
    def setUp(self):
        super(QubesTestCase, self).setUp()
        self.app = QubesTest()

    def assertAllCalled(self):
        self.assertEqual(
            set(self.app.expected_calls.keys()),
            set(self.app.actual_calls))
