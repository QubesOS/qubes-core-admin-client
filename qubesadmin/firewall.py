# -*- encoding: utf8 -*-
# pylint: disable=too-few-public-methods
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

'''Firewall configuration interface'''

import datetime
import socket
import string


class RuleOption(object):
    '''Base class for a single rule element'''
    def __init__(self, value):
        self._value = str(value)

    @property
    def rule(self):
        '''API representation of this rule element'''
        raise NotImplementedError

    @property
    def pretty_value(self):
        '''Human readable representation'''
        return str(self)

    def __str__(self):
        return self._value

    def __eq__(self, other):
        return str(self) == other


# noinspection PyAbstractClass
class RuleChoice(RuleOption):
    '''Base class for multiple-choices rule elements'''
    # pylint: disable=abstract-method
    def __init__(self, value):
        super().__init__(value)
        self.allowed_values = \
            [v for k, v in self.__class__.__dict__.items()
                if not k.startswith('__') and isinstance(v, str) and
                   not v.startswith('__')]
        if value not in self.allowed_values:
            raise ValueError(value)


class Action(RuleChoice):
    '''Rule action'''
    accept = 'accept'
    drop = 'drop'

    @property
    def rule(self):
        '''API representation of this rule element'''
        return 'action=' + str(self)


class Proto(RuleChoice):
    '''Protocol name'''
    tcp = 'tcp'
    udp = 'udp'
    icmp = 'icmp'

    @property
    def rule(self):
        '''API representation of this rule element'''
        return 'proto=' + str(self)


class DstHost(RuleOption):
    '''Represent host/network address: either IPv4, IPv6, or DNS name'''
    def __init__(self, value, prefixlen=None):
        # TODO: in python >= 3.3 ipaddress module could be used
        if value.count('/') > 1:
            raise ValueError('Too many /: ' + value)
        if not value.count('/'):
            # add prefix length to bare IP addresses
            try:
                socket.inet_pton(socket.AF_INET6, value)
                if prefixlen is not None:
                    self.prefixlen = prefixlen
                else:
                    self.prefixlen = 128
                if self.prefixlen < 0 or self.prefixlen > 128:
                    raise ValueError(
                        'netmask for IPv6 must be between 0 and 128')
                value += '/' + str(self.prefixlen)
                self.type = 'dst6'
            except socket.error:
                try:
                    socket.inet_pton(socket.AF_INET, value)
                    if value.count('.') != 3:
                        raise ValueError(
                            'Invalid number of dots in IPv4 address')
                    if prefixlen is not None:
                        self.prefixlen = prefixlen
                    else:
                        self.prefixlen = 32
                    if self.prefixlen < 0 or self.prefixlen > 32:
                        raise ValueError(
                            'netmask for IPv4 must be between 0 and 32')
                    value += '/' + str(self.prefixlen)
                    self.type = 'dst4'
                except socket.error:
                    self.type = 'dsthost'
                    self.prefixlen = 0
                    safe_set = string.ascii_lowercase + string.digits + '-._'
                    if not all(c in safe_set for c in value):
                        raise ValueError('Invalid hostname')
        else:
            host, prefixlen = value.split('/', 1)
            prefixlen = int(prefixlen)
            if prefixlen < 0:
                raise ValueError('netmask must be non-negative')
            self.prefixlen = prefixlen
            try:
                socket.inet_pton(socket.AF_INET6, host)
                if prefixlen > 128:
                    raise ValueError('netmask for IPv6 must be <= 128')
                self.type = 'dst6'
            except socket.error:
                try:
                    socket.inet_pton(socket.AF_INET, host)
                    if prefixlen > 32:
                        raise ValueError('netmask for IPv4 must be <= 32')
                    self.type = 'dst4'
                    if host.count('.') != 3:
                        raise ValueError(
                            'Invalid number of dots in IPv4 address')
                except socket.error:
                    raise ValueError('Invalid IP address: ' + host)

        super().__init__(value)

    @property
    def rule(self):
        '''API representation of this rule element'''
        if self.prefixlen == 0 and self.type != 'dsthost':
            # 0.0.0.0/0 or ::/0, doesn't limit to any particular host,
            # so skip it
            return None
        return self.type + '=' + str(self)


