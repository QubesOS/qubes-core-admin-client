# pylint: disable=protected-access,pointless-statement

#
# The Qubes OS Project, https://www.qubesmgmt-os.org/
#
# Copyright (C) 2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015  Wojtek Porczyk <woju@invisiblethingslab.com>
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

import qubesmgmt
import qubesmgmt.vm
import qubesmgmt.tools.qvm_ls

import qubesmgmt.tests
import qubesmgmt.tests.tools

from qubesmgmt.tests import TestVM, TestVMCollection


class TestApp(object):
    def __init__(self):
        self.domains = TestVMCollection(
            [
                ('dom0', TestVM('dom0')),
                ('test-vm', TestVM('test-vm')),
            ]
        )

class TC_00_Column(qubesmgmt.tests.QubesTestCase):
    def test_100_init(self):
        try:
            testcolumn = qubesmgmt.tools.qvm_ls.Column('TESTCOLUMN')
            self.assertEqual(testcolumn.ls_head, 'TESTCOLUMN')
        finally:
            try:
                qubesmgmt.tools.qvm_ls.Column.columns['TESTCOLUMN']
            except KeyError:
                pass


class TC_10_globals(qubesmgmt.tests.QubesTestCase):
    def test_100_simple_flag(self):
        flag = qubesmgmt.tools.qvm_ls.simple_flag(1, 'T', 'internal')

        # TODO after serious testing of QubesVM and Qubes app, this should be
        #      using normal components
        vm = TestVM('test-vm', internal=False)

        self.assertFalse(flag(None, vm))
        vm.internal = True
        self.assertTrue(flag(None, vm))

    @unittest.skip('column list generated dynamically')
    def test_900_formats_columns(self):
        for fmt in qubesmgmt.tools.qvm_ls.formats:
            for col in qubesmgmt.tools.qvm_ls.formats[fmt]:
                self.assertIn(col.upper(), qubesmgmt.tools.qvm_ls.Column.columns)


class TC_50_List(qubesmgmt.tests.QubesTestCase):
    def test_100_list_with_status(self):
        app = TestApp()
        app.domains['test-vm'].internal = False
        app.domains['test-vm'].updateable = False
        app.domains['test-vm'].template = TestVM('template')
        app.domains['test-vm'].netvm = TestVM('sys-net')
        app.domains['test-vm'].label = 'green'
        app.domains['dom0'].label = 'black'
        with qubesmgmt.tests.tools.StdoutBuffer() as stdout:
            qubesmgmt.tools.qvm_ls.main([], app=app)
        self.assertEqual(stdout.getvalue(),
            'NAME     STATUS    LABEL  TEMPLATE  NETVM\n'
            'dom0     -r------  black  -         -\n'
            'test-vm  -r------  green  template  sys-net\n')


class TC_90_List_with_qubesd_calls(qubesmgmt.tests.QubesTestCase):
    def test_100_list_with_status(self):
        self.app.expected_calls[
            ('dom0', 'mgmt.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n' \
            b'template1 class=TemplateVM state=Halted\n' \
            b'sys-net class=AppVM state=Running\n'
        self.app.expected_calls[
            ('dom0', 'mgmt.label.List', None, None)] = \
            b'0\x00red\nblack\ngreen\nblue\n'
        self.app.expected_calls[
            ('vm1', 'mgmt.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n'
        self.app.expected_calls[
            ('sys-net', 'mgmt.vm.List', None, None)] = \
            b'0\x00sys-net class=AppVM state=Running\n'
        self.app.expected_calls[
            ('template1', 'mgmt.vm.List', None, None)] = \
            b'0\x00template1 class=TemplateVM state=Halted\n'
        props = {
            'label': b'type=label green',
            'template': b'type=vm template1',
            'netvm': b'type=vm sys-net',
            'updateable': b'type=bool False',
            'provides_network': b'type=bool False',
            'hvm': b'type=bool False',
            'installed_by_rpm': b'type=bool False',
            'internal': b'type=bool False',
            'debug': b'type=bool False',
            'autostart': b'type=bool False',
        }
        for key, value in props.items():
            self.app.expected_calls[
                ('vm1', 'mgmt.vm.property.Get', key, None)] = \
                b'0\x00default=True ' + value

        # setup template1
        props['label'] = b'type=label black'
        props['updateable'] = b'type=bool True'
        for key, value in props.items():
            self.app.expected_calls[
                ('template1', 'mgmt.vm.property.Get', key, None)] = \
                b'0\x00default=True ' + value
        self.app.expected_calls[
            ('template1', 'mgmt.vm.property.Get', 'template', None)] = \
            b''  # request refused - no such property

        # setup sys-net
        props['label'] = b'type=label red'
        props['provides_network'] = b'type=bool True'
        props['updateable'] = b'type=bool False'
        for key, value in props.items():
            self.app.expected_calls[
                ('sys-net', 'mgmt.vm.property.Get', key, None)] = \
                b'0\x00default=True ' + value

        with qubesmgmt.tests.tools.StdoutBuffer() as stdout:
            qubesmgmt.tools.qvm_ls.main([], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME       STATUS    LABEL  TEMPLATE   NETVM\n'
            'sys-net    ar-N----  red    template1  sys-net\n'
            'template1  t-U-----  black  -          sys-net\n'
            'vm1        ar------  green  template1  sys-net\n')
        self.assertAllCalled()
