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
import qubesmgmt.storage


class TestVMVolume(qubesmgmt.tests.QubesTestCase):
    def setUp(self):
        super(TestVMVolume, self).setUp()
        self.vol = qubesmgmt.storage.Volume(self.app, vm='test-vm',
            vm_name='volname')
        self.pool_vol = qubesmgmt.storage.Volume(self.app, pool='test-pool',
            vid='some-id')

    def expect_info(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.volume.Info', 'volname', None)] = \
            b'0\x00' \
            b'pool=test-pool\n' \
            b'vid=some-id\n' \
            b'size=1024\n' \
            b'usage=512\n' \
            b'rw=True\n' \
            b'snap_on_start=True\n' \
            b'save_on_stop=True\n' \
            b'source=\n' \
            b'internal=True\n' \
            b'revisions_to_keep=3\n'

    def test_000_qubesd_call(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.volume.TestMethod', 'volname', None)] = \
            b'0\x00method_result'
        self.assertEqual(self.vol._qubesd_call('TestMethod'),
            b'method_result')
        self.assertAllCalled()

    def test_001_fetch_info(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.volume.Info', 'volname', None)] = \
            b'0\x00prop1=val1\nprop2=val2\n'
        self.vol._fetch_info()
        self.assertEqual(self.vol._info, {'prop1': 'val1', 'prop2': 'val2'})
        self.assertAllCalled()

    def test_010_pool(self):
        self.expect_info()
        self.assertEqual(self.vol.pool, 'test-pool')
        self.assertAllCalled()

    def test_011_vid(self):
        self.expect_info()
        self.assertEqual(self.vol.vid, 'some-id')
        self.assertAllCalled()

    def test_012_size(self):
        self.expect_info()
        self.assertEqual(self.vol.size, 1024)
        self.assertAllCalled()

    def test_013_usage(self):
        self.expect_info()
        self.assertEqual(self.vol.usage, 512)
        self.assertAllCalled()

    def test_014_rw(self):
        self.expect_info()
        self.assertEqual(self.vol.rw, True)
        self.assertAllCalled()

    def test_015_snap_on_start(self):
        self.expect_info()
        self.assertEqual(self.vol.snap_on_start, True)
        self.assertAllCalled()

    def test_016_save_on_stop(self):
        self.expect_info()
        self.assertEqual(self.vol.save_on_stop, True)
        self.assertAllCalled()

    def test_017_source_none(self):
        self.expect_info()
        self.assertEqual(self.vol.source, None)
        self.assertAllCalled()

    def test_018_source(self):
        self.expect_info()
        call_key = list(self.app.expected_calls)[0]
        self.app.expected_calls[call_key] = self.app.expected_calls[
            call_key].replace(b'source=\n', b'source=test-pool:other-id\n')
        self.assertEqual(self.vol.source, 'test-pool:other-id')
        self.assertAllCalled()

    def test_019_internal(self):
        self.expect_info()
        self.assertEqual(self.vol.internal, True)
        self.assertAllCalled()

    def test_020_revisions_to_keep(self):
        self.expect_info()
        self.assertEqual(self.vol.revisions_to_keep, 3)
        self.assertAllCalled()

    def test_021_revisions(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.volume.ListSnapshots', 'volname', None)] = \
            b'0\x00' \
            b'snapid1\n' \
            b'snapid2\n' \
            b'snapid3\n'
        self.assertEqual(self.vol.revisions,
            ['snapid1', 'snapid2', 'snapid3'])
        self.assertAllCalled()

    def test_022_revisions_empty(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.volume.ListSnapshots', 'volname', None)] = \
            b'0\x00'
        self.assertEqual(self.vol.revisions, [])
        self.assertAllCalled()

    def test_030_resize(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.volume.Resize', 'volname', b'2048')] = b'0\x00'
        self.vol.resize(2048)
        self.assertAllCalled()

    def test_031_revert(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.volume.Revert', 'volname', b'snapid1')] = \
            b'0\x00'
        self.vol.revert('snapid1')
        self.assertAllCalled()


class TestPoolVolume(TestVMVolume):
    def setUp(self):
        super(TestPoolVolume, self).setUp()
        self.vol = qubesmgmt.storage.Volume(self.app, pool='test-pool',
            vid='some-id')

    def test_000_qubesd_call(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.pool.volume.TestMethod',
            'test-pool', b'some-id')] = \
            b'0\x00method_result'
        self.assertEqual(self.vol._qubesd_call('TestMethod'),
            b'method_result')
        self.assertAllCalled()

    def expect_info(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.pool.volume.Info', 'test-pool', b'some-id')] = \
            b'0\x00' \
            b'pool=test-pool\n' \
            b'vid=some-id\n' \
            b'size=1024\n' \
            b'usage=512\n' \
            b'rw=True\n' \
            b'snap_on_start=True\n' \
            b'save_on_stop=True\n' \
            b'source=\n' \
            b'internal=True\n' \
            b'revisions_to_keep=3\n'

    def test_001_fetch_info(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.pool.volume.Info', 'test-pool',
            b'some-id')] = \
            b'0\x00prop1=val1\nprop2=val2\n'
        self.vol._fetch_info()
        self.assertEqual(self.vol._info, {'prop1': 'val1', 'prop2': 'val2'})
        self.assertAllCalled()

    def test_010_pool(self):
        # this should _not_ produce any api call, as pool is already known
        self.assertEqual(self.vol.pool, 'test-pool')
        self.assertAllCalled()

    def test_011_vid(self):
        # this should _not_ produce any api call, as vid is already known
        self.assertEqual(self.vol.vid, 'some-id')
        self.assertAllCalled()

    def test_021_revisions(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.pool.volume.ListSnapshots',
             'test-pool', b'some-id')] = \
            b'0\x00' \
            b'snapid1\n' \
            b'snapid2\n' \
            b'snapid3\n'
        self.assertEqual(self.vol.revisions,
            ['snapid1', 'snapid2', 'snapid3'])
        self.assertAllCalled()

    def test_022_revisions_empty(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.pool.volume.ListSnapshots',
            'test-pool', b'some-id')] = b'0\x00'
        self.assertEqual(self.vol.revisions, [])
        self.assertAllCalled()

    def test_030_resize(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.pool.volume.Resize',
            'test-pool', b'some-id 2048')] = b'0\x00'
        self.vol.resize(2048)
        self.assertAllCalled()

    def test_031_revert(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.pool.volume.Revert', 'test-pool',
            b'some-id snapid1')] = b'0\x00'
        self.vol.revert('snapid1')
        self.assertAllCalled()
