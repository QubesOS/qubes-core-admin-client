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
import unittest

import qubesmgmt.tests.vm


class TC_00_Actions(qubesmgmt.tests.vm.VMTestCase):
    def test_000_start(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.Start', None, None)] = \
            b'0\x00'
        self.vm.start()
        self.assertAllCalled()

    def test_001_shutdown(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.Shutdown', None, None)] = \
            b'0\x00'
        self.vm.shutdown()
        self.assertAllCalled()

    def test_002_kill(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.Kill', None, None)] = \
            b'0\x00'
        self.vm.kill()
        self.assertAllCalled()

    def test_003_pause(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.Pause', None, None)] = \
            b'0\x00'
        self.vm.pause()
        self.assertAllCalled()

    def test_004_unpause(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.Unpause', None, None)] = \
            b'0\x00'
        self.vm.unpause()
        self.assertAllCalled()

    @unittest.skip('Not part of the mgmt API yet')
    def test_005_suspend(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.Suspend', None, None)] = \
            b'0\x00'
        self.vm.suspend()
        self.assertAllCalled()

    @unittest.skip('Not part of the mgmt API yet')
    def test_006_resume(self):
        self.app.expected_calls[
            ('test-vm', 'mgmt.vm.Resume', None, None)] = \
            b'0\x00'
        self.vm.resume()
        self.assertAllCalled()
