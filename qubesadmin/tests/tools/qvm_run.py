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

import io
import os
import unittest.mock

import subprocess
import sys

import qubesadmin.tests
import qubesadmin.tools.qvm_run


class TC_00_qvm_run(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        if sys.stdout is not sys.__stdout__ or sys.stderr is not sys.__stderr__:
            self.skipTest("qvm-run change behavior on redirected stdout/stderr")
        super().setUp()

    def default_filter_esc(self):
        return os.isatty(sys.stdout.fileno())

    def test_000_run_single(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "test-vm", "command"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_000_run_single_auto_nogui_nodisplay(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        orig_display = os.environ.pop("DISPLAY", None)
        try:
            ret = qubesadmin.tools.qvm_run.main(
                ["test-vm", "command"], app=self.app
            )
        finally:
            if orig_display is not None:
                os.environ["DISPLAY"] = orig_display
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_000_run_single_auto_nogui_noguivm(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        self.app.expected_calls[
            ("test-vm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=False type=vm "
        ret = qubesadmin.tools.qvm_run.main(
            ["test-vm", "command"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_000_run_single_auto_nogui_noguifeat(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        self.app.expected_calls[
            ("test-vm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=True type=vm dom0"
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "gui", None)
        ] = b"0\x00"
        ret = qubesadmin.tools.qvm_run.main(
            ["test-vm", "command"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_001_run_multiple(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
            b"test-vm2 class=AppVM state=Running\n"
            b"test-vm3 class=AppVM state=Halted\n"
            b"disp007 class=DispVM state=Paused\n"
        )
        for vm in ["test-vm", "test-vm2"]:
            self.app.expected_calls[
                (vm, "admin.vm.feature.Get", "internal", None)
            ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00"
        self.app.expected_calls[
            ("disp007", "admin.vm.feature.Get", "internal", None)
        ] = b"0\x001x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        self.app.expected_calls[
            ("test-vm2", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        self.app.expected_calls[
            ("test-vm3", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Halted"
        self.app.expected_calls[
            ("disp007", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Paused"
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm2", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=False type=vm "
        self.app.expected_calls[
            ("test-vm2", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=True type=vm dom0"
        self.app.expected_calls[
            ("test-vm2", "admin.vm.feature.CheckWithTemplate", "gui", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'gui' not set\x00"
        self.app.expected_calls[
            ("test-vm2", "admin.vm.property.Get", "default_user", None)
        ] = b"0\x00default=yes type=str user"
        ret = qubesadmin.tools.qvm_run.main(["--all", "command"], app=self.app)
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\n"),
                (
                    "test-vm2",
                    "qubes.WaitForSession",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                    },
                ),
                ("test-vm2", "qubes.WaitForSession", b"user"),
                (
                    "test-vm2",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm2", "qubes.VMShell", b"command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_002_passio(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        with subprocess.Popen(
            ["echo", "some-data"], stdout=subprocess.PIPE
        ) as echo:
            with unittest.mock.patch("sys.stdin", echo.stdout):
                ret = qubesadmin.tools.qvm_run.main(
                    [
                        "--no-gui",
                        "--pass-io",
                        "--filter-escape-chars",
                        "test-vm",
                        "command",
                    ],
                    app=self.app,
                )
            echo.stdout.close()

        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "filter_esc": True,
                        "stdout": None,
                        "stderr": None,
                        "user": None,
                    },
                ),
                # TODO: find a way to compare b'some-data\n' sent from another
                # proces
                ("test-vm", "qubes.VMShell", b"command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_002_passio_service(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        with subprocess.Popen(
            ["echo", "some-data"], stdout=subprocess.PIPE
        ) as echo:
            with unittest.mock.patch("sys.stdin", echo.stdout):
                ret = qubesadmin.tools.qvm_run.main(
                    [
                        "--no-gui",
                        "--service",
                        "--pass-io",
                        "--filter-escape-chars",
                        "test-vm",
                        "test.service",
                    ],
                    app=self.app,
                )
            echo.stdout.close()

        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "test.service",
                    {
                        "filter_esc": True,
                        "stdout": None,
                        "stderr": None,
                        "user": None,
                    },
                ),
                # TODO: find a way to compare b'some-data\n' sent from another
                # proces
                ("test-vm", "test.service", b""),
            ],
        )
        self.assertAllCalled()

    @unittest.expectedFailure
    def test_002_color_output(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        stdout = io.StringIO()
        with subprocess.Popen(
            ["echo", "some-data"], stdout=subprocess.PIPE
        ) as echo:
            with unittest.mock.patch("sys.stdin", echo.stdout):
                with unittest.mock.patch("sys.stdout", stdout):
                    ret = qubesadmin.tools.qvm_run.main(
                        [
                            "--no-gui",
                            "--filter-esc",
                            "--pass-io",
                            "test-vm",
                            "command",
                        ],
                        app=self.app,
                    )
            echo.stdout.close()

        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "filter_esc": True,
                        "stdout": None,
                        "stderr": None,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\nsome-data\n"),
            ],
        )
        self.assertEqual(stdout.getvalue(), "\033[0;31m\033[0m")
        stdout.close()
        self.assertAllCalled()

    @unittest.expectedFailure
    def test_003_no_color_output(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        stdout = io.StringIO()
        with subprocess.Popen(
            ["echo", "some-data"], stdout=subprocess.PIPE
        ) as echo:
            with unittest.mock.patch("sys.stdin", echo.stdout):
                with unittest.mock.patch("sys.stdout", stdout):
                    ret = qubesadmin.tools.qvm_run.main(
                        [
                            "--no-gui",
                            "--pass-io",
                            "--no-color-output",
                            "test-vm",
                            "command",
                        ],
                        app=self.app,
                    )

            echo.stdout.close()

        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "filter_esc": self.default_filter_esc(),
                        "stdout": None,
                        "stderr": None,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\nsome-data\n"),
            ],
        )
        self.assertEqual(stdout.getvalue(), "")
        stdout.close()
        self.assertAllCalled()

    @unittest.expectedFailure
    def test_004_no_filter_esc(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        # self.app.expected_calls[
        #     ('test-vm', 'admin.vm.List', None, None)] = \
        #     b'0\x00test-vm class=AppVM state=Running\n'
        stdout = io.StringIO()
        with subprocess.Popen(
            ["echo", "some-data"], stdout=subprocess.PIPE
        ) as echo:
            with unittest.mock.patch("sys.stdin", echo.stdout):
                with unittest.mock.patch("sys.stdout", stdout):
                    ret = qubesadmin.tools.qvm_run.main(
                        [
                            "--no-gui",
                            "--pass-io",
                            "--no-filter-esc",
                            "test-vm",
                            "command",
                        ],
                        app=self.app,
                    )

            echo.stdout.close()

        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "filter_esc": False,
                        "stdout": None,
                        "stderr": None,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\nsome-data\n"),
            ],
        )
        self.assertEqual(stdout.getvalue(), "")
        stdout.close()
        self.assertAllCalled()

    @unittest.mock.patch("subprocess.Popen")
    def test_005_localcmd(self, mock_popen):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        mock_popen.return_value.wait.return_value = 0
        ret = qubesadmin.tools.qvm_run.main(
            [
                "--no-gui",
                "--pass-io",
                "--localcmd",
                "local-command",
                "test-vm",
                "command",
            ],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.PIPE,
                        "stdin": subprocess.PIPE,
                        "stderr": None,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\n"),
            ],
        )
        mock_popen.assert_called_once_with(
            "local-command",
            # TODO: check if the right stdin/stdout objects are used
            stdout=unittest.mock.ANY,
            stdin=unittest.mock.ANY,
            shell=True,
        )
        self.assertAllCalled()

    def test_006_run_single_with_gui(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.property.Get", "default_user", None)
        ] = b"0\x00default=yes type=str user"
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        self.app.expected_calls[
            ("test-vm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=True type=vm dom0"
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "gui", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'gui' not set\x00"
        ret = qubesadmin.tools.qvm_run.main(
            ["test-vm", "command"], app=self.app
        )
        self.assertEqual(ret, 0)
        # make sure we have the same instance below
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.WaitForSession",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                    },
                ),
                ("test-vm", "qubes.WaitForSession", b"user"),
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_007_run_service_with_gui(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.property.Get", "default_user", None)
        ] = b"0\x00default=yes type=str user"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        self.app.expected_calls[
            ("test-vm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=True type=vm dom0"
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "gui", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'gui' not set\x00"
        ret = qubesadmin.tools.qvm_run.main(
            ["--service", "test-vm", "service.name"], app=self.app
        )
        self.assertEqual(ret, 0)
        # make sure we have the same instance below
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.WaitForSession",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                    },
                ),
                ("test-vm", "qubes.WaitForSession", b"user"),
                (
                    "test-vm",
                    "service.name",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "service.name", b""),
            ],
        )
        self.assertAllCalled()

    def test_008_dispvm_remote(self):
        self.app.expected_calls[
            ("dom0", "admin.property.Get", "default_dispvm", None)
        ] = b"0\x00default=True type=vm default-dvm"
        self.app.expected_calls[
            ("default-dvm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=True type=vm dom0"
        self.app.expected_calls[
            ("default-dvm", "admin.vm.feature.CheckWithTemplate", "gui", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'gui' not set\x00"
        ret = qubesadmin.tools.qvm_run.main(
            ["--service", "--dispvm", "--", "test.service"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "@dispvm",
                    "test.service",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("@dispvm", "test.service", b""),
            ],
        )
        self.assertAllCalled()

    def test_009_dispvm_remote_specific(self):
        self.app.expected_calls[
            ("test-vm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=True type=vm dom0"
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "gui", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'gui' not set\x00"
        ret = qubesadmin.tools.qvm_run.main(
            ["--dispvm=test-vm", "--service", "test.service"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "@dispvm:test-vm",
                    "test.service",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("@dispvm:test-vm", "test.service", b""),
            ],
        )
        self.assertAllCalled()

    def test_010_dispvm_local(self):
        self.app.qubesd_connection_type = "socket"
        self.app.expected_calls[
            ("dom0", "admin.vm.CreateDisposable", None, None)
        ] = b"0\x00disp123"
        self.app.expected_calls[("disp123", "admin.vm.Kill", None, None)] = (
            b"0\x00"
        )
        self.app.expected_calls[
            ("disp123", "admin.vm.property.Get", "qrexec_timeout", None)
        ] = b"0\x00default=yes type=int 30"
        self.app.expected_calls[
            ("dom0", "admin.property.Get", "default_dispvm", None)
        ] = b"0\x00default=True type=vm default-dvm"
        self.app.expected_calls[
            ("default-dvm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=True type=vm dom0"
        self.app.expected_calls[
            ("default-dvm", "admin.vm.feature.CheckWithTemplate", "gui", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'gui' not set\x00"
        ret = qubesadmin.tools.qvm_run.main(
            ["--service", "--dispvm", "--", "test.service"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "disp123",
                    "test.service",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                        "connect_timeout": 30,
                    },
                ),
                ("disp123", "test.service", b""),
            ],
        )
        self.assertAllCalled()

    def test_011_dispvm_local_specific(self):
        self.app.qubesd_connection_type = "socket"
        self.app.expected_calls[
            ("test-vm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=False type=vm "
        self.app.expected_calls[
            ("test-vm", "admin.vm.CreateDisposable", None, None)
        ] = b"0\x00disp123"
        self.app.expected_calls[("disp123", "admin.vm.Kill", None, None)] = (
            b"0\x00"
        )
        self.app.expected_calls[
            ("disp123", "admin.vm.property.Get", "qrexec_timeout", None)
        ] = b"0\x00default=yes type=int 30"
        ret = qubesadmin.tools.qvm_run.main(
            ["--dispvm=test-vm", "--service", "test.service"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "disp123",
                    "test.service",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                        "connect_timeout": 30,
                    },
                ),
                ("disp123", "test.service", b""),
            ],
        )
        self.assertAllCalled()

    def test_012_exclude(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
            b"test-vm2 class=AppVM state=Running\n"
            b"test-vm3 class=AppVM state=Halted\n"
            b"disp007 class=DispVM state=Paused\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.Get", "internal", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature not set\x00"
        self.app.expected_calls[
            ("disp007", "admin.vm.feature.Get", "internal", None)
        ] = b"0\x001x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        self.app.expected_calls[
            ("test-vm3", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Halted"
        self.app.expected_calls[
            ("disp007", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Paused"
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--all", "--exclude", "test-vm2", "command"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_013_no_autostart(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
            b"test-vm2 class=AppVM state=Running\n"
            b"test-vm3 class=AppVM state=Halted\n"
        )
        self.app.expected_calls[
            ("test-vm3", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Halted"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--no-autostart", "test-vm3", "command"], app=self.app
        )
        self.assertEqual(ret, 1)
        self.assertEqual(self.app.service_calls, [])
        self.assertAllCalled()

    def test_014_dispvm_local_gui(self):
        self.app.qubesd_connection_type = "socket"
        self.app.expected_calls[
            ("dom0", "admin.vm.CreateDisposable", None, None)
        ] = b"0\x00disp123"
        self.app.expected_calls[("disp123", "admin.vm.Kill", None, None)] = (
            b"0\x00"
        )
        self.app.expected_calls[
            ("dom0", "admin.property.Get", "default_dispvm", None)
        ] = b"0\x00default=True type=vm default-dvm"
        self.app.expected_calls[
            ("default-dvm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=True type=vm dom0"
        self.app.expected_calls[
            ("default-dvm", "admin.vm.feature.CheckWithTemplate", "gui", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'gui' not set\x00"
        self.app.expected_calls[
            ("disp123", "admin.vm.property.Get", "qrexec_timeout", None)
        ] = b"0\x00default=yes type=int 30"
        self.app.expected_calls[
            ("disp123", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        ret = qubesadmin.tools.qvm_run.main(
            ["--dispvm", "--", "test.command"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "disp123",
                    "qubes.VMShell+WaitForSession",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                        "connect_timeout": 30,
                    },
                ),
                (
                    "disp123",
                    "qubes.VMShell+WaitForSession",
                    b"test.command; exit\n",
                ),
            ],
        )
        self.assertAllCalled()

    def test_015_dispvm_local_nogui(self):
        self.app.qubesd_connection_type = "socket"
        self.app.expected_calls[
            ("dom0", "admin.vm.CreateDisposable", None, None)
        ] = b"0\x00disp123"
        self.app.expected_calls[("disp123", "admin.vm.Kill", None, None)] = (
            b"0\x00"
        )
        self.app.expected_calls[
            ("disp123", "admin.vm.property.Get", "qrexec_timeout", None)
        ] = b"0\x00default=yes type=int 30"
        self.app.expected_calls[
            ("disp123", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--dispvm", "--", "test.command"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "disp123",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                        "connect_timeout": 30,
                    },
                ),
                ("disp123", "qubes.VMShell", b"test.command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_015_dispvm_local_nogui_implicit(self):
        self.app.qubesd_connection_type = "socket"
        self.app.expected_calls[
            ("dom0", "admin.vm.CreateDisposable", None, None)
        ] = b"0\x00disp123"
        self.app.expected_calls[("disp123", "admin.vm.Kill", None, None)] = (
            b"0\x00"
        )
        self.app.expected_calls[
            ("dom0", "admin.property.Get", "default_dispvm", None)
        ] = b"0\x00default=True type=vm default-dvm"
        self.app.expected_calls[
            ("default-dvm", "admin.vm.property.Get", "guivm", None)
        ] = b"0\x00default=False type=vm "
        self.app.expected_calls[
            ("disp123", "admin.vm.property.Get", "qrexec_timeout", None)
        ] = b"0\x00default=yes type=int 30"
        self.app.expected_calls[
            ("disp123", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        ret = qubesadmin.tools.qvm_run.main(
            ["--dispvm", "--", "test.command"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "disp123",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                        "connect_timeout": 30,
                    },
                ),
                ("disp123", "qubes.VMShell", b"test.command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_016_run_single_windows(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"0\x00Windows"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "test-vm", "command"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command& exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_020_run_exec_with_vmexec_not_supported(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = (
            b"2\x00QubesFeatureNotFoundError\x00\x00Feature "
            b"'vmexec' not set\x00"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "test-vm", "command", "arg"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command arg; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_020_run_exec_with_vmexec_supported(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = b"0\x001"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "test-vm", "command", "arg"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMExec+command+arg",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMExec+command+arg", b""),
            ],
        )
        self.assertAllCalled()

    def test_021_paused_vm(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Paused\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Paused"
        self.app.expected_calls[("test-vm", "admin.vm.Unpause", None, None)] = (
            b"0\x00"
        )
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "test-vm", "command"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMShell", b"command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_022_no_shell(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Paused\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = b"0\x001"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--no-shell", "test-vm", "command"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMExec+command",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMExec+command", b""),
            ],
        )
        self.assertAllCalled()

    def test_023_dispvm_no_shell(self):
        self.app.expected_calls[
            (
                "test-vm",
                "admin.vm.feature.CheckWithTemplate",
                "vmexec",
                None,
            )
        ] = b"0\x001"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--no-shell", "--dispvm=test-vm", "command"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "@dispvm:test-vm",
                    "qubes.VMExec+command",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("@dispvm:test-vm", "qubes.VMExec+command", b""),
            ],
        )
        self.assertAllCalled()

    def test_024_no_shell_dashdash(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Paused\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = b"0\x001"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--no-shell", "test-vm", "command", "--", "arg"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMExec+command+arg",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMExec+command+arg", b""),
            ],
        )
        self.assertAllCalled()

    def test_025_no_shell_double_dashdash(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Paused\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = b"0\x001"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--no-shell", "test-vm", "command", "--", "--", "arg"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMExec+command+----+arg",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMExec+command+----+arg", b""),
            ],
        )
        self.assertAllCalled()

    def test_026_no_shell_double_dashdash(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Paused\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = b"0\x001"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--no-shell", "--", "test-vm", "command", "--", "arg"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMExec+command+----+arg",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMExec+command+----+arg", b""),
            ],
        )
        self.assertAllCalled()

    def test_027_no_shell_dispvm(self):
        self.app.expected_calls[
            (
                "test-vm",
                "admin.vm.feature.CheckWithTemplate",
                "vmexec",
                None,
            )
        ] = b"0\x001"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--dispvm=test-vm", "command", "--", "arg"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "@dispvm:test-vm",
                    "qubes.VMExec+command+arg",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("@dispvm:test-vm", "qubes.VMExec+command+arg", b""),
            ],
        )
        self.assertAllCalled()

    def test_028_argparse_bug_workaround(self):
        self.app.expected_calls[
            (
                "test-vm",
                "admin.vm.feature.CheckWithTemplate",
                "vmexec",
                None,
            )
        ] = b"0\x001"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--dispvm=test-vm", "command", "--", "--"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "@dispvm:test-vm",
                    "qubes.VMExec+command+----",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("@dispvm:test-vm", "qubes.VMExec+command+----", b""),
            ],
        )
        self.assertAllCalled()

    def test_029_command_is_dashdash(self):
        self.app.expected_calls[
            (
                "test-vm",
                "admin.vm.feature.CheckWithTemplate",
                "vmexec",
                None,
            )
        ] = b"0\x001"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--dispvm=test-vm", "--no-shell", "--", "--"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "@dispvm:test-vm",
                    "qubes.VMExec+----",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("@dispvm:test-vm", "qubes.VMExec+----", b""),
            ],
        )
        self.assertAllCalled()

    def test_030_no_shell_dispvm(self):
        self.app.expected_calls[
            ("dom0", "admin.property.Get", "default_dispvm", None)
        ] = b"0\x00default=True type=vm test-vm"
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = b"0\x001"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--dispvm", "--", "test-vm", "command", "arg"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "@dispvm",
                    "qubes.VMExec+test--vm+command+arg",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("@dispvm", "qubes.VMExec+test--vm+command+arg", b""),
            ],
        )
        self.assertAllCalled()

    def test_031_argparse_bug_workaround(self):
        self.app.expected_calls[
            ("dom0", "admin.property.Get", "default_dispvm", None)
        ] = b"0\x00default=True type=vm test-vm"
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = b"0\x001"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--dispvm", "--", "test-vm", "command", "--"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "@dispvm",
                    "qubes.VMExec+test--vm+command+----",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("@dispvm", "qubes.VMExec+test--vm+command+----", b""),
            ],
        )
        self.assertAllCalled()

    @unittest.expectedFailure
    def test_032_argparse_bug_workaround_unnamed_dispvm(self):
        self.app.expected_calls[
            ("@dispvm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = b"0\x001"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "--dispvm", "test-vm", "command", "--"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "@dispvm",
                    "qubes.VMExec+test--vm+command+----",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("@dispvm", "qubes.VMExec+test--vm+command+----", b""),
            ],
        )
        self.assertAllCalled()

    def test_040_run_root_shell(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "os", None)
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature 'os' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "-u", "root", "test-vm", "shell command"], app=self.app
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMRootShell",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMRootShell", b"shell command; exit\n"),
            ],
        )
        self.assertAllCalled()

    def test_041_run_root_exec(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = b"0\x001"
        self.app.expected_calls[
            (
                "test-vm",
                "admin.vm.feature.CheckWithTemplate",
                "supported-rpc.qubes.VMRootExec",
                None,
            )
        ] = b"0\x001"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "-u", "root", "test-vm", "command", "arg"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMRootExec+command+arg",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": None,
                    },
                ),
                ("test-vm", "qubes.VMRootExec+command+arg", b""),
            ],
        )
        self.assertAllCalled()

    def test_041_run_root_exec_not_supported(self):
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00test-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("test-vm", "admin.vm.feature.CheckWithTemplate", "vmexec", None)
        ] = b"0\x001"
        self.app.expected_calls[
            (
                "test-vm",
                "admin.vm.feature.CheckWithTemplate",
                "supported-rpc.qubes.VMRootExec",
                None,
            )
        ] = b"2\x00QubesFeatureNotFoundError\x00\x00Feature '...' not set\x00"
        self.app.expected_calls[
            ("test-vm", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        ret = qubesadmin.tools.qvm_run.main(
            ["--no-gui", "-u", "root", "test-vm", "command", "arg"],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.app.service_calls,
            [
                (
                    "test-vm",
                    "qubes.VMExec+command+arg",
                    {
                        "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL,
                        "user": "root",
                    },
                ),
                ("test-vm", "qubes.VMExec+command+arg", b""),
            ],
        )
        self.assertAllCalled()
