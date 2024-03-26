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
import qubesadmin.tools.qvm_kill


class TC_00_qvm_kill(qubesadmin.tests.QubesTestCase):
    def test_000_with_vm(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[("some-vm", "admin.vm.Kill", None, None)] = (
            b"0\x00"
        )
        qubesadmin.tools.qvm_kill.main(["some-vm"], app=self.app)
        self.assertAllCalled()

    def test_001_missing_vm(self):
        with self.assertRaises(SystemExit):
            with qubesadmin.tests.tools.StderrBuffer() as stderr:
                qubesadmin.tools.qvm_kill.main([], app=self.app)
        self.assertIn(
            "one of the arguments --all VMNAME is required", stderr.getvalue()
        )
        self.assertAllCalled()

    def test_002_invalid_vm(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
        )
        with self.assertRaises(SystemExit):
            with qubesadmin.tests.tools.StderrBuffer() as stderr:
                qubesadmin.tools.qvm_kill.main(["no-such-vm"], app=self.app)
        self.assertIn("no such domain", stderr.getvalue())
        self.assertAllCalled()

    def test_003_not_running(self):
        self.app.expected_calls[("some-vm", "admin.vm.Kill", None, None)] = (
            b"2\x00QubesVMNotStartedError\x00\x00Domain is powered off: "
            b"some-vm\x00"
        )
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Halted\n"
        )
        self.assertEqual(
            qubesadmin.tools.qvm_kill.main(["some-vm"], app=self.app), 0
        )
        self.assertAllCalled()

    def test_004_other_error(self):
        self.app.expected_calls[("some-vm", "admin.vm.Kill", None, None)] = (
            b"2\x00QubesVMError\x00\x00Error message\x00"
        )
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
        )
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            self.assertEqual(
                qubesadmin.tools.qvm_kill.main(["some-vm"], app=self.app), 1
            )
        self.assertAllCalled()
        self.assertIn(
            "Failed to kill 'some-vm': Error message", stderr.getvalue()
        )
