#
# SPDX-FileCopyrightText: 2025 - 2026 Benjamin Grande <ben.grande.b@gmail.com>
#
# SPDX-License-Identifier: GPL-2.0-only

"""
Statistics of qubes from ``vm-stats`` events, for clients that show them.

Memory is always in KiB, to avoid rounding errors when clients calculate
with it. Values that are not known are ``None``.
"""

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from qubesadmin.app import QubesBase
from qubesadmin.events import EventsDispatcher
from qubesadmin.exc import QubesException
from qubesadmin.vm import QubesVM

#: stats of all qubes come at the same time, keep one history point for them
HISTORY_MERGE_SECONDS = 1

StatsData = dict[str, int | float | None]
Listener = Callable[[str, StatsData | None], None]


def boottime_clock() -> float:
    """
    Seconds since boot, including time spent in suspend.
    """
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def memory_usage_assigned(
    memory_assigned_total: int | None, memory_max: int | None
) -> float | None:
    """
    Percentage of the assigned memory compared to the maximum the qube can
    have assigned.
    """
    if memory_assigned_total is None or memory_max is None or memory_max <= 0:
        return None
    return round(float(memory_assigned_total / memory_max) * 100, 1)


def compute_stats(memory_max: int | None, **kwargs: str) -> StatsData:
    """
    Values derived from the arguments of a ``vm-stats`` event, given the
    qube's ``maxmem`` in KiB.

    Keys: ``memory_assigned_total``, ``memory_assigned_usable``,
    ``memory_used_total`` (with swap), ``memory_used_noswap``, ``swap_used``,
    ``memory_usage_assigned``, ``memory_usage_used``,
    ``memory_usage_swap_over_used`` (percentages), ``cpu_time`` (seconds),
    ``cpu_usage``, ``online_vcpus``, their ``_internal`` variants (stubdomain)
    and ``cpu_time_total``, ``online_vcpus_total``.
    """
    # pylint: disable=too-many-locals
    memory_assigned_total = int(kwargs["memory_assigned_total"])
    memory_assigned_usable = int(kwargs["memory_assigned_usable"])
    memory_with_swap_used = int(kwargs["memory_with_swap_used"])
    memory_used_total = memory_with_swap_used
    swap_used = kwargs.get("swap_used")
    memory_used_noswap: int | None
    if swap_used:
        swap_used = int(swap_used)
        memory_used_noswap = memory_with_swap_used - swap_used
    else:
        swap_used = None
        memory_used_noswap = None

    memory_usage_used: float | None
    if memory_assigned_usable > 0:
        if memory_used_noswap is not None:
            memory_usage_used = round(
                float(memory_used_noswap / memory_assigned_usable) * 100, 1
            )
        else:
            memory_usage_used = None
    else:
        memory_usage_used = 0.0
    memory_usage_swap_over_used: float | None
    if memory_used_noswap is None or swap_used is None:
        memory_usage_swap_over_used = None
    elif memory_used_noswap > 0:
        memory_usage_swap_over_used = round(
            float(swap_used / memory_used_noswap) * 100, 1
        )
    else:
        memory_usage_swap_over_used = 0.0

    cpu_time = int(kwargs["cpu_time"]) // 10**3
    cpu_time_internal = kwargs.get("cpu_time_internal")
    if cpu_time_internal is None:
        cpu_time_total = cpu_time
    else:
        cpu_time_internal = int(cpu_time_internal) // 10**3
        cpu_time_total = cpu_time + cpu_time_internal

    cpu_usage = int(kwargs["cpu_usage"])
    cpu_usage_internal = kwargs.get("cpu_usage_internal")
    if cpu_usage_internal is not None:
        cpu_usage_internal = float(cpu_usage_internal)

    online_vcpus = int(kwargs["online_vcpus"])
    online_vcpus_internal = kwargs.get("online_vcpus_internal")
    if online_vcpus_internal is None:
        online_vcpus_total = online_vcpus
    else:
        online_vcpus_internal = int(online_vcpus_internal)
        online_vcpus_total = online_vcpus + online_vcpus_internal

    return {
        "memory_assigned_total": memory_assigned_total,
        "memory_assigned_usable": memory_assigned_usable,
        "memory_used_total": memory_used_total,
        "memory_used_noswap": memory_used_noswap,
        "swap_used": swap_used,
        "memory_usage_used": memory_usage_used,
        "memory_usage_assigned": memory_usage_assigned(
            memory_assigned_total, memory_max
        ),
        "memory_usage_swap_over_used": memory_usage_swap_over_used,
        "cpu_time": cpu_time,
        "cpu_usage": cpu_usage,
        "online_vcpus": online_vcpus,
        "cpu_time_internal": cpu_time_internal,
        "cpu_usage_internal": cpu_usage_internal,
        "online_vcpus_internal": online_vcpus_internal,
        "cpu_time_total": cpu_time_total,
        "online_vcpus_total": online_vcpus_total,
    }


