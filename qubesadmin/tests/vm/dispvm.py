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
import qubesadmin.vm

class TC_00_Dispvm(qubesadmin.tests.QubesTestCase):
    def test_000_local_create_default(self):
        self.app.qubesd_connection_type = 'socket'
        self.app.expected_calls[
            ('dom0', 'admin.vm.CreateDisposable', None, None)] = b'0\0disp123'
        self.app.expected_calls[
            ('disp123', 'admin.vm.Kill', None, None)] = b'0\0'
        self.app.expected_calls[
            ('disp123', 'admin.vm.property.Get', 'qrexec_timeout', None)] = \
            b'0\0default=yes type=int 30'
        vm = qubesadmin.vm.DispVM.from_appvm(self.app, None)
        vm.run_service_for_stdio('test.service')
        vm.cleanup()
        self.assertEqual(self.app.service_calls, [
            ('disp123', 'test.service', {'connect_timeout': 30}),
            ('disp123', 'test.service', b''),
        ])
        self.assertAllCalled()

    def test_001_local_create_specific(self):
        self.app.qubesd_connection_type = 'socket'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.CreateDisposable', None, None)] = \
            b'0\0disp123'
        self.app.expected_calls[
            ('disp123', 'admin.vm.Kill', None, None)] = b'0\0'
        self.app.expected_calls[
            ('disp123', 'admin.vm.property.Get', 'qrexec_timeout', None)] = \
            b'0\0default=yes type=int 30'
        vm = qubesadmin.vm.DispVM.from_appvm(self.app, 'test-vm')
        vm.run_service_for_stdio('test.service')
        vm.cleanup()
        self.assertEqual(self.app.service_calls, [
            ('disp123', 'test.service', {'connect_timeout': 30}),
            ('disp123', 'test.service', b''),
        ])
        self.assertAllCalled()

    def test_002_local_no_run_cleanup(self):
        self.app.qubesd_connection_type = 'socket'
        vm = qubesadmin.vm.DispVM.from_appvm(self.app, None)
        vm.cleanup()
        self.assertEqual(self.app.service_calls, [])
        self.assertAllCalled()

    def test_010_remote_create_default(self):
        vm = qubesadmin.vm.DispVM.from_appvm(self.app, None)
        vm.run_service_for_stdio('test.service')
        vm.cleanup()
        self.assertEqual(self.app.service_calls, [
            ('@dispvm', 'test.service', {}),
            ('@dispvm', 'test.service', b''),
        ])
        self.assertAllCalled()

    def test_011_remote_create_specific(self):
        vm = qubesadmin.vm.DispVM.from_appvm(self.app, 'test-vm')
        vm.run_service_for_stdio('test.service')
        vm.cleanup()
        self.assertEqual(self.app.service_calls, [
            ('@dispvm:test-vm', 'test.service', {}),
            ('@dispvm:test-vm', 'test.service', b''),
        ])
        self.assertAllCalled()

    def test_012_remote_no_run_cleanup(self):
        vm = qubesadmin.vm.DispVM.from_appvm(self.app, None)
        vm.cleanup()
        self.assertEqual(self.app.service_calls, [])
        self.assertAllCalled()
