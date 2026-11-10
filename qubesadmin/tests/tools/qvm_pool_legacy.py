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

import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_pool


class TC_00_qvm_pool_legacy(qubesadmin.tests.QubesTestCase):
    def test_000_list(self):
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00pool-file\npool-lvm\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.Info', 'pool-file', None)] = \
            b'0\x00driver=file\ndir_path=/var/lib/qubes\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.Info', 'pool-lvm', None)] = \
            b'0\x00driver=lvm\nvolume_group=qubes_dom0\nthin_pool=pool00\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_pool.main(['-l'], app=self.app))
        self.assertEqual(stdout.getvalue(),
            'NAME       DRIVER\n'
            'pool-file  file\n'
            'pool-lvm   lvm\n')
        self.assertAllCalled()

    def test_010_list_drivers(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.ListDrivers', None, None)] = \
            b'0\x00file dir_path revisions_to_keep\n' \
            b'lvm volume_group thin_pool revisions_to_keep\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_pool.main(['--help-drivers'],
                                               app=self.app))
        self.assertEqual(stdout.getvalue(),
            'DRIVER  OPTIONS\n'
            'file    dir_path, revisions_to_keep\n'
            'lvm     volume_group, thin_pool, revisions_to_keep\n'
        )
        self.assertAllCalled()

    def test_020_add(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.Add', 'file',
            b'name=test-pool\ndir_path=/some/path\n')] = b'0\x00'
        self.assertEqual(0,
            qubesadmin.tools.qvm_pool.main(
                ['--add', 'test-pool', 'file', '-o', 'dir_path=/some/path'],
                app=self.app))
        self.assertAllCalled()

    def test_030_remove(self):
        self.app.expected_calls[
            ('dom0', 'admin.pool.Remove', 'test-pool', None)] = b'0\x00'
        self.assertEqual(0,
            qubesadmin.tools.qvm_pool.main(['--remove', 'test-pool'],
                app=self.app))
        self.assertAllCalled()

    def test_040_info(self):
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00pool-file\npool-lvm\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.Info', 'pool-lvm', None)] = \
            b'0\x00driver=lvm\nvolume_group=qubes_dom0\nthin_pool=pool00\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            self.assertEqual(0,
                qubesadmin.tools.qvm_pool.main(['-i', 'pool-lvm'],
                    app=self.app))
        self.assertEqual(stdout.getvalue(),
            'name          pool-lvm\n'
            'driver        lvm\n'
            'thin_pool     pool00\n'
            'volume_group  qubes_dom0\n'
            )
        self.assertAllCalled()

    def test_050_set(self):
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00pool-file\npool-lvm\n'
        self.app.expected_calls[
            ('dom0', 'admin.pool.Set.revisions_to_keep', 'pool-lvm', b'2')] = \
            b'0\x00'
        self.assertEqual(0,
            qubesadmin.tools.qvm_pool.main(['-s', 'pool-lvm', '-o',
                'revisions_to_keep=2'],
                app=self.app))
        self.assertAllCalled()

    def test_051_set_invalid(self):
        self.app.expected_calls[('dom0', 'admin.pool.List', None, None)] = \
            b'0\x00pool-file\npool-lvm\n'
        with self.assertRaises(SystemExit) as e:
            qubesadmin.tools.qvm_pool.main(
                ['-s', 'pool-lvm', '-o', 'prop=1'],
                app=self.app)
        self.assertEqual(e.exception.code, 2)
        self.assertAllCalled()
