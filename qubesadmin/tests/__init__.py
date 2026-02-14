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

# pylint: disable=missing-docstring

import string
import subprocess
import traceback
import unittest

import io

import qubesadmin
import qubesadmin.app

QREXEC_ALLOWED_CHARS = string.ascii_letters + string.digits + "_-+."

class TestVM(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.klass = 'TestVM'
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_power_state(self):
        return getattr(self, 'power_state', 'Running')

    def is_networked(self):
        return bool(getattr(self, 'netvm', False))

    def __str__(self):
        return self.name

    def __lt__(self, other):
        if isinstance(other, TestVM):
            return self.name < other.name
        return NotImplemented


class TestVMCollection(dict):
    def __iter__(self):
        return iter(self.values())

    get_blind = dict.get


class TestProcess(object):
    def __init__(self, input_callback=None, stdout=None, stderr=None,
            stdout_data=None):
        self.input_callback = input_callback
        self.got_any_input = False
        self.stdin = io.BytesIO()
        # don't let anyone close it, before we get the value
        self.stdin_close = self.stdin.close
        self.stdin.close = self.store_input
        self.stdin.flush = self.store_input
        if stdout == subprocess.PIPE or stdout == subprocess.DEVNULL \
                or stdout is None:
            self.stdout = io.BytesIO()
        else:
            self.stdout = stdout
        if stderr == subprocess.PIPE or stderr == subprocess.DEVNULL \
                or stderr is None:
            self.stderr = io.BytesIO()
        else:
            self.stderr = stderr
        if stdout_data:
            self.stdout.write(stdout_data)
            # Seek to head so that it can be read later
            try:
                self.stdout.seek(0)
            except io.UnsupportedOperation:
                # this can happen if (say) stdout is a pipe
                pass
        self.returncode = 0

    def store_input(self):
        value = self.stdin.getvalue()
        if (not self.got_any_input or value) and self.input_callback:
            self.input_callback(self.stdin.getvalue())
        self.got_any_input = True
        self.stdin.truncate(0)

    def communicate(self, input=None, timeout=None):
        # pylint: disable=redefined-builtin,unused-argument
        if input is not None:
            self.stdin.write(input)
        self.stdin.close()
        self.stdin_close()
        return self.stdout.read(), self.stderr.read()

    def wait(self):
        self.stdin_close()
        return 0

    def poll(self):
        return self.returncode


class _AssertNotRaisesContext(object):
    """A context manager used to implement TestCase.assertNotRaises methods.

    Stolen from unittest and hacked. Regexp support stripped.
    """ # pylint: disable=too-few-public-methods

    def __init__(self, expected, test_case, expected_regexp=None):
        if expected_regexp is not None:
            raise NotImplementedError('expected_regexp is unsupported')

        self.expected = expected
        self.exception = None

        # pylint: disable=invalid-name
        self.failureException = test_case.failureException

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback_):
        if exc_type is None:
            return True

        if issubclass(exc_type, self.expected):
            raise self.failureException(
                "{!r} raised, traceback:\n{!s}".format(
                    exc_value, ''.join(traceback.format_tb(traceback_))))
        # pass through
        return False


class QubesTest(qubesadmin.app.QubesBase):
    expected_service_calls = None
    expected_calls = None
    actual_calls = None
    service_calls = None
    # used to be None. casting to "none" for type correctness
    # but outside of tests, this value is not valid
    # TODO should likely update tests to avoid
    #  this hacky choice
    qubesd_connection_type: str = "none"

    def __init__(self):
        super().__init__()
        #: expected Admin API calls and saved replies for them
        self.expected_calls = {}
        #: expected qrexec service calls and saved replies for them
        self.expected_service_calls = {}
        #: actual calls made
        self.actual_calls = []
        #: rpc service calls
        self.service_calls = []

    def qubesd_call(self, dest, method, arg=None, payload=None,
            payload_stream=None):
        if arg:
            assert all(c in QREXEC_ALLOWED_CHARS for c in arg), \
                f"forbidden char in service arg '{arg}"
        if payload_stream:
            payload = (payload or b'') + payload_stream.read()
        call_key = (dest, method, arg, payload)
        self.actual_calls.append(call_key)
        if call_key not in self.expected_calls:
            raise AssertionError('Unexpected call {!r}'.format(call_key))
        return_data = self.expected_calls[call_key]
        if isinstance(return_data, list):
            try:
                return_data = return_data.pop(0)
            except IndexError:
                raise AssertionError('Extra call {!r}'.format(call_key))
        return self._parse_qubesd_response(return_data)

    def run_service(self, dest, service, **kwargs):
        # pylint: disable=arguments-differ
        assert all(c in QREXEC_ALLOWED_CHARS for c in service), \
            f"forbidden char in service '{service}"
        self.service_calls.append((dest, service, kwargs))
        call_key = (dest, service)
        # TODO: consider it as a future extension, as a replacement for
        #  checking app.service_calls later
        # if call_key not in self.expected_service_calls:
        #     raise AssertionError(
        #         'Unexpected service call {!r}'.format(call_key))
        if call_key in self.expected_service_calls:
            kwargs = kwargs.copy()
            kwargs['stdout_data'] = self.expected_service_calls[call_key]
        return TestProcess(lambda input: self.service_calls.append((dest,
            service, input)),
            stdout=kwargs.get('stdout', None),
            stderr=kwargs.get('stderr', None),
            stdout_data=kwargs.get('stdout_data', None),
        )


class QubesTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.app = QubesTest()

    def assertAllCalled(self):
        # pylint: disable=invalid-name
        self.assertEqual(
            set(self.app.expected_calls.keys()),
            set(self.app.actual_calls))
        # and also check if calls expected multiple times were called
        self.assertFalse([(call, ret)
            for call, ret in self.app.expected_calls.items() if
            isinstance(ret, list) and ret],
            'Some calls not called expected number of times')

    def assertNotRaises(self, excClass, *args, callableObj=None, **kwargs):
        """Fail if an exception of class excClass is raised
           by callableObj when invoked with arguments args and keyword
           arguments kwargs. If a different type of exception is
           raised, it will not be caught, and the test case will be
           deemed to have suffered an error, exactly as for an
           unexpected exception.

           If called with callableObj omitted or None, will return a
           context object used like this::

                with self.assertRaises(SomeException):
                    do_something()

           The context manager keeps a reference to the exception as
           the 'exception' attribute. This allows you to inspect the
           exception after the assertion::

               with self.assertRaises(SomeException) as cm:
                   do_something()
               the_exception = cm.exception
               self.assertEqual(the_exception.error_code, 3)
        """
        # pylint: disable=invalid-name
        context = _AssertNotRaisesContext(excClass, self)
        if callableObj is None:
            return context
        with context:
            callableObj(*args, **kwargs)
