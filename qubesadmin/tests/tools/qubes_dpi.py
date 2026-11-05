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

# pylint: disable=missing-docstring

from unittest import mock

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qubes_dpi


class TC_00_qubes_dpi(qubesadmin.tests.QubesTestCase):
    @mock.patch('subprocess.run')
    def test_000_no_args(self, mock_run):
        self.assertEqual(
            qubesadmin.tools.qubes_dpi.main([], app=self.app), 0)
        mock_run.assert_not_called()
        self.assertAllCalled()

    @mock.patch.dict('os.environ', {'XDG_CURRENT_DESKTOP': 'XFCE'})
    @mock.patch('qubesadmin.tools.qubes_dpi.set_dom0_scale_factor')
    @mock.patch('subprocess.run')
    def test_001_set_scale_xfce(self, mock_run, mock_set_dom0_scale_factor):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n'
        self.app.expected_calls[
            ('dom0', 'admin.vm.feature.Set', 'dpi.scale', b'2')] = b'0\x00'
        self.assertEqual(
            qubesadmin.tools.qubes_dpi.main(['--scale', '2'], app=self.app),
            0)
        mock_set_dom0_scale_factor.assert_called_once_with(
            2, cursor=False, theme=False)
        self.assertEqual(mock_run.mock_calls, [
            mock.call(['/usr/bin/qvm-start-gui', '--notify-monitor-layout',
                       '--all'], check=True),
            mock.call(['/usr/bin/xfce4-panel', '-r'], check=True),
        ])
        self.assertAllCalled()

    @mock.patch.dict('os.environ', {'XDG_CURRENT_DESKTOP': 'KDE'})
    @mock.patch('qubesadmin.tools.qubes_dpi.set_dom0_scale_factor')
    @mock.patch('subprocess.run')
    def test_002_set_scale_other_desktop(self, mock_run,
                                         mock_set_dom0_scale_factor):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n'
        self.app.expected_calls[
            ('dom0', 'admin.vm.feature.Set', 'dpi.scale', b'1')] = b'0\x00'
        self.assertEqual(
            qubesadmin.tools.qubes_dpi.main(['-s', '1'], app=self.app),
            0)
        mock_set_dom0_scale_factor.assert_called_once_with(
            1, cursor=False, theme=False)
        mock_run.assert_called_once_with(
            ['/usr/bin/qvm-start-gui', '--notify-monitor-layout', '--all'],
            check=True)
        self.assertAllCalled()

    def test_003_invalid_scale(self):
        with qubesadmin.tests.tools.StderrBuffer():
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qubes_dpi.main(['--scale', '3'],
                    app=self.app)
        self.assertAllCalled()

    @mock.patch.dict('os.environ', {'XDG_CURRENT_DESKTOP': 'KDE'})
    @mock.patch('qubesadmin.tools.qubes_dpi.set_dom0_scale_factor')
    @mock.patch('subprocess.run')
    def test_004_set_scale_cursor_theme(self, _, mock_set_dom0_scale_factor):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00dom0 class=AdminVM state=Running\n'
        self.app.expected_calls[
            ('dom0', 'admin.vm.feature.Set', 'dpi.scale', b'2')] = b'0\x00'
        self.assertEqual(
            qubesadmin.tools.qubes_dpi.main(
                ['--scale', '2', '--cursor', '--theme'], app=self.app),
            0)
        mock_set_dom0_scale_factor.assert_called_once_with(
            2, cursor=True, theme=True)
        self.assertAllCalled()

    def test_005_cursor_theme_without_scale(self):
        for flag in ('--cursor', '--theme'):
            with self.subTest(flag=flag):
                with qubesadmin.tests.tools.StderrBuffer() as stderr:
                    with self.assertRaises(SystemExit):
                        qubesadmin.tools.qubes_dpi.main([flag], app=self.app)
                self.assertIn('require --scale', stderr.getvalue())
        self.assertAllCalled()

    @staticmethod
    def _set_dom0_scale_factor(*args, **kwargs):
        """Run set_dom0_scale_factor with a mocked Xfconf, return the mock
        and a dict of the channels that were requested, by name"""
        xfconf = mock.Mock()
        channels = {}
        xfconf.Channel.get.side_effect = \
            lambda name: channels.setdefault(name, mock.Mock())
        with mock.patch('gi.require_version'), \
                mock.patch.dict('sys.modules',
                                {'gi.repository': mock.Mock(Xfconf=xfconf)}):
            qubesadmin.tools.qubes_dpi.set_dom0_scale_factor(*args, **kwargs)
        return xfconf, channels

    def test_010_dom0_scale_factor(self):
        xfconf, channels = self._set_dom0_scale_factor(2)
        xfconf.init.assert_called_once_with()
        self.assertEqual(list(channels), ['xsettings'])
        self.assertEqual(channels['xsettings'].set_int.mock_calls, [
            mock.call('/Gdk/WindowScalingFactor', 2),
            mock.call('/Gdk/UnscaledDPI', 96 * 1024),
            mock.call('/Xft/DPI', 192),
        ])

    def test_012_dom0_cursor_size(self):
        for scale, size in ((1, 32), (2, 48)):
            with self.subTest(scale=scale):
                _, channels = self._set_dom0_scale_factor(scale, cursor=True)
                self.assertEqual(list(channels), ['xsettings'])
                self.assertEqual(channels['xsettings'].set_int.mock_calls, [
                    mock.call('/Gdk/WindowScalingFactor', scale),
                    mock.call('/Gdk/UnscaledDPI', 96 * 1024),
                    mock.call('/Xft/DPI', 96 * scale),
                    mock.call('/Gtk/CursorThemeSize', size),
                ])

    def test_013_dom0_theme(self):
        for scale, theme in ((1, 'Default'), (2, 'Default-xhdpi')):
            with self.subTest(scale=scale):
                _, channels = self._set_dom0_scale_factor(scale, theme=True)
                self.assertEqual(list(channels), ['xsettings', 'xfwm4'])
                self.assertNotIn(
                    mock.call('/Gtk/CursorThemeSize', mock.ANY),
                    channels['xsettings'].set_int.mock_calls)
                channels['xfwm4'].set_string.assert_called_once_with(
                    '/general/theme', theme)

    @mock.patch('gi.require_version', side_effect=ValueError)
    def test_011_dom0_scale_factor_no_xfconf(self, _):
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            qubesadmin.tools.qubes_dpi.set_dom0_scale_factor(2)
        self.assertIn('Xfconfig not available', stderr.getvalue())
