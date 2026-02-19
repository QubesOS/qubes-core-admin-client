#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

# pylint: disable=missing-docstring

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_tags


class TC_00_qvm_tags(qubesadmin.tests.QubesTestCase):
    def test_000_list(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.tag.List', None, None)] = \
            b'0\x00tag1\ntag2\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_tags.main(['some-vm'], app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'tag1\n'
                'tag2\n')
        self.assertAllCalled()

    def test_001_list_action(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.tag.List', None, None)] = \
            b'0\x00tag1\ntag2\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_tags.main(['some-vm', 'list'],
                    app=self.app), 0)
            self.assertEqual(stdout.getvalue(),
                'tag1\n'
                'tag2\n')
        self.assertAllCalled()

    def test_002_list_alias(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.tag.List', None, None)] = \
            b'0\x00tag1\ntag2\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_tags.main(['some-vm', 'ls'],
                    app=self.app), 0)
            self.assertEqual(stdout.getvalue(),
                'tag1\n'
                'tag2\n')
        self.assertAllCalled()

    def test_003_list_check(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.tag.Get', 'tag1', None)] = \
            b'0\x001'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_tags.main(['some-vm', 'ls', 'tag1'],
                    app=self.app), 0)
            self.assertEqual(stdout.getvalue(), 'tag1\n')
        self.assertAllCalled()

    def test_004_list_check_missing(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.tag.Get', 'tag1', None)] = \
            b'0\x000'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_tags.main(['some-vm', 'ls', 'tag1'],
                    app=self.app), 1)
            self.assertEqual(stdout.getvalue(), '')
        self.assertAllCalled()

    def test_005_list_empty(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.tag.List', None, None)] = \
            b'0\x00'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_tags.main(['some-vm', 'list'],
                    app=self.app), 0)
            self.assertEqual(stdout.getvalue(), '')
        self.assertAllCalled()

    def test_010_add(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.tag.Set', 'tag3', None)] = b'0\x00'
        self.assertEqual(
            qubesadmin.tools.qvm_tags.main(['some-vm', 'add', 'tag3'],
                app=self.app),
            0)
        self.assertAllCalled()

    def test_020_del(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.tag.Remove', 'tag3', None)] = b'0\x00'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_tags.main(['some-vm', 'del', 'tag3'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(), '')
        self.assertAllCalled()