@dataclass(frozen=True)
class MemoryTotals:
    """
    Memory of all qubes that have stats, in KiB.
    """

    #: sum of ``memory_assigned_total``
    assigned: int
    #: sum of ``memory_used_noswap``, or ``memory_used_total`` for qubes
    #: that don't report swap (which is the assigned memory for qubes that
    #: report nothing, like ones without memory balancing)
    used: int
    #: free memory as computed by qmemman, sent by dom0 (``None`` if older)
    available: int | None


class StatsMonitor:
    """
    Latest stats of each running qube, from ``vm-stats`` events.

    Stats of a qube are dropped when it stops, and its late stats are ignored
    until it starts again: qmemman gives its memory to other qubes at
    ``domain-stopped``, so keeping them would count that memory twice.

    *listeners* are called with the qube name and its new stats, or ``None``
    when they are dropped. They are called once per qube for each stats
    round, so a GUI redrawing totals should debounce (e.g. with
    ``GLib.idle_add``).

    Both dispatchers must be running: stats are only dropped on the qube
    lifecycle events of *dispatcher*.
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        app: QubesBase,
        dispatcher: EventsDispatcher,
        stats_dispatcher: EventsDispatcher,
        history_seconds: float = 0,
        clock: Callable[[], float] = boottime_clock,
    ) -> None:
        # pylint: disable=too-many-positional-arguments
        self.app = app
        self.dispatcher = dispatcher
        self.stats_dispatcher = stats_dispatcher
        #: latest stats by qube name
        self.stats: dict[str, StatsData] = {}
        #: latest ``memory_available`` of dom0
        self.memory_available: int | None = None
        #: seconds of history to keep, 0 disables it
        self.history_seconds = history_seconds
        #: ``(clock(), MemoryTotals)``, oldest first
        self.history: deque[tuple[float, MemoryTotals]] = deque()
        self.clock = clock
        self.listeners: list[Listener] = []
        self._memory_max: dict[str, int | None] = {}
        self._stopped: set[str] = set()
        self._global_properties: dict[str, int | None] = {}

    def _handlers(self) -> list[tuple[EventsDispatcher, str, Callable]]:
        """
        Event handlers, with their dispatcher.
        """
        return [
            (self.stats_dispatcher, "vm-stats", self.on_vm_stats),
            (self.dispatcher, "domain-pre-start", self.on_domain_start),
            (self.dispatcher, "domain-start", self.on_domain_start),
            (self.dispatcher, "domain-start-failed", self.on_domain_stopped),
            (self.dispatcher, "domain-stopped", self.on_domain_stopped),
            (self.dispatcher, "domain-shutdown", self.on_domain_stopped),
            (self.dispatcher, "domain-delete", self.on_domain_delete),
            (self.dispatcher, "property-set:maxmem", self.on_maxmem_change),
            (self.dispatcher, "property-reset:maxmem", self.on_maxmem_change),
            (
                self.dispatcher,
                "connection-established",
                self.on_connection_established,
            ),
        ]

    def register_events(self) -> None:
        """
        Add event handlers to the dispatchers.
        """
        for dispatcher, event, handler in self._handlers():
            dispatcher.add_handler(event, handler)

    def unregister_events(self) -> None:
        """
        Remove event handlers from the dispatchers.
        """
        for dispatcher, event, handler in self._handlers():
            dispatcher.remove_handler(event, handler)

    @staticmethod
    def _cached_int(
        cache: dict[str, int | None],
        key: str,
        getter: Callable[[], Any],
        scale: int = 1,
    ) -> int | None:
        """
        ``getter()`` as int times *scale*, ``None`` if missing, denied or on
        a qubesd error. Cached until the next ``connection-established``.
        """
        if key not in cache:
            try:
                value: int | None = int(getter()) * scale
            except (AttributeError, TypeError, ValueError, QubesException):
                value = None
            cache[key] = value
        return cache[key]

    def _global_property(self, name: str) -> int | None:
        """
        Global property as int.
        """
        return self._cached_int(
            self._global_properties, name, lambda: getattr(self.app, name)
        )

    @property
    def host_memory_max(self) -> int | None:
        """
        Total host memory in KiB, ``None`` if not available (older dom0 or
        denied by policy).
        """
        maxmem = self._global_property("maxmem")
        if maxmem is None or maxmem <= 0:
            return None
        return maxmem * 1024

    @property
    def host_cpus(self) -> int | None:
        """
        Number of host CPUs, ``None`` if not available.
        """
        no_cpus = self._global_property("no_cpus")
        if no_cpus is None or no_cpus <= 0:
            return None
        return no_cpus

    def _get_memory_max(self, vm: QubesVM) -> int | None:
        """
        The qube's ``maxmem`` in KiB.
        """
        return self._cached_int(
            self._memory_max, str(vm), lambda: vm.maxmem, 1024
        )

    def totals(self) -> MemoryTotals:
        """
        Memory of all qubes that have stats.
        """
        return MemoryTotals(
            assigned=sum(
                int(data["memory_assigned_total"] or 0)
                for data in self.stats.values()
            ),
            used=sum(
                int(
                    data["memory_used_noswap"]
                    if data["memory_used_noswap"] is not None
                    else data["memory_used_total"] or 0
                )
                for data in self.stats.values()
            ),
            available=self.memory_available,
        )

    def _trim_history(self, now: float) -> None:
        """
        Drop history older than *history_seconds*, but one point, so a graph
        can start at its left edge.
        """
        while (
            len(self.history) > 1
            and now - self.history[1][0] > self.history_seconds
        ):
            self.history.popleft()

    def _record_history(self) -> None:
        """
        Add the current totals to the history.
        """
        if not self.history_seconds:
            return
        now = self.clock()
        totals = self.totals()
        if self.history and now - self.history[-1][0] < HISTORY_MERGE_SECONDS:
            self.history[-1] = (self.history[-1][0], totals)
        else:
            self.history.append((now, totals))
        self._trim_history(now)

    def _notify(self, name: str, data: StatsData | None) -> None:
        """
        Call the listeners.
        """
        for listener in self.listeners:
            listener(name, data)

    def _forget(self, name: str) -> None:
        """
        Drop stats of a stopped qube and ignore its late ones.
        """
        self._stopped.add(name)
        if self.stats.pop(name, None) is not None:
            self._record_history()
            self._notify(name, None)

    def on_vm_stats(self, vm: QubesVM, _event: str, **kwargs: str) -> None:
        """
        Handle ``vm-stats``. Stats without ``memory_assigned_total`` (older
        dom0) are ignored.
        """
        name = str(vm)
        if name in self._stopped or "memory_assigned_total" not in kwargs:
            return
        if name == "dom0":
            available = kwargs.get("memory_available")
            self.memory_available = (
                None if available is None else int(available)
            )
        data = compute_stats(self._get_memory_max(vm), **kwargs)
        self.stats[name] = data
        self._record_history()
        self._notify(name, data)

    def on_domain_start(self, vm: QubesVM, _event: str, **_kwargs) -> None:
        """
        Handle ``domain-pre-start`` and ``domain-start``.
        """
        self._stopped.discard(str(vm))

    def on_domain_stopped(self, vm: QubesVM, _event: str, **_kwargs) -> None:
        """
        Handle ``domain-stopped``, ``domain-shutdown`` and
        ``domain-start-failed``.
        """
        self._forget(str(vm))

    def on_domain_delete(
        self, _subject: None, _event: str, vm: str, **_kwargs
    ) -> None:
        """
        Handle ``domain-delete``.
        """
        self._memory_max.pop(str(vm), None)
        self._forget(str(vm))

    def on_maxmem_change(
        self, vm: QubesVM, event: str, newvalue: str | None = None, **_kwargs
    ) -> None:
        """
        Handle ``property-set:maxmem`` and ``property-reset:maxmem``.
        """
        name = str(vm)
        if event.startswith("property-reset:") or newvalue is None:
            self._memory_max.pop(name, None)
            return
        memory_max = int(newvalue) * 1024
        self._memory_max[name] = memory_max
        if (data := self.stats.get(name)) is None:
            return
        data["memory_usage_assigned"] = memory_usage_assigned(
            data["memory_assigned_total"], memory_max  # type: ignore[arg-type]
        )
        self._notify(name, data)

    def on_connection_established(
        self, _subject: None, _event: str, **_kwargs
    ) -> None:
        """
        Handle ``connection-established``: events may have been missed, so
        check which qubes still exist and run.
        """
        self._memory_max.clear()
        self._global_properties.clear()
        self.memory_available = None
        for name in list(self.stats):
            if name not in self.app.domains:
                self._forget(name)
        for vm in self.app.domains:
            try:
                halted = vm.get_power_state() == "Halted"
            except QubesException:
                halted = True
            if halted:
                self._forget(str(vm))
            else:
                self._stopped.discard(str(vm))
