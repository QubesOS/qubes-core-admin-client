#!/usr/bin/env python3

## SPDX-FileCopyrightText: 2025 Benjamin Grande M. S. <ben.grande.b@gmail.com>
##
## SPDX-License-Identifier: GPL-2.0-only

"""
Top-like info for Qubes.
"""

import curses
import time
import subprocess
from qubesadmin import Qubes

def get_xentop_data():
    """
    Read data from xentop.
    """
    ## Only the 2nd iteration and after 1 second it shows the correct info.
    output = subprocess.check_output("xentop -bfi2d1", shell=True, text=True)
    lines = output.strip().split("\n")
    data = {}
    for line in lines:
        parts = line.split()
        if parts[1] == "STATE":
            continue
        if len(parts) >= 4:
            name = parts[0]
            if name == "Domain-0":
                name = "dom0"
            cpu_usage = int(float(parts[3]))
            data[name] = cpu_usage
    return data


def get_filtered_qubes() -> list:
    """
    Get information from qubes.
    """
    qube_list = []
    xentop_data = get_xentop_data()
    for qube in Qubes().domains:
        power_state = qube.get_power_state()
        if power_state == "Halted":
            continue
        cpu_usage = xentop_data.get(qube.name, "ERROR")
        cpu_usage = f"{cpu_usage}%"
        if power_state != "Running":
            mem_usage = "NA"
        else:
            filter_esc = bool(qube.name != "dom0")
            proc = qube.run_service("qubes.GetMem", user="root", stderr=None,
                                    filter_esc=filter_esc)
            try:
                ## TODO: how to stdout.read(2) with timeout to avoid qube
                ## filling up Dom0 memory.
                untrusted_mem, _ = proc.communicate(timeout=1)
                untrusted_mem = untrusted_mem.decode("ascii", errors="ignore")
                untrusted_mem = str(untrusted_mem.strip())
                if len(untrusted_mem) != 2 or not untrusted_mem.isdigit():
                    raise ValueError
                mem_usage = f"{untrusted_mem}%"
            except ValueError:
                mem_usage = "ERROR"
            except subprocess.CalledProcessError:
                mem_usage = "NA"
        qube_list.insert(0 if qube.name == "dom0" else len(qube_list), {
            "name": qube.name,
            "status": power_state,
            "mem_usage": mem_usage,
            "cpu_usage": cpu_usage,
        })
    return qube_list


def draw_table(stdscr, qubes):
    """
    Draw a top-like table about qubes statuses.
    """
    stdscr.clear()
    height, _ = stdscr.getmaxyx()

    stdscr.attron(curses.A_BOLD)
    stdscr.attron(curses.A_REVERSE)
    stdscr.addstr(0, 0, "Qube".ljust(40))
    stdscr.addstr(0, 40, "State".ljust(50))
    stdscr.addstr(0, 51, "MEM(%)".ljust(57))
    stdscr.addstr(0, 59, "CPU(%)".ljust(64))
    stdscr.attroff(curses.A_BOLD)
    stdscr.attroff(curses.A_REVERSE)

    for i, qube in enumerate(qubes, start=1):
        if i >= height - 1:
            break
        stdscr.addstr(i, 0, qube["name"].ljust(40))
        stdscr.addstr(i, 40, qube["status"].ljust(50))
        stdscr.addstr(i, 51, qube["mem_usage"].rjust(6))
        stdscr.addstr(i, 59, qube["cpu_usage"].rjust(6))

    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    stdscr.addstr(height-1, 0, f"qvm-top - {current_time}")
    stdscr.refresh()


def main(stdscr) -> None: # pylint:disable=missing-function-docstring
    curses.curs_set(0)
    stdscr.clear()
    stdscr.timeout(0)

    while True:
        filtered_qubes = get_filtered_qubes()
        draw_table(stdscr, filtered_qubes)
        key = stdscr.getch()
        if key in [ord("q"), ord("Q"), 27]:
            break


if __name__ == "__main__":
    curses.wrapper(main)
