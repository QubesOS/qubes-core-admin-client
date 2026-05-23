# -*- encoding: utf-8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2025 Marek Marczykowski-Górecki
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
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_restart


class TC_00_qvm_restart(qubesadmin.tests.QubesTestCase):
    def test_000_restart_running(self):
        """Restarting just one already running qube"""
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[("some-vm","admin.vm.CurrentState",None,None)] = (
            b"0\x00some-vm mem=42069 mem_static_max=42069 cputime=1337 power_state=Running\n"
        )
        self.app.expected_calls[
            ("some-vm", "admin.vm.Shutdown", "wait", None)
        ] = b"0\x00"
        self.app.expected_calls[("some-vm", "admin.vm.Start", None, None)] = (
            b"0\x00"
        )
        qubesadmin.tools.qvm_restart.main(["some-vm"], app=self.app)
        self.assertAllCalled()

    def test_001_restart_halted(self):
        """Trying to restart a halted qube"""
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Halted\n"
        )
        self.app.expected_calls[("some-vm", "admin.vm.CurrentState", None, None)] = (
            b"0\x00some-vm mem=42069 mem_static_max=42069 cputime=0 power_state=Halted\n"
        )
        qubesadmin.tools.qvm_restart.main(["some-vm"], app=self.app)
        self.assertAllCalled()

    def test_002_restart_halted_startopt(self):
        """Trying to restart a halted qube with `--start` option"""
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Halted\n"
        )
        self.app.expected_calls[("some-vm", "admin.vm.Shutdown", "wait", None)] = (
            b"0\x00"
        )
        self.app.expected_calls[("some-vm", "admin.vm.Start", None, None)] = (
            b"0\x00"
        )
        qubesadmin.tools.qvm_restart.main(["--start", "some-vm"], app=self.app)
        self.assertAllCalled()

    def test_003_restart_all(self):
        """Restarting all running qubes (and skipping unnamed DispVMs)"""
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
            b"dom0 class=AdminVM state=Running\n"
            b"sys-usb class=DispVM state=Running\n"
            b"disp007 class=DispVM state=Running\n"
            b"dormant-vm class=DispVM state=Halted\n"
        )
        self.app.expected_calls[
            ("sys-usb", "admin.vm.property.Get", "auto_cleanup", None)
        ] = b"0\x00default=True type=bool True"
        self.app.expected_calls[
            ("disp007", "admin.vm.property.Get", "auto_cleanup", None)
        ] = b"0\x00default=True type=bool True"
        self.app.expected_calls[
            ("dormant-vm", "admin.vm.property.Get", "auto_cleanup", None)
        ] = b"0\x00default=True type=bool False"
        self.app.expected_calls[("some-vm", "admin.vm.CurrentState", None, None)] = (
            b"0\x00some-vm mem=42069 mem_static_max=42069 cputime=1337 power_state=Running\n"
        )
        self.app.expected_calls[("dormant-vm", "admin.vm.CurrentState", None, None)] = (
            b"0\x00dormant-vm mem=0 mem_static_max=42069 cputime=0 power_state=Halted\n"
        )
        self.app.expected_calls[
            ("some-vm", "admin.vm.Shutdown", "force+wait", None)
        ] = b"0\x00"
        self.app.expected_calls[
            ("some-vm", "admin.vm.Start", None, None)
        ] = b"0\x00"
        # sys-usb should not be restarted because it's a DispVM with auto_cleanup=False
        qubesadmin.tools.qvm_restart.main(["--all"], app=self.app)
        self.assertAllCalled()

    def test_004_restart_all_start(self):
        """Restarting all running qubes (and skipping unnamed DispVMs)
        with `--start` argument
        """
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
            b"dom0 class=AdminVM state=Running\n"
            b"sys-usb class=DispVM state=Running\n"
            b"disp007 class=DispVM state=Running\n"
            b"dormant-vm class=DispVM state=Halted\n"
        )
        self.app.expected_calls[
            ("sys-usb", "admin.vm.property.Get", "auto_cleanup", None)
        ] = b"0\x00default=True type=bool True"
        self.app.expected_calls[
            ("disp007", "admin.vm.property.Get", "auto_cleanup", None)
        ] = b"0\x00default=True type=bool True"
        self.app.expected_calls[
            ("dormant-vm", "admin.vm.property.Get", "auto_cleanup", None)
        ] = b"0\x00default=True type=bool False"
        self.app.expected_calls[
            ("some-vm", "admin.vm.Shutdown", "force+wait", None)
        ] = b"0\x00"
        self.app.expected_calls[
            ("some-vm", "admin.vm.Start", None, None)
        ] = b"0\x00"
        self.app.expected_calls[
            ("dormant-vm", "admin.vm.Shutdown", "force+wait", None)
        ] = b"0\x00"
        self.app.expected_calls[
            ("dormant-vm", "admin.vm.Start", None, None)
        ] = b"0\x00"
        # sys-usb should not be restarted because it's a DispVM with auto_cleanup=False
        qubesadmin.tools.qvm_restart.main(["--all","--start"], app=self.app)
        self.assertAllCalled()

    def test_005_restart_dispvm(self):
        """Trying to restart a unnamed DispVM"""
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
            b"dom0 class=AdminVM state=Running\n"
            b"disp007 class=DispVM state=Running\n"
        )
        self.app.expected_calls[
            ("disp007", "admin.vm.property.Get", "auto_cleanup", None)
        ] = b"0\x00default=True type=bool True"
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_restart.main(["disp007"], app=self.app)
        self.assertAllCalled()

    def test_006_restart_force(self):
        """Restart with --force flag"""
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[("some-vm", "admin.vm.CurrentState", None, None)] = (
            b"0\x00some-vm mem=42069 mem_static_max=42069 cputime=1337 power_state=Running\n"
        )
        self.app.expected_calls[
            ("some-vm", "admin.vm.Shutdown", "force+wait", None)
        ] = b"0\x00"
        self.app.expected_calls[("some-vm", "admin.vm.Start", None, None)] = (
            b"0\x00"
        )
        qubesadmin.tools.qvm_restart.main(["--force", "some-vm"], app=self.app)
        self.assertAllCalled()
