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

# pylint: disable=missing-docstring

import unittest

import qubesadmin
import qubesadmin.vm
import qubesadmin.tools.qvm_ls

import qubesadmin.tests
import qubesadmin.tests.tools

from qubesadmin.tests import TestVM, TestVMCollection


class TestApp:
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
        for cols in qubesadmin.tools.qvm_ls.formats.values():
            for col in cols:
                self.assertIn(col.upper(),
                              qubesadmin.tools.qvm_ls.Column.columns)


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
            qubesadmin.tools.qvm_ls.main(['-O', 'name,virt_mode,class'],
                                         app=app)
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

    def test_103_list_all(self):
        app = TestApp()
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--all'], app=app)
        self.assertEqual(stdout.getvalue(),
            'NAME     STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'dom0     Running  TestVM  -      -         -\n'
            'test-vm  Running  TestVM  -      -         -\n')

    def test_104_wildcards(self):
        app = TestApp()
        app.domains = TestVMCollection(
            [
                ('dom0',                TestVM('dom0')),
                ('debian-13',           TestVM('debian-13')),
                ('debian-13-minimal',   TestVM('debian-13-minimal')),
                ('debian-13-xfce',      TestVM('debian-13-xfce')),
                ('debian-sid',          TestVM('debian-sid')),
                ('fedora-41',           TestVM('fedora-41')),
                ('fedora-41-minimal',   TestVM('fedora-41-minimal')),
                ('fedora-41-xfce',      TestVM('fedora-41-xfce')),
                ('fedora-rawhide',      TestVM('fedora-rawhide')),
            ]
        )
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--raw-list', 'fedora*'], app=app)
        self.assertEqual(stdout.getvalue(),
        'fedora-41\nfedora-41-minimal\nfedora-41-xfce\nfedora-rawhide\n')

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--raw-list', '*minimal'], app=app)
        self.assertEqual(stdout.getvalue(),
        'debian-13-minimal\nfedora-41-minimal\n')

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--raw-list', '????'], app=app)
        self.assertEqual(stdout.getvalue(),
        'dom0\n')

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--raw-list', '??????-[rs]*'],
                                         app=app)
        self.assertEqual(stdout.getvalue(),
        'debian-sid\nfedora-rawhide\n')

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--raw-list', '??????-[!14s]*'],
                                         app=app)
        self.assertEqual(stdout.getvalue(),
        'fedora-rawhide\n')

    def test_110_network_tree(self):
        app = TestApp()
        app.domains = TestVMCollection(
            [
                ('dom0', TestVM('dom0')),
                ('test-vm-temp', TestVM('test-vm-temp')),
                ('test-vm-proxy', TestVM('test-vm-proxy')),
                ('test-vm-1', TestVM('test-vm-1')),
                ('test-vm-2', TestVM('test-vm-2')),
                ('test-vm-3', TestVM('test-vm-3')),
                ('test-vm-4', TestVM('test-vm-4')),
                ('test-vm-net-1', TestVM('test-vm-net-1')),
                ('test-vm-net-2', TestVM('test-vm-net-2')),
            ]
        )
        appd = app.domains # For the sake of a 80 character line
        appd['dom0'].label = 'black'
        appd['test-vm-temp'].template = TestVM('template')
        appd['test-vm-net-1'].netvm = None
        appd['test-vm-net-1'].provides_network = True
        appd['test-vm-net-2'].netvm = None
        appd['test-vm-net-2'].provides_network = True
        appd['test-vm-proxy'].netvm = TestVM('test-vm-net-2')
        appd['test-vm-proxy'].provides_network = True
        appd['test-vm-1'].netvm = TestVM('test-vm-net-1')
        appd['test-vm-1'].provides_network = False
        appd['test-vm-2'].netvm = TestVM('test-vm-proxy')
        appd['test-vm-2'].provides_network = False
        appd['test-vm-3'].netvm = TestVM('test-vm-proxy')
        appd['test-vm-3'].provides_network = False
        appd['test-vm-4'].netvm = TestVM('test-vm-net-2')
        appd['test-vm-4'].provides_network = False
        appd['test-vm-net-1'].connected_vms = [appd['test-vm-1']]
        appd['test-vm-proxy'].connected_vms = [appd['test-vm-2'],
                                               appd['test-vm-3']]
        appd['test-vm-net-2'].connected_vms = [appd['test-vm-proxy'],
                                               appd['test-vm-4']]

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--tree'], app=app)
        self.assertEqual(stdout.getvalue(),
        'NAME             STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
        'dom0             Running  TestVM  black  -         -\n'
        'test-vm-temp     Running  TestVM  -      template  -\n'
        'test-vm-net-1    Running  TestVM  -      -         -\n'
        '└─test-vm-1      Running  TestVM  -      -         test-vm-net-1\n'
        'test-vm-net-2    Running  TestVM  -      -         -\n'
        '└─test-vm-proxy  Running  TestVM  -      -         test-vm-net-2\n'
        '  └─test-vm-2    Running  TestVM  -      -         test-vm-proxy\n'
        '  └─test-vm-3    Running  TestVM  -      -         test-vm-proxy\n'
        '└─test-vm-4      Running  TestVM  -      -         test-vm-net-2\n')

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
            qubesadmin.tools.qvm_ls.main(['--tags', 'my', 'other'],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME     STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'dom0     Running  TestVM  black  -         -\n'
            'test-vm  Running  TestVM  red    template  sys-firewall\n')

    def test_100_tags_nomatch(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--tags', 'nx1', 'nx2'],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE  CLASS  LABEL  TEMPLATE  NETVM\n')

    def test_100_exclude_tag(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--exclude-tags', 'not-my'], \
                    app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'dom0  Running  TestVM  black  -         -\n')


class TC_80_Power_state_filters(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        self.app = TestApp()
        self.app.domains = TestVMCollection(
            [
                ('a', TestVM('a', power_state='Halted')),
                ('b', TestVM('b', power_state='Transient')),
                ('c', TestVM('c', power_state='Running'))
            ]
        )

    def test_100_nofilter(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main([], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE      CLASS   LABEL  TEMPLATE  NETVM\n'
            'a     Halted     TestVM  -      -         -\n'
            'b     Transient  TestVM  -      -         -\n'
            'c     Running    TestVM  -      -         -\n')

    def test_100_running(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--running'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'c     Running  TestVM  -      -         -\n')

    def test_100_running_or_halted(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--running', '--halted'],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'a     Halted   TestVM  -      -         -\n'
            'c     Running  TestVM  -      -         -\n')


class TC_90_List_with_qubesd_calls(qubesadmin.tests.QubesTestCase):
    def test_100_list_with_status(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n' \
            b'template1 class=TemplateVM state=Halted\n' \
            b'sys-net class=AppVM state=Running\n'
        props = {
            'label': 'type=label green',
            'template': 'type=vm template1',
            'netvm': 'type=vm sys-net',
#           'virt_mode': b'type=str pv',
        }
        self.app.expected_calls[
            ('vm1', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        # setup sys-net
        props['label'] = 'type=label red'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        # setup template1
        props['label'] = 'type=label black'
        del props['template']
        self.app.expected_calls[
            ('template1', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

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
            ('vm1', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.CurrentState', None, None)] = \
            b'0\x00power_state=Running'
        props = {
            'label': 'type=label green',
            'template': 'type=vm template1',
            'netvm': 'type=vm sys-net',
#           'virt_mode': b'type=str pv',
        }
        self.app.expected_calls[
            ('vm1', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        # setup sys-net
        props['label'] = 'type=label red'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['vm1', 'sys-net'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME     STATE    CLASS  LABEL  TEMPLATE   NETVM\n'
            'sys-net  Running  AppVM  red    template1  sys-net\n'
            'vm1      Running  AppVM  green  template1  sys-net\n')
        self.assertAllCalled()

class TC_100_Sort(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        self.app = TestApp()
        self.app.domains = TestVMCollection(
            [
                ('a', TestVM('a', label='red', maxmem='100')),
                ('B', TestVM('B', label='green', maxmem='1000')),
                ('c', TestVM('c', label='blue',  maxmem='300')),
                ('dom0', TestVM('dom0', label='black', maxmem='-'))
            ]
        )

    def test_101_sort_string(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(
                ['--sort', 'NAME', '--reverse', '--ignore-case'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'dom0  Running  TestVM  black  -         -\n'
            'c     Running  TestVM  blue   -         -\n'
            'B     Running  TestVM  green  -         -\n'
            'a     Running  TestVM  red    -         -\n')

    def test_102_sort_numeric(self):
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(
                ['--field', 'NAME,MAXMEM', '--sort', 'MAXMEM'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  MAXMEM\n'
            'dom0  -\n'
            'a     100\n'
            'c     300\n'
            'B     1000\n')


class TC_110_Filtering(qubesadmin.tests.QubesTestCase):
    def test_111_filter_class(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=AppVM state=Running\n' \
            b'template1 class=TemplateVM state=Halted\n' \
            b'sys-net class=AppVM state=Running\n'
        props = {
            'label': 'type=label green',
            'template': 'type=vm template1',
            'netvm': 'type=vm sys-net',
        }

        # setup template1
        props['label'] = 'type=label black'
        del props['template']
        self.app.expected_calls[
            ('template1', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--class', 'TemplateVM'],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME       STATE   CLASS       LABEL  TEMPLATE  NETVM\n'
            'template1  Halted  TemplateVM  black  -         sys-net\n')
        self.assertAllCalled()

    def test_112_filter_label(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00template1 class=TemplateVM state=Halted\n' \
            b'sys-net class=AppVM state=Running\n'
        props = {
            'label': 'type=label green',
            'template': 'type=vm template1',
            'netvm': 'type=vm sys-net',
        }

        # setup sys-net
        props['label'] = 'type=label red'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        # setup template1
        props['label'] = 'type=label black'
        del props['template']
        self.app.expected_calls[
            ('template1', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--label', 'black'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME       STATE   CLASS       LABEL  TEMPLATE  NETVM\n'
            'template1  Halted  TemplateVM  black  -         sys-net\n')
        self.assertAllCalled()

    def test_113_filter_template_source(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00template1 class=TemplateVM state=Halted\n' \
            b'sys-net class=AppVM state=Running\n'
        props = {
            'label': 'type=label green',
            'template': 'type=vm template1',
            'netvm': 'type=vm sys-net',
        }

        # setup sys-net
        props['label'] = 'type=label red'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        # setup template1
        props['label'] = 'type=label black'
        del props['template']
        self.app.expected_calls[
            ('template1', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--template-source', 'template1'],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME     STATE    CLASS  LABEL  TEMPLATE   NETVM\n'
            'sys-net  Running  AppVM  red    template1  sys-net\n')
        self.assertAllCalled()

    def test_114_filter_netvm_is(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00template1 class=TemplateVM state=Halted\n' \
            b'sys-net class=AppVM state=Running\n'
        props = {
            'label': 'type=label green',
            'template': 'type=vm template1',
            'netvm': 'type=vm sys-net',
        }

        # setup sys-net
        props['label'] = 'type=label red'
        self.app.expected_calls[
            ('sys-net', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        # setup template1
        props['label'] = 'type=label black'
        del props['template']
        self.app.expected_calls[
            ('template1', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--netvm-is', 'sys-net'],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME       STATE    CLASS       LABEL  TEMPLATE   NETVM\n'
            'sys-net    Running  AppVM       red    template1  sys-net\n'
            'template1  Halted   TemplateVM  black  -          sys-net\n')
        self.assertAllCalled()

    def test_115_internal_servicevm_pending_updates(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00internalvm class=AppVM state=Running\n' \
            b'service-vm class=AppVM state=Running\n'
        props = {
            'label': 'type=label green',
            'template': 'type=vm template1',
            'netvm': 'type=vm sys-net',
        }

        # setup internalvm
        props['label'] = 'type=label red'
        self.app.expected_calls[
            ('internalvm', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        self.app.expected_calls[
            ('internalvm', 'admin.vm.feature.Get', 'internal', None)] = \
            b'0\x00true'

        self.app.expected_calls[
            ('internalvm', 'admin.vm.feature.Get', 'servicevm', None)] = \
            b'0\x00'

        self.app.expected_calls[
            ('internalvm', 'admin.vm.feature.Get', 'updates-available',
             None)] = b'0\x00true'

        # setup service-vm
        props['label'] = 'type=label red'
        self.app.expected_calls[
            ('service-vm', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        self.app.expected_calls[
            ('service-vm', 'admin.vm.feature.Get', 'internal', None)] = \
            b'0\x00'

        self.app.expected_calls[
            ('service-vm', 'admin.vm.feature.Get', 'servicevm', None)] = \
            b'0\x00true'

        self.app.expected_calls[
            ('service-vm', 'admin.vm.feature.Get', 'updates-available',
             None)] = b'0\x00'

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--internal', 'y'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME        STATE    CLASS  LABEL  TEMPLATE   NETVM\n'
            'internalvm  Running  AppVM  red    template1  sys-net\n')
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--internal', 'n'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME        STATE    CLASS  LABEL  TEMPLATE   NETVM\n'
            'service-vm  Running  AppVM  red    template1  sys-net\n')
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--servicevm', 'y'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME        STATE    CLASS  LABEL  TEMPLATE   NETVM\n'
            'service-vm  Running  AppVM  red    template1  sys-net\n')
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--servicevm', 'n'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME        STATE    CLASS  LABEL  TEMPLATE   NETVM\n'
            'internalvm  Running  AppVM  red    template1  sys-net\n')
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--pending-update'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME        STATE    CLASS  LABEL  TEMPLATE   NETVM\n'
            'internalvm  Running  AppVM  red    template1  sys-net\n')
        self.assertAllCalled()

    def test_116_features(self):
        self.app.expected_calls[
            ('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00internalvm class=AppVM state=Running\n' \
            b'service-vm class=AppVM state=Running\n'
        props = {
            'label': 'type=label green',
            'template': 'type=vm template1',
            'netvm': 'type=vm sys-net',
        }

        # setup internalvm
        props['label'] = 'type=label red'
        self.app.expected_calls[
            ('internalvm', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        self.app.expected_calls[
            ('internalvm', 'admin.vm.feature.Get', 'cool-feature', None)] = \
            b'0\x00yes'

        # setup service-vm
        props['label'] = 'type=label red'
        self.app.expected_calls[
            ('service-vm', 'admin.vm.property.GetAll', None, None)] = \
            b'0\x00' + ''.join(
                '{} default=True {}\n'.format(key, value)
                for key, value in props.items()).encode()

        self.app.expected_calls[
            ('service-vm', 'admin.vm.feature.Get', 'cool-feature', None)] = \
            b'0\x00'

        with qubesadmin.tests.tools.StderrBuffer():
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_ls.main(['--features', 'cool-feature:yes'],
                                             app=self.app)

        with qubesadmin.tests.tools.StderrBuffer():
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_ls.main(['--features', '=yes'],
                                             app=self.app)

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--features', 'cool-feature=yes'],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME        STATE    CLASS  LABEL  TEMPLATE   NETVM\n'
            'internalvm  Running  AppVM  red    template1  sys-net\n')

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--features', 'cool-feature='],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE  CLASS  LABEL  TEMPLATE  NETVM\n')

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--features', 'cool-feature=""'],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME        STATE    CLASS  LABEL  TEMPLATE   NETVM\n'
            'service-vm  Running  AppVM  red    template1  sys-net\n')

        self.assertAllCalled()

    def test_117_preferences(self):
        self.app = TestApp()
        self.app.domains = TestVMCollection(
            [
                ('a', TestVM('a', label='red', maxmem='100')),
                ('b', TestVM('b', label='green', maxmem=''))
            ]
        )

        with qubesadmin.tests.tools.StderrBuffer():
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_ls.main(['--prefs', 'maxmem:100'],
                                             app=self.app)

        with qubesadmin.tests.tools.StderrBuffer():
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_ls.main(['--prefs', ':100'], app=self.app)

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--prefs', 'maxmem=100'],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'a     Running  TestVM  red    -         -\n')

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--prefs', 'maxmem=""'], app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE    CLASS   LABEL  TEMPLATE  NETVM\n'
            'b     Running  TestVM  green  -         -\n')

        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_ls.main(['--prefs', 'non-existent='],
                                         app=self.app)
        self.assertEqual(stdout.getvalue(),
            'NAME  STATE  CLASS  LABEL  TEMPLATE  NETVM\n')
