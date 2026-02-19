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

# pylint: disable=missing-docstring,protected-access

import subprocess

import qubesadmin.tests
import qubesadmin.storage


class TestVMVolume(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.vol = qubesadmin.storage.Volume(self.app, vm='test-vm',
            vm_name='volname')
        self.pool_vol = qubesadmin.storage.Volume(self.app, pool='test-pool',
            vid='some-id')

    def expect_info(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.Info', 'volname', None)] = \
            b'0\x00' \
            b'pool=test-pool\n' \
            b'vid=some-id\n' \
            b'size=1024\n' \
            b'usage=512\n' \
            b'rw=True\n' \
            b'snap_on_start=True\n' \
            b'save_on_stop=True\n' \
            b'source=\n' \
            b'revisions_to_keep=3\n'

    def test_000_qubesd_call(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.TestMethod', 'volname', None)] = \
            b'0\x00method_result'
        self.assertEqual(self.vol._qubesd_call('TestMethod'),
            b'method_result')
        self.assertAllCalled()

    def test_001_fetch_info(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.Info', 'volname', None)] = \
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

    def test_020_revisions_to_keep(self):
        self.expect_info()
        self.assertEqual(self.vol.revisions_to_keep, 3)
        self.assertAllCalled()

    def test_021_revisions(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.ListSnapshots', 'volname', None)] = \
            b'0\x00' \
            b'snapid1\n' \
            b'snapid2\n' \
            b'snapid3\n'
        self.assertEqual(self.vol.revisions,
            ['snapid1', 'snapid2', 'snapid3'])
        self.assertAllCalled()

    def test_022_revisions_empty(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.ListSnapshots', 'volname', None)] = \
            b'0\x00'
        self.assertEqual(self.vol.revisions, [])
        self.assertAllCalled()

    def test_030_resize(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.Resize', 'volname', b'2048')] = \
            b'0\x00'
        self.vol.resize(2048)
        self.assertAllCalled()

    def test_031_revert(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.Revert', 'volname', b'snapid1')] = \
            b'0\x00'
        self.vol.revert('snapid1')
        self.assertAllCalled()

    def test_040_import_data(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.Import', 'volname', b'some-data')] = \
            b'0\x00'
        with subprocess.Popen(['echo', '-n', 'some-data'],
                stdout=subprocess.PIPE) as input_proc:
            self.vol.import_data(input_proc.stdout)
        self.assertAllCalled()

    def test_050_clone(self):
        self.app.expected_calls[
            ('source-vm', 'admin.vm.volume.CloneFrom', 'volname', None)] = \
            b'0\x00abcdef'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.CloneTo', 'volname', b'abcdef')] = \
            b'0\x00'
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00source-vm class=AppVM state=Halted\n'
        self.app.expected_calls[
            ('source-vm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00volname\nother\n'
        self.vol.clone(self.app.domains['source-vm'].volumes['volname'])
        self.assertAllCalled()


class TestPoolVolume(TestVMVolume):
    def setUp(self):
        super().setUp()
        self.vol = qubesadmin.storage.Volume(self.app, pool='test-pool',
            vid='some-id')

    def test_000_qubesd_call(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.volume.TestMethod',
            'test-pool', b'some-id')] = \
            b'0\x00method_result'
        self.assertEqual(self.vol._qubesd_call('TestMethod'),
            b'method_result')
        self.assertAllCalled()

    def expect_info(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.volume.Info', 'test-pool', b'some-id')] = \
            b'0\x00' \
            b'pool=test-pool\n' \
            b'vid=some-id\n' \
            b'size=1024\n' \
            b'usage=512\n' \
            b'rw=True\n' \
            b'snap_on_start=True\n' \
            b'save_on_stop=True\n' \
            b'source=\n' \
            b'revisions_to_keep=3\n'

    def test_001_fetch_info(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.volume.Info', 'test-pool',
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
            ('dom0', 'admin.pool.volume.ListSnapshots',
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
            ('dom0', 'admin.pool.volume.ListSnapshots',
            'test-pool', b'some-id')] = b'0\x00'
        self.assertEqual(self.vol.revisions, [])
        self.assertAllCalled()

    def test_030_resize(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.volume.Resize',
            'test-pool', b'some-id 2048')] = b'0\x00'
        self.vol.resize(2048)
        self.assertAllCalled()

    def test_031_revert(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.volume.Revert', 'test-pool',
            b'some-id snapid1')] = b'0\x00'
        self.vol.revert('snapid1')
        self.assertAllCalled()

    def test_040_import_data(self):
        self.skipTest('admin.pool.volume.Import not supported')

    def test_050_clone(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.volume.CloneFrom', 'test-pool',
            b'volid')] = b'0\x00abcdef'
        self.app.expected_calls[
            ('dom0', 'admin.pool.volume.CloneTo', 'test-pool',
            b'some-id abcdef')] = b'0\x00'
        source_vol = qubesadmin.storage.Volume(self.app, pool='test-pool',
            vid='volid')
        self.vol.clone(source_vol)
        self.assertAllCalled()

    def test_050_clone_wrong_volume(self):
        self.skipTest('admin.pool.volume.Clone not supported')


class TestPool(qubesadmin.tests.QubesTestCase):
    def test_000_list(self):
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00file\nlvm\n'
        seen = set()
        for pool in self.app.pools.values():
            self.assertIsInstance(pool, qubesadmin.storage.Pool)
            self.assertIn(pool.name, ('file', 'lvm'))
            self.assertNotIn(pool.name, seen)
            seen.add(pool.name)

        self.assertEqual(seen, {'file', 'lvm'})
        self.assertAllCalled()

    def test_010_config(self):
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00file\nlvm\n'
        self.app.expected_calls[('dom0', 'admin.pool.Info', 'file', None)] = \
            b'0\x00driver=file\n' \
            b'dir_path=/var/lib/qubes\n' \
            b'name=file\n' \
            b'revisions_to_keep=3\n'
        pool = self.app.pools['file']
        self.assertEqual(pool.config, {
            'driver': 'file',
            'dir_path': '/var/lib/qubes',
            'name': 'file',
            'revisions_to_keep': '3',
        })
        self.assertAllCalled()

    def test_011_usage(self):
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00file\nlvm\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.UsageDetails', 'lvm', None)] = \
            b'0\x00data_size=204800\n' \
            b'data_usage=102400\n' \
            b'metadata_size=1024\n' \
            b'metadata_usage=50\n'
        pool = self.app.pools['lvm']
        self.assertEqual(pool.usage_details, {
            'data_size': 204800,
            'data_usage': 102400,
            'metadata_size': 1024,
            'metadata_usage': 50,
        })
        self.assertAllCalled()

    def test_012_size_and_usage(self):
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00file\nlvm\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.UsageDetails', 'lvm', None)] = \
            b'0\x00data_size=204800\n' \
            b'data_usage=102400\n' \
            b'metadata_size=1024\n' \
            b'metadata_usage=50\n'
        pool = self.app.pools['lvm']
        self.assertEqual(pool.size, 204800)
        self.assertEqual(pool.usage, 102400)
        self.assertAllCalled()

    def test_020_volumes(self):
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00file\nlvm\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.volume.List', 'file', None)] = \
            b'0\x00vol1\n' \
            b'vol2\n'
        pool = self.app.pools['file']
        seen = set()
        for volume in pool.volumes:
            self.assertIsInstance(volume, qubesadmin.storage.Volume)
            self.assertIn(volume.vid, ('vol1', 'vol2'))
            self.assertEqual(volume.pool, 'file')
            self.assertNotIn(volume.vid, seen)
            seen.add(volume.vid)

        self.assertEqual(seen, {'vol1', 'vol2'})
        self.assertAllCalled()

    def test_030_pool_drivers(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.ListDrivers', None, None)] = \
            b'0\x00file dir_path revisions_to_keep\n' \
            b'lvm volume_group thin_pool revisions_to_keep\n'
        self.assertEqual(set(self.app.pool_drivers), {'file', 'lvm'})
        self.assertEqual(set(self.app.pool_driver_parameters('file')),
            {'dir_path', 'revisions_to_keep'})
        self.assertAllCalled()

    def test_040_add(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.Add', 'some-driver',
            b'name=test-pool\nparam1=value1\nparam2=123\n')] = b'0\x00'
        self.app.add_pool('test-pool', driver='some-driver',
            param1='value1', param2=123)
        self.assertAllCalled()

    def test_050_remove(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.Remove', 'test-pool', None)] = b'0\x00'
        self.app.remove_pool('test-pool')
        self.assertAllCalled()
