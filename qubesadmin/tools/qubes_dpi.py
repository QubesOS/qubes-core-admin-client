#!/usr/bin/python3

#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2026 Guillaume Chinal <guiiix@invisiblethingslab.com>
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

"""qubes-dpi tool: Manage DPI configuration on QubesOS"""

import os
import subprocess
import sys

from argparse import ArgumentParser

import gi
import qubesadmin


def parse_args():
    """Parse CLI args"""
    parser = ArgumentParser()
    parser.add_argument(
        "-s",
        "--scale",
        choices=["1", "2"],
        help="Window scale factor",
    )
    return parser.parse_args()


def set_dom0_scale_factor(scale: int):
    """Set scaling settings on dom0"""
    try:
        gi.require_version("Xfconf", "0")
        from gi.repository import Xfconf  # pylint: disable=no-name-in-module
    except ValueError:
        print(
            "Xfconfig not available, skipping dom0 configuration...",
            file=sys.stderr,
        )
        return

    dpi = 96 * scale
    unscaled_dpi = 96 * 1024  # to prevent applying DPI twice on GDK apps

    Xfconf.init()
    channel = Xfconf.Channel.get("xsettings")
    channel.set_int("/Gdk/WindowScalingFactor", scale)
    channel.set_int("/Gdk/UnscaledDPI", unscaled_dpi)
    channel.set_int("/Xft/DPI", dpi)


def set_feature_dpi_scale(scale: int):
    """Set dpi.scale feature on dom0"""
    app = qubesadmin.Qubes()
    app.domains["dom0"].features["dpi.scale"] = scale


def main():
    """Main function of qubes-dpi tool"""
    args = parse_args()
    current_desktop = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get(
        "XDG_SESSION_DESKTOP", ""
    )
    if args.scale:
        scale = int(args.scale)
        set_feature_dpi_scale(scale)
        set_dom0_scale_factor(scale)
        subprocess.run(
            ["/usr/bin/qvm-start-gui", "--notify-monitor-layout", "--all"],
            check=True,
        )
        if current_desktop.lower() == "xfce":
            subprocess.run(["/usr/bin/xfce4-panel", "-r"], check=True)


if __name__ == "__main__":
    main()
