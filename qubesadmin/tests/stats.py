# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2026 hippalectryon
#                    <6502864+hippalectryon-0@users.noreply.github.com>
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

# pylint: disable=missing-docstring,protected-access

import unittest.mock

import qubesadmin.events
import qubesadmin.tests
from qubesadmin.stats import MemoryTotals, StatsMonitor, compute_stats


def stats_kwargs(assigned=1024000, used=409600, swap=102400, **kwargs):
    """Arguments of a vm-stats event, as strings like qubesd sends them"""
    data = {
        "memory_kb": str(assigned),
        "memory_assigned_total": str(assigned + 1024),
        "memory_assigned_usable": str(assigned),
        "memory_with_swap_used": str(used),
        "swap_used": str(swap),
        "cpu_time": "5000000",
        "cpu_usage": "3",
        "online_vcpus": "2",
    }
    data.update(kwargs)
    return data


class TC_00_ComputeStats(qubesadmin.tests.QubesTestCase):
    def test_000_derived(self):
        """Memory used without swap, percentages and CPU totals."""
        data = compute_stats(
            4096000,
            **stats_kwargs(
                cpu_time_internal="1000000",
                cpu_usage_internal="1.5",
                online_vcpus_internal="1",
            ),
        )
        self.assertEqual(data["memory_assigned_total"], 1025024)
        self.assertEqual(data["memory_used_total"], 409600)
        self.assertEqual(data["memory_used_noswap"], 307200)
        self.assertEqual(data["swap_used"], 102400)
        self.assertEqual(data["memory_usage_assigned"], 25.0)
        self.assertEqual(data["memory_usage_used"], 30.0)
        self.assertEqual(data["memory_usage_swap_over_used"], 33.3)
        self.assertEqual(data["cpu_time"], 5000)
        self.assertEqual(data["cpu_time_total"], 6000)
        self.assertEqual(data["cpu_usage_internal"], 1.5)
        self.assertEqual(data["online_vcpus_total"], 3)

    def test_001_missing(self):
        """Values not sent or without maxmem are None."""
        kwargs = stats_kwargs()
        del kwargs["swap_used"]
        data = compute_stats(None, **kwargs)
        self.assertIsNone(data["memory_used_noswap"])
        self.assertIsNone(data["memory_usage_used"])
        self.assertIsNone(data["memory_usage_swap_over_used"])
        self.assertIsNone(data["memory_usage_assigned"])
        self.assertIsNone(data["cpu_time_internal"])
        self.assertEqual(data["cpu_time_total"], 5000)
        self.assertEqual(data["online_vcpus_total"], 2)


