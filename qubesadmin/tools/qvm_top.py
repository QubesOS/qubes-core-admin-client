#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2025 - 2026 Benjamin Grande <ben.grande.b@gmail.com>
#
# SPDX-License-Identifier: GPL-2.0-only

"""
Top-like info for Qubes.

Visuals from htop and xentop.
"""

import curses

from argparse import Action, SUPPRESS, ArgumentTypeError
from asyncio import (
    CancelledError,
    create_subprocess_exec,
    create_task,
    ensure_future,
    gather,
    run,
    sleep,
    to_thread,
)
from asyncio.subprocess import PIPE, STDOUT, DEVNULL
from asyncio.subprocess import subprocess as async_subprocess
from collections import Counter
from curses.ascii import (
    ESC,
    STX,
    NAK,
    EOT,
    ACK,
    SOH,
    ENQ,
    DLE,
    SO,
    FF,
    SP,
    CR,
)
from importlib.metadata import metadata
from logging import getLogger, Formatter, Logger, DEBUG, INFO
from logging.handlers import SysLogHandler
from os import environ
from sys import stderr, exc_info, exit as sys_exit
from time import strftime
from textwrap import TextWrapper
from traceback import print_exception
from typing import TypedDict, NotRequired, Callable, Awaitable, Any

from qubesadmin.app import QubesBase
from qubesadmin.events import EventsDispatcher
from qubesadmin.events import POWER_EVENTS
from qubesadmin.exc import (
    QubesPropertyAccessError,
    QubesVMNotFoundError,
)
from qubesadmin.label import Label
from qubesadmin.tools import QubesArgumentParser
from qubesadmin.utils import start, pause, unpause, shutdown, kill
from qubesadmin.vm import QubesVM, POWER_STATES


class ActionEntry(TypedDict):
    # pylint: disable=missing-class-docstring
    identity: int
    action: Callable[[list[QubesVM]], Awaitable[object]]
    on_state: list[str]
    when: NotRequired[list[str]]


def log_failures(qubes, results) -> None:
    """
    Filter results for failures and log them.
    """
    failed: dict[QubesVM, BaseException] = {}
    for qube, res in zip(qubes, results):
        if not isinstance(res, BaseException):
            continue
        failed[qube] = res
    for qube, exc in failed.items():
        qube.log.exception(exc, exc_info=exc)


async def exec_and_check(*args):
    """
    Execute subprocess asynchronously and check for its result.
    """
    proc = await create_subprocess_exec(
        *args,
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=STDOUT,
    )
    outerr, _ = await proc.communicate()
    if proc.returncode != 0:
        raise async_subprocess.CalledProcessError(
            returncode=proc.returncode, cmd=[*args], output=outerr
        )


async def console(qubes: list[QubesVM]) -> None:
    """
    Get debug console for provided qubes.
    """
    tasks = [
        exec_and_check("qvm-console-dispvm", "--autostart", qube.name)
        for qube in qubes
    ]
    results = await gather(*tasks, return_exceptions=True)
    log_failures(qubes, results)


async def terminal(qubes: list[QubesVM], user: str | None = None) -> None:
    """
    Get GUI terminal for provided qubes.
    """
    tasks = [
        to_thread(
            qube.run_service_for_stdio,
            "qubes.StartApp+qubes-run-terminal",
            user=user,
        )
        for qube in qubes
    ]
    results = await gather(*tasks, return_exceptions=True)
    log_failures(qubes, results)


async def action_wrapper(
    qubes: list[QubesVM], action: Callable, **kwargs
) -> None:
    """
    Run action from utils and log failures.
    """
    results = await action(domains=qubes, **kwargs)
    log_failures(qubes, results)


ACTIONS: dict[str, ActionEntry] = {
    "Run terminal": {
        "identity": 0,
        "action": lambda qubes: terminal(qubes=qubes),
        "on_state": ["Halted", "Running"],
        "when": ["can_gui"],
    },
    "Run root terminal": {
        "identity": 1,
        "action": lambda qubes: terminal(qubes=qubes, user="root"),
        "on_state": ["Halted", "Running"],
        "when": ["can_gui"],
    },
    "Debug console": {
        "identity": 2,
        "action": lambda qubes: console(qubes=qubes),
        "on_state": ["Halted", "Running"],
        "when": ["can_console"],
    },
    "Start": {
        "identity": 3,
        "action": lambda qubes: action_wrapper(qubes=qubes, action=start),
        "on_state": ["Halted"],
    },
    "Pause": {
        "identity": 4,
        "action": lambda qubes: action_wrapper(qubes=qubes, action=pause),
        "on_state": ["Running"],
    },
    "Unpause": {
        "identity": 5,
        "action": lambda qubes: action_wrapper(qubes=qubes, action=unpause),
        "on_state": ["Paused"],
    },
    "Shutdown": {
        "identity": 6,
        "action": lambda qubes: action_wrapper(
            qubes=qubes, action=shutdown, wait=True
        ),
        "on_state": ["Transient", "Running"],
    },
    "Force shutdown": {
        "identity": 7,
        "action": lambda qubes: action_wrapper(
            qubes=qubes, action=shutdown, force=True, wait=True
        ),
        "on_state": ["Transient", "Running"],
    },
    # "Restart": {
    #    "identity": 8,
    #    "action": lambda qubes: action_wrapper(qubes=qubes, action=restart),
    #    "on_state": ["Transient", "Running", "Paused", "Halting"],
    #    "when": ["can_restart"],
    # },
    "Kill": {
        "identity": 9,
        "action": lambda qubes: action_wrapper(qubes=qubes, action=kill),
        "on_state": ["Transient", "Running", "Paused", "Halting"],
    },
}
ACTION_NUMBERS: list[int] = [action["identity"] for action in ACTIONS.values()]
ACTION_WIDTH = max(len(action) for action in ACTIONS)
ACTION_NUMBER_WIDTH = max(len(str(number)) for number in ACTION_NUMBERS)
ACTION_ALL_WIDTHS = ACTION_WIDTH + ACTION_NUMBER_WIDTH + 1

QUBES_TOP_DEBUG = bool(environ.get("QUBES_TOP_DEBUG"))
LOGGING_LEVEL = DEBUG if QUBES_TOP_DEBUG else INFO
NO_COLOR = bool(environ.get("NO_COLOR"))
UNICODE = bool("utf-8" in environ.get("LC_ALL", "").lower())
if UNICODE:
    SORT_SIGN_UP = "\u2193"
    SORT_SIGN_DOWN = "\u2191"
    ELLIPSIS = "\u2026"
else:
    SORT_SIGN_UP = "^"
    SORT_SIGN_DOWN = "v"
    ELLIPSIS = "..."
UNTRUSTED_NUMBER_MAX_LEN = 20
MEMORY_UNIT = "MiB"
MEMORY_UNIT_PRECISION = 0
MEMORY_UNIT_AVAILABLE = ["KiB", "MiB", "GiB.0", "GiB.1", "GiB.2", "GiB.3"]


def convert_html_color_to_curses(hexadecimal: str):
    """
    Convert HTML color codes to RGB accepted by curses.
    """
    number = int(hexadecimal, 16)
    red = (number >> 16) & 255
    green = (number >> 8) & 255
    blue = number & 255
    return (
        int(red * 1000 / 255),
        int(green * 1000 / 255),
        int(blue * 1000 / 255),
    )


def gen_logger(name: str) -> Logger:
    """
    Return logger for a given name. Use syslog, as stdout and stderr are being
    used by curses.
    """
    logger = getLogger(name)
    logger.setLevel(LOGGING_LEVEL)
    formatter = Formatter(
        f" %(levelname)s: {name} %(funcName)s:%(lineno)d: %(message)s"
    )
    handler = SysLogHandler(address="/dev/log")
    handler.setFormatter(formatter)
    handler.ident = "qvm-top"
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def convert_memory(number: int) -> int | float:
    """
    Convert memory data to the expected unit.
    """
    precision: int | None = MEMORY_UNIT_PRECISION
    if precision == 0:
        precision = None
    match MEMORY_UNIT:
        case "KiB":
            return number
        case "MiB":
            return number // 1024
        case "GiB":
            return round(float(number / 1024**2), precision)
        case _:
            raise ValueError("Unknown MEMORY_UNIT")


