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

from unittest import mock
import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_clone


class TC_00_qvm_clone(qubesadmin.tests.QubesTestCase):
    def test_000_simple(self):
        self.app.clone_vm = mock.Mock()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        qubesadmin.tools.qvm_clone.main(['test-vm', 'new-vm'], app=self.app)
        self.app.clone_vm.assert_called_with(self.app.domains['test-vm'],
            'new-vm', new_cls=None, pool=None, pools={}, ignore_errors=False)
        self.assertAllCalled()

    def test_001_missing_vm(self):
        self.app.clone_vm = mock.Mock()
        with self.assertRaises(SystemExit):
            with qubesadmin.tests.tools.StderrBuffer() as stderr:
                qubesadmin.tools.qvm_clone.main(['test-vm'], app=self.app)
        self.assertIn('NAME', stderr.getvalue())
        self.assertFalse(self.app.clone_vm.called)
        self.assertAllCalled()

    def test_002_ignore_errors(self):
        self.app.clone_vm = mock.Mock()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'

        test_args = ['test-vm', 'new-vm', '--ignore-errors']
        qubesadmin.tools.qvm_clone.main(test_args, app=self.app)
        self.app.clone_vm.assert_called_with(self.app.domains['test-vm'],
            'new-vm', new_cls=None, pool=None, pools={},
            ignore_errors=True)
        self.assertAllCalled()

    def test_004_pool(self):
        self.app.clone_vm = mock.Mock()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        qubesadmin.tools.qvm_clone.main(
            ['-P', 'some-pool', 'test-vm', 'new-vm'],
            app=self.app)
        self.app.clone_vm.assert_called_with(self.app.domains['test-vm'],
            'new-vm', new_cls=None, pool='some-pool', pools={},
            ignore_errors=False)
        self.assertAllCalled()

    def test_005_pools(self):
        self.app.clone_vm = mock.Mock()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        qubesadmin.tools.qvm_clone.main(['--pool', 'private=some-pool',
            '--pool', 'volatile=other-pool', 'test-vm', 'new-vm'],
            app=self.app)
        self.app.clone_vm.assert_called_with(self.app.domains['test-vm'],
            'new-vm', new_cls=None, pool=None, pools={'private': 'some-pool',
                'volatile': 'other-pool'}, ignore_errors=False)
        self.assertAllCalled()

    def test_006_new_cls(self):
        self.app.clone_vm = mock.Mock()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        qubesadmin.tools.qvm_clone.main(['--class', 'StandaloneVM',
            'test-vm', 'new-vm'],
            app=self.app)
        self.app.clone_vm.assert_called_with(self.app.domains['test-vm'],
            'new-vm', new_cls='StandaloneVM', pool=None, pools={},
            ignore_errors=False)
        self.assertAllCalled()
