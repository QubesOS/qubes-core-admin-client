#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016 Marek Marczykowski-Górecki
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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

# pylint: disable=missing-docstring

import argparse
import datetime
import re
import time

import qubesadmin.firewall
import qubesadmin.tests
import qubesadmin.tests.tools
import qubesadmin.tools.qvm_firewall

class RuleNamespace(argparse.Namespace):
    rule = None


class TC_00_RuleAction(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.action = qubesadmin.tools.qvm_firewall.RuleAction(
            None, dest='rule')

    def test_000_named_opts(self):
        args = RuleNamespace()
        self.action(None, args, ['dsthost=127.0.0.1', 'action=accept'])
        self.assertEqual(args.rule,
            qubesadmin.firewall.Rule(
                None, action='accept', dsthost='127.0.0.1/32'))

    def test_001_unnamed_opts(self):
        args = RuleNamespace()
        self.action(None, args, ['accept', '127.0.0.1', 'tcp', '80'])
        self.assertEqual(args.rule,
            qubesadmin.firewall.Rule(
                None, action='accept', dsthost='127.0.0.1/32',
                proto='tcp', dstports=80))

    def test_002_unnamed_opts(self):
        args = RuleNamespace()
        self.action(None, args, ['accept', '127.0.0.1', 'icmp', '8'])
        self.assertEqual(args.rule,
            qubesadmin.firewall.Rule(
                None, action='accept', dsthost='127.0.0.1/32',
                proto='icmp', icmptype=8))

    def test_003_mixed_opts(self):
        args = RuleNamespace()
        self.action(None, args, ['dsthost=127.0.0.1', 'accept',
            'dstports=443', 'tcp'])
        self.assertEqual(args.rule,
            qubesadmin.firewall.Rule(
                None, action='accept', dsthost='127.0.0.1/32',
                proto='tcp', dstports=443))

    def test_004_expire_absolute(self):
        args = RuleNamespace()
        self.action(None, args, ['dsthost=127.0.0.1', 'action=accept',
            'expire=1525054180'])
        self.assertEqual(args.rule,
            qubesadmin.firewall.Rule(
                None, action='accept', dsthost='127.0.0.1/32',
                expire=1525054180))

    def test_005_expire_relative(self):
        args = RuleNamespace()
        now = int(datetime.datetime.now().strftime('%s'))
        self.action(None, args, ['dsthost=127.0.0.1', 'action=accept',
            'expire=+100'])
        self.assertEqual(args.rule,
            qubesadmin.firewall.Rule(
                None, action='accept', dsthost='127.0.0.1/32',
                expire=now+100))

    def test_006_dsthost_aliases(self):
        args = RuleNamespace()
        for name in ['dsthost', 'dst4', 'dst6']:
            self.action(None, args, [name + '=127.0.0.1', 'accept'])
            self.assertEqual(args.rule,
                qubesadmin.firewall.Rule(
                    None, action='accept', dsthost='127.0.0.1/32'))

    def test_007_none_errors(self):
        args = RuleNamespace()
        with self.assertRaises(argparse.ArgumentError):
            self.action(None, args, ['dsthost=', 'action=accept'])
        with self.assertRaises(argparse.ArgumentError):
            self.action(None, args, ['dsthost=127.0.0.1', 'dstports=',
                                   'action=accept'])
        with self.assertRaises(argparse.ArgumentError):
            self.action(None, args, ['dsthost=127.0.0.1', 'icmptype=',
                                   'action=accept'])


class TC_10_qvm_firewall(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=AppVM state=Halted\n'

    def test_000_list(self):
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org\n' \
            b'action=drop proto=icmp\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_firewall.main(['test-vm', 'list'],
                                               app=self.app)
            self.assertEqual(
                [l.strip() for l in stdout.getvalue().splitlines()],
                ['NO  ACTION  HOST          PROTOCOL  PORT(S)  SPECIAL '
                 'TARGET  ICMP TYPE  EXPIRE  COMMENT',
                 '0   accept  qubes-os.org  -         -        -       '
                 '        -          -       -',
                 '1   drop    -             icmp      -        -       '
                 '        -          -       -',
                ])

    def test_001_list_default(self):
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org proto=tcp ' \
            b'dstports=443-443\n' \
            b'action=drop proto=icmp icmptype=8\n' \
            b'action=accept specialtarget=dns comment=Allow DNS\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_firewall.main(['test-vm'], app=self.app)
            self.assertEqual(
                [l.strip() for l in stdout.getvalue().splitlines()],
                ['NO  ACTION  HOST          PROTOCOL  PORT(S)  SPECIAL '
                 'TARGET  ICMP TYPE  EXPIRE  COMMENT',
                 '0   accept  qubes-os.org  tcp       443      -       '
                 '        -          -       -',
                 '1   drop    -             icmp      -        -       '
                 '        8          -       -',
                 '2   accept  -             -         -        dns     '
                 '        -          -       Allow DNS',
                ])


    def test_002_list_expire(self):
        in_1h = int(time.time()) + 3600
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            '0\0action=accept dsthost=qubes-os.org proto=tcp ' \
            'dstports=443-443 expire={}\n'.format(in_1h).encode()
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_firewall.main(['test-vm'], app=self.app)
            line = stdout.getvalue().splitlines()[-1]
            match = re.match(
                r'0   accept  qubes-os.org  tcp       443      -         '
                r'      -          \+(.{4})s  -',
                line)
            self.assertTrue(match, f"no match for: {line!r}")
            duration = int(match.group(1))
            self.assertTrue(3590 < duration <= 3600)

    def test_002_list_raw(self):
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org\n' \
            b'action=drop proto=icmp\n'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_firewall.main(['test-vm', '--raw', 'list'],
                app=self.app)
            self.assertEqual(
                [l.strip() for l in stdout.getvalue().splitlines()],
                ['action=accept dsthost=qubes-os.org',
                 'action=drop proto=icmp',
                ])

    def test_003_list_raw_reload(self):
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org\n' \
            b'action=drop proto=icmp\n'
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Reload',
                None, None)] = b'0\0'
        with qubesadmin.tests.tools.StdoutBuffer() as stdout:
            qubesadmin.tools.qvm_firewall.main(
                ['test-vm', '--raw', '--reload', 'list'],
                app=self.app)
            self.assertEqual(
                [l.strip() for l in stdout.getvalue().splitlines()],
                ['action=accept dsthost=qubes-os.org',
                 'action=drop proto=icmp',
                ])

    def test_010_add_after(self):
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org\n' \
            b'action=drop proto=icmp\n'
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Set', None,
            b'action=accept dsthost=qubes-os.org\n'
            b'action=drop proto=icmp\n'
            b'action=accept dst4=192.168.0.0/24 comment=Allow LAN\n')] = \
            b'0\0'
        qubesadmin.tools.qvm_firewall.main(
            ['test-vm', 'add', 'accept', '192.168.0.0/24', 'comment=Allow LAN'],
            app=self.app
        )

    def test_011_add_before(self):
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org\n' \
            b'action=drop proto=icmp\n'
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Set', None,
            b'action=accept dsthost=qubes-os.org\n'
            b'action=accept dst4=192.168.0.0/24 comment=Allow LAN\n'
            b'action=drop proto=icmp\n')] = b'0\0'
        qubesadmin.tools.qvm_firewall.main(
            ['test-vm', 'add', '--before', '1', 'accept', '192.168.0.0/24',
                'comment=Allow LAN'],
            app=self.app
        )

    def test_020_del_number(self):
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org\n' \
            b'action=drop proto=icmp\n'
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Set', None,
            b'action=accept dsthost=qubes-os.org\n')] = b'0\0'
        qubesadmin.tools.qvm_firewall.main(
            ['test-vm', 'del', '--rule-no', '1'],
            app=self.app
        )

    def test_021_del_rule(self):
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org\n' \
            b'action=drop proto=icmp\n'
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Set', None,
            b'action=accept dsthost=qubes-os.org\n')] = b'0\0'
        qubesadmin.tools.qvm_firewall.main(
            ['test-vm', 'del', 'drop', 'proto=icmp'],
            app=self.app
        )

    def test_030_reset(self):
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org\n' \
            b'action=drop proto=icmp\n'
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Set', None,
            b'action=accept\n')] = b'0\0'
        qubesadmin.tools.qvm_firewall.main(
            ['test-vm', 'reset'],
            app=self.app
        )
