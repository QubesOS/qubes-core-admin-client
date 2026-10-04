# encoding=utf-8
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2026  Guillaume Chinal <guiiix@invisiblethingslab.com>
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


import os
import subprocess
import sys

import gi
import qubesadmin


from argparse import ArgumentParser


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "-s",
        "--scale",
        choices=["1", "2"],
        help="Window scale factor",
    )
    return parser.parse_args()


def set_dom0_scale_factor(scale: int):
    try:
        gi.require_version("Xfconf", "0")
        from gi.repository import Xfconf
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
    app = qubesadmin.Qubes()
    app.domains["dom0"].features["dpi.scale"] = scale


def main():
    args = parse_args()
    if args.scale:
        scale = int(args.scale)
        set_feature_dpi_scale(scale)
        set_dom0_scale_factor(scale)
        subprocess.run(
            ["/usr/bin/qvm-start-gui", "--notify-monitor-layout", "--all"],
            check=True,
        )
        subprocess.run(["/usr/bin/xfce4-panel", "-r"], check=True)


if __name__ == "__main__":
    main()
