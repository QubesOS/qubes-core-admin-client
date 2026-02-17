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

# pylint: disable=missing-docstring

'''Tests for firewall API. This is mostly copy from core-admin'''
import datetime
import unittest
import qubesadmin.firewall
import qubesadmin.tests


class TestOption(qubesadmin.firewall.RuleChoice):
    opt1 = 'opt1'
    opt2 = 'opt2'
    another = 'another'

    @property
    def rule(self):
        return ''


# noinspection PyPep8Naming
class TC_00_RuleChoice(qubesadmin.tests.QubesTestCase):
    def test_000_accept_allowed(self):
        with self.assertNotRaises(ValueError):
            TestOption('opt1')
            TestOption('opt2')
            TestOption('another')

    def test_001_value_list(self):
        instance = TestOption('opt1')
        self.assertEqual(
            set(instance.allowed_values), {'opt1', 'opt2', 'another'})

    def test_010_reject_others(self):
        self.assertRaises(ValueError, lambda: TestOption('invalid'))


class TC_01_Action(qubesadmin.tests.QubesTestCase):
    def test_000_allowed_values(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.Action('accept')
        self.assertEqual(
            set(instance.allowed_values), {'accept', 'drop'})

    def test_001_rule(self):
        instance = qubesadmin.firewall.Action('accept')
        self.assertEqual(instance.rule, 'action=accept')


# noinspection PyPep8Naming
class TC_02_Proto(qubesadmin.tests.QubesTestCase):
    def test_000_allowed_values(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.Proto('tcp')
        self.assertEqual(
            set(instance.allowed_values), {'tcp', 'udp', 'icmp'})

    def test_001_rule(self):
        instance = qubesadmin.firewall.Proto('tcp')
        self.assertEqual(instance.rule, 'proto=tcp')


# noinspection PyPep8Naming
class TC_02_DstHost(qubesadmin.tests.QubesTestCase):
    def test_000_hostname(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.DstHost('qubes-os.org')
        self.assertEqual(instance.type, 'dsthost')

    def test_001_ipv4(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.DstHost('127.0.0.1')
        self.assertEqual(instance.type, 'dst4')
        self.assertEqual(instance.prefixlen, 32)
        self.assertEqual(str(instance), '127.0.0.1/32')
        self.assertEqual(instance.rule, 'dst4=127.0.0.1/32')

    def test_002_ipv4_prefixlen(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.DstHost('127.0.0.0', 8)
        self.assertEqual(instance.type, 'dst4')
        self.assertEqual(instance.prefixlen, 8)
        self.assertEqual(str(instance), '127.0.0.0/8')
        self.assertEqual(instance.rule, 'dst4=127.0.0.0/8')

    def test_003_ipv4_parse_prefixlen(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.DstHost('127.0.0.0/8')
        self.assertEqual(instance.type, 'dst4')
        self.assertEqual(instance.prefixlen, 8)
        self.assertEqual(str(instance), '127.0.0.0/8')
        self.assertEqual(instance.rule, 'dst4=127.0.0.0/8')

    def test_004_ipv4_invalid_prefix(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('127.0.0.0/33')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('127.0.0.0', 33)
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('127.0.0.0/-1')

    def test_005_ipv4_reject_shortened(self):
        # not strictly required, but ppl are used to it
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('127/8')

    def test_006_ipv4_invalid_addr(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('137.327.0.0/16')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('1.2.3.4.5/32')

    @unittest.expectedFailure
    def test_007_ipv4_invalid_network(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('127.0.0.1/32')

    def test_010_ipv6(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.DstHost('2001:abcd:efab::3')
        self.assertEqual(instance.type, 'dst6')
        self.assertEqual(instance.prefixlen, 128)
        self.assertEqual(str(instance), '2001:abcd:efab::3/128')
        self.assertEqual(instance.rule, 'dst6=2001:abcd:efab::3/128')

    def test_011_ipv6_prefixlen(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.DstHost('2001:abcd:efab::', 64)
        self.assertEqual(instance.type, 'dst6')
        self.assertEqual(instance.prefixlen, 64)
        self.assertEqual(str(instance), '2001:abcd:efab::/64')
        self.assertEqual(instance.rule, 'dst6=2001:abcd:efab::/64')

    def test_012_ipv6_parse_prefixlen(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.DstHost('2001:abcd:efab::/64')
        self.assertEqual(instance.type, 'dst6')
        self.assertEqual(instance.prefixlen, 64)
        self.assertEqual(str(instance), '2001:abcd:efab::/64')
        self.assertEqual(instance.rule, 'dst6=2001:abcd:efab::/64')

    def test_013_ipv6_invalid_prefix(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('2001:abcd:efab::3/129')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('2001:abcd:efab::3', 129)
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('2001:abcd:efab::3/-1')

    def test_014_ipv6_invalid_addr(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('2001:abcd:efab0123::3/128')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('2001:abcd:efab:3/128')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('2001:abcd:efab:a:a:a:a:a:a:3/128')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('2001:abcd:efgh::3/128')

    @unittest.expectedFailure
    def test_015_ipv6_invalid_network(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('2001:abcd:efab::3/64')

    def test_020_invalid_hostname(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('www  qubes-os.org')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstHost('https://qubes-os.org')


class TC_03_DstPorts(qubesadmin.tests.QubesTestCase):
    def test_000_single_str(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.DstPorts('80')
        self.assertEqual(str(instance), '80')
        self.assertEqual(instance.range, [80, 80])
        self.assertEqual(instance.rule, 'dstports=80-80')

    def test_001_single_int(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.DstPorts(80)
        self.assertEqual(str(instance), '80')
        self.assertEqual(instance.range, [80, 80])
        self.assertEqual(instance.rule, 'dstports=80-80')

    def test_002_range(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.DstPorts('80-90')
        self.assertEqual(str(instance), '80-90')
        self.assertEqual(instance.range, [80, 90])
        self.assertEqual(instance.rule, 'dstports=80-90')

    def test_003_invalid(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstPorts('80-90-100')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstPorts('abcdef')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstPorts('80 90')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstPorts('')

    def test_004_reversed_range(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstPorts('100-20')

    def test_005_out_of_range(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstPorts('1000000000000')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstPorts(1000000000000)
        with self.assertRaises(ValueError):
            qubesadmin.firewall.DstPorts('1-1000000000000')


class TC_04_IcmpType(qubesadmin.tests.QubesTestCase):
    def test_000_number(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.IcmpType(8)
        self.assertEqual(str(instance), '8')
        self.assertEqual(instance.rule, 'icmptype=8')

    def test_001_str(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.IcmpType('8')
        self.assertEqual(str(instance), '8')
        self.assertEqual(instance.rule, 'icmptype=8')

    def test_002_invalid(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.IcmpType(600)
        with self.assertRaises(ValueError):
            qubesadmin.firewall.IcmpType(-1)
        with self.assertRaises(ValueError):
            qubesadmin.firewall.IcmpType('abcde')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.IcmpType('')


class TC_05_SpecialTarget(qubesadmin.tests.QubesTestCase):
    def test_000_allowed_values(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.SpecialTarget('dns')
        self.assertEqual(
            set(instance.allowed_values), {'dns'})

    def test_001_rule(self):
        instance = qubesadmin.firewall.SpecialTarget('dns')
        self.assertEqual(instance.rule, 'specialtarget=dns')


class TC_06_Expire(qubesadmin.tests.QubesTestCase):
    def test_000_number(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.Expire(1463292452)
        self.assertEqual(str(instance), '1463292452')
        self.assertEqual(
            instance.datetime,
            datetime.datetime(2016, 5, 15, 6, 7,
                              32, tzinfo=datetime.timezone.utc))
        self.assertEqual(instance.rule, 'expire=1463292452')

    def test_001_str(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.Expire('1463292452')
        self.assertEqual(str(instance), '1463292452')
        self.assertEqual(instance.datetime,
            datetime.datetime(2016, 5, 15, 6, 7,
                              32, tzinfo=datetime.timezone.utc))
        self.assertEqual(instance.rule, 'expire=1463292452')

    def test_002_invalid(self):
        with self.assertRaises(ValueError):
            qubesadmin.firewall.Expire('abcdef')
        with self.assertRaises(ValueError):
            qubesadmin.firewall.Expire('')

    def test_003_expired(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.Expire('1463292452')
        self.assertTrue(instance.expired)
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.Expire('2583292452')
        self.assertFalse(instance.expired)


class TC_07_Comment(qubesadmin.tests.QubesTestCase):
    def test_000_str(self):
        with self.assertNotRaises(ValueError):
            instance = qubesadmin.firewall.Comment('Some comment')
        self.assertEqual(str(instance), 'Some comment')
        self.assertEqual(instance.rule, 'comment=Some comment')


class TC_10_Rule(qubesadmin.tests.QubesTestCase):
    def test_000_simple(self):
        with self.assertNotRaises(ValueError):
            rule = qubesadmin.firewall.Rule(None, action='accept', proto='icmp')
        self.assertEqual(rule.rule, 'action=accept proto=icmp')
        self.assertIsNone(rule.dsthost)
        self.assertIsNone(rule.dstports)
        self.assertIsNone(rule.icmptype)
        self.assertIsNone(rule.comment)
        self.assertIsNone(rule.expire)
        self.assertEqual(str(rule.action), 'accept')
        self.assertEqual(str(rule.proto), 'icmp')

    def test_001_expire(self):
        with self.assertNotRaises(ValueError):
            rule = qubesadmin.firewall.Rule(None, action='accept', proto='icmp',
                expire='1463292452')
        self.assertEqual(rule.rule,
            'action=accept proto=icmp expire=1463292452')


    def test_002_dstports(self):
        with self.assertNotRaises(ValueError):
            rule = qubesadmin.firewall.Rule(None, action='accept', proto='tcp',
                dstports=80)
        self.assertEqual(str(rule.dstports), '80')

    def test_003_reject_invalid(self):
        with self.assertRaises((ValueError, AssertionError)):
            # missing action
            qubesadmin.firewall.Rule(None, proto='icmp')
        with self.assertRaises(ValueError):
            # not proto=tcp or proto=udp for dstports
            qubesadmin.firewall.Rule(None, action='accept', proto='icmp',
                dstports=80)
        with self.assertRaises(ValueError):
            # not proto=tcp or proto=udp for dstports
            qubesadmin.firewall.Rule(None, action='accept', dstports=80)
        with self.assertRaises(ValueError):
            # not proto=icmp for icmptype
            qubesadmin.firewall.Rule(None, action='accept', proto='tcp',
                icmptype=8)
        with self.assertRaises(ValueError):
            # not proto=icmp for icmptype
            qubesadmin.firewall.Rule(None, action='accept', icmptype=8)

    def test_004_proto_change(self):
        rule = qubesadmin.firewall.Rule(None, action='accept', proto='tcp')
        with self.assertNotRaises(ValueError):
            rule.proto = 'udp'
        self.assertEqual(rule.rule, 'action=accept proto=udp')
        rule = qubesadmin.firewall.Rule(None, action='accept', proto='tcp',
            dstports=80)
        with self.assertNotRaises(ValueError):
            rule.proto = 'udp'
        self.assertEqual(rule.rule, 'action=accept proto=udp dstports=80-80')
        rule = qubesadmin.firewall.Rule(None, action='accept')
        with self.assertNotRaises(ValueError):
            rule.proto = 'udp'
        self.assertEqual(rule.rule, 'action=accept proto=udp')
        with self.assertNotRaises(ValueError):
            rule.dstports = 80
        self.assertEqual(rule.rule, 'action=accept proto=udp dstports=80-80')
        with self.assertNotRaises(ValueError):
            rule.proto = 'icmp'
        self.assertEqual(rule.rule, 'action=accept proto=icmp')
        self.assertIsNone(rule.dstports)
        rule.icmptype = 8
        self.assertEqual(rule.rule, 'action=accept proto=icmp icmptype=8')
        with self.assertNotRaises(ValueError):
            rule.proto = None
        self.assertEqual(rule.rule, 'action=accept')
        self.assertIsNone(rule.dstports)

    def test_005_parse_str(self):
        rule_txt = \
            'action=accept dst4=192.168.0.0/24 proto=tcp dstports=443'
        with self.assertNotRaises(ValueError):
            rule = qubesadmin.firewall.Rule(rule_txt)
        self.assertEqual(rule.dsthost, '192.168.0.0/24')
        self.assertEqual(rule.proto, 'tcp')
        self.assertEqual(rule.dstports, '443')
        self.assertIsNone(rule.expire)
        self.assertIsNone(rule.comment)

    def test_006_parse_str_comment(self):
        rule_txt = \
            'action=accept dsthost=qubes-os.org comment=Some comment'
        with self.assertNotRaises(ValueError):
            rule = qubesadmin.firewall.Rule(rule_txt)
        self.assertEqual(rule.dsthost, 'qubes-os.org')
        self.assertIsNone(rule.proto)
        self.assertIsNone(rule.dstports)
        self.assertIsNone(rule.expire)
        self.assertEqual(rule.comment, 'Some comment')


class TC_11_Firewall(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=AppVM state=Halted\n'
        self.vm = self.app.domains['test-vm']

    def test_010_load_rules(self):
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org\n' \
            b'action=drop proto=icmp\n'
        rules = self.vm.firewall.rules
        self.assertListEqual(rules, [
            qubesadmin.firewall.Rule('action=accept dsthost=qubes-os.org'),
            qubesadmin.firewall.Rule('action=drop proto=icmp'),
        ])
        # check caching
        del self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)]
        rules2 = self.vm.firewall.rules
        self.assertEqual(rules, rules2)
        # then force reload
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Get',
                None, None)] = \
            b'0\0action=accept dsthost=qubes-os.org proto=tcp dstports=443\n'
        self.vm.firewall.load_rules()
        rules3 = self.vm.firewall.rules
        self.assertListEqual(rules3, [
            qubesadmin.firewall.Rule(
                'action=accept dsthost=qubes-os.org proto=tcp dstports=443')])
        self.assertAllCalled()

    def test_020_set_rules(self):
        rules_txt = (
            'action=accept proto=tcp dsthost=qubes-os.org dstports=443-443',
            'action=accept dsthost=example.com',
        )
        rules = [qubesadmin.firewall.Rule(rule) for rule in rules_txt]
        self.app.expected_calls[('test-vm', 'admin.vm.firewall.Set', None,
        ''.join(rule + '\n' for rule in rules_txt).encode('ascii'))] = b'0\0'
        self.vm.firewall.rules = rules
        self.assertAllCalled()