class Stats:
    """
    Storage qube statistics.

    Memory is always saved in KiB to avoid rounding errors when values are
    calculated by clients.
    """

    # pylint: disable=too-many-instance-attributes

    outdated_by_removal: list[str] = []
    host_checked: bool = False
    host_memory_max: int | str = "NA"
    host_no_cpus: int | str = "NA"

    def __init__(self, vm: QubesVM) -> None:
        super().__init__()
        self.vm: QubesVM = vm

        self.uptodate: bool = False
        self.name = str(self.vm)
        self.log = gen_logger(f"{self.__class__.__qualname__}.{self.name}")

        self.features_default = {"gui": True, "internal": False}
        self.state: str = "NA"
        self.label: Label | str = ""
        self.is_preload: bool = False
        self.gui: bool = True
        self.internal: bool = False
        self.guivm: QubesVM | None = None
        self.management_dispvm: QubesVM | None = None
        self.auto_cleanup: bool = False
        self.memory_max: int | str = "NA"
        self.memory_init: int | str = "NA"
        self.update_cache()

        self.memory_assigned_total: int | str = "NA"
        self.memory_assigned_usable: int | str = "NA"
        self.memory_usage_assigned: float | str = "NA"
        self.memory_used_noswap: int | str = "NA"
        self.swap_used: int | str = "NA"
        self.memory_usage_used: float | str = "NA"
        self.memory_usage_swap_over_used: float | str = "NA"
        self.cpu_time: int | str = "NA"
        self.cpu_usage: int | str = "NA"
        self.online_vcpus: int | str = "NA"

        self.cpu_time_internal: int | str = "NA"
        self.cpu_usage_internal: float | str = "NA"
        self.online_vcpus_internal: int | str = "NA"

        self.memory_used_total: int | str = "NA"
        self.cpu_time_total: int | str = "NA"
        self.online_vcpus_total: int | str = "NA"

        if self.__class__.host_checked is False:
            self.__class__.host_checked = True
            host_memory_max: int | str = getattr(self.vm.app, "maxmem", "NA")
            if isinstance(host_memory_max, int):
                host_memory_max = int(host_memory_max) * 1024
            self.__class__.host_memory_max = host_memory_max
            self.__class__.host_no_cpus = getattr(self.vm.app, "no_cpus", "NA")

    def can_gui(self) -> bool:
        """
        Returns boolean if qube can show graphical applications.
        """
        return bool(
            self.guivm
            and self.gui
            and not self.is_preload
            and not self.internal
        )

    def can_console(self) -> bool:
        """
        Returns boolean if qube can have a debug console.
        """
        return bool(
            self.guivm
            and self.management_dispvm
            and not self.is_preload
            and not self.internal
        )

    def can_restart(self) -> bool:
        """
        Returns boolean if qube can be restarted.
        """
        return bool(not self.auto_cleanup)

    def filter_actions(self) -> list[str]:
        """
        Only show actions that passes all filters.
        """
        actions: list[str] = []
        for action, entry in ACTIONS.items():
            state = entry["on_state"]
            when = entry.get("when", [])
            if self.state not in state:
                continue
            if not (not when or all(getattr(self, meth)() for meth in when)):
                continue
            actions.append(action)
        return actions

    def get_actions(self) -> list[str]:
        """
        List available actions depending on the state.
        """
        if self.vm.klass in ["AdminVM", "RemoteVM"]:
            actions = []
        else:
            actions = self.filter_actions()
        return actions

    def _setter(self, name: str, newvalue) -> dict | None:
        """
        Set instance attribute, inform if status is outdated and return changes.
        """
        oldvalue = getattr(self, name)
        if oldvalue == newvalue:
            return None
        self.uptodate = False
        setattr(self, name, newvalue)
        return {name: [oldvalue, newvalue]}

    def set_verbose(self, items_to_update: dict) -> None:
        """
        Set multiple properties at a time and log outdated ones.
        """
        updates = [
            res
            for prop, value in items_to_update.items()
            if (res := self._setter(prop, value))
        ]
        if updates:
            self.log.debug("update=%s", updates)

    def update_cache(self) -> None:
        """
        Regenerate cache upon (re)connection.
        """
        data = {
            "state": self.vm.get_power_state(),
            "label": self.vm.label,
            "memory_init": getattr(self.vm, "memory", "NA"),
            "memory_max": getattr(self.vm, "maxmem", "NA"),
            "auto_cleanup": getattr(self.vm, "auto_cleanup", False),
            "is_preload": getattr(self.vm, "is_preload", False),
            "guivm": getattr(self.vm, "guivm", None),
            "management_dispvm": getattr(self.vm, "management_dispvm", None),
            "gui": (
                self.vm.features.check_with_template(
                    "gui", self.features_default["gui"]
                )
                if self.vm.klass != "RemoteVM"
                else self.features_default["gui"]
            ),
            "internal": (
                self.vm.features.check_with_template(
                    "internal", self.features_default["internal"]
                )
                if self.vm.klass != "RemoteVM"
                else self.features_default["internal"]
            ),
        }
        for k in ["memory_init", "memory_max"]:
            if isinstance(data[k], int):
                data[k] = data[k] * 1024

        self.set_verbose(data)

    def update_stats(self, **kwargs: Any) -> None:
        """
        Update memory and CPU statistics.
        """
        memory_assigned_total = int(kwargs["memory_assigned_total"])
        memory_assigned_usable = int(kwargs["memory_assigned_usable"])
        memory_with_swap_used = int(kwargs["memory_with_swap_used"])
        memory_used_total = memory_with_swap_used
        swap_used = kwargs.get("swap_used")
        if swap_used:
            swap_used = int(swap_used)
            memory_used_noswap = round(
                memory_with_swap_used - swap_used, MEMORY_UNIT_PRECISION
            )
        else:
            swap_used = "NA"
            memory_used_noswap = "NA"

        if isinstance(self.memory_max, int) and self.memory_max > 0:
            memory_usage_assigned: float | str = round(
                float(memory_assigned_total / self.memory_max) * 100, 1
            )
        else:
            memory_usage_assigned = "NA"
        if memory_assigned_usable > 0:
            if isinstance(memory_used_noswap, (int, float)):
                memory_usage_used: float | str = round(
                    float(memory_used_noswap / memory_assigned_usable) * 100, 1
                )
            else:
                memory_usage_used = "NA"
        else:
            memory_usage_used = 0.0
        if (
            isinstance(memory_used_noswap, (int, float))
            and memory_used_noswap > 0
            and isinstance(swap_used, (int, float))
        ):
            memory_usage_swap_over_used: float | str = round(
                float(swap_used / memory_used_noswap) * 100, 1
            )
        elif not isinstance(memory_used_noswap, (int, float)) or not isinstance(
            swap_used, (int, float)
        ):
            memory_usage_swap_over_used = "NA"
        else:
            memory_usage_swap_over_used = 0.0

        cpu_time = int(kwargs["cpu_time"]) // 10**3
        cpu_time_internal = kwargs.get("cpu_time_internal")
        if cpu_time_internal is None:
            cpu_time_internal = "NA"
            cpu_time_total = cpu_time
        else:
            cpu_time_internal = int(cpu_time_internal) // 10**3
            cpu_time_total = cpu_time + cpu_time_internal

        cpu_usage = int(kwargs["cpu_usage"])
        cpu_usage_internal = kwargs.get("cpu_usage_internal")
        if cpu_usage_internal is None:
            cpu_usage_internal = "NA"
        else:
            cpu_usage_internal = float(cpu_usage_internal)

        online_vcpus = int(kwargs["online_vcpus"])
        online_vcpus_internal = kwargs.get("online_vcpus_internal")
        if online_vcpus_internal is None:
            online_vcpus_internal = "NA"
            online_vcpus_total = online_vcpus
        else:
            online_vcpus_internal = int(online_vcpus_internal)
            online_vcpus_total = online_vcpus + online_vcpus_internal

        data = {
            "memory_assigned_total": memory_assigned_total,
            "memory_assigned_usable": memory_assigned_usable,
            "memory_used_total": memory_used_total,
            "memory_used_noswap": memory_used_noswap,
            "swap_used": swap_used,
            "memory_usage_used": memory_usage_used,
            "memory_usage_assigned": memory_usage_assigned,
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
        self.set_verbose(data)

    def update_memory_init(self, value: int) -> None:
        """
        Update initial memory.
        """
        self.set_verbose({"memory_init": value * 1024})

    def update_memory_max(self, value: int) -> None:
        """
        Update maximum memory and it's related properties.
        """
        memory_max = int(value) * 1024
        if memory_max > 0:
            memory_usage_assigned: float | str = "NA"
            if isinstance(self.memory_assigned_total, int):
                memory_usage_assigned = round(
                    float(self.memory_assigned_total / memory_max) * 100, 1
                )
        else:
            memory_usage_assigned = "NA"
        data = {
            "memory_max": memory_max,
            "memory_usage_assigned": memory_usage_assigned,
        }
        self.set_verbose(data)

    def update_generic(self, name: str, value: Any) -> None:
        """
        Update instance attributes.
        """
        self.set_verbose({name: value})

    def update_feat_from_template(self, name: str) -> None:
        """
        Update instance features according to template features.
        """
        default = self.features_default[name]
        if self.vm.klass != "RemoteVM":
            value = self.vm.features.check_with_template(name, default)
        else:
            value = default
        self.set_verbose({name: value})


class Screen:
    """
    Organize the screen for drawing, scrolling, typing.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        app: QubesBase,
        show_halted: bool,
        allow_color: bool,
        filter_query: str,
        sort_reverse: bool,
        sort_col_index: int | None,
        columns: dict[str, "Column"],
        thin_columns: bool,
    ):
        # pylint: disable=too-many-positional-arguments
        self.allow_color = allow_color
        self.app = app
        self.show_halted = show_halted
        self.filter_query = filter_query
        self.filter = False
        self.sort_reverse = sort_reverse
        self.sort_col_index = sort_col_index
        self.columns = columns
        self.thin_columns = thin_columns

        self.log = gen_logger(f"{self.__class__.__qualname__}")
        self.getch_timeout = 1000
        self.version: str = metadata("qubesadmin")["version"]

        self.selected_stats: list[Stats] = []
        self._stats: list[Stats] | None = None

        self.header_row = 4
        self.old_cursor_row = 0
        self.visible_stats: dict[int, Stats] = {}
        self.visible_actions: dict[int, str] = {}
        self.column_width: dict[str, int] = {}
        self.act = False
        self.actions: list[str] = []
        self.label_index = 0

        self.scroll_offset = 0
        self.max_offset = 0
        self.action_scroll_offset = 0
        self.action_max_offset = 0
        self.body_height = 0
        self.body_top = 0
        self.body_bottom = 0
        self.cursor_row = 0
        self.outdated_sleep = 0.010
        self.uptodate_sleep = 0.1
        self._old_cursor_visibility = 0

        self.last_selected_stat: Stats | None = None
        self.last_selected_row: int | None = None

    def init_label(self, label: Label | str) -> Label | None:
        """
        Initialize colors from qube labels.
        """
        if not curses.can_change_color():
            return None
        if isinstance(label, str):
            label = self.app.labels[label]
        name: str = label.name
        color: str = label.color
        if name in self.label_colors:
            return label
        index = self.label_index
        if name == "black":
            self.label_colors[name] = self.colors["FG_DEFAULT"]
            return label
        r1000, g1000, b1000 = convert_html_color_to_curses(color)
        curses.init_color(index, r1000, g1000, b1000)
        curses.init_pair(index, index, -1)
        self.label_colors[name] = curses.color_pair(index)
        self.label_index += 1
        return label

    def init_screen(self) -> None:
        """
        Initialize curses.

        Not a color expert, relied on how existing applications such as Vim and
        htop use the 8 default colors.

        - Black: only as reverse video
        - Red: critical
        - Green: header
        - Blue: not very used, use with discretion
        - Yellow: tag, warning
        - Magenta: not very used, use with discretion
        - Cyan: filter, cursor
        - White: only as reverse video

        The problematic colors:

        - White and black: Never use them without reverse video, as they might
          be the default font and background color.
        - Blue: Some shades of blue can be too dark to read on dark background.
          Not widely used.
        - Magenta: Not widely used, unknown reason, might be too alarming?
        """
        # pylint: disable=attribute-defined-outside-init
        term_fallback = "xterm-256color"
        term = environ.get("TERM")
        curses_unknown_colored_term = ["tmux-256color", "tmux-direct"]
        if term in curses_unknown_colored_term:
            self.log.debug(
                "TERM is known to support colors but curses renders it poorly, "
                "falling back to sane TERM"
            )
            environ["TERM"] = term_fallback
        self.stdscr = curses.initscr()
        self.stdscr.timeout(self.getch_timeout)
        self.stdscr.keypad(True)
        colors = {
            "BLACK": 0,
            "RED": 1,
            "GREEN": 2,
            "YELLOW": 3,
            "BLUE": 4,
            "MAGENTA": 5,
            "CYAN": 6,
            "WHITE": 7,
        }
        self.label_colors: dict[str, int] = {}
        self.colors: dict[str, int] = {}
        if self.allow_color:
            curses.start_color()
            curses.use_default_colors()
            for curses_color_name, index in colors.items():
                color_code = getattr(curses, f"COLOR_{curses_color_name}")
                curses.init_pair(index, color_code, -1)
                self.colors[f"FG_{curses_color_name}"] = curses.color_pair(
                    index
                )
                curses.init_pair(index + len(colors), -1, color_code)
                self.colors[f"BG_{curses_color_name}"] = curses.color_pair(
                    index
                )
            self.colors.update(
                {
                    "FG_DEFAULT": curses.color_pair(0),
                    "BG_DEFAULT": curses.color_pair(0),
                }
            )
            self.label_index = len(list(self.colors.keys())) + 1

            if curses.can_change_color():
                for label in self.app.labels.values():
                    self.init_label(label=label)
            else:
                self.label_colors = {
                    "red": self.colors["FG_RED"],
                    "orange": self.colors["FG_YELLOW"] | curses.A_DIM,
                    "yellow": self.colors["FG_YELLOW"],
                    "green": self.colors["FG_GREEN"],
                    "gray": self.colors["FG_WHITE"] | curses.A_DIM,
                    "blue": self.colors["FG_BLUE"],
                    "purple": self.colors["FG_MAGENTA"],
                    "black": self.colors["FG_DEFAULT"],
                }
                self.label_color_backup = (
                    self.colors["FG_BLACK"] | curses.A_UNDERLINE
                )
            self.header_summary_attr: int | None = self.colors["FG_GREEN"]
            self.header_attr = curses.A_REVERSE | self.colors["BG_GREEN"]
            self.header_sel_attr: int | None = (
                curses.A_REVERSE | self.colors["BG_CYAN"]
            )
            self.footer_attr: int | None = (
                curses.A_REVERSE | self.colors["BG_GREEN"]
            )
            self.footer_sel_attr: int | None = (
                curses.A_REVERSE | self.colors["BG_CYAN"]
            )
            self.sel_attr: int | None = (
                self.colors["FG_YELLOW"] | curses.A_REVERSE
            )
            self.cursor_attr: int | None = (
                curses.A_REVERSE | self.colors["BG_CYAN"]
            )
            self.sel_and_cursor_attr = self.cursor_attr | curses.A_DIM
        else:
            self.header_summary_attr = None
            self.header_attr = curses.A_REVERSE
            self.header_sel_attr = curses.A_REVERSE | curses.A_DIM
            self.footer_attr = curses.A_REVERSE
            self.footer_sel_attr = curses.A_REVERSE | curses.A_DIM
            self.sel_attr = curses.A_DIM
            self.cursor_attr = curses.A_REVERSE
            self.sel_and_cursor_attr = curses.A_REVERSE | curses.A_DIM
        curses.noecho()
        curses.cbreak()
        curses.nonl()
        self._old_cursor_visibility = curses.curs_set(0)
        curses.mousemask(curses.ALL_MOUSE_EVENTS)

    def restore_screen(self) -> None:
        """
        Restore sane window.
        """
        curses.nl()
        curses.nocbreak()
        curses.echo()
        try:
            curses.curs_set(self._old_cursor_visibility)
        except curses.error:
            pass
        curses.endwin()

    def write(self, *args: Any, **kwargs: Any) -> None:
        """
        Set screen text and attributes and deal with errors without panic.
        """
        attr = kwargs.pop("attr", None)
        max_width = kwargs.pop("max_width", None)
        row, col, text = args
        try:
            if attr is not None:
                self.stdscr.attron(attr)
            if max_width:
                self.stdscr.addnstr(row, col, text, max_width)
            else:
                self.stdscr.addstr(row, col, text)
        except curses.error:
            pass
        finally:
            if attr is not None:
                self.stdscr.attroff(attr)

    def get_selection(self) -> list[Stats]:
        """
        Get selected qube. If none is selected, consider the last one the
        cursor was in.
        """
        stats = self.selected_stats
        if not stats and self.last_selected_stat:
            stats = [self.last_selected_stat]
        if not stats:
            stats = []
        return stats

    def get_action_from_selection(self) -> list[str]:
        """
        List common actions that is valid for all selected qubes.
        """
        stats = self.get_selection()
        if not stats:
            return []
        actions = []
        all_actions = []
        for stat in stats:
            if not (stat_actions := stat.get_actions()):
                return []
            all_actions.append(stat_actions)
        actions = list(set.intersection(*(set(x) for x in all_actions)))
        actions = sorted(actions, key=lambda k: int(ACTIONS[k]["identity"]))
        self.log.debug("available-actions=%s", actions)
        return actions

    def get_stats(self):
        """
        Qubes that can be shown.
        """
        if self._stats is not None:
            return self._stats

        self._stats = sorted(
            [
                stats
                for stats in Monitor.entries.values()
                if (
                    self.show_halted
                    or (
                        stats.state != "Halted" and stats.vm.klass != "RemoteVM"
                    )
                )
                and stats.vm in Monitor.domains
                and (
                    (not self.filter_query and not self.filter)
                    or any(
                        string in stats.vm.name
                        for string in self.filter_query.split(",")
                    )
                )
            ],
            key=self.sort_stats_helper,
            reverse=self.sort_reverse,
        )
        return self._stats

    def sort_stats_helper(self, row) -> tuple[int, float]:
        """
        Helper to sort a column according to the values it owns.
        """
        if self.sort_col_index is None or (
            (header := list(self.columns.keys())[self.sort_col_index])
            and header == "name"
        ):
            if row.vm.klass == "AdminVM":
                return (0, row.vm.name)
            return (1, row.vm.name)
        val = getattr(row, header.lower())
        try:
            return (1, float(val))
        except (TypeError, ValueError):
            return (0, val.lower())

    def mark_uptodate(self) -> None:
        """
        Mark everything as up-to-date.
        """
        for stats in self.get_stats():
            stats.uptodate = True
        Stats.outdated_by_removal = []

    def is_uptodate(self) -> bool:
        """
        Check if statistics are live or expired.
        """
        self._stats = None
        outdated = (
            [stats.vm.name for stats in self.get_stats() if not stats.uptodate],
        )
        uptodate = not Stats.outdated_by_removal and not outdated
        self.log.debug(
            "removed=%s outdated=%s",
            Stats.outdated_by_removal,
            outdated,
        )
        return uptodate

    def draw_table(self) -> None:
        """
        Define screen regions.
        """
        # pylint: disable=too-many-locals,too-many-statements,too-many-branches
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        sums_row = self.header_row - 1
        self.body_top = self.header_row + 1
        self.body_top = self.header_row + 1
        self.body_bottom = height - 1
        self.body_height = max(0, self.body_bottom - self.body_top)

        if not self.cursor_row:
            self.cursor_row = self.body_top

        wanted = self.get_stats()
        self.mark_uptodate()

        total_items = len(wanted)
        self.max_offset = max(0, total_items - self.body_height)
        self.scroll_offset = min(self.max_offset, max(0, self.scroll_offset))
        scroll_start = self.scroll_offset
        scroll_end = min(total_items, scroll_start + self.body_height)
        visible = wanted[scroll_start:scroll_end]

        self.actions = self.get_action_from_selection()
        total_actions = len(self.actions)
        self.action_max_offset = max(0, total_actions - self.body_height)
        self.action_scroll_offset = min(
            self.action_max_offset, max(0, self.action_scroll_offset)
        )
        action_scroll_start = self.action_scroll_offset
        action_scroll_end = min(
            total_actions, action_scroll_start + self.body_height
        )
        action_visible = self.actions[action_scroll_start:action_scroll_end]

        memory_used_noswap_total: list[int] = [
            stats.memory_used_noswap
            for stats in wanted
            if isinstance(stats.memory_used_noswap, int)
        ]
        swap_used_total: list[int] = [
            stats.swap_used
            for stats in wanted
            if isinstance(stats.swap_used, int)
        ]
        memory_assigned_total_total: list[int] = [
            stats.memory_assigned_total
            for stats in wanted
            if isinstance(stats.memory_assigned_total, int)
        ]
        states = [stats.state for stats in wanted]
        sums: dict[str, list[int]] = {}
        for machine_header, column in self.columns.items():
            if not column.summable_for_overall:
                continue
            sums[machine_header] = [
                val
                for stats in wanted
                if (val := getattr(stats, machine_header, "NA"))
                and isinstance(val, (int, float))
            ]

        if self.sort_reverse:
            sort_sign = SORT_SIGN_UP
        else:
            sort_sign = SORT_SIGN_DOWN

        self.visible_stats = {}
        self.visible_actions = {}
        for row_index in range(self.body_height):
            curr_height = self.body_top + row_index
            if row_index >= len(visible):
                continue
            self.visible_stats[curr_height] = visible[row_index]

        if (
            not self.act
            and self.cursor_row > len(self.visible_stats) + self.header_row
        ):
            self.cursor_row = self.body_top
        elif self.cursor_row == -1:
            if self.last_selected_stat in visible:
                self.cursor_row = (
                    visible.index(self.last_selected_stat) + self.body_top
                )
            else:
                self.cursor_row = self.body_top

        line_content: dict[str, dict[int, tuple]] = {}
        line_start_after_action = 0

        for row_index in range(self.body_height):
            line_start = 0
            curr_height = self.body_top + row_index
            if self.act and self.actions:
                act_attr = None
                if curr_height == self.cursor_row and not self.filter:
                    act_attr = self.cursor_attr
                if row_index < len(action_visible):
                    curr_action = action_visible[row_index]
                    self.visible_actions[curr_height] = curr_action
                    action = str(curr_action).ljust(ACTION_WIDTH)
                    action_number = str(
                        ACTIONS[action.strip()]["identity"]
                    ).rjust(ACTION_NUMBER_WIDTH)
                    content = action_number + " " + action
                    self.write(
                        curr_height,
                        line_start,
                        content,
                        attr=act_attr,
                        max_width=width - line_start,
                    )
                line_start = ACTION_ALL_WIDTHS
                self.write(
                    curr_height,
                    line_start,
                    " ",
                    max_width=width - line_start,
                )
                line_start += 1
                line_start_after_action = line_start
            if row_index >= len(visible):
                if row_index not in wanted:
                    continue
                for column in self.columns.values():
                    stats = wanted[row_index]
                    data = getattr(stats, column.machine_header.lower())
                    line_content.setdefault(
                        column.machine_header, {}
                    ).setdefault(curr_height, (data, None))
                continue
            stats = self.visible_stats[curr_height]
            sel_attr = None
            if (
                curr_height == self.cursor_row
                and not self.filter
                and not self.act
            ):
                if stats in self.selected_stats:
                    sel_attr = self.sel_and_cursor_attr
                else:
                    sel_attr = self.cursor_attr
            elif stats in self.selected_stats:
                sel_attr = self.sel_attr
            elif (
                not self.selected_stats
                and curr_height == self.last_selected_row
                and not self.filter
                and self.act
            ):
                sel_attr = self.cursor_attr
            for column in self.columns.values():
                color_attr = None
                attr = column.machine_header.lower()
                data = getattr(stats, attr)
                if not sel_attr and self.allow_color:
                    if attr == "name":
                        try:
                            assert isinstance(stats.label, Label)
                            color_attr = self.label_colors[stats.label.name]
                        except KeyError:
                            color_attr = self.label_color_backup
                    elif attr == "state":
                        if stats.state in ["Paused", "Suspended"]:
                            color_attr = self.colors["FG_YELLOW"]
                        elif stats.state != "Running":
                            color_attr = self.colors["FG_RED"]
                    elif (
                        column.percentage
                        and data != "NA"
                        and column.percentage_intensity
                    ):
                        if data > max(column.percentage_intensity):
                            color_attr = self.colors["FG_RED"]
                        elif data > min(column.percentage_intensity):
                            color_attr = self.colors["FG_YELLOW"]
                        elif isinstance(data, (int, float)) and data == 0:
                            color_attr = self.label_colors["gray"]
                    elif data == "NA" or (
                        isinstance(data, (int, float)) and data == 0
                    ):
                        color_attr = self.label_colors["gray"]

                if attr == "state" and self.thin_columns:
                    data = POWER_STATES[data]["short"]
                elif (
                    isinstance(data, int)
                    and not column.percentage
                    and column.memory_convertable
                ):
                    data = convert_memory(data)

                line_content.setdefault(column.machine_header, {}).setdefault(
                    curr_height, (data, sel_attr or color_attr)
                )

        del column

        self.column_width = {}
        col_line_start: dict[int, int] = {}
        for machine_header, column in self.columns.items():
            self.column_width[machine_header] = 0
            header_sum: int | float = 0
            if machine_header in sums:
                header_sum = sum(sums[machine_header])
                if column.memory_convertable:
                    header_sum = convert_memory(header_sum)
                if not column.percentage and isinstance(header_sum, float):
                    header_sum_formatted = (
                        f"{header_sum:.{MEMORY_UNIT_PRECISION}f}"
                    )
                else:
                    header_sum_formatted = str(header_sum)
                header_sum_len = len(str(header_sum_formatted))
                if not column.untrusted or (
                    column.untrusted
                    and header_sum_len <= UNTRUSTED_NUMBER_MAX_LEN
                ):
                    self.column_width[machine_header] = header_sum_len

            if machine_header not in line_content:
                continue

            for curr_height, height_data in line_content[
                machine_header
            ].items():
                col_line_start.setdefault(curr_height, line_start_after_action)
                col_width = len(str(height_data[0]))
                if col_width > self.column_width[machine_header]:
                    self.column_width[machine_header] = col_width

            for curr_height, height_data in line_content[
                machine_header
            ].items():
                data, data_attr = height_data

                if not column.percentage and isinstance(data, float):
                    content_str = f"{data:.{MEMORY_UNIT_PRECISION}f}"
                else:
                    content_str = str(data)
                curr_width = self.column_width[machine_header]
                content = column.justify(content_str, curr_width)
                if (
                    column.untrusted
                    and len(content_str) > UNTRUSTED_NUMBER_MAX_LEN
                ):
                    content = column.justify(ELLIPSIS, curr_width)

                if column.summable_for_overall:
                    sum_content = column.justify(
                        header_sum_formatted, curr_width
                    )
                else:
                    sum_content = " " * len(content)

                content += " "
                sum_content += " "
                self.write(
                    sums_row,
                    col_line_start[curr_height],
                    sum_content,
                    max_width=width - col_line_start[curr_height],
                )
                self.write(
                    curr_height,
                    col_line_start[curr_height],
                    content,
                    attr=data_attr,
                    max_width=width - col_line_start[curr_height],
                )
                col_line_start[curr_height] += (
                    max(curr_width, column.min_width) + 1
                )

        state_counts = Counter(states)
        total_states = len(states)
        total_states_len = len(str(total_states))
        all_states = list(POWER_STATES)

        if self.thin_columns:
            top_text = "top"
            domain_text = "D"
            mem_text = "M"
            mem_unit = MEMORY_UNIT[0]
            cpu_text = "C"
            selected_text = "*"
            assigned_text = "a"
            used_text = "u"
            swap_text = "s"
        else:
            top_text = "qvm-top"
            domain_text = "Domain{}".format("s" if total_states > 0 else "")
            mem_text = "Mem"
            mem_unit = MEMORY_UNIT
            cpu_text = "CPUs"
            selected_text = "selected"
            assigned_text = "assigned"
            used_text = "used"
            swap_text = "swap"

        memory_total = Stats.host_memory_max
        if isinstance(memory_total, int):
            memory_total = convert_memory(memory_total)
        sum_memory_used_noswap = convert_memory(sum(memory_used_noswap_total))
        sum_swap_used = convert_memory(sum(swap_used_total))
        sum_memory_assigned_total_total = convert_memory(
            sum(memory_assigned_total_total)
        )
        pct_memory_used_noswap: float | str = "NA"
        pct_swap_used: float | str = "NA"
        pct_memory_assigned_total_total: float | str = "NA"
        if isinstance(memory_total, (int, float)):
            pct_memory_used_noswap = round(
                sum_memory_used_noswap / memory_total * 100, 1
            )
            pct_swap_used = round(sum_swap_used / memory_total * 100, 1)
            pct_memory_assigned_total_total = round(
                sum_memory_assigned_total_total / memory_total * 100, 1
            )

        no_cpus = Stats.host_no_cpus
        header_cpu_prefix = "  {}".format(cpu_text)
        header_cpu_suffix = ": {}".format(no_cpus)
        if MEMORY_UNIT_PRECISION == 0:
            header_mem_prefix = "{}({})".format(mem_text, mem_unit)
        else:
            header_mem_prefix = "{}({}.{})".format(
                mem_text, mem_unit, MEMORY_UNIT_PRECISION
            )
        total_mem_len = len(str(memory_total))
        header_mem_total = "{}".format(memory_total)

        header_mem_assigned_max_total = "{}({}%) {}".format(
            str(sum_memory_assigned_total_total).rjust(total_mem_len),
            pct_memory_assigned_total_total,
            assigned_text,
        )
        header_mem_used_noswap = "{}({}%) {}".format(
            str(sum_memory_used_noswap).rjust(total_mem_len),
            pct_memory_used_noswap,
            used_text,
        )
        header_mem_used_swap = "{}({}%) {}".format(
            str(sum_swap_used).rjust(total_mem_len),
            pct_swap_used,
            swap_text,
        )
        header_mem_suffix = ": "
        header_mem_values = [
            header_mem_total,
            header_mem_assigned_max_total,
            header_mem_used_noswap,
            header_mem_used_swap,
        ]
        header_mem_suffix += ", ".join(header_mem_values)

        state_parts = ["{}".format(total_states)]
        state_parts.append(
            "({} {})".format(
                str(len(self.selected_stats)).rjust(total_states_len),
                selected_text,
            )
        )
        for state in all_states:
            if self.thin_columns:
                pretty_state = POWER_STATES[state]["short"]
            else:
                pretty_state = state.lower() if state != "NA" else "NA"
            state_parts.append(
                "{} {}".format(
                    str(state_counts.get(state, 0)).rjust(total_states_len),
                    pretty_state,
                )
            )
        extra = [state for state in state_counts if state not in all_states]
        for state in sorted(extra):
            state_parts.append(
                "{} {}".format(
                    str(state_counts[state]).rjust(total_states_len),
                    state.lower(),
                )
            )
        header_dom_prefix = domain_text
        header_dom_suffix = ": " + ", ".join(state_parts)

        current_time = strftime("%H:%M:%S")
        if self.sort_col_index is not None:
            sort_col_index = self.sort_col_index
        else:
            sort_col_index = 0
        sorted_col = list(self.columns.values())[sort_col_index]
        sorted_header = str(
            sorted_col.justify(
                sorted_col.header, self.column_width[sorted_col.machine_header]
            )
        )
        sorted_header += sort_sign

        header_desc_prefix = top_text
        header_desc_suffix = f": {self.version} - {current_time}"
        scroll_hint = (
            f"{scroll_start + 1}-{scroll_end}/{total_items}"
            if total_items > 0
            else "0/0"
        )

        self.write(
            0,
            0,
            header_desc_prefix,
            max_width=width,
            attr=self.header_summary_attr,
        )
        self.write(
            0,
            len(header_desc_prefix),
            header_desc_suffix,
            max_width=width - len(header_desc_prefix),
        )

        self.write(
            1,
            0,
            header_dom_prefix,
            max_width=width,
            attr=self.header_summary_attr,
        )
        self.write(
            1,
            len(header_dom_prefix),
            header_dom_suffix,
            max_width=width - len(header_dom_prefix),
        )

        header_resources_start = 0
        self.write(
            2,
            0,
            header_mem_prefix,
            max_width=width,
            attr=self.header_summary_attr,
        )
        header_resources_start += len(header_mem_prefix)
        self.write(
            2,
            header_resources_start,
            header_mem_suffix,
            max_width=width - header_resources_start,
        )
        header_resources_start += len(header_mem_suffix)
        self.write(
            2,
            header_resources_start,
            header_cpu_prefix,
            max_width=width - header_resources_start,
            attr=self.header_summary_attr,
        )
        header_resources_start += len(header_cpu_prefix)
        self.write(
            2,
            header_resources_start,
            header_cpu_suffix,
            max_width=width - header_resources_start,
        )

        action_headers = ""
        if self.act and self.actions:
            action_headers = "ACTION".ljust(ACTION_ALL_WIDTHS)
        pre_headers = " ".join(
            col.justify(col.header, self.column_width[col.machine_header])
            for col in list(self.columns.values())[:sort_col_index]
        )
        if sort_col_index > 0:
            pre_headers += " "
        post_headers = " ".join(
            col.justify(col.header, self.column_width[col.machine_header])
            for col in list(self.columns.values())[sort_col_index + 1 :]
        )
        if post_headers:
            post_headers += " "
        self.log.debug("draw-header-pre=%r", pre_headers)
        self.log.debug("draw-header-sorted=%r", sorted_header)
        self.log.debug("draw-header-post=%r", post_headers)
        header_start = 0
        if action_headers:
            self.write(
                self.header_row,
                0,
                action_headers,
                max_width=width - header_start,
                attr=self.header_attr,
            )
            header_start += len(action_headers)
            self.write(
                self.header_row,
                header_start,
                " ",
                max_width=width - header_start,
            )
            header_start += 1
        self.write(
            self.header_row,
            header_start,
            pre_headers,
            max_width=width - header_start,
            attr=self.header_attr,
        )
        header_start += len(pre_headers)
        self.log.debug("pre-sort-start=%s", header_start)
        if header_start < width:
            self.write(
                self.header_row,
                header_start,
                sorted_header,
                max_width=width - header_start,
                attr=self.header_sel_attr,
            )
        header_start += len(sorted_header)
        self.log.debug("post-sort-start=%s", header_start)
        if len(post_headers.strip()) > 0 and header_start < width:
            self.write(
                self.header_row,
                header_start,
                post_headers,
                max_width=width - header_start,
                attr=self.header_attr,
            )
            header_end = header_start + len(post_headers)
        else:
            header_end = header_start

        current_headers_len = header_end
        if self.actions:
            current_headers_len += len(action_headers)
        filter_prefix = "Filter: "
        if self.filter or self.filter_query:
            if self.filter:
                footer_base = filter_prefix
            else:
                footer_base = filter_prefix.upper()
            footer_filter = self.filter_query

            footer_start = 0
            self.write(
                height - 1,
                0,
                footer_base,
                max_width=width,
                attr=self.footer_attr,
            )
            footer_start += len(footer_base)
            self.write(
                height - 1,
                footer_start,
                footer_filter,
                max_width=width - footer_start,
                attr=self.footer_sel_attr,
            )
            footer_start += len(footer_filter)
            if self.filter:
                self.write(
                    height - 1,
                    footer_start,
                    " ",
                    max_width=width - footer_start,
                    attr=curses.A_REVERSE,
                )
                footer_start += 1
            space_between = (
                min(width, current_headers_len)
                - footer_start
                - len(scroll_hint)
            )
            footer_suffix = " " * space_between + scroll_hint
            self.write(
                height - 1,
                footer_start,
                footer_suffix,
                max_width=width - footer_start,
                attr=self.footer_attr,
            )

        else:
            footer_base = ""
            space_between = (
                min(width, current_headers_len)
                - len(footer_base)
                - len(scroll_hint)
            )
            footer = footer_base + (" " * space_between) + scroll_hint
            self.write(
                height - 1,
                0,
                footer,
                max_width=width,
                attr=self.footer_attr,
            )

        self.stdscr.refresh()

    def select_row(self, row) -> bool | None:
        """
        React to selecting and deselecting a row.
        """
        if (
            row in self.visible_stats
            and self.visible_stats[row] in self.selected_stats
        ):
            self.log.debug("unlick-row=%s", row)
            self.selected_stats.remove(self.visible_stats[row])
            return True

        if (
            row != self.header_row
            and row in self.visible_stats
            and self.visible_stats[row].get_actions()
        ):
            self.log.debug("click-row=%s", row)
            self.selected_stats.append(self.visible_stats[row])
            return True
        return None

    def line_scroll(self, upward: bool):
        """
        React to clicking on a row, selecting an deselecting line.
        """
        if upward:
            self.cursor_row -= 1
            if self.cursor_row == self.header_row:
                self.cursor_row = self.old_cursor_row
                if self.act:
                    self.action_scroll_offset = max(
                        0, self.action_scroll_offset - 1
                    )
                else:
                    self.scroll_offset = max(0, self.scroll_offset - 1)
        else:
            self.cursor_row += 1
            if self.act:
                bottom = self.body_top + len(self.visible_actions)
                visible: dict[int, str] | dict[int, Stats] = (
                    self.visible_actions
                )
            else:
                bottom = self.body_bottom
                visible = self.visible_stats
            if self.cursor_row == bottom:
                self.cursor_row = self.old_cursor_row
                if self.act:
                    self.action_scroll_offset = min(
                        self.action_max_offset, self.action_scroll_offset + 1
                    )
                else:
                    self.scroll_offset = min(
                        self.max_offset, self.scroll_offset + 1
                    )
            elif self.cursor_row > len(visible) + self.header_row:
                self.cursor_row = self.old_cursor_row

    def page_scroll(self, upward: bool, half: bool = False):
        """
        Scroll a page up to down and even half in the chosen direction.
        """
        if upward:
            self.scroll_offset = max(0, self.scroll_offset - self.body_height)
            if half:
                self.scroll_offset = self.scroll_offset // 2
        else:
            self.scroll_offset = min(
                self.max_offset, self.scroll_offset + self.body_height
            )
            if half:
                self.scroll_offset = self.scroll_offset // 2

    def cancel_filter(self) -> None:
        """
        Cancel filter mode.
        """
        self.filter = False
        self.cursor_row = self.body_top

    def cancel_act(self) -> None:
        """
        Cancel action mode.
        """
        self.act = False
        self.cursor_row = -1

    def getch(self) -> bool | None:
        """
        Act based on received key, if any. Returns ``True`` if screen should be
        refreshed.
        """
        # pylint: disable=too-many-return-statements,too-many-statements,too-many-branches

        char = self.stdscr.getch()
        if char == -1:
            return None

        self.log.debug("char: %s", char)

        if self.filter:
            if 32 <= char <= 126:
                self.filter_query += chr(char)
            elif char in (curses.KEY_BACKSPACE,):
                self.filter_query = self.filter_query[:-1]
            else:
                if char not in (
                    curses.KEY_ENTER,
                    CR,
                ):
                    self.filter_query = ""
                self.cancel_filter()
            return True

        if self.act:
            if char in (curses.KEY_ENTER, CR):
                action: str = self.actions[self.cursor_row - self.body_top]
                qubes = [stat.vm for stat in self.get_selection()]
                self.log.info(
                    "Running action '%s' on domain%s: %s",
                    action,
                    "s" if len(qubes) > 1 else "",
                    ", ".join(qube.name for qube in qubes),
                )
                command = ACTIONS[action]["action"]
                self.cancel_act()
                ensure_future(command(qubes))
                return True
            if char in (ord("a"),):
                self.cancel_act()
                return True
            if char in [ord(str(n)) for n in ACTION_NUMBERS]:
                action = [
                    action
                    for action in self.actions
                    if str(ACTIONS[action]["identity"]) == chr(char)
                ][0]
                action_index = self.actions.index(action)
                self.cursor_row = self.body_top + action_index
                return True

        if char in (ord("q"), ord("Q"), ESC):
            raise KeyboardInterrupt

        old_sort_col_index = self.sort_col_index
        old_scroll_offset = self.scroll_offset
        self.old_cursor_row = self.cursor_row
        old_selected_stats = self.selected_stats

        if char in (curses.KEY_UP, ord("k"), DLE):
            self.line_scroll(upward=True)

        elif char in (curses.KEY_DOWN, ord("j"), SO):
            self.line_scroll(upward=False)

        elif char in (curses.KEY_PPAGE, NAK, STX):
            self.page_scroll(upward=True, half=char == NAK)

        elif char in (curses.KEY_NPAGE, ACK, EOT):
            self.page_scroll(upward=False, half=char == EOT)

        elif char in (curses.KEY_HOME, SOH, ord("g")):
            self.scroll_offset = 0

        elif char in (curses.KEY_END, ENQ, ord("G")):
            self.scroll_offset = self.max_offset

        elif char in (FF,):
            self.stdscr.clearok(True)

        elif char in (curses.KEY_LEFT, ord("h")):
            if self.sort_col_index is None:
                self.sort_col_index = -1
            else:
                self.sort_col_index -= 1
            if self.sort_col_index == -1:
                self.sort_col_index = len(self.columns) - 1
            if not bool(self.sort_col_index != old_sort_col_index):
                return None
            self.log.debug("sort-col=%s", self.sort_col_index)
            return True

        elif char in (curses.KEY_RIGHT, ord("l")):
            if self.sort_col_index is None:
                self.sort_col_index = 1
            else:
                self.sort_col_index += 1
            if self.sort_col_index > len(self.columns) - 1:
                self.sort_col_index = 0
            if not bool(self.sort_col_index != old_sort_col_index):
                return None
            self.log.debug("sort-col=%s", self.sort_col_index)
            return True

        elif char in (ord("r"),):
            self.sort_reverse = not self.sort_reverse

        elif char in (ord("S"),):
            self.show_halted = not self.show_halted

        elif char in (SP,) and not self.act:
            return self.select_row(self.cursor_row)

        elif char in (ord("U"),):
            self.selected_stats = []

        elif char in (ord("T"),):
            if self.visible_stats:
                first_visible = list(self.visible_stats.values())[0]
                if first_visible in self.selected_stats:
                    self.selected_stats = [
                        stat
                        for stat in self.selected_stats
                        if stat in self.visible_stats
                    ]
                else:
                    self.selected_stats += [
                        stat
                        for stat in self.visible_stats.values()
                        if stat not in self.selected_stats
                    ]

        elif char in (ord("a"),):
            if self.cursor_row in self.visible_stats:
                self.last_selected_row = self.cursor_row
                self.last_selected_stat = self.visible_stats[
                    self.last_selected_row
                ]
                self.log.debug(
                    "last-stat(row)=%s(%s)",
                    self.last_selected_stat.vm.name,
                    self.last_selected_row,
                )
            if self.get_action_from_selection():
                self.cursor_row = self.body_top
                self.act = True
                return True
            if self.act:
                self.act = False
                return True

        elif not self.act and char in (ord("/"),):
            self.filter = True

        elif char == curses.KEY_MOUSE:
            try:
                _, mouse_col, mouse_row, _, button_state = curses.getmouse()
            except curses.error:
                return None

            if button_state & curses.BUTTON4_PRESSED:
                self.page_scroll(upward=True, half=True)

            elif button_state & curses.BUTTON5_PRESSED:
                self.page_scroll(upward=False, half=True)

            elif button_state & curses.BUTTON1_DOUBLE_CLICKED:
                return self.select_row(mouse_row)

            elif button_state & curses.BUTTON1_CLICKED:
                if self.body_top <= mouse_row <= self.body_bottom:
                    self.cursor_row = mouse_row
                else:
                    col_index = self.get_col_index(mouse_col)
                    if col_index is None:
                        return None
                    if self.sort_col_index == col_index:
                        self.sort_reverse = not self.sort_reverse
                    else:
                        if self.sort_col_index is None:
                            reverse = not self.sort_reverse
                        else:
                            reverse = False
                        self.sort_col_index = col_index
                        self.sort_reverse = reverse
                    self.log.debug(
                        "sort-col=%s, reverse=%s",
                        self.sort_col_index,
                        self.sort_reverse,
                    )
                    return True

        scrolled = bool(
            self.scroll_offset != old_scroll_offset
            or self.cursor_row != self.old_cursor_row
            or self.selected_stats != old_selected_stats
        )
        return scrolled

    def get_col_index(self, col) -> int | None:
        """
        Returns the index of the specified column.
        """
        pos = 0
        # The +1 is to consider space between columns.
        for i, width in enumerate(
            max(column.min_width, self.column_width[machine_header]) + 1
            for machine_header, column in self.columns.items()
        ):
            if pos <= col < pos + width:
                return i
            pos += width
        return None

    async def paint(self) -> None:
        """
        Draw a top-like table when necessary, and get input to react on quit or
        body scrolling.
        """
        scrolled: bool | None = False
        while True:
            try:
                self.log.debug("loop")
                uptodate = self.is_uptodate()
                self.log.debug("uptodate=%s, scrolled=%s", uptodate, scrolled)
                if scrolled or not uptodate:
                    self.log.debug("draw")
                    self.draw_table()
                self.log.debug("getch")
                scrolled = self.getch()
                self.log.debug("scrolled=%s", scrolled)
                if not uptodate or scrolled or scrolled is False:
                    self.log.debug(
                        "urgent need redraw, sleeping for %ss",
                        self.outdated_sleep,
                    )
                    # Sleep a bit to avoid unhappy CPU.
                    await sleep(self.outdated_sleep)
                    continue
                self.log.debug(
                    "not rushing redraw, sleeping for %ss",
                    self.outdated_sleep,
                )
                await sleep(self.uptodate_sleep)
                continue
            except (KeyboardInterrupt, CancelledError):
                if self.filter:
                    self.filter_query = ""
                    self.cancel_filter()
                    continue
                if self.act:
                    self.cancel_act()
                    continue
                break


class Monitor:
    """
    Monitor and react to events.
    """

    entries: dict[QubesVM, Stats] = {}
    domains: list[QubesVM]

    def __init__(
        self,
        app: QubesBase,
        domains: list[QubesVM],
        dispatcher: EventsDispatcher,
        stats_dispatcher: EventsDispatcher,
        show_halted: bool,
        all_domains: bool,
        allow_color: bool,
        columns: dict[str, "Column"],
        sort_reverse: bool = False,
        sort_column: str | None = None,
        filter_query: str = "",
        thin_columns: bool = False,
    ) -> None:
        # pylint: disable=too-many-positional-arguments
        self.app = app
        self.__class__.domains = domains
        self.dispatcher = dispatcher
        self.stats_dispatcher = stats_dispatcher
        self.all_domains = all_domains
        sort_col_index: int | None = None
        if sort_column is not None:
            sort_col_index = list(columns.keys()).index(sort_column)
        self.screen = Screen(
            app=self.app,
            show_halted=show_halted,
            allow_color=allow_color,
            filter_query=filter_query,
            sort_reverse=sort_reverse,
            sort_col_index=sort_col_index,
            columns=columns,
            thin_columns=thin_columns,
        )
        self.log = gen_logger(f"{self.__class__.__qualname__}")
        root_logger = getLogger()
        root_logger.setLevel(LOGGING_LEVEL)
        root_logger.handlers.clear()
        root_logger.addHandler(self.log.handlers[0])

    def init_entries(self) -> None:
        """
        Initialize statistics holder for all qubes.
        """
        for vm in sorted(
            [vm for vm in self.app.domains if vm.klass == "AdminVM"]
        ):
            self.add_domain(submitter=None, vm=vm, event=None)
        for vm in sorted(
            [vm for vm in self.app.domains if vm not in self.__class__.entries]
        ):
            self.add_domain(submitter=None, vm=vm, event=None)

    def update_stats(self, vm: QubesVM, _event: str, **kwargs: Any) -> None:
        """
        Read vm-stats and update qube statistics.
        """
        if vm not in self.__class__.entries:
            return
        self.__class__.entries[vm].update_stats(**kwargs)

    def refresh_all_items(
        self, submitter: QubesVM | None, _event: str, **_kwargs: Any
    ) -> None:
        """
        Reconnected to the API, check if all entries are up to date.
        """
        # pylint: disable=unused-argument
        items_to_delete = [
            vm for vm in self.__class__.entries if vm not in self.app.domains
        ]
        for vm in items_to_delete:
            self.remove_domain(submitter=None, vm=vm, event=None)
        for vm in self.app.domains:
            self.update_domain_item(vm=vm, event=None)

    def add_domain(
        self,
        submitter: QubesVM | None,
        event: str | None,
        vm: QubesVM,
        **kwargs: Any,
    ) -> None:
        """
        Add qube to the statistics holder.
        """
        # pylint: disable=unused-argument
        if str(vm) in self.__class__.entries:
            return
        try:
            vm = self.app.domains[str(vm)]
        except KeyError:
            return

        self.log.debug("add=%s", str(vm))
        try:
            self.__class__.entries[vm] = Stats(vm)
        except QubesVMNotFoundError:
            self.log.debug("Qube removed while adding its entry: %s", str(vm))
            self.remove_domain(submitter=None, vm=vm, event=event)
        if self.all_domains:
            self.__class__.domains.append(vm)

    def remove_domain(
        self,
        submitter: QubesVM | None,
        event: str | None,
        vm: QubesVM,
        **kwargs: Any,
    ) -> None:
        """
        Remove qube from the statistics holder.
        """
        # pylint: disable=unused-argument
        if str(vm) not in self.__class__.entries:
            return
        self.log.debug("remove=%s", str(vm))
        if vm in self.__class__.domains:
            Stats.outdated_by_removal.append(str(vm))
        if self.__class__.entries[vm] in self.screen.selected_stats:
            self.screen.selected_stats.remove(self.__class__.entries[vm])
        del self.__class__.entries[vm]

    def get_entry(self, vm: QubesVM, event: str | None) -> Stats | None:
        """
        Safely get ``Stats`` if qube can be accessed, else, remove the entry and
        return ``None``.
        """
        try:
            item = self.__class__.entries[vm]
        except QubesPropertyAccessError as e:
            self.log.exception(e)
            self.remove_domain(submitter=None, vm=vm, event=event)
            return None
        return item

    def update_domain_item(
        self, vm: QubesVM, event: str | None, **kwargs: Any
    ) -> None:
        """
        Fully update the statistics holder of the qube.
        """
        # pylint: disable=unused-argument
        try:
            item = self.get_entry(vm=vm, event=event)
            if item is None:
                return
        except KeyError:
            self.add_domain(submitter=None, vm=vm, event=event)
            if not vm in self.__class__.entries:
                return
            item = self.__class__.entries[vm]
        try:
            item.update_cache()
        except QubesVMNotFoundError:
            self.log.debug("Qube removed while updating cache: %s", str(vm))
            self.remove_domain(submitter=None, vm=vm, event=event)

    def set_generic(
        self, vm, event, name, newvalue=None, oldvalue=None
    ) -> None:
        """
        Update attributes of the qube's statistics holder.
        """
        # pylint: disable=unused-argument
        if not (item := self.get_entry(vm=vm, event=event)):
            return
        self.log.debug("update -> %s=%s(%s)", name, vm.name, newvalue)
        if name == "maxmem":
            item.update_memory_max(value=newvalue)
            return
        if name == "memory":
            item.update_memory_init(value=newvalue)
            return
        if name == "label":
            newvalue = self.screen.init_label(label=newvalue)
        item.update_generic(name=name, value=newvalue)

    def set_feat_generic(
        self, vm, event, feature, value, oldvalue=None
    ) -> None:
        """
        Update feature attributes of the qube's statistics holder.
        """
        # pylint: disable=unused-argument
        if not (item := self.get_entry(vm=vm, event=event)):
            return
        self.log.debug("update -> %s=%s(%s)", feature, vm.name, value)
        item.update_generic(name=feature, value=value)
        for qube in vm.derived_vms:
            if qube not in self.__class__.entries:
                continue
            self.__class__.entries[qube].update_feat_from_template(name=feature)

    def del_feat_generic(self, vm, event, feature) -> None:
        """
        Update feature attributes of the qube's statistics holder.
        """
        # pylint: disable=unused-argument
        if not (item := self.get_entry(vm=vm, event=event)):
            return
        self.log.debug("update del -> %s=%s", feature, vm.name)
        item.update_feat_from_template(name=feature)
        for qube in vm.derived_vms:
            if qube not in self.__class__.entries:
                continue
            self.__class__.entries[qube].update_feat_from_template(name=feature)

    async def run(self) -> None:
        """
        Run initial setup.
        """
        self.register_events()
        self.init_entries()
        exc_data = None
        try:
            # Allow registering events.
            await sleep(0)
            self.screen.init_screen()
            await self.screen.paint()
        except BaseException as e:
            exc_data = exc_info()
            self.log.exception(e)
        finally:
            self.unregister_events()
            self.screen.restore_screen()
            if exc_data:
                print_exception(*exc_data, file=stderr)

    def register_events(self):  # type: ignore[list-item]
        """
        Track and set event handlers.
        """
        stats_handlers = [("vm-stats", self.update_stats)]
        handlers = [
            ("connection-established", self.refresh_all_items),
            ("domain-add", self.add_domain),
            ("domain-delete", self.remove_domain),
            ("property-set:maxmem", self.set_generic),
            ("property-set:memory", self.set_generic),
            ("property-set:label", self.set_generic),
            ("property-set:auto_cleanup", self.set_generic),
            ("property-reset:is_preload", self.set_generic),
            ("property-set:guivm", self.set_generic),
            ("domain-feature-set:gui", self.set_feat_generic),
            ("domain-feature-delete:gui", self.del_feat_generic),
            ("domain-feature-set:internal", self.set_feat_generic),
            ("domain-feature-delete:internal", self.del_feat_generic),
        ]
        for event in POWER_EVENTS:
            handlers.append((event, self.update_domain_item))
        for event, handler in stats_handlers:
            self.stats_dispatcher.add_handler(event=event, handler=handler)
        for event, handler in handlers:
            self.dispatcher.add_handler(event=event, handler=handler)

    def unregister_events(self) -> None:
        """
        Stop watchers.
        """
        self.stats_dispatcher.stop()
        self.dispatcher.stop()


class Column:
    """
    Column store.
    """

    columns: dict[str, "Column"] = {}

    def __init__(
        self,
        header: str,
        min_header: str | None = None,
        min_width: int | Callable = 0,
        internal: bool = False,
        total: bool = False,
        machine_header: str = "",
        doc: str | None = None,
        right_justify: bool = True,
        percentage: bool = False,
        percentage_intensity: list[int] | None = None,
        summable_for_overall: bool = False,
        untrusted: bool = False,
        memory_convertable: bool = False,
    ):
        # pylint: disable=too-many-positional-arguments
        self.internal = internal
        self.total = total
        self.percentage = percentage
        self.summable_for_overall = summable_for_overall
        self.untrusted = untrusted
        self.memory_convertable = memory_convertable
        self.min_header = min_header
        if percentage_intensity is None:
            self.percentage_intensity = [75, 50]
        else:
            self.percentage_intensity = percentage_intensity
        self.__doc__ = doc

        self.header = header
        if machine_header:
            self.machine_header = machine_header
        else:
            self.machine_header = self.header.strip()
        if isinstance(min_width, (int, float)):
            self.min_width = min_width
        else:
            self.min_width = min_width(header)
        self.min_width = max(self.min_width, len(header))
        if right_justify:
            self.justify = lambda x, w: x.rjust(max(w, self.min_width))
        else:
            self.justify = lambda x, w: x.ljust(max(w, self.min_width))
        self.columns[self.machine_header] = self


class _HelpColumnsAction(Action):
    """Action for argument parser that displays all columns and exits."""

    # pylint: disable=redefined-builtin
    def __init__(
        self,
        option_strings,
        dest=SUPPRESS,
        default=SUPPRESS,
        help="list all available columns with short descriptions and exit",
    ):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )

    def __call__(self, _parser, _namespace, _values, option_string=None):
        sep = " -> "
        width = max(
            len(column.header) + len(sep) + len(column.machine_header)
            for column in Column.columns.values()
        )
        text = f"Available columns (machine_header{sep}header   Description):\n"
        if QUBES_TOP_DEBUG:
            text += "\n" + "\n".join(
                ".. option:: {header:{width}s}\n\n   {doc}\n".format(
                    header=f"{column.machine_header}{sep}{column.header}",
                    doc=column.__doc__,
                    width=width,
                )
                for column in Column.columns.values()
            )

        else:
            wrapper = TextWrapper(
                width=80,
                initial_indent="  ",
                subsequent_indent=" " * (width + 6),
            )
            text += "\n".join(
                wrapper.fill(
                    "{header:{width}s}  {doc}".format(
                        header=f"{column.machine_header}{sep}{column.header}",
                        doc=column.__doc__,
                        width=width,
                    )
                )
                for column in Column.columns.values()
            )
        print(text)
        sys_exit(0)


class _HelpFormatsAction(Action):
    """Action for argument parser that displays all formats and exits."""

    # pylint: disable=redefined-builtin
    def __init__(
        self,
        option_strings,
        dest=SUPPRESS,
        default=SUPPRESS,
        help="list all available formats with short descriptions and exit",
    ):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )

    def __call__(self, _parser, _namespace, _values, option_string=None):
        width = max(len(fmt) for fmt in FORMATS)
        text = "Available formats:\n" + "".join(
            "  {fmt:{width}s}  {columns}\n".format(
                fmt=fmt, columns=",".join(columns), width=width
            )
            for fmt, columns in FORMATS.items()
        )
        print(text, end="")
        sys_exit(0)


UNTRUSTED_COLUMN = (
    "This value or part of it is broadcast by the qube, it can be a lie."
)

# Basic
Column(
    header="NAME",
    machine_header="name",
    min_width=31,
    doc="Qube's name.",
    right_justify=False,
)
Column(
    header="STATE",
    min_header="S",
    machine_header="state",
    min_width=max(len(state) for state in POWER_STATES),
    doc="Qube's power state.",
    right_justify=False,
)

# Memory
Column(
    header="MI",
    machine_header="memory_init",
    min_width=lambda header: max(len(header), 5),
    doc="How much memory the system must reserve for the qube to be able to "
    "initialize. On non-memory-balanced qubes, this is the maximum amount of "
    "memory a domain will ever have while it is running.",
    memory_convertable=True,
)
Column(
    header="MM",
    machine_header="memory_max",
    min_width=lambda header: max(len(header), 5),
    doc="How much memory the qube can use from the system. Part of this value "
    "is reserved to videoram, while the rest is up to qmemman to balloon up "
    "this qube when there is enough free memory on the host.",
    memory_convertable=True,
)
Column(
    header="MAM",
    machine_header="memory_assigned_total",
    min_width=lambda header: max(len(header), 5),
    doc="How much memory has been assigned to the qube, including overhead of "
    "videoram and internal usage.",
    summable_for_overall=True,
    memory_convertable=True,
)
Column(
    header="MAU",
    machine_header="memory_assigned_usable",
    min_width=lambda header: max(len(header), 5),
    doc="How much memory has been assigned to the qube and can be used. A qube "
    "is allowed to claim this amount at any time, and it cannot use more memory"
    " than what has been assigned to it. When the system is under memory "
    "pressure, the value can be just low enough for the qube to survive.",
    summable_for_overall=True,
    memory_convertable=True,
)

Column(
    header="MUT",
    machine_header="memory_used_total",
    min_width=lambda header: max(len(header), 5),
    doc="``MU`` + ``MUi``.",
    total=True,
    untrusted=True,
    summable_for_overall=True,
    memory_convertable=True,
)

Column(
    header="MU",
    machine_header="memory_used_noswap",
    min_width=lambda header: max(len(header), 5),
    doc="How much memory the qube alleges to use. " + UNTRUSTED_COLUMN,
    summable_for_overall=True,
    untrusted=True,
    memory_convertable=True,
)
Column(
    header="SU",
    machine_header="swap_used",
    min_width=lambda header: max(len(header), 5),
    doc="How much swap the qube alleges to use. " + UNTRUSTED_COLUMN,
    summable_for_overall=True,
    untrusted=True,
    memory_convertable=True,
)

Column(
    header="MAM/MM",
    machine_header="memory_usage_assigned",
    min_width=lambda header: max(len(header), 5),
    doc="How much memory the qube has assigned compared to the maximum it can "
    "have assigned, in percentage. A high percentage means the system is not "
    "pressuring the qube to release memory.",
    percentage=True,
    percentage_intensity=[],
)
Column(
    header="MU/MAU",
    machine_header="memory_usage_used",
    min_width=lambda header: max(len(header), 5),
    doc="How much memory the qube alleges to use from the assigned amount, in "
    "percentage. A high percentage on non-memory-balanced qubes is irrelevant. "
    "On memory balanced qubes, a higher value indicates the qube is using a lot"
    " of the memory it has assigned, which might be near exhaustion, if ``MAU``"
    " can't be ballooned up anymore.",
    percentage=True,
    untrusted=True,
)
Column(
    header="SU/MU",
    machine_header="memory_usage_swap_over_used",
    min_width=lambda header: max(len(header), 5),
    doc="How much swap the qube alleges to do from how much memory it alleges "
    "to use, in percentage. When it is over 10%, the qube might be swaping too "
    "much.",
    percentage=True,
    percentage_intensity=[30, 10],
    untrusted=True,
)

# CPU
Column(
    header="CPUsecT",
    machine_header="cpu_time_total",
    doc="``CPUsec`` + ``CPUisec``.",
    total=True,
    summable_for_overall=True,
)
Column(
    header="VCT",
    machine_header="online_vcpus_total",
    min_width=lambda header: max(len(header), 3),
    doc="``VC`` + ``VCi``.",
    total=True,
    summable_for_overall=True,
)
Column(
    header="CPUsec",
    machine_header="cpu_time",
    doc="How many seconds the qube has used from the CPU.",
    summable_for_overall=True,
)
Column(
    header="CPU%",
    machine_header="cpu_usage",
    min_width=lambda header: max(len(header), 5),
    doc="How much CPU the qube is using, in percentage.",
    percentage=True,
)
Column(
    header="VC",
    machine_header="online_vcpus",
    min_width=lambda header: max(len(header), 3),
    doc="How many Virtual CPUs are online.",
    summable_for_overall=True,
)

# Internal
Column(
    header="CPUisec",
    machine_header="cpu_time_internal",
    doc="Same as ``CPUsec``, but internal usage.",
    internal=True,
    summable_for_overall=True,
)
Column(
    header="CPUi%",
    machine_header="cpu_usage_internal",
    min_width=lambda header: max(len(header), 5),
    doc="Same as ``CPU%``, but internal usage.",
    percentage=True,
    internal=True,
)
Column(
    header="VCi",
    machine_header="online_vcpus_internal",
    min_width=lambda header: max(len(header), 3),
    doc="Same as ``VC``, but internal usage.",
    internal=True,
    summable_for_overall=True,
)


# TODO: ben: check formats
FORMATS: dict[str, list[str]] = {
    "min": ["name", "state", "memory_usage_used", "cpu_usage"],
    "default": [
        "name",
        "state",
        "memory_assigned_usable",
        "memory_used_noswap",
        "swap_used",
        "memory_usage_used",
        "online_vcpus",
        "cpu_usage",
    ],
    "max-no-internal": [
        machine_header
        for machine_header, column in list(Column.columns.items())
        if not column.internal
    ],
    "max-no-total": [
        machine_header
        for machine_header, column in list(Column.columns.items())
        if not column.total
    ],
    "max-no-total-no-internal": [
        machine_header
        for machine_header, column in list(Column.columns.items())
        if not column.internal and not column.total
    ],
    "max": list(Column.columns.keys()),
}


def column_multiple_choice(value: str):
    """
    Validate CSV column values.
    """
    if bad := [x for x in value.split(",") if x not in Column.columns]:
        raise ArgumentTypeError("Invalid choice(s): {}".format(", ".join(bad)))
    return value


parser = QubesArgumentParser(
    description=__doc__ + " Defaults is to show all non-halted qubes.",
    vmname_nargs="*",
    all_default=True,
    all_include_adminvm=True,
)
parser.add_argument(
    "--show-halted",
    "-S",
    action="store_true",
    default=False,
    help="don't hide halted qubes",
)
parser.add_argument(
    "--filter",
    "-f",
    metavar="FILTER,...",
    action="store",
    default="",
    help="filter domains name matching each fixed string separated by comma",
)
parser.add_argument(
    "--thin-columns",
    action="store_true",
    default=False,
    help="Columns will to be as large as the its header or current lengthiest "
    "data. It is not the default because columns will move every time the "
    "length of the lengthiest data change.",
)
parser.add_argument(
    "--memory-unit",
    action="store",
    choices=MEMORY_UNIT_AVAILABLE,
    default=MEMORY_UNIT,
    metavar="UNIT",
    help="Unit to use for displaying memory. The digit after the dot is the "
    "precision. Available: " + ", ".join(MEMORY_UNIT_AVAILABLE),
)

parser_format = parser.add_argument_group(title="formatting options")
parser_format_exclusive = parser_format.add_mutually_exclusive_group()

parser_format_exclusive.add_argument(
    "--columns",
    "-C",
    metavar="COLUMN,...",
    action="store",
    type=column_multiple_choice,
    help="show only specified columns",
)
parser_format_exclusive.add_argument(
    "--format",
    "-F",
    metavar="FORMAT",
    action="store",
    choices=FORMATS.keys(),
    help="show only columns declared by format: " + ", ".join(FORMATS),
)
parser_format.add_argument("--help-columns", action=_HelpColumnsAction)
parser_format.add_argument("--help-formats", action=_HelpFormatsAction)

parser_sort = parser.add_argument_group(title="sorting options")
parser_sort.add_argument(
    "--sort-column",
    "-k",
    metavar="COLUMN",
    action="store",
    choices=Column.columns,
    help="sort by specified column",
)
parser_sort.add_argument(
    "--reverse",
    "-r",
    action="store_true",
    help="reverse sorting",
)
parser.add_argument(
    "--no-color",
    action="store_true",
    help="do not colorize the screen",
)


async def run_async(args) -> int:
    """
    Dispatch events, display statistics and wait for exit.
    """
    global MEMORY_UNIT  # pylint: disable=global-statement
    global MEMORY_UNIT_PRECISION  # pylint: disable=global-statement
    MEMORY_UNIT = args.memory_unit.split(".")[0]
    if "." in args.memory_unit:
        MEMORY_UNIT_PRECISION = int(args.memory_unit.split(".")[1])
    if args.columns:
        user_columns = [col.strip() for col in args.columns.split(",")]
    elif args.format:
        user_columns = [col.strip() for col in FORMATS[args.format]]
    else:
        user_columns = [col.strip() for col in FORMATS["default"]]
    columns = {col: Column.columns[col] for col in user_columns}
    if args.thin_columns:
        for col, column in columns.items():
            if column.min_header:
                columns[col].header = column.min_header
            columns[col].min_width = len(column.header)

    sort_column = args.sort_column or None

    app = args.app
    app.cache_enabled = True
    dispatcher = EventsDispatcher(app)
    stats_dispatcher = EventsDispatcher(app, api_method="admin.vm.Stats")
    top = Monitor(
        all_domains=args.all_domains,
        app=app,
        domains=args.domains,
        dispatcher=dispatcher,
        stats_dispatcher=stats_dispatcher,
        show_halted=args.show_halted,
        sort_column=sort_column,
        sort_reverse=args.reverse,
        columns=columns,
        allow_color=not (args.no_color or NO_COLOR),
        filter_query=args.filter,
        thin_columns=args.thin_columns,
    )
    tasks = [
        create_task(dispatcher.listen_for_events()),
        create_task(stats_dispatcher.listen_for_events()),
        create_task(top.run()),
    ]
    await gather(*tasks)
    return 0


def main(args=None, app=None) -> int:
    """
    Show top-like statistics for all qubes by default, else, show for the
    specified qubes.
    """
    try:
        args = parser.parse_args(args, app=app)
        run(run_async(args=args))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys_exit(main())
