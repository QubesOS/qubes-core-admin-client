#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2025 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
# Copyright (C) 2025 Ali Mirjamali <ali@mirjamali.com>
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

import tempfile
from unittest.mock import patch

import qubesadmin.exc
import qubesadmin.tests
import qubesadmin.tools.qvm_notes


class TC_00_qvm_notes(qubesadmin.tests.QubesTestCase):

    @patch("subprocess.run")
    @patch("os.path.getmtime", side_effect=[2025, 1984])
    def test_001_edit(self, run, getmtime):
        # pylint: disable=w0613
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[("vm", "admin.vm.notes.Get", None, None)] = (
            b"0\x00For Your Eyes Only"
        )
        self.app.expected_calls[
            ("vm", "admin.vm.notes.Set", None, b"For Your Eyes Only")
        ] = b"0\x00"
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(["vm"], app=self.app), 0
        )
        self.assertAllCalled()

    def test_002_print(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[("vm", "admin.vm.notes.Get", None, None)] = (
            b"0\x00For Your Eyes Only\n"
        )
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(["vm", "--print"], app=self.app), 0
        )
        self.assertAllCalled()

    def test_003_set(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("vm", "admin.vm.notes.Set", None, b"For Your Eyes Only")
        ] = b"0\x00"
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(
                ["vm", "--force", "--set", "For Your Eyes Only"], app=self.app
            ),
            0,
        )
        self.assertAllCalled()

    def test_004_import(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("vm", "admin.vm.notes.Set", None, b"For Your Eyes Only")
        ] = b"0\x00"
        with tempfile.NamedTemporaryFile(
            mode="w+",
            delete=False,
        ) as temp:
            temp.write("For Your Eyes Only")
            temp.close()
            self.assertEqual(
                qubesadmin.tools.qvm_notes.main(
                    [
                        "vm",
                        "--force",
                        "--import",
                        temp.name,
                    ],
                    app=self.app,
                ),
                0,
            )
        self.assertAllCalled()

    def test_005_append(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[("vm", "admin.vm.notes.Get", None, None)] = (
            b"0\0Note 1"
        )
        self.app.expected_calls[
            ("vm", "admin.vm.notes.Set", None, b"Note 1\nNote 2")
        ] = b"0\x00"
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(
                ["vm", "--force", "--append", "Note 2"], app=self.app
            ),
            0,
        )
        self.assertAllCalled()

    def test_006_delete(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[("vm", "admin.vm.notes.Set", None, b"")] = (
            b"0\x00"
        )
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(
                [
                    "vm",
                    "--force",
                    "--delete",
                ],
                app=self.app,
            ),
            0,
        )
        self.assertAllCalled()

    @patch("builtins.input", return_value="NO")
    def test_007_delete_canceled(self, input):
        # pylint: disable=w0613,w0622
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00vm class=AppVM state=Running\n"
        )
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_notes.main(
                [
                    "vm",
                    "--delete",
                ],
                app=self.app,
            )
        self.assertAllCalled()

    def test_010_no_read_access(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[("vm", "admin.vm.notes.Get", None, None)] = (
            b"2\0QubesNotesException\0\0You do not have read access to notes!\0"
        )
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(
                [
                    "vm",
                    "--print",
                ],
                app=self.app,
            ),
            1,
        )
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(
                [
                    "vm",
                ],
                app=self.app,
            ),
            1,
        )
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(
                [
                    "vm",
                    "--append",
                    "Some note",
                ],
                app=self.app,
            ),
            1,
        )
        self.assertAllCalled()

    def test_011_no_write_access(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00vm class=AppVM state=Running\nq2 class=AppVM state=Running\n"
        )
        self.app.expected_calls[("vm", "admin.vm.notes.Get", None, None)] = (
            b"0\x00"
        )
        self.app.expected_calls[
            ("vm", "admin.vm.notes.Set", None, b"New note")
        ] = b"2\0QubesNotesException\0\0You do not have read access to notes!\0"
        self.app.expected_calls[("q2", "admin.vm.notes.Set", None, b"")] = (
            b"2\0QubesNotesException\0\0You do not have read access to notes!\0"
        )
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(
                [
                    "vm",
                    "--force",
                    "--append",
                    "New note",
                ],
                app=self.app,
            ),
            1,
        )
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(
                [
                    "vm",
                    "--force",
                    "--set",
                    "New note",
                ],
                app=self.app,
            ),
            1,
        )
        with tempfile.NamedTemporaryFile(
            mode="w+",
            delete=False,
        ) as temp:
            temp.write("New note")
            temp.close()
            self.assertEqual(
                qubesadmin.tools.qvm_notes.main(
                    [
                        "vm",
                        "--force",
                        "--import",
                        temp.name,
                    ],
                    app=self.app,
                ),
                1,
            )
        self.assertEqual(
            qubesadmin.tools.qvm_notes.main(
                [
                    "q2",
                    "--force",
                    "--delete",
                ],
                app=self.app,
            ),
            1,
        )
        self.assertAllCalled()
