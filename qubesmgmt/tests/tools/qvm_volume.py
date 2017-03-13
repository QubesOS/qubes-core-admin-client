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
import qubesmgmt.tools.qvm_volume


class TC_00_qvm_volume(qubesmgmt.tests.QubesTestCase):

    def setup_expected_calls_for_list(self, vms=('vm1', 'sys-net')):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n' \
            b'sys-net class=AppVM state=Running\n'
        for vm in vms:
            for vol in ('root', 'private'):
                self.app.expected_calls[
                    (vm, 'mgmt.vm.volume.Info', vol, None)] = \
                    b'0\x00' + \
                    (b'pool=pool-file\n' if vol == 'root' else
                        b'pool=other-pool\n') + \
                    b'vid=' + vm.encode() + b'-' + vol.encode() + b'\n' \
                    b'internal=True\n' \
                    b'size=10737418240\n'
                self.app.expected_calls[
                    (vm, 'mgmt.vm.volume.ListSnapshots', vol, None)] = \
                    b'0\x00snap1\n' if vol == 'private' else b'0\x00'
            self.app.expected_calls[
                (vm, 'mgmt.vm.volume.List', None, None)] = \
                b'0\x00root\nprivate\n'

    def test_000_list(self):
        self.setup_expected_calls_for_list()
        with qubesmgmt.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesmgmt.tools.qvm_volume.main(['ls', '-i'], app=self.app))
        self.assertEqual(stdout.getvalue(),
            'POOL:VOLUME                 VMNAME   VOLUME_NAME  '
            'REVERT_POSSIBLE\n'
            'other-pool:sys-net-private  sys-net  private      Yes\n'
            'other-pool:vm1-private      vm1      private      Yes\n'
            'pool-file:sys-net-root      sys-net  root         No\n'
            'pool-file:vm1-root          vm1      root         No\n'
            )
        self.assertAllCalled()

    def test_001_list_domain(self):
        self.setup_expected_calls_for_list(vms=('vm1',))
        with qubesmgmt.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesmgmt.tools.qvm_volume.main(['ls', '-i', 'vm1'],
                    app=self.app))
        self.assertEqual(stdout.getvalue(),
            'POOL:VOLUME             VMNAME  VOLUME_NAME  REVERT_POSSIBLE\n'
            'other-pool:vm1-private  vm1     private      Yes\n'
            'pool-file:vm1-root      vm1     root         No\n'
            )
        self.assertAllCalled()

    def test_002_list_domain_pool(self):
        self.setup_expected_calls_for_list(vms=('vm1',))
        self.app.expected_calls[('dom0', 'mgmt.pool.List', None, None)] = \
            b'0\x00pool-file\nother-pool\n'
        del self.app.expected_calls[
            ('vm1', 'mgmt.vm.volume.ListSnapshots', 'private', None)]
        with qubesmgmt.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesmgmt.tools.qvm_volume.main(
                    ['ls', '-i', '-p', 'pool-file', 'vm1'],
                    app=self.app))
        self.assertEqual(stdout.getvalue(),
            'POOL:VOLUME         VMNAME  VOLUME_NAME  REVERT_POSSIBLE\n'
            'pool-file:vm1-root  vm1     root         No\n'
        )
        self.assertAllCalled()

    def test_003_list_pool(self):
        self.setup_expected_calls_for_list()
        self.app.expected_calls[('dom0', 'mgmt.pool.List', None, None)] = \
            b'0\x00pool-file\nother-pool\n'
        del self.app.expected_calls[
            ('vm1', 'mgmt.vm.volume.ListSnapshots', 'private', None)]
        del self.app.expected_calls[
            ('sys-net', 'mgmt.vm.volume.ListSnapshots', 'private', None)]

        with qubesmgmt.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesmgmt.tools.qvm_volume.main(
                    ['ls', '-i', '-p', 'pool-file'],
                    app=self.app))
        self.assertEqual(stdout.getvalue(),
            'POOL:VOLUME             VMNAME   VOLUME_NAME  REVERT_POSSIBLE\n'
            'pool-file:sys-net-root  sys-net  root         No\n'
            'pool-file:vm1-root      vm1      root         No\n'
            )
        self.assertAllCalled()

    def test_004_list_multiple_domains(self):
        self.setup_expected_calls_for_list(vms=('vm1', 'vm2'))
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n' \
            b'vm2 class=AppVM state=Running\n' \
            b'vm3 class=AppVM state=Running\n'
        with qubesmgmt.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesmgmt.tools.qvm_volume.main(
                    ['ls', '-i', 'vm1', 'vm2'], app=self.app))
        self.assertEqual(stdout.getvalue(),
            'POOL:VOLUME             VMNAME  VOLUME_NAME  REVERT_POSSIBLE\n'
            'other-pool:vm1-private  vm1     private      Yes\n'
            'other-pool:vm2-private  vm2     private      Yes\n'
            'pool-file:vm1-root      vm1     root         No\n'
            'pool-file:vm2-root      vm2     root         No\n'
            )
        self.assertAllCalled()

    def test_010_extend(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'mgmt.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'mgmt.vm.volume.Resize', 'private', b'10737418240')] = \
            b'0\x00'
        self.assertEqual(0,
            qubesmgmt.tools.qvm_volume.main(
                ['extend', 'testvm:private', '10GiB'],
                app=self.app))
        self.assertAllCalled()

    def test_011_extend_error(self):
        self.app.expected_calls[('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'mgmt.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'mgmt.vm.volume.Resize', 'private', b'1073741824')] = \
            b'2\x00StoragePoolException\x00\x00Failed to resize volume: ' \
            b'shrink not allowed\x00'
        with qubesmgmt.tests.tools.StderrBuffer() as stderr:
            self.assertEqual(1,
                qubesmgmt.tools.qvm_volume.main(
                    ['extend', 'testvm:private', '1GiB'],
                    app=self.app))
        self.assertIn('shrink not allowed', stderr.getvalue())
        self.assertAllCalled()
