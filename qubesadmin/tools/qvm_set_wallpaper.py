# -*- encoding: utf-8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
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

"""Safely set desktop wallpaper from a VM image"""

import logging
import os
import struct
import subprocess
import sys
import zlib

import qubesadmin
import qubesadmin.tools
from qubesadmin.app import QubesBase
from qubesadmin.tools import QubesArgumentParser

DEFAULT_OUTPUT_DIR = os.path.expanduser("~/.local/share/qubes-wallpaper")
DEFAULT_OUTPUT_PATH = os.path.join(DEFAULT_OUTPUT_DIR, "wallpaper.png")


def get_parser() -> QubesArgumentParser:
    """Create :py:class:`argparse.ArgumentParser` suitable for
    :program:`qvm-set-wallpaper`.
    """
    parser = qubesadmin.tools.QubesArgumentParser(
        description="Safely set desktop wallpaper from a VM image",
        vmname_nargs=1,
    )
    parser.add_argument(
        "filepath",
        metavar="FILEPATH",
        help="path to image file within the source VM",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        default=DEFAULT_OUTPUT_PATH,
        help="output path for the converted PNG (default: %(default)s)",
    )
    return parser


def rgba_to_png(data: bytes, width: int, height: int) -> bytes:
    """Encode raw RGBA data as a PNG file.

    :param data: raw RGBA pixel data
    :param width: image width in pixels
    :param height: image height in pixels
    :returns: PNG file contents
    """

    def _chunk(chunk_type, chunk_data):
        raw = chunk_type + chunk_data
        return (
            struct.pack(">I", len(chunk_data))
            + raw
            + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR: width, height, bit depth 8, color type 6 (RGBA)
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    # IDAT: filter byte 0 (None) before each scanline, then zlib compress
    row_size = width * 4
    raw_lines = b""
    for row in range(height):
        raw_lines += b"\x00" + data[row * row_size : (row + 1) * row_size]
    idat = _chunk(b"IDAT", zlib.compress(raw_lines))

    iend = _chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


def set_wallpaper(path: str) -> None:
    """Detect desktop environment and set wallpaper.

    :param path: absolute path to the wallpaper image
    """
    path = os.path.abspath(path)
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    if "xfce" in desktop:
        # List all backdrop properties and set every last-image one
        result = subprocess.run(
            ["xfconf-query", "-c", "xfce4-desktop", "-l"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            if line.endswith("/last-image"):
                subprocess.run(
                    ["xfconf-query", "-c", "xfce4-desktop", "-p",
                     line, "-s", path],
                    check=True,
                )
    elif any(de in desktop for de in ("gnome", "cinnamon", "unity")):
        uri = "file://" + path
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.background",
             "picture-uri", uri],
            check=True,
        )
    elif "kde" in desktop:
        subprocess.run(
            ["plasma-apply-wallpaperimage", path],
            check=True,
        )
    else:
        logging.warning(
            "Unknown desktop environment. Wallpaper saved to: %s\n"
            "Set it manually in your desktop environment settings."
            "Feel free to raise a Github issue so that we can add support"
            " for your environment.",
            path,
        )


def main(args: list[str] | None = None, app: QubesBase | None = None) -> int:
    """Main function of :program:`qvm-set-wallpaper`."""
    app = app or qubesadmin.Qubes()
    parser = get_parser()
    args = parser.parse_args(args, app=app)
    vm = args.domains.pop()
    filepath = args.filepath
    output_path = args.output

    try:
        stdout, _stderr = vm.run_service_for_stdio(
            "qubes.GetImageRGBA", input=filepath.encode()
        )
    except subprocess.CalledProcessError as e:
        parser.print_error(
            "Failed to get image from '{}': {}".format(vm.name, e)
        )
        return 1

    # Parse header: "width height\n"
    try:
        header_end = stdout.index(b"\n")
        header = stdout[:header_end].decode("ascii")
        width_s, height_s = header.split()
        width, height = int(width_s), int(height_s)
    except (ValueError, IndexError) as e:
        parser.print_error(
            "Invalid response from qubes.GetImageRGBA: {}".format(e)
        )
        return 1

    if width <= 0 or height <= 0:
        parser.print_error(
            "Invalid image dimensions: {}x{}".format(width, height)
        )
        return 1

    rgba_data = stdout[header_end + 1 :]
    expected_size = width * height * 4
    if len(rgba_data) != expected_size:
        parser.print_error(
            "Expected {} bytes of RGBA data, got {}".format(
                expected_size, len(rgba_data)
            )
        )
        return 1

    png_data = rgba_to_png(rgba_data, width, height)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as png_file:
        png_file.write(png_data)

    try:
        set_wallpaper(output_path)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        parser.print_error("Failed to set wallpaper: {}".format(e))
        logging.error("Wallpaper saved to: %s", output_path)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
