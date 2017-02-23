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


import ast
import os

import qubesmgmt.exc

DEFAULT = object()


class PropertyHolder(object):
    '''A base class for object having properties retrievable using mgmt API.

    Warning: each (non-private) local attribute needs to be defined at class
    level, even if initialized in __init__; otherwise will be treated as
    property retrievable using mgmt call.
    '''
    #: a place for appropriate Qubes() object (QubesLocal or QubesRemote),
    # use None for self
    app = None

    def __init__(self, app, method_prefix, method_dest):
        #: appropriate Qubes() object (QubesLocal or QubesRemote), use None
        # for self
        self.app = app
        self._method_prefix = method_prefix
        self._method_dest = method_dest
        self._properties = None
        self._properties_help = None

    def qubesd_call(self, dest, method, arg=None, payload=None):
        '''
        Call into qubesd using appropriate mechanism. This method should be
        defined by a subclass.

        :param dest: Destination VM name
        :param method: Full API method name ('mgmt...')
        :param arg: Method argument (if any)
        :param payload: Payload send to the method
        :return: Data returned by qubesd (string)
        '''
        # have the actual implementation at Qubes() instance
        if self.app:
            return self.app.qubesd_call(dest, method, arg, payload)
        raise NotImplementedError

    @staticmethod
    def _parse_qubesd_response(response_data):
        if response_data[0:2] == b'\x30\x00':
            return response_data[2:]
        elif response_data[0:2] == b'\x32\x00':
            (_, exc_type, _traceback, format_string, args) = \
                response_data.split(b'\x00', 4)
            # drop last field because of terminating '\x00'
            args = [arg.decode() for arg in args.split(b'\x00')[:-1]]
            format_string = format_string.decode('utf-8')
            exc_class = getattr(qubesmgmt.exc, exc_type, 'QubesException')
            # TODO: handle traceback if given
            raise exc_class(format_string, *args)
        else:
            raise qubesmgmt.exc.QubesException('Invalid response format')


    def property_list(self):
        if self._properties is None:
            properties_str = self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'List',
                None,
                None)
            self._properties = properties_str.splitlines()
        # TODO: make it somehow immutable
        return self._properties

    def property_is_default(self, item):
        if item.startswith('_'):
            raise AttributeError(item)
        property_str = self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'Get',
                item,
                None)
        (default, _value) = property_str.split(b' ', 1)
        assert default.startswith(b'default=')
        is_default_str = default.split(b'=')[1]
        is_default = ast.literal_eval(is_default_str.decode('ascii'))
        assert isinstance(is_default, bool)
        return is_default

    def __getattr__(self, item):
        if item.startswith('_'):
            raise AttributeError(item)
        property_str = self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'Get',
                item,
                None)
        (_default, value) = property_str.split(' ', 1)
        if value[0] == '\'':
            return ast.literal_eval('b' + value)
        else:
            return ast.literal_eval(value)

    def __setattr__(self, key, value):
        if key.startswith('_') or key in dir(self):
            return super(PropertyHolder, self).__setattr__(key, value)
        if value is DEFAULT:
            self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'Reset',
                key,
                None)
        else:
            if isinstance(value, qubesmgmt.vm.QubesVM):
                # pylint: disable=protected-access
                value = value._name
            self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'Set',
                key,
                bytes(value))

    def __delattr__(self, name):
        if name.startswith('_') or name in dir(self):
            return super(PropertyHolder, self).__delattr__(name)
        self.qubesd_call(
            self._method_dest,
            self._method_prefix + 'Reset',
            name
        )

# pylint: disable=wrong-import-position
import qubesmgmt.app

if os.path.exists(qubesmgmt.app.QUBESD_SOCK):
    Qubes = qubesmgmt.app.QubesLocal
else:
    Qubes = qubesmgmt.app.QubesRemote
