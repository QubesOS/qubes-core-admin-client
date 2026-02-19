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

import qubesadmin.tests.vm


class TestVMVolumes(qubesadmin.tests.vm.VMTestCase):
    def test_000_list_volumes(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\nvolatile\nmodules\n'
        self.assertEqual(set(self.vm.volumes.keys()),
            {'root', 'private', 'volatile', 'modules'})
        self.assertAllCalled()

    def test_001_volume_get(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.List', None, None)] = \
            b'0\x00root\nprivate\nvolatile\nmodules\n'
        vol = self.vm.volumes['private']
        self.assertEqual(vol._vm, 'test-vm')
        self.assertEqual(vol._vm_name, 'private')
        # add it here, to raise exception if was called earlier
        self.app.expected_calls[
            ('test-vm', 'admin.vm.volume.Info', 'private', None)] = \
            b'0\x00pool=test-pool\nvid=some-id\n'
        self.assertEqual(vol.pool, 'test-pool')
        self.assertEqual(vol.vid, 'some-id')
        self.assertAllCalled()
