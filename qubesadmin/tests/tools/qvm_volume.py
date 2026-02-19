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

import tempfile
import unittest.mock

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_volume


class TC_00_qvm_volume(qubesadmin.tests.QubesTestCase):

    def setup_expected_calls_for_list(self, vms=('vm1', 'sys-net')):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n' \
            b'sys-net class=AppVM state=Running\n'
        for vm in vms:
            for vol in ('root', 'private'):
                self.app.expected_calls[
                    (vm, 'admin.vm.volume.Info', vol, None)] = \
                    b'0\x00' + \
                    (b'pool=pool-file\n' if vol == 'root' else
                        b'pool=other-pool\n') + \
                    b'vid=' + vm.encode() + b'-' + vol.encode() + b'\n' \
                    b'size=10737418240\n'
                self.app.expected_calls[
                    (vm, 'admin.vm.volume.ListSnapshots', vol, None)] = \
                    b'0\x00snap1\n' if vol == 'private' else b'0\x00'
            self.app.expected_calls[
                (vm, 'admin.vm.volume.List', None, None)] = \
                b'0\x00root\nprivate\n'

    def test_000_list(self):
        self.setup_expected_calls_for_list()
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(['ls'], app=self.app))
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
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(['ls', 'vm1'],
                    app=self.app))
        self.assertEqual(stdout.getvalue(),
            'POOL:VOLUME             VMNAME  VOLUME_NAME  REVERT_POSSIBLE\n'
            'other-pool:vm1-private  vm1     private      Yes\n'
            'pool-file:vm1-root      vm1     root         No\n'
            )
        self.assertAllCalled()

    def test_002_list_domain_pool(self):
        self.setup_expected_calls_for_list(vms=('vm1',))
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00pool-file\nother-pool\n'
        del self.app.expected_calls[
            ('vm1', 'admin.vm.volume.ListSnapshots', 'private', None)]
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(
                    ['ls', '-p', 'pool-file', 'vm1'],
                    app=self.app))
        self.assertEqual(stdout.getvalue(),
            'POOL:VOLUME         VMNAME  VOLUME_NAME  REVERT_POSSIBLE\n'
            'pool-file:vm1-root  vm1     root         No\n'
        )
        self.assertAllCalled()

    def test_003_list_pool(self):
        self.setup_expected_calls_for_list()
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00pool-file\nother-pool\n'
        del self.app.expected_calls[
            ('vm1', 'admin.vm.volume.ListSnapshots', 'private', None)]
        del self.app.expected_calls[
            ('sys-net', 'admin.vm.volume.ListSnapshots', 'private', None)]

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(
                    ['ls', '-p', 'pool-file'],
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
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n' \
            b'vm2 class=AppVM state=Running\n' \
            b'vm3 class=AppVM state=Running\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(
                    ['ls', 'vm1', 'vm2'], app=self.app))
        self.assertEqual(stdout.getvalue(),
            'POOL:VOLUME             VMNAME  VOLUME_NAME  REVERT_POSSIBLE\n'
            'other-pool:vm1-private  vm1     private      Yes\n'
            'other-pool:vm2-private  vm2     private      Yes\n'
            'pool-file:vm1-root      vm1     root         No\n'
            'pool-file:vm2-root      vm2     root         No\n'
            )
        self.assertAllCalled()

    def test_005_list_default_action(self):
        self.setup_expected_calls_for_list()
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main([], app=self.app))
        self.assertEqual(stdout.getvalue(),
            'POOL:VOLUME                 VMNAME   VOLUME_NAME  '
            'REVERT_POSSIBLE\n'
            'other-pool:sys-net-private  sys-net  private      Yes\n'
            'other-pool:vm1-private      vm1      private      Yes\n'
            'pool-file:sys-net-root      sys-net  root         No\n'
            'pool-file:vm1-root          vm1      root         No\n'
            )
        self.assertAllCalled()

    def test_010_extend(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Info', 'private', None)] = \
            b'0\x00pool=lvm\n' \
            b'vid=qubes_dom0/vm-testvm-private\n' \
            b'size=2147483648\n' \
            b'usage=10000000\n' \
            b'rw=True\n' \
            b'source=\n' \
            b'save_on_stop=True\n' \
            b'snap_on_start=False\n' \
            b'revisions_to_keep=3\n' \
            b'is_outdated=False\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Resize', 'private', b'10737418240')] = \
            b'0\x00'
        self.assertEqual(0,
            qubesadmin.tools.qvm_volume.main(
                ['extend', 'testvm:private', '10GiB'],
                app=self.app))
        self.assertAllCalled()

    def test_011_extend_error(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Info', 'private', None)] = \
            b'0\x00pool=lvm\n' \
            b'vid=qubes_dom0/vm-testvm-private\n' \
            b'size=2147483648\n' \
            b'usage=10000000\n' \
            b'rw=True\n' \
            b'source=\n' \
            b'save_on_stop=True\n' \
            b'snap_on_start=False\n' \
            b'revisions_to_keep=3\n' \
            b'is_outdated=False\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Resize', 'private', b'10737418240')] = \
            b'2\x00StoragePoolException\x00\x00Failed to resize volume: ' \
            b'error: success\x00'
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            self.assertEqual(1,
                qubesadmin.tools.qvm_volume.main(
                    ['extend', 'testvm:private', '10GiB'],
                    app=self.app))
        self.assertIn('error: success', stderr.getvalue())
        self.assertAllCalled()

    def test_012_extend_deny_shrink(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Info', 'private', None)] = \
            b'0\x00pool=lvm\n' \
            b'vid=qubes_dom0/vm-testvm-private\n' \
            b'size=2147483648\n' \
            b'usage=10000000\n' \
            b'rw=True\n' \
            b'source=\n' \
            b'save_on_stop=True\n' \
            b'snap_on_start=False\n' \
            b'revisions_to_keep=3\n' \
            b'is_outdated=False\n'
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            self.assertEqual(1,
                qubesadmin.tools.qvm_volume.main(
                    ['resize', 'testvm:private', '1GiB'],
                    app=self.app))
        self.assertIn('shrinking of private is disabled', stderr.getvalue())
        self.assertAllCalled()

    def test_013_resize_force_shrink(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Resize', 'private', b'1073741824')] = \
            b'0\x00'
        self.assertEqual(0,
            qubesadmin.tools.qvm_volume.main(
                ['resize', '-f', 'testvm:private', '1GiB'],
                app=self.app))
        self.assertAllCalled()

    def test_020_revert(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ListSnapshots', 'private', None)] = \
            b'0\x00200101010000\n200201010000\n200301010000\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Revert', 'private',
             b'200301010000')] = b'0\x00'
        self.assertEqual(0,
            qubesadmin.tools.qvm_volume.main(
                ['revert', 'testvm:private'],
                app=self.app))
        self.assertAllCalled()

    def test_021_revert_error(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ListSnapshots', 'private', None)] = \
            b'0\x00200101010000\n200201010000\n200301010000\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Revert', 'private',
             b'200301010000')] = \
            b'2\x00StoragePoolException\x00\x00Failed to revert volume: ' \
            b'some error\x00'
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            self.assertEqual(1,
                qubesadmin.tools.qvm_volume.main(
                    ['revert', 'testvm:private'],
                    app=self.app))
        self.assertIn('some error', stderr.getvalue())
        self.assertAllCalled()

    def test_022_revert_no_snapshots(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ListSnapshots', 'private', None)] = \
            b'0\x00'
        with qubesadmin.tests.tools.StderrBuffer() as stderr:
            self.assertEqual(1,
                qubesadmin.tools.qvm_volume.main(
                    ['revert', 'testvm:private'],
                    app=self.app))
        self.assertIn('No snapshots', stderr.getvalue())
        self.assertAllCalled()

    def test_023_revert_specific(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Revert', 'private', b'20050101')] = \
            b'0\x00'
        self.assertEqual(0,
            qubesadmin.tools.qvm_volume.main(
                ['revert', 'testvm:private', '20050101'],
                app=self.app))
        self.assertAllCalled()

    def test_030_set_revisions_to_keep(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Set.revisions_to_keep', 'private',
            b'3')] = b'0\x00'
        self.assertEqual(0,
            qubesadmin.tools.qvm_volume.main(
                ['set', 'testvm:private', 'revisions_to_keep', '3'],
                app=self.app))
        self.assertAllCalled()

    def test_031_set_rw(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Set.rw', 'private',
            b'True')] = b'0\x00'
        self.assertEqual(0,
            qubesadmin.tools.qvm_volume.main(
                ['set', 'testvm:private', 'rw', 'True'],
                app=self.app))
        self.assertAllCalled()

    def test_032_set_invalid(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.assertNotEqual(0,
            qubesadmin.tools.qvm_volume.main(
                ['set', 'testvm:private', 'invalid', 'True'],
                app=self.app))
        self.assertAllCalled()

    def test_033_set_ephemeral(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\nvolatile\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Set.ephemeral', 'volatile',
            b'True')] = b'0\x00'
        self.assertEqual(0,
            qubesadmin.tools.qvm_volume.main(
                ['set', 'testvm:volatile', 'ephemeral', 'True'],
                app=self.app))
        self.assertAllCalled()

    def test_040_info(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Info', 'private', None)] = \
            b'0\x00pool=lvm\n' \
            b'vid=qubes_dom0/vm-testvm-private\n' \
            b'size=2147483648\n' \
            b'usage=10000000\n' \
            b'rw=True\n' \
            b'source=\n' \
            b'save_on_stop=True\n' \
            b'snap_on_start=False\n' \
            b'revisions_to_keep=-1\n' \
            b'ephemeral=False\n' \
            b'is_outdated=False\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ListSnapshots', 'private', None)] = \
            b'0\x00200101010000\n200201010000\n200301010000\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(['info', 'testvm:private'],
                    app=self.app))
        output = stdout.getvalue()
        # travis...
        output = output.replace('\nsource\n', '\nsource             \n')
        self.assertEqual(output,
            'pool               lvm\n'
            'vid                qubes_dom0/vm-testvm-private\n'
            'rw                 True\n'
            'source             \n'
            'save_on_stop       True\n'
            'snap_on_start      False\n'
            'size               2147483648\n'
            'usage              10000000\n'
            'revisions_to_keep  -1 (snapshot disabled)\n'
            'ephemeral          False\n'
            'is_outdated        False\n'
            'List of available revisions (for revert):\n'
            '  200101010000\n'
            '  200201010000\n'
            '  200301010000\n')
        self.assertAllCalled()

    def test_041_info_no_revisions(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Info', 'root', None)] = \
            b'0\x00pool=lvm\n' \
            b'vid=qubes_dom0/vm-testvm-root\n' \
            b'size=2147483648\n' \
            b'usage=10000000\n' \
            b'rw=True\n' \
            b'source=qubes_dom0/vm-fedora-26-root\n' \
            b'save_on_stop=False\n' \
            b'snap_on_start=True\n' \
            b'revisions_to_keep=0\n' \
            b'ephemeral=True\n' \
            b'is_outdated=False\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ListSnapshots', 'root', None)] = \
            b'0\x00'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(['info', 'testvm:root'],
                    app=self.app))
        self.assertEqual(stdout.getvalue(),
            'pool               lvm\n'
            'vid                qubes_dom0/vm-testvm-root\n'
            'rw                 True\n'
            'source             qubes_dom0/vm-fedora-26-root\n'
            'save_on_stop       False\n'
            'snap_on_start      True\n'
            'size               2147483648\n'
            'usage              10000000\n'
            'revisions_to_keep  0\n'
            'ephemeral          True\n'
            'is_outdated        False\n'
            'List of available revisions (for revert): none\n')
        self.assertAllCalled()

    def test_042_info_single_prop(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Info', 'root', None)] = \
            b'0\x00pool=lvm\n' \
            b'vid=qubes_dom0/vm-testvm-root\n' \
            b'size=2147483648\n' \
            b'usage=10000000\n' \
            b'rw=True\n' \
            b'source=qubes_dom0/vm-fedora-26-root\n' \
            b'save_on_stop=False\n' \
            b'snap_on_start=True\n' \
            b'revisions_to_keep=0\n' \
            b'is_outdated=False\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(
                    ['info', 'testvm:root', 'usage'],
                    app=self.app))
        self.assertEqual(stdout.getvalue(), '10000000\n')
        self.assertAllCalled()

    def test_043_info_revisions_only(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ListSnapshots', 'private', None)] = \
            b'0\x00200101010000\n200201010000\n200301010000\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(
                    ['info', 'testvm:private', 'revisions'],
                    app=self.app))
        self.assertEqual(stdout.getvalue(),
            '200101010000\n'
            '200201010000\n'
            '200301010000\n')
        self.assertAllCalled()

    def test_044_info_no_ephemeral(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Info', 'private', None)] = \
            b'0\x00pool=lvm\n' \
            b'vid=qubes_dom0/vm-testvm-private\n' \
            b'size=2147483648\n' \
            b'usage=10000000\n' \
            b'rw=True\n' \
            b'source=\n' \
            b'save_on_stop=True\n' \
            b'snap_on_start=False\n' \
            b'revisions_to_keep=3\n' \
            b'is_outdated=False\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ListSnapshots', 'private', None)] = \
            b'0\x00200101010000\n200201010000\n200301010000\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(['info', 'testvm:private'],
                    app=self.app))
        output = stdout.getvalue()
        # travis...
        output = output.replace('\nsource\n', '\nsource             \n')
        self.assertEqual(output,
            'pool               lvm\n'
            'vid                qubes_dom0/vm-testvm-private\n'
            'rw                 True\n'
            'source             \n'
            'save_on_stop       True\n'
            'snap_on_start      False\n'
            'size               2147483648\n'
            'usage              10000000\n'
            'revisions_to_keep  3\n'
            'ephemeral          False\n'
            'is_outdated        False\n'
            'List of available revisions (for revert):\n'
            '  200101010000\n'
            '  200201010000\n'
            '  200301010000\n')
        self.assertAllCalled()

    def test_050_import_file(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ImportWithSize', 'private',
             b'9\ntest-data')] = b'0\x00'
        with tempfile.NamedTemporaryFile() as input_file:
            input_file.write(b'test-data')
            input_file.seek(0)
            input_file.flush()
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(
                    ['import', 'testvm:private', input_file.name],
                    app=self.app))
        self.assertAllCalled()

    def test_051_import_stdin(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ImportWithSize', 'private',
             b'9\ntest-data')] =  b'0\x00'
        with tempfile.NamedTemporaryFile() as input_file:
            input_file.write(b'test-data')
            input_file.seek(0)
            with unittest.mock.patch('sys.stdin') as mock_stdin:
                mock_stdin.buffer = input_file
                self.assertEqual(0,
                    qubesadmin.tools.qvm_volume.main(
                        ['import', 'testvm:private', '-'],
                        app=self.app))
        self.assertAllCalled()

    def test_052_import_file_size(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ImportWithSize', 'private',
             b'512\ntest-data')] = b'0\x00'
        with tempfile.NamedTemporaryFile() as input_file:
            input_file.write(b'test-data')
            input_file.seek(0)
            input_file.flush()
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(
                    ['import', '--size=512', 'testvm:private', input_file.name],
                    app=self.app))
        self.assertAllCalled()

    def test_053_import_file_noresize(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.Import', 'private', b'test-data')] = \
            b'0\x00'
        with tempfile.NamedTemporaryFile() as input_file:
            input_file.write(b'test-data')
            input_file.seek(0)
            input_file.flush()
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(
                    ['import', '--no-resize', 'testvm:private',
                     input_file.name],
                    app=self.app))
        self.assertAllCalled()

    def test_053_import_file_matching_size(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00testvm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\n'
        self.app.expected_calls[
            ('testvm', 'admin.vm.volume.ImportWithSize', 'private',
             b'9\ntest-data')] = b'0\x00'
        with tempfile.NamedTemporaryFile() as input_file:
            input_file.write(b'test-data')
            input_file.seek(0)
            input_file.flush()
            self.assertEqual(0,
                qubesadmin.tools.qvm_volume.main(
                    ['import', 'testvm:private', input_file.name],
                    app=self.app))
        self.assertAllCalled()
