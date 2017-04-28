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
import qubesmgmt.tests
import qubesmgmt.tests.tools
import qubesmgmt.tools.qvm_clone


class TC_00_qvm_clone(qubesmgmt.tests.QubesTestCase):
    def test_000_simple(self):
        self.app.expected_calls[('test-vm', 'mgmt.vm.Clone', None,
            b'name=new-vm')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        qubesmgmt.tools.qvm_clone.main(['test-vm', 'new-vm'], app=self.app)
        self.assertAllCalled()

    def test_001_missing_vm(self):
        with self.assertRaises(SystemExit):
            with qubesmgmt.tests.tools.StderrBuffer() as stderr:
                qubesmgmt.tools.qvm_clone.main(['test-vm'], app=self.app)
        self.assertIn('NAME', stderr.getvalue())
        self.assertAllCalled()

    def test_004_pool(self):
        self.app.expected_calls[('test-vm', 'mgmt.vm.CloneInPool',
            None, b'name=new-vm pool=some-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        qubesmgmt.tools.qvm_clone.main(['-P', 'some-pool', 'test-vm', 'new-vm'],
            app=self.app)
        self.assertAllCalled()

    def test_005_pools(self):
        self.app.expected_calls[('test-vm', 'mgmt.vm.CloneInPool',
            None, b'name=new-vm pool:private=some-pool '
                  b'pool:volatile=other-pool')] = b'0\x00'
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00new-vm class=AppVM state=Halted\n' \
            b'test-vm class=AppVM state=Halted\n'
        qubesmgmt.tools.qvm_clone.main(['--pool', 'private=some-pool',
            '--pool', 'volatile=other-pool', 'test-vm', 'new-vm'],
            app=self.app)
        self.assertAllCalled()
