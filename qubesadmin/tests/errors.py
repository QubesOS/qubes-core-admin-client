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

import qubesadmin.exc
import qubesadmin.tests

class TC_00_Errors(qubesadmin.tests.QubesTestCase):
    def test_000_exception(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'2\x00QubesException\x00\x00An error occurred\x00'
        with self.assertRaises(qubesadmin.exc.QubesException) as context:
            list(self.app.domains)
        self.assertEqual(str(context.exception), 'An error occurred')

    def test_001_exception_with_fields(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'2\x00QubesException\x00\x00' \
            b'An error occurred: %s, %s\x00string\x00other\x00'
        with self.assertRaises(qubesadmin.exc.QubesException) as context:
            list(self.app.domains)
        self.assertEqual(str(context.exception),
            'An error occurred: string, other')

    def test_002_exception_with_numbers(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'2\x00QubesException\x00\x00' \
            b'An error occurred: %d, %d\x001\x002\x00'
        try:
            with self.assertRaises(qubesadmin.exc.QubesException) as context:
                list(self.app.domains)
        except TypeError as e:
            self.fail(f'TypeError: {e!s}')
        self.assertEqual(str(context.exception), 'An error occurred: 1, 2')

    def test_010_empty(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = b''
        with self.assertRaises(qubesadmin.exc.QubesDaemonNoResponseError) \
                as context:
            list(self.app.domains)
        self.assertEqual(str(context.exception),
            'Got empty response from qubesd. '
            'See journalctl in dom0 for details.')
