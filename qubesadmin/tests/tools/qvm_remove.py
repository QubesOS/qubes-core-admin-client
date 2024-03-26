# -*- encoding: utf-8 -*-
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

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_remove
import unittest.mock


class TC_00_qvm_remove(qubesadmin.tests.QubesTestCase):
    def test_000_single(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[("some-vm", "admin.vm.Remove", None, None)] = (
            b"0\x00\n"
        )
        qubesadmin.tools.qvm_remove.main(["-f", "some-vm"], app=self.app)
        self.assertAllCalled()

    @unittest.mock.patch("qubesadmin.utils.vm_dependencies")
    def test_100_dependencies(self, mock_dependencies):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[("some-vm", "admin.vm.Remove", None, None)] = (
            b"2\x00QubesVMInUseError\x00\x00An error occurred\x00"
        )

        mock_dependencies.return_value = [
            (None, "default_template"),
            (self.app.domains["some-vm"], "netvm"),
        ]

        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_remove.main(["-f", "some-vm"], app=self.app)

        self.assertTrue(
            mock_dependencies.called, "Dependencies check not called."
        )