class DstPorts(RuleOption):
    '''Destination port(s), for TCP/UDP only'''
    def __init__(self, value):
        if isinstance(value, int):
            value = str(value)
        if value.count('-') == 1:
            self.range = [int(x) for x in value.split('-', 1)]
        elif not value.count('-'):
            self.range = [int(value), int(value)]
        else:
            raise ValueError(value)
        if any(port < 0 or port > 65536 for port in self.range):
            raise ValueError('Ports out of range')
        if self.range[0] > self.range[1]:
            raise ValueError('Invalid port range')
        super().__init__(
            str(self.range[0]) if self.range[0] == self.range[1]
            else '{!s}-{!s}'.format(*self.range))

    @property
    def rule(self):
        '''API representation of this rule element'''
        return 'dstports=' + '{!s}-{!s}'.format(*self.range)


class IcmpType(RuleOption):
    '''ICMP packet type'''
    def __init__(self, value):
        super().__init__(value)
        value = int(value)
        if value < 0 or value > 255:
            raise ValueError('ICMP type out of range')

    @property
    def rule(self):
        '''API representation of this rule element'''
        return 'icmptype=' + str(self)


class SpecialTarget(RuleChoice):
    '''Special destination'''
    dns = 'dns'

    @property
    def rule(self):
        '''API representation of this rule element'''
        return 'specialtarget=' + str(self)


class Expire(RuleOption):
    '''Rule expire time'''
    def __init__(self, value):
        super().__init__(value)
        self.datetime = datetime.datetime.utcfromtimestamp(int(value))

    @property
    def rule(self):
        '''API representation of this rule element'''
        return 'expire=' + str(self)

    @property
    def expired(self):
        '''Has this rule expired already?'''
        return self.datetime < datetime.datetime.utcnow()

    @property
    def pretty_value(self):
        '''Human readable representation'''
        now = datetime.datetime.utcnow()
        duration = (self.datetime - now).total_seconds()
        return "{:+.0f}s".format(duration)


class Comment(RuleOption):
    '''User comment'''
    @property
    def rule(self):
        '''API representation of this rule element'''
        return 'comment=' + str(self)


