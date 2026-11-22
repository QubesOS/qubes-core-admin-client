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

import unittest.mock
import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_remove


class TC_00_qvm_remove(qubesadmin.tests.QubesTestCase):
    def test_000_single(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Remove', None, None)] = \
            b'0\x00\n'
        qubesadmin.tools.qvm_remove.main(['-f', 'some-vm'], app=self.app)
        self.assertAllCalled()

    @unittest.mock.patch('qubesadmin.utils.vm_dependencies')
    def test_100_dependencies(self, mock_dependencies):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=AppVM state=Running\n'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.Remove', None, None)] = \
            b'2\x00QubesVMInUseError\x00\x00An error occurred\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.property.Get', 'is_preload', None)] = \
            b'2\x00QubesNoSuchPropertyError\x00\x00Invalid property\x00'

        mock_dependencies.return_value = \
            [(None, 'default_template'), (self.app.domains['some-vm'], 'netvm')]
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_remove.main(['-f', 'some-vm'], app=self.app)
        mock_dependencies.assert_called_once()

    @unittest.mock.patch('qubesadmin.utils.vm_dependencies')
    def test_101_dvm_dependencies(self, mock_dependencies):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-template class=TemplateVM state=Halted\n' \
            b'some-vm class=AppVM state=Running\n' \
            b'some-dvm class=AppVM state=Running\n' \
            b'some-disp class=DispVM state=Running\n' \
            b'some-disp2 class=DispVM state=Running\n'
        self.app.expected_calls[
            ('some-dvm', 'admin.vm.Remove', None, None)] = \
            b'2\x00QubesVMInUseError\x00\x00An error occurred\x00'
        self.app.expected_calls[
            ('some-vm', 'admin.vm.property.Get', 'is_preload', None)] = \
            b'2\x00QubesNoSuchPropertyError\x00\x00Invalid property\x00'

        # Cannot remove while it is default_dispvm of the system.
        mock_dependencies.return_value = \
            [(None, 'default_dispvm')]
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_remove.main(['-f', 'some-dvm'], app=self.app)
        mock_dependencies.assert_called_once()
        mock_dependencies.reset_mock()

        # Cannot remove while it is default_dispvm of a qube.
        mock_dependencies.return_value = \
            [(self.app.domains['some-vm'], 'default_dispvm')]
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_remove.main(['-f', 'some-dvm'], app=self.app)
        mock_dependencies.assert_called_once()
        mock_dependencies.reset_mock()

        # Cannot remove while it is default_dispvm of its own disposable.
        self.app.expected_calls[
            ('some-disp', 'admin.vm.property.Get', 'is_preload', None)] = \
            b'0\x00default=False type=bool False'
        mock_dependencies.return_value = \
            [(self.app.domains['some-disp'], 'default_dispvm')]
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_remove.main(['-f', 'some-dvm'], app=self.app)
        mock_dependencies.assert_called_once()
        mock_dependencies.reset_mock()

        # Cannot remove while it is template of non preload.
        self.app.expected_calls[
            ('some-disp', 'admin.vm.property.Get', 'is_preload', None)] = \
            b'0\x00default=False type=bool True'
        self.app.expected_calls[
            ('some-disp2', 'admin.vm.property.Get', 'is_preload', None)] = \
            b'0\x00default=False type=bool False'
        mock_dependencies.return_value = [
            (self.app.domains['some-disp'], 'template'),
            (self.app.domains['some-disp2'], 'template')
        ]
        with self.assertRaises(SystemExit):
            qubesadmin.tools.qvm_remove.main(['-f', 'some-dvm'], app=self.app)
        mock_dependencies.assert_called_once()
        mock_dependencies.reset_mock()

        self.assertAllCalled()
