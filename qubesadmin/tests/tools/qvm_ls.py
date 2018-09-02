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

import qubesadmin
import qubesadmin.vm
import qubesadmin.tools.qvm_ls

import qubesadmin.tests
import qubesadmin.tests.tools

from qubesadmin.tests import TestVM, TestVMCollection


class TestApp(object):
    def __init__(self):
        self.domains = TestVMCollection(
            [
                ('dom0', TestVM('dom0')),
                ('test-vm', TestVM('test-vm')),
            ]
        )

class TC_00_Column(qubesadmin.tests.QubesTestCase):
    def test_100_init(self):
        try:
            testcolumn = qubesadmin.tools.qvm_ls.Column('TESTCOLUMN')
            self.assertEqual(testcolumn.ls_head, 'TESTCOLUMN')
        finally:
            try:
                qubesadmin.tools.qvm_ls.Column.columns['TESTCOLUMN']
            except KeyError:
                pass


class TC_10_globals(qubesadmin.tests.QubesTestCase):
    def test_100_simple_flag(self):
        flag = qubesadmin.tools.qvm_ls.simple_flag(1, 'T', 'internal')

        # TODO after serious testing of QubesVM and Qubes app, this should be
        #      using normal components
        vm = TestVM('test-vm', internal=False)

        self.assertFalse(flag(None, vm))
        vm.internal = True
        self.assertTrue(flag(None, vm))

    @unittest.skip('column list generated dynamically')
    def test_900_formats_columns(self):
        for fmt in qubesadmin.tools.qvm_ls.formats:
            for col in qubesadmin.tools.qvm_ls.formats[fmt]:
                self.assertIn(col.upper(), qubesadmin.tools.qvm_ls.Column.columns)


class TC_50_List(qubesadmin.tests.QubesTestCase):
    def test_100_list_with_status(self):
        app = TestApp()
        app.domains['test-vm'].internal = False
        app.domains['test-vm'].updateable = False
        app.domains['test-vm'].template = TestVM('template')
        app.domains['test-vm'].netvm = TestVM('sys-net')
        app.domains['test-vm'].label = 'green'
        app.domains['dom0'].label = 'black'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main([], app=app)
        self.assertEqual(stdout.getvalue(),
            'NAME     STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'dom0     Running  TestVM  black  -         -\n'
            'test-vm  Running  TestVM  green  template  sys-net\n')

    def test_101_list_with_underscore(self):
        app = TestApp()
        app.domains['test-vm'].virt_mode = 'pv'
        app.domains['test-vm'].label = 'green'
        app.domains['dom0'].label = 'black'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['-O', 'name,virt_mode,class'], app=app)
        self.assertEqual(stdout.getvalue(),
            'NAME     VIRT-MODE  CLASS\n'
            'dom0     -          TestVM\n'
            'test-vm  pv         TestVM\n')

    def test_102_list_selected(self):
        app = TestApp()
        app.domains['test-vm'].internal = False
        app.domains['test-vm'].updateable = False
        app.domains['test-vm'].template = TestVM('template')
        app.domains['test-vm'].netvm = TestVM('sys-net')
        app.domains['test-vm'].label = 'green'
        app.domains['dom0'].label = 'black'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['test-vm'], app=app)
        self.assertEqual(stdout.getvalue(),
            'NAME     STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'test-vm  Running  TestVM  green  template  sys-net\n')

    def test_102_raw_list(self):
        app = TestApp()
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--raw-list'], app=app)
        self.assertEqual(stdout.getvalue(),
            'dom0\n'
            'test-vm\n')


class TC_70_Tags(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        self.app = TestApp()
        self.app.domains = TestVMCollection(
            [
                (
                    'dom0',
                    TestVM(
                        'dom0',
                        tags=['my'],
                        label='black'
                    )
                ),
                (
                    'test-vm',
                    TestVM(
                        'test-vm',
                        tags=['not-my', 'other'],
                        label='red',
                        netvm=TestVM('sys-firewall'),
                        template=TestVM('template')
                    )
                ),
            ]
        )

    def test_100_tag(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--tags', 'my'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'dom0  Running  TestVM  black  -         -\n')

    def test_100_tag_nomatch(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--tags', 'nx'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE  CLASS  LABEL  TEMPLATE  NETVM\n')

    def test_100_tags(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--tags', 'my', 'other'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME     STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'dom0     Running  TestVM  black  -         -\n'
            'test-vm  Running  TestVM  red    template  sys-firewall\n')

    def test_100_tags_nomatch(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--tags', 'nx1', 'nx2'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE  CLASS  LABEL  TEMPLATE  NETVM\n')


class TC_90_List_with_qubesd_calls(qubesadmin.tests.QubesTestCase):
    def test_100_list_with_status(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n' \
            b'template1 class=TemplateVM state=Halted\n' \
            b'sys-net class=AppVM state=Running\n'
        self.app.expected_calls[
            ('vm1', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.List', None, None)] = \
            b'0\x00sys-net class=AppVM state=Running\n'
        self.app.expected_calls[
            ('template1', 'admin.vm.List', None, None)] = \
            b'0\x00template1 class=TemplateVM state=Halted\n'
        props = {
            'label': b'type=label green',
            'template': b'type=vm template1',
            'netvm': b'type=vm sys-net',
#           'virt_mode': b'type=str pv',
        }
        for key, value in props.items():
            self.app.expected_calls[
                ('vm1', 'admin.vm.property.Get', key, None)] = \
                b'0\x00default=True ' + value

        # setup template1
        props['label'] = b'type=label black'
        for key, value in props.items():
            self.app.expected_calls[
                ('template1', 'admin.vm.property.Get', key, None)] = \
                b'0\x00default=True ' + value
        self.app.expected_calls[
            ('template1', 'admin.vm.property.Get', 'template', None)] = \
            b''  # request refused - no such property

        # setup sys-net
        props['label'] = b'type=label red'
        for key, value in props.items():
            self.app.expected_calls[
                ('sys-net', 'admin.vm.property.Get', key, None)] = \
                b'0\x00default=True ' + value

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main([], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME       STATE    CLASS       LABEL  TEMPLATE   NETVM\n'
            'sys-net    Running  AppVM       red    template1  sys-net\n'
            'template1  Halted   TemplateVM  black  -          sys-net\n'
            'vm1        Running  AppVM       green  template1  sys-net\n')
        self.assertAllCalled()

    def test_101_list_selected(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n' \
            b'template1 class=TemplateVM state=Halted\n' \
            b'sys-net class=AppVM state=Running\n'
        self.app.expected_calls[
            ('vm1', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.List', None, None)] = \
            b'0\x00sys-net class=AppVM state=Running\n'
        props = {
            'label': b'type=label green',
            'template': b'type=vm template1',
            'netvm': b'type=vm sys-net',
#           'virt_mode': b'type=str pv',
        }
        for key, value in props.items():
            self.app.expected_calls[
                ('vm1', 'admin.vm.property.Get', key, None)] = \
                b'0\x00default=True ' + value

        # setup sys-net
        props['label'] = b'type=label red'
        for key, value in props.items():
            self.app.expected_calls[
                ('sys-net', 'admin.vm.property.Get', key, None)] = \
                b'0\x00default=True ' + value

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['vm1', 'sys-net'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME     STATE    CLASS  LABEL  TEMPLATE   NETVM\n'
            'sys-net  Running  AppVM  red    template1  sys-net\n'
            'vm1      Running  AppVM  green  template1  sys-net\n')
        self.assertAllCalled()
