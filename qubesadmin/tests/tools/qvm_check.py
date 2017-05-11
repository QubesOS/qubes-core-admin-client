# -*- encoding: utf8 -*-
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

import qubesadmin.tests
import qubesadmin.tools.qvm_check

class TC_00_qvm_check(qubesadmin.tests.QubesTestCase):
    def test_000_exists(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.assertEqual(
            qubesadmin.tools.qvm_check.main(['some-vm'], app=self.app),
            0)
        self.assertAllCalled()

    def test_001_exists_multi(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        self.assertEqual(
            qubesadmin.tools.qvm_check.main(['some-vm', 'other-vm'],
                app=self.app),
            0)
        self.assertAllCalled()

    def test_002_exists_verbose(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_check.main(['some-vm'], app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'VM some-vm exists\n')
        self.assertAllCalled()

    def test_003_exists_multi_verbose(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'other-vm class=AppVM state=Running\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_check.main(['some-vm', 'other-vm'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'VMs other-vm, some-vm exist\n')
        self.assertAllCalled()

    def test_004_running_verbose(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'some-vm2 class=AppVM state=Running\n' \
            b'some-vm3 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('some-vm', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_check.main(['--running',
                    'some-vm'], app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'VM some-vm is running\n')
        self.assertAllCalled()

    def test_005_running_multi_verbose(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'some-vm2 class=AppVM state=Running\n' \
            b'some-vm3 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('some-vm', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm2', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm2 class=AppVM state=Running\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_check.main(['--running',
                    'some-vm', 'some-vm2'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'VMs some-vm, some-vm2 are running\n')
        self.assertAllCalled()

    def test_006_running_multi_verbose2(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'some-vm2 class=AppVM state=Running\n' \
            b'some-vm3 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('some-vm', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm2', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm2 class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm3', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm3 class=AppVM state=Halted\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_check.main(['--running',
                    '--all'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'VMs some-vm, some-vm2 are running\n')
        self.assertAllCalled()

    def test_007_not_running_verbose(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'some-vm2 class=AppVM state=Running\n' \
            b'some-vm3 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('some-vm3', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm3 class=AppVM state=Halted\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_check.main(['--running',
                    'some-vm3'],
                    app=self.app),
                1)
            self.assertEqual(stdout.getvalue(),
                'None of given VM is running\n')
        self.assertAllCalled()

    def test_008_paused(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'some-vm2 class=AppVM state=Paused\n' \
            b'some-vm3 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('some-vm2', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm2 class=AppVM state=Paused\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_check.main(['--paused',
                    'some-vm2'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'VM some-vm2 is paused\n')
        self.assertAllCalled()

    def test_009_paused_multi(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'some-vm2 class=AppVM state=Paused\n' \
            b'some-vm3 class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('some-vm2', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm2 class=AppVM state=Paused\n'
        self.app.expected_calls[
            ('some-vm', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_check.main(['--paused',
                    'some-vm2', 'some-vm'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'VM some-vm2 is paused\n')
        self.assertAllCalled()


    def test_010_template(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'some-vm2 class=AppVM state=Paused\n' \
            b'some-vm3 class=TemplateVM state=Halted\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_check.main(['--template',
                    'some-vm3'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'VM some-vm3 is a template\n')
        self.assertAllCalled()

    def test_011_template_multi(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n' \
            b'some-vm2 class=AppVM state=Paused\n' \
            b'some-vm3 class=TemplateVM state=Halted\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(
                qubesadmin.tools.qvm_check.main(['--template',
                    'some-vm2', 'some-vm3'],
                    app=self.app),
                0)
            self.assertEqual(stdout.getvalue(),
                'VM some-vm3 is a template\n')
        self.assertAllCalled()