class TC_10_StatsMonitor(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00dom0 class=AdminVM state=Running\n"
            b"sys-net class=AppVM state=Running\n"
            b"untrusted class=AppVM state=Running\n"
        )
        for name in ("sys-net", "untrusted"):
            self.app.expected_calls[
                (name, "admin.vm.property.Get", "maxmem", None)
            ] = b"0\x00default=False type=int 4000"
        self.app.expected_calls[
            ("dom0", "admin.vm.property.Get", "maxmem", None)
        ] = b"2\x00QubesNoSuchPropertyError\x00\x00Invalid property\x00"
        self.app.domains.refresh_cache()
        self.dispatcher = qubesadmin.events.EventsDispatcher(
            self.app, enable_cache=False
        )
        self.stats_dispatcher = qubesadmin.events.EventsDispatcher(
            self.app, api_method="admin.vm.Stats", enable_cache=False
        )
        self.now = 1000.0
        self.monitor = StatsMonitor(
            self.app,
            self.dispatcher,
            self.stats_dispatcher,
            history_seconds=600,
            clock=lambda: self.now,
        )
        self.listener = unittest.mock.Mock()
        self.monitor.listeners.append(self.listener)
        self.monitor.register_events()

    def send_stats(self, name, **kwargs):
        self.stats_dispatcher.handle(name, "vm-stats", **stats_kwargs(**kwargs))

    def test_000_totals(self):
        """Latest stats of each qube are summed, dom0 included."""
        self.send_stats("dom0", assigned=4096000, memory_available="2048000")
        self.send_stats("untrusted", assigned=1024000)
        self.send_stats("untrusted", assigned=2048000)
        self.assertEqual(
            self.monitor.totals(),
            MemoryTotals(
                assigned=4097024 + 2049024,
                used=2 * 307200,
                available=2048000,
            ),
        )
        self.assertEqual(self.listener.call_count, 3)
        self.listener.assert_called_with(
            "untrusted", self.monitor.stats["untrusted"]
        )
        self.assertEqual(
            self.monitor.stats["untrusted"]["memory_usage_assigned"], 50.0
        )

    def test_001_no_memory_available(self):
        """Without memory_available from dom0 (older dom0) it is None."""
        self.send_stats("dom0")
        self.assertIsNone(self.monitor.totals().available)

    def test_002_memory_available_cleared(self):
        """memory_available is cleared when dom0 omits it, or on reconnect."""
        self.send_stats("dom0", memory_available="2048000")
        self.send_stats("dom0")
        self.assertIsNone(self.monitor.memory_available)
        self.send_stats("dom0", memory_available="2048000")
        self.app.expected_calls[
            ("dom0", "admin.vm.CurrentState", None, None)
        ] = b"0\x00power_state=Running"
        for name in ("sys-net", "untrusted"):
            self.app.expected_calls[
                (name, "admin.vm.CurrentState", None, None)
            ] = b"0\x00power_state=Running"
        self.dispatcher.handle(None, "connection-established")
        self.assertIsNone(self.monitor.memory_available)

    def test_003_used_without_swap(self):
        """Qubes that don't report swap count their used memory with swap."""
        self.send_stats("untrusted", used=409600, swap=102400)
        kwargs = stats_kwargs(assigned=2048000, used=2048000)
        del kwargs["swap_used"]
        self.stats_dispatcher.handle("sys-net", "vm-stats", **kwargs)
        self.assertEqual(self.monitor.totals().used, 307200 + 2048000)

    def test_004_old_dom0_ignored(self):
        """Stats without memory_assigned_total are ignored."""
        self.stats_dispatcher.handle(
            "untrusted", "vm-stats", memory_kb="4096", cpu_usage="1"
        )
        self.assertEqual(self.monitor.stats, {})
        self.listener.assert_not_called()

    def test_010_stopped_dropped(self):
        """domain-stopped drops stats and ignores late ones until start."""
        self.send_stats("untrusted")
        self.dispatcher.handle("untrusted", "domain-stopped")
        self.assertNotIn("untrusted", self.monitor.stats)
        self.listener.assert_called_with("untrusted", None)
        self.send_stats("untrusted")
        self.dispatcher.handle("untrusted", "domain-shutdown")
        self.send_stats("untrusted")
        self.assertNotIn("untrusted", self.monitor.stats)
        self.dispatcher.handle("untrusted", "domain-pre-start")
        self.send_stats("untrusted")
        self.assertIn("untrusted", self.monitor.stats)

    def test_011_deleted_dropped(self):
        """domain-delete drops stats and ignores late ones."""
        self.send_stats("untrusted")
        self.dispatcher.handle(None, "domain-delete", vm="untrusted")
        self.send_stats("untrusted")
        self.assertEqual(self.monitor.stats, {})

    def test_012_start_failed_dropped(self):
        """domain-start-failed drops stats sent while starting."""
        self.dispatcher.handle("untrusted", "domain-pre-start")
        self.send_stats("untrusted")
        self.dispatcher.handle("untrusted", "domain-start-failed")
        self.assertEqual(self.monitor.stats, {})

    def test_020_maxmem_change(self):
        """A new maxmem recomputes the assigned percentage."""
        self.send_stats("untrusted", assigned=1022976)
        self.listener.reset_mock()
        self.dispatcher.handle(
            "untrusted",
            "property-set:maxmem",
            name="maxmem",
            newvalue="2000",
            oldvalue="4000",
        )
        self.assertEqual(
            self.monitor.stats["untrusted"]["memory_usage_assigned"], 50.0
        )
        self.listener.assert_called_once_with(
            "untrusted", self.monitor.stats["untrusted"]
        )

    def test_030_host_memory(self):
        """Global maxmem in MiB is fetched once and given in KiB."""
        self.app.expected_calls[
            ("dom0", "admin.property.Get", "maxmem", None)
        ] = [b"0\x00default=False type=int 16000"]
        self.assertEqual(self.monitor.host_memory_max, 16000 * 1024)
        self.assertEqual(self.monitor.host_memory_max, 16000 * 1024)
        self.assertEqual(
            self.app.expected_calls[
                ("dom0", "admin.property.Get", "maxmem", None)
            ],
            [],
        )

    def test_031_host_memory_denied(self):
        """Global maxmem denied by policy is None and not asked again."""
        self.app.expected_calls[
            ("dom0", "admin.property.Get", "maxmem", None)
        ] = [b"2\x00QubesDaemonAccessError\x00\x00denied\x00"]
        self.assertIsNone(self.monitor.host_memory_max)
        self.assertIsNone(self.monitor.host_memory_max)

    def test_032_host_memory_retried(self):
        """Global maxmem is asked again after reconnecting to qubesd."""
        self.app.expected_calls[
            ("dom0", "admin.property.Get", "maxmem", None)
        ] = [
            b"2\x00QubesDaemonCommunicationError\x00\x00error\x00",
            b"0\x00default=False type=int 16000",
        ]
        self.assertIsNone(self.monitor.host_memory_max)
        self.assertIsNone(self.monitor.host_memory_max)
        for name in ("dom0", "sys-net", "untrusted"):
            self.app.expected_calls[
                (name, "admin.vm.CurrentState", None, None)
            ] = b"0\x00power_state=Running"
        self.dispatcher.handle(None, "connection-established")
        self.assertEqual(self.monitor.host_memory_max, 16000 * 1024)

    def test_033_host_cpus(self):
        """Global no_cpus is given as is, and 0 as None."""
        self.app.expected_calls[
            ("dom0", "admin.property.Get", "no_cpus", None)
        ] = [b"0\x00default=False type=int 0"]
        self.assertIsNone(self.monitor.host_cpus)

    def test_040_history(self):
        """History merges stats of one round and keeps the last minutes."""
        self.send_stats("dom0", assigned=4096000)
        self.now += 0.5
        self.send_stats("untrusted", assigned=1024000)
        self.assertEqual(len(self.monitor.history), 1)
        self.assertEqual(self.monitor.history[0][0], 1000.0)
        self.assertEqual(self.monitor.history[0][1].assigned, 4097024 + 1025024)
        for _ in range(4):
            self.now += 300
            self.send_stats("untrusted")
        # one point older than 600 s is kept for the left edge of a graph
        self.assertEqual(
            [point[0] for point in self.monitor.history],
            [1300.5, 1600.5, 1900.5, 2200.5],
        )

    def test_041_history_on_drop(self):
        """Dropping stats of a stopped qube adds a history point."""
        self.send_stats("untrusted")
        self.now += 3
        self.dispatcher.handle("untrusted", "domain-stopped")
        self.assertEqual(self.monitor.history[-1][1].assigned, 0)

    def test_050_reconnect(self):
        """On reconnection, removed and halted qubes are dropped."""
        self.send_stats("sys-net")
        self.send_stats("untrusted")
        self.dispatcher.handle("untrusted", "domain-stopped")
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00dom0 class=AdminVM state=Running\n"
            b"untrusted class=AppVM state=Running\n"
        )
        for name in ("dom0", "untrusted"):
            self.app.expected_calls[
                (name, "admin.vm.CurrentState", None, None)
            ] = b"0\x00power_state=Running"
        self.dispatcher.handle(None, "connection-established")
        self.assertEqual(self.monitor.stats, {})
        self.send_stats("untrusted")
        self.assertIn("untrusted", self.monitor.stats)

    def test_060_unregister(self):
        """Unregistered monitor ignores events."""
        self.monitor.unregister_events()
        self.send_stats("untrusted")
        self.assertEqual(self.monitor.stats, {})
