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

# pylint: disable=missing-docstring

import os
import struct
import tempfile
import zlib
from unittest.mock import patch, MagicMock

import qubesadmin.tests
import qubesadmin.tools.qvm_set_wallpaper


class TC_00_rgba_to_png(qubesadmin.tests.QubesTestCase):

    def test_000_valid_png_signature(self):
        """Output starts with the 8-byte PNG magic signature."""
        rgba = b"\xff\x00\x00\xff" * 4  # 2x2 red image
        png = qubesadmin.tools.qvm_set_wallpaper.rgba_to_png(rgba, 2, 2)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_001_valid_png_chunks(self):
        """First chunk is IHDR and file ends with IEND."""
        rgba = b"\xff\x00\x00\xff" * 4
        png = qubesadmin.tools.qvm_set_wallpaper.rgba_to_png(rgba, 2, 2)
        # After 8-byte signature, first chunk should be IHDR
        self.assertEqual(png[12:16], b"IHDR")
        # PNG must end with IEND
        self.assertTrue(png.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"))

    def test_002_ihdr_dimensions(self):
        """IHDR chunk encodes the correct width and height."""
        rgba = b"\x00" * (3 * 5 * 4)
        png = qubesadmin.tools.qvm_set_wallpaper.rgba_to_png(rgba, 3, 5)
        # IHDR data starts at offset 16 (8 sig + 4 len + 4 type)
        width, height = struct.unpack(">II", png[16:24])
        self.assertEqual(width, 3)
        self.assertEqual(height, 5)

    def test_003_roundtrip_idat(self):
        """Decompressed IDAT contains filter-byte-prefixed scanlines."""
        rgba = b"\xff\x00\x00\xff\x00\xff\x00\xff"  # 2x1
        png = qubesadmin.tools.qvm_set_wallpaper.rgba_to_png(rgba, 2, 1)
        # Find IDAT chunk
        idx = png.index(b"IDAT")
        idat_len = struct.unpack(">I", png[idx - 4 : idx])[0]
        idat_data = png[idx + 4 : idx + 4 + idat_len]
        raw = zlib.decompress(idat_data)
        # Should be filter byte (0) + 2 pixels * 4 bytes = 9 bytes
        self.assertEqual(len(raw), 1 + 2 * 4)
        self.assertEqual(raw[0:1], b"\x00")  # filter byte
        self.assertEqual(raw[1:], rgba)


def _make_service_response(width, height, rgba_data):
    """Build a qubes.GetImageRGBA response."""
    header = "{} {}\n".format(width, height).encode()
    return header + rgba_data


class TC_01_qvm_set_wallpaper(qubesadmin.tests.QubesTestCase):

    def setUp(self):
        super().setUp()
        self.app.expected_calls[("dom0", "admin.vm.List", None, None)] = (
            b"0\x00vm class=AppVM state=Running\n"
        )
        self.tmpdir = tempfile.mkdtemp()
        self.output_path = os.path.join(self.tmpdir, "wallpaper.png")

    def tearDown(self):
        if os.path.exists(self.output_path):
            os.unlink(self.output_path)
        os.rmdir(self.tmpdir)
        super().tearDown()

    @patch("qubesadmin.tools.qvm_set_wallpaper.set_wallpaper")
    def test_000_success(self, mock_set_wp):
        """Valid RGBA response produces a PNG and sets wallpaper."""
        rgba = b"\xff\x00\x00\xff" * 4
        self.app.expected_service_calls[("vm", "qubes.GetImageRGBA")] = (
            _make_service_response(2, 2, rgba)
        )
        ret = qubesadmin.tools.qvm_set_wallpaper.main(
            ["vm", "/path/to/img.jpg", "--output", self.output_path],
            app=self.app,
        )
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(self.output_path))
        with open(self.output_path, "rb") as png_file:
            self.assertTrue(png_file.read().startswith(b"\x89PNG"))
        mock_set_wp.assert_called_once_with(self.output_path)

    @patch("qubesadmin.tools.qvm_set_wallpaper.set_wallpaper")
    def test_001_service_sends_filepath(self, _mock_set_wp):
        """VM filepath is sent as stdin to the qrexec service."""
        rgba = b"\xff\x00\x00\xff" * 4
        self.app.expected_service_calls[("vm", "qubes.GetImageRGBA")] = (
            _make_service_response(2, 2, rgba)
        )
        qubesadmin.tools.qvm_set_wallpaper.main(
            ["vm", "/home/user/photo.jpg", "--output", self.output_path],
            app=self.app,
        )
        # service_calls has two entries per call: one from run_service
        # (with kwargs) and one from the input_callback (with input bytes)
        self.assertEqual(self.app.service_calls[0][1], "qubes.GetImageRGBA")
        self.assertEqual(
            self.app.service_calls[1],
            ("vm", "qubes.GetImageRGBA", b"/home/user/photo.jpg"),
        )

    @patch("qubesadmin.tools.qvm_set_wallpaper.set_wallpaper")
    def test_002_invalid_header_no_newline(self, mock_set_wp):
        """Response without a newline-terminated header fails."""
        self.app.expected_service_calls[("vm", "qubes.GetImageRGBA")] = (
            b"garbage without newline"
        )
        ret = qubesadmin.tools.qvm_set_wallpaper.main(
            ["vm", "/path/img.jpg", "--output", self.output_path],
            app=self.app,
        )
        self.assertEqual(ret, 1)
        mock_set_wp.assert_not_called()

    @patch("qubesadmin.tools.qvm_set_wallpaper.set_wallpaper")
    def test_003_invalid_header_not_numbers(self, mock_set_wp):
        """Non-numeric dimensions in header fail."""
        self.app.expected_service_calls[("vm", "qubes.GetImageRGBA")] = (
            b"abc def\n\x00"
        )
        ret = qubesadmin.tools.qvm_set_wallpaper.main(
            ["vm", "/path/img.jpg", "--output", self.output_path],
            app=self.app,
        )
        self.assertEqual(ret, 1)
        mock_set_wp.assert_not_called()

    @patch("qubesadmin.tools.qvm_set_wallpaper.set_wallpaper")
    def test_004_negative_dimensions(self, mock_set_wp):
        """Negative image dimensions are rejected."""
        self.app.expected_service_calls[("vm", "qubes.GetImageRGBA")] = (
            b"-1 10\n\x00"
        )
        ret = qubesadmin.tools.qvm_set_wallpaper.main(
            ["vm", "/path/img.jpg", "--output", self.output_path],
            app=self.app,
        )
        self.assertEqual(ret, 1)
        mock_set_wp.assert_not_called()

    @patch("qubesadmin.tools.qvm_set_wallpaper.set_wallpaper")
    def test_005_data_size_mismatch(self, mock_set_wp):
        """RGBA payload size not matching dimensions fails."""
        self.app.expected_service_calls[("vm", "qubes.GetImageRGBA")] = (
            _make_service_response(2, 2, b"\x00" * 8)
        )
        ret = qubesadmin.tools.qvm_set_wallpaper.main(
            ["vm", "/path/img.jpg", "--output", self.output_path],
            app=self.app,
        )
        self.assertEqual(ret, 1)
        mock_set_wp.assert_not_called()

    @patch("qubesadmin.tools.qvm_set_wallpaper.set_wallpaper")
    def test_006_wallpaper_set_failure(self, mock_set_wp):
        """DE command failure returns 1 but still saves the PNG."""
        rgba = b"\xff\x00\x00\xff" * 4
        self.app.expected_service_calls[("vm", "qubes.GetImageRGBA")] = (
            _make_service_response(2, 2, rgba)
        )
        mock_set_wp.side_effect = FileNotFoundError("xfconf-query not found")
        ret = qubesadmin.tools.qvm_set_wallpaper.main(
            ["vm", "/path/img.jpg", "--output", self.output_path],
            app=self.app,
        )
        self.assertEqual(ret, 1)
        # File should still be saved
        self.assertTrue(os.path.exists(self.output_path))


