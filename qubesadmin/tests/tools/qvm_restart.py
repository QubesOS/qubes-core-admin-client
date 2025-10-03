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

import asyncio
import unittest.mock

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_restart


class TC_00_qvm_restart(qubesadmin.tests.QubesTestCase):
    @unittest.skipUnless(
        qubesadmin.tools.qvm_restart.have_events, "Events not present"
    )
    def test_000_restart_running(self):
        """Restarting just one already running qube"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_events = unittest.mock.AsyncMock()
        patch = unittest.mock.patch(
            "qubesadmin.events.EventsDispatcher._get_events_reader", mock_events
        )
        patch.start()
        self.addCleanup(patch.stop)
        mock_events.side_effect = qubesadmin.tests.tools.MockEventsReader(
            [
                b"1\0\0connection-established\0\0",
                b"1\0some-vm\0domain-shutdown\0\0",
            ]
        )

        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
        )
        self.app.expected_calls[
            ("some-vm", "admin.vm.Shutdown", "force", None)
        ] = b"0\x00"
        self.app.expected_calls[
            ("some-vm", "admin.vm.CurrentState", None, None)
        ] = (
            [b"0\x00power_state=Running"]
            + [b"0\x00power_state=Halted"]
            + [b"0\x00power_state=Halted"]
        )
        self.app.expected_calls[("some-vm", "admin.vm.Start", None, None)] = (
            b"0\x00"
        )
        qubesadmin.tools.qvm_restart.main(["some-vm"], app=self.app)
        self.assertAllCalled()

    @unittest.skipUnless(
        qubesadmin.tools.qvm_restart.have_events, "Events not present"
    )
    def test_001_restart_halted(self):
        """Trying restart on a already halted qube"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_events = unittest.mock.AsyncMock()
        patch = unittest.mock.patch(
            "qubesadmin.events.EventsDispatcher._get_events_reader", mock_events
        )
        patch.start()
        self.addCleanup(patch.stop)
        mock_events.side_effect = qubesadmin.tests.tools.MockEventsReader(
            [
                b"1\0\0connection-established\0\0",
                b"1\0some-vm\0domain-shutdown\0\0",
            ]
        )

        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Halted\n"
        )
        self.app.expected_calls[
            ("some-vm", "admin.vm.Shutdown", "force", None)
        ] = b"0\x00"
        self.app.expected_calls[
            ("some-vm", "admin.vm.CurrentState", None, None)
        ] = (
            [b"0\x00power_state=Halted"]
            + [b"0\x00power_state=Halted"]
            + [b"0\x00power_state=Halted"]
        )
        self.app.expected_calls[("some-vm", "admin.vm.Start", None, None)] = (
            b"0\x00"
        )
        qubesadmin.tools.qvm_restart.main(["some-vm"], app=self.app)
        self.assertAllCalled()

    @unittest.skipUnless(
        qubesadmin.tools.qvm_restart.have_events, "Events not present"
    )
    def test_002_restart_all(self):
        """Restarting all running qubes (and skipping unnamed DispVMs)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_events = unittest.mock.AsyncMock()
        patch = unittest.mock.patch(
            "qubesadmin.events.EventsDispatcher._get_events_reader", mock_events
        )
        patch.start()
        self.addCleanup(patch.stop)
        mock_events.side_effect = qubesadmin.tests.tools.MockEventsReader(
            [
                b"1\0\0connection-established\0\0",
                b"1\0some-vm\0domain-shutdown\0\0",
                b"1\0sys-usb\0domain-shutdown\0\0",
            ]
        )

        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
            b"dom0 class=AdminVM state=Running\n"
            b"sys-usb class=DispVM state=Running\n"
            b"disp007 class=DispVM state=Running\n"
            b"dormant-vm class=DispVM state=Halted\n"
        )
        self.app.expected_calls[
            ("sys-usb", "admin.vm.CurrentState", None, None)
        ] = [b"0\x00power_state=Running"]
        self.app.expected_calls[
            ("sys-usb", "admin.vm.property.Get", "auto_cleanup", None)
        ] = b"0\x00default=True type=bool False"
        self.app.expected_calls[
            ("disp007", "admin.vm.CurrentState", None, None)
        ] = [b"0\x00power_state=Running"]
        self.app.expected_calls[
            ("disp007", "admin.vm.property.Get", "auto_cleanup", None)
        ] = b"0\x00default=True type=bool True"
        self.app.expected_calls[
            ("dormant-vm", "admin.vm.CurrentState", None, None)
        ] = [b"0\x00power_state=Halted"]
        for vm in ["some-vm", "sys-usb"]:
            self.app.expected_calls[
                (vm, "admin.vm.Shutdown", "force", None)
            ] = b"0\x00"
            self.app.expected_calls[
                (vm, "admin.vm.CurrentState", None, None)
            ] = (
                [b"0\x00power_state=Running"]
                + [b"0\x00power_state=Running"]
                + [b"0\x00power_state=Halted"]
                + [b"0\x00power_state=Halted"]
            )
            self.app.expected_calls[(vm, "admin.vm.Start", None, None)] = (
                b"0\x00"
            )
        qubesadmin.tools.qvm_restart.main(["--all"], app=self.app)
        self.assertAllCalled()

    def test_003_restart_dispvm(self):
        """Trying to restart a unnamed DispVM"""
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00some-vm class=AppVM state=Running\n"
            b"dom0 class=AdminVM state=Running\n"
            b"sys-usb class=DispVM state=Running\n"
            b"disp007 class=DispVM state=Running\n"
            b"dormant-vm class=DispVM state=Halted\n"
        )
        self.app.expected_calls[
            ("disp007", "admin.vm.property.Get", "auto_cleanup", None)
        ] = b"0\x00default=True type=bool True"
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_restart.main(["disp007"], app=self.app)
        self.assertAllCalled()