class Rule(object):
    '''A single firewall rule'''

    def __init__(self, rule, **kwargs):
        '''Single firewall rule

        :param xml: XML element describing rule, or None
        :param kwargs: rule elements
        '''
        self._action = None
        self._proto = None
        self._dsthost = None
        self._dstports = None
        self._icmptype = None
        self._specialtarget = None
        self._expire = None
        self._comment = None

        rule_dict = {}
        if rule is not None:
            rule_opts, _, comment = rule.partition('comment=')

            rule_dict = dict(rule_opt.split('=', 1) for rule_opt in
                rule_opts.split(' ') if rule_opt)
            if comment:
                rule_dict['comment'] = comment
        rule_dict.update(kwargs)

        rule_elements = ('action', 'proto', 'dsthost', 'dst4', 'dst6',
            'specialtarget', 'dstports', 'icmptype', 'expire', 'comment')
        for rule_opt in rule_elements:
            value = rule_dict.pop(rule_opt, None)
            if value is None:
                continue
            if rule_opt in ('dst4', 'dst6'):
                rule_opt = 'dsthost'
            setattr(self, rule_opt, value)

        if rule_dict:
            raise ValueError('Unknown rule elements: {!r}'.format(
                rule_dict))

        if self.action is None:
            raise ValueError('missing action=')

    @property
    def action(self):
        '''rule action'''
        return self._action

    @action.setter
    def action(self, value):
        if not isinstance(value, Action):
            value = Action(value)
        self._action = value

    @property
    def proto(self):
        '''protocol to match'''
        return self._proto

    @proto.setter
    def proto(self, value):
        if value is not None and not isinstance(value, Proto):
            value = Proto(value)
        if value not in ('tcp', 'udp'):
            self.dstports = None
        if value not in ('icmp',):
            self.icmptype = None
        self._proto = value

    @property
    def dsthost(self):
        '''destination host/network'''
        return self._dsthost

    @dsthost.setter
    def dsthost(self, value):
        if value is not None and not isinstance(value, DstHost):
            value = DstHost(value)
        self._dsthost = value

    @property
    def dstports(self):
        ''''Destination port(s) (for \'tcp\' and \'udp\' protocol only)'''
        return self._dstports

    @dstports.setter
    def dstports(self, value):
        if value is not None:
            if self.proto not in ('tcp', 'udp'):
                raise ValueError(
                    'dstports valid only for \'tcp\' and \'udp\' protocols')
            if not isinstance(value, DstPorts):
                value = DstPorts(value)
        self._dstports = value

    @property
    def icmptype(self):
        '''ICMP packet type (for \'icmp\' protocol only)'''
        return self._icmptype

    @icmptype.setter
    def icmptype(self, value):
        if value is not None:
            if self.proto not in ('icmp',):
                raise ValueError('icmptype valid only for \'icmp\' protocol')
            if not isinstance(value, IcmpType):
                value = IcmpType(value)
        self._icmptype = value

    @property
    def specialtarget(self):
        '''Special target, for now only \'dns\' supported'''
        return self._specialtarget

    @specialtarget.setter
    def specialtarget(self, value):
        if not isinstance(value, SpecialTarget):
            value = SpecialTarget(value)
        self._specialtarget = value

    @property
    def expire(self):
        '''Timestamp (UNIX epoch) on which this rule expire'''
        return self._expire

    @expire.setter
    def expire(self, value):
        if not isinstance(value, Expire):
            value = Expire(value)
        self._expire = value

    @property
    def comment(self):
        '''User comment'''
        return self._comment

    @comment.setter
    def comment(self, value):
        if not isinstance(value, Comment):
            value = Comment(value)
        self._comment = value

    @property
    def rule(self):
        '''API representation of this rule'''
        values = []
        # comment must be the last one
        for prop in ('action', 'proto', 'dsthost', 'dstports', 'icmptype',
                'specialtarget', 'expire', 'comment'):
            value = getattr(self, prop)
            if value is None:
                continue
            if value.rule is None:
                continue
            values.append(value.rule)
        return ' '.join(values)

    def __eq__(self, other):
        if isinstance(other, Rule):
            return self.rule == other.rule
        if isinstance(other, str):
            return self.rule == str
        return NotImplemented

    def __repr__(self):
        return 'Rule(\'{}\')'.format(self.rule)


class Firewall(object):
    '''Firewal manager for a VM'''
    def __init__(self, vm):
        self.vm = vm
        self._rules: list[Rule] = []
        self._policy = None
        self._loaded = False

    def load_rules(self):
        '''Force (re-)loading firewall rules'''
        rules_str = self.vm.qubesd_call(None, 'admin.vm.firewall.Get')
        rules = []
        for rule_str in rules_str.decode().splitlines():
            rules.append(Rule(rule_str))
        self._rules = rules
        self._loaded = True

    @property
    def rules(self):
        '''Firewall rules

        You can either copy them, edit and then assign new rules list to this
        property, or edit in-place and call :py:meth:`save_rules`.
        Once rules are loaded, they are cached. To reload rules,
        call :py:meth:`load_rules`.
        '''
        if not self._loaded:
            self.load_rules()
        return self._rules

    @rules.setter
    def rules(self, value):
        self.save_rules(value)
        self._rules = value

    def save_rules(self, rules=None):
        '''Save firewall rules. Needs to be called after in-place editing
        :py:attr:`rules`.
        '''
        if rules is None:
            rules = self._rules
        self.vm.qubesd_call(None, 'admin.vm.firewall.Set',
            payload=(''.join('{}\n'.format(rule.rule)
                for rule in rules)).encode('ascii'))

    @property
    def policy(self):
        '''Default action to take if no rule matches'''
        return Action('drop')

    def reload(self):
        '''Force reload the same firewall rules.

        Can be used for example to force again names resolution.
        '''
        self.vm.qubesd_call(None, 'admin.vm.firewall.Reload')