class TC_02_set_wallpaper(qubesadmin.tests.QubesTestCase):

    @patch("subprocess.run")
    @patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "XFCE"})
    def test_000_xfce(self, mock_run):
        """XFCE: sets all /last-image xfconf properties."""
        mock_run.return_value = MagicMock(
            stdout="/backdrop/screen0/monitor0/workspace0/last-image\n"
            "/backdrop/screen0/monitor1/workspace0/last-image\n",
        )
        qubesadmin.tools.qvm_set_wallpaper.set_wallpaper("/tmp/wp.png")
        # First call: list properties
        mock_run.assert_any_call(
            ["xfconf-query", "-c", "xfce4-desktop", "-l"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Should set both monitors
        mock_run.assert_any_call(
            [
                "xfconf-query",
                "-c",
                "xfce4-desktop",
                "-p",
                "/backdrop/screen0/monitor0/workspace0/last-image",
                "-s",
                "/tmp/wp.png",
            ],
            check=True,
        )
        mock_run.assert_any_call(
            [
                "xfconf-query",
                "-c",
                "xfce4-desktop",
                "-p",
                "/backdrop/screen0/monitor1/workspace0/last-image",
                "-s",
                "/tmp/wp.png",
            ],
            check=True,
        )

    @patch("subprocess.run")
    @patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "GNOME"})
    def test_001_gnome(self, mock_run):
        """GNOME: sets picture-uri via gsettings."""
        qubesadmin.tools.qvm_set_wallpaper.set_wallpaper("/tmp/wp.png")
        mock_run.assert_called_once_with(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.background",
                "picture-uri",
                "file:///tmp/wp.png",
            ],
            check=True,
        )

    @patch("subprocess.run")
    @patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE"})
    def test_002_kde(self, mock_run):
        """KDE: calls plasma-apply-wallpaperimage."""
        qubesadmin.tools.qvm_set_wallpaper.set_wallpaper("/tmp/wp.png")
        mock_run.assert_called_once_with(
            ["plasma-apply-wallpaperimage", "/tmp/wp.png"],
            check=True,
        )

    @patch("subprocess.run")
    @patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": ""})
    def test_003_unknown_de(self, mock_run):
        """Unknown DE: logs warning, no subprocess calls."""
        qubesadmin.tools.qvm_set_wallpaper.set_wallpaper("/tmp/wp.png")
        mock_run.assert_not_called()
