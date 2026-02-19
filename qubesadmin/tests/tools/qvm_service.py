#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
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

import sys
import unittest

import qubesadmin.tests
import qubesadmin.tools.qvm_service


class TC_00_qvm_service(qubesadmin.tests.QubesTestCase):
    def test_000_list(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.List', None, None)] = \
            b'0\x00feature1\nservice.service1\nservice.service2\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Get', 'service.service1', None)] = \
            b'0\x00value1'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Get', 'service.service2', None)] = \
            b'0\x00'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_service.main(['some-vm'], app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'service1  on\n'
                'service2  off\n')
        self.assertAllCalled()

    def test_001_list_l(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.List', None, None)] = \
            b'0\x00feature1\nservice.service1\nservice.service2\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Get', 'service.service1', None)] = \
            b'0\x00value1'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Get', 'service.service2', None)] = \
            b'0\x00'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_service.main(['-l', 'some-vm'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'service1  on\n'
                'service2  off\n')
        self.assertAllCalled()

    def test_002_enable(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Set',
             'service.service1', b'1')] = b'0\x00'
        self.assertEqual(
            qubesadmin.tools.qvm_service.main(['some-vm', 'service1',
                'on'],
                app=self.app),
            0)
        self.assertAllCalled()

    def test_003_enable_opt(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Set',
             'service.service1', b'1')] = b'0\x00'
        self.assertEqual(
            qubesadmin.tools.qvm_service.main(['--enable', 'some-vm',
                'service1'],
                app=self.app),
            0)
        self.assertAllCalled()

    @unittest.skipIf(sys.version_info.minor < 13, reason="argparse bug")
    def test_004_enable_opt_mixed(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Set',
             'service.service1', b'1')] = b'0\x00'
        with self.assertNotRaises(SystemExit):
            self.assertEqual(
                qubesadmin.tools.qvm_service.main(
                    ['some-vm', '--enable', 'service1'],
                    app=self.app),
                0)
        self.assertAllCalled()

    @unittest.skipIf(
        sys.version_info.minor >= 13, reason="argparse works correctly"
    )
    def test_004_enable_opt_mixed_broken(self):
        with self.assertRaises(SystemExit):
            self.assertEqual(
                qubesadmin.tools.qvm_service.main(
                    ['some-vm', '--enable', 'service1'],
                    app=self.app),
                0)
        self.assertAllCalled()

    def test_005_disable(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Set',
             'service.service1', b'')] = b'0\x00'
        self.assertEqual(
            qubesadmin.tools.qvm_service.main(
                ['some-vm', 'service1', 'off'],
                app=self.app),
            0)
        self.assertAllCalled()

    def test_006_disable_opt(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Set',
             'service.service1', b'')] = b'0\x00'
        with self.assertNotRaises(SystemExit):
            self.assertEqual(
                qubesadmin.tools.qvm_service.main(
                    ['--disable', 'some-vm', 'service1'],
                    app=self.app),
                0)
        self.assertAllCalled()

    def test_007_get(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Get', 'service.service3', None)] = \
            b'0\x00value2 with spaces'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_service.main(['some-vm', 'service3'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'on\n')
        self.assertAllCalled()

    def test_008_del(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Remove', 'service.srv4', None)] = \
            b'0\x00'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_service.main(
                    ['--unset', 'some-vm', 'srv4'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                '')
        self.assertAllCalled()

    def test_009_del_legacy(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.feature.Remove', 'service.srv4', None)] = \
            b'0\x00'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_service.main(
                    ['--default', 'some-vm', 'srv4'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                '')
        self.assertAllCalled()

    def test_010_set_invalid(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_service.main(
                ['some-vm', 'service1', 'invalid-value'],
                app=self.app)
        self.assertAllCalled()
