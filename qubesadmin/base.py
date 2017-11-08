# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

'''Base classes for managed objects'''

import sys
import traceback
import re

import ast
import qubesadmin.exc

DEFAULT = object()

ESCAPE_RE = re.compile("\\\\(.)")

def unescape(escaped_string):
    '''Unescape Admin API string'''
    def replacement(match):
        '''Replace escape sequence'''
        esc = match.group(1)
        if esc == "n":
            return "\n"
        if esc == "r":
            return "\r"
        if esc == "t":
            return "\t"
        if esc == "0":
            return "\0"
        return esc
    return ESCAPE_RE.sub(replacement, escaped_string)

CONFLICTING_KEYS = frozenset(["name", "klass"])

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
        self._values = dict()
        self._explicit = dict()
        self._update_needed = dict()
        self._exhaustive = False
        self._use_cache = True
        self._get_all = True

    def qubesd_call(self, dest, method, arg=None, payload=None,
            payload_stream=None):
        '''
        Call into qubesd using appropriate mechanism. This method should be
        defined by a subclass.

        Only one of `payload` and `payload_stream` can be specified.

        :param dest: Destination VM name
        :param method: Full API method name ('admin...')
        :param arg: Method argument (if any)
        :param payload: Payload send to the method
        :param payload_stream: file-like object to read payload from
        :return: Data returned by qubesd (string)
        '''
        if dest is None:
            dest = self._method_dest
        # have the actual implementation at Qubes() instance
        if self.app:
            return self.app.qubesd_call(dest, method, arg, payload,
                payload_stream)
        raise NotImplementedError

    @staticmethod
    def _parse_qubesd_response(response_data):
        '''Parse response from qubesd.

        In case of success, return actual data. In case of error,
        raise appropriate exception.
        '''

        if response_data == b'':
            raise qubesadmin.exc.QubesDaemonNoResponseError(
                'Got empty response from qubesd. See journalctl in dom0 for '
                'details.')

        if response_data[0:2] == b'\x30\x00':
            return response_data[2:]
        elif response_data[0:2] == b'\x32\x00':
            (_, exc_type, _traceback, format_string, args) = \
                response_data.split(b'\x00', 4)
            # drop last field because of terminating '\x00'
            args = [arg.decode() for arg in args.split(b'\x00')[:-1]]
            format_string = format_string.decode('utf-8')
            exc_type = exc_type.decode('ascii')
            try:
                exc_class = getattr(qubesadmin.exc, exc_type)
            except AttributeError:
                if exc_type.endswith('Error'):
                    exc_class = __builtins__.get(exc_type,
                        qubesadmin.exc.QubesException)
                else:
                    exc_class = qubesadmin.exc.QubesException
            # TODO: handle traceback if given
            raise exc_class(format_string, *args)
        else:
            raise qubesadmin.exc.QubesDaemonCommunicationError(
                'Invalid response format')

    def property_list(self):
        '''
        List available properties (their names).

        :return: list of strings
        '''
        if self._properties is None:
            properties_str = self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'List',
                None,
                None)
            self._properties = properties_str.decode('ascii').splitlines()
        # TODO: make it somehow immutable
        return self._properties

    def property_help(self, name):
        '''
        Get description of a property.

        :return: property help text
        '''
        help_text = self.qubesd_call(
            self._method_dest,
            self._method_prefix + 'Help',
            name,
            None)
        return help_text.decode('ascii')

    def _lookup(self, item):
        '''Ensure that item is in the cache, updating it if required'''
        if not self._use_cache:
            self._update_one(item)
            return

        if item in self._values:
            return

        if item in self._update_needed:
            self._update_one(item)
            return

        if self._exhaustive:
            raise qubesadmin.exc.QubesPropertyAccessError(item)

        if self._get_all and not self._update_all():
            self._get_all = False

        if not self._get_all:
            self._update_one(item)

        if item not in self._values:
            raise qubesadmin.exc.QubesPropertyAccessError(item)

    def property_is_default(self, item):
        '''
        Check if given property have default value

        :param str item: name of property
        :return: bool
        '''
        if item.startswith('_'):
            raise AttributeError(item)
        self._lookup(item)
        return item not in self._explicit

    def clone_properties(self, src, proplist=None):
        '''Clone properties from other object.

        :param PropertyHolder src: source object
        :param list proplist: list of properties \
            (:py:obj:`None` or omit for all properties)
        '''

        if proplist is None:
            proplist = self.property_list()

        for prop in proplist:
            try:
                setattr(self, prop, getattr(src, prop))
            except AttributeError:
                continue

    def __getattr__(self, item):
        # pylint: disable=too-many-return-statements
        if item.startswith('_'):
            raise AttributeError(item)
        self._lookup(item)
        return self._values[item]

    def clear_cache(self):
        '''Clear the cache'''
        self._get_all = True
        self._clear_properties()

    def _clear_properties(self):
        '''Clear cached properties'''
        for key in self._values:
            if key not in CONFLICTING_KEYS:
                object.__delattr__(self, key)

        self._values.clear()
        self._explicit.clear()
        self._update_needed.clear()
        self._exhaustive = False

    def enable_cache(self, enabled):
        '''Enable or disable using data in the cache without updating it'''
        self._use_cache = enabled
        if not enabled:
            for key in self._values:
                if key not in CONFLICTING_KEYS:
                    object.__delattr__(self, key)
        else:
            for key in self._values:
                if key not in CONFLICTING_KEYS:
                    object.__setattr__(self, key, self._values[key])

    def _decode_value(self, value, prop_type):
        '''Decode value from qubesd'''
        value = value.decode()
        if prop_type == 'str':
            value = value
        elif prop_type == 'bool':
            if value == '':
                raise AttributeError
            value = ast.literal_eval(value)
        elif prop_type == 'int':
            if value == '':
                value = None # hack for stubdom_mem
                #raise AttributeError
            else:
                value = ast.literal_eval(value)
        elif prop_type == 'vm':
            if value == '':
                value = None
            else:
                value = self.app.domains[value]
        elif prop_type == 'label':
            if value == '':
                value = None
            else:
                value = self.app.labels[value]
        else:
            raise qubesadmin.exc.QubesDaemonCommunicationError(
                'Received invalid value type: {}'.format(prop_type))
        return value

    def _update_one(self, item):
        '''Call Get to update one property, raise on failure'''
        try:
            property_str = self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'Get',
                item,
                None)
        except qubesadmin.exc.QubesDaemonNoResponseError:
            raise qubesadmin.exc.QubesPropertyAccessError(item)
        (default, prop_type, value) = property_str.split(b' ', 2)

        assert default.startswith(b'default=')
        is_default_str = default.split(b'=')[1]
        is_default = ast.literal_eval(is_default_str.decode('ascii'))
        assert isinstance(is_default, bool)

        prop_type = prop_type.decode('ascii')
        if not prop_type.startswith('type='):
            raise qubesadmin.exc.QubesDaemonCommunicationError(
                'Invalid type prefix received: {}'.format(prop_type))
        (_, prop_type) = prop_type.split('=', 1)

        value = self._decode_value(value, prop_type)

        self._set_item(item, value, is_default)

    def _update_all(self):
        '''Call GetAll to update all properties, return False on failure'''
        if not self.app.use_get_all:
            return False

        try:
            response = self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'GetAll',
                None,
                None)
        except qubesadmin.exc.QubesDaemonNoResponseError:
            return False

        self.process_response(response.splitlines())
        return True

    # also called by get_all_data()
    def process_response(self, lines):
        '''Process data from the response to GetAll or GetAllData'''
        self._clear_properties()
        successful = True
        for line in lines:
            try:
                (name, is_default, prop_type, value) = line.split(b'\t', 3)
                name = name.decode('ascii')
                prop_type = prop_type.decode('ascii')
                is_default = is_default == b'D'

                value = self._decode_value(value, prop_type)
                if prop_type == 'str' and value is not None:
                    value = unescape(value)

                self._set_item(name, value, is_default)
            except: # pylint: disable=bare-except
                successful = False
                traceback.print_exc(file=sys.stderr)

        self._exhaustive = successful

    @classmethod
    def _local_properties(cls):
        '''
        Get set of property names that are properties on the Python object,
        and must not be set on the remote object
        '''
        if "_local_properties_set" not in cls.__dict__:
            props = set()
            for class_ in cls.__mro__:
                for key in class_.__dict__:
                    props.add(key)
            cls._local_properties_set = props

        return cls._local_properties_set

    def __setattr__(self, key, value):
        if key.startswith('_') or key in self._local_properties():
            return super(PropertyHolder, self).__setattr__(key, value)
        if value is qubesadmin.DEFAULT:
            self.__delattr__(key)
        else:
            send_value = value
            if isinstance(send_value, qubesadmin.vm.QubesVM):
                send_value = value.name
            if send_value is None:
                send_value = ''
            try:
                self.qubesd_call(
                    self._method_dest,
                    self._method_prefix + 'Set',
                    key,
                    str(send_value).encode('utf-8'))
            except qubesadmin.exc.QubesDaemonNoResponseError:
                raise qubesadmin.exc.QubesPropertyAccessError(key)

            self._set_item(key, value, False)

    def __delattr__(self, name):
        if name.startswith('_') or name in self._local_properties():
            return super(PropertyHolder, self).__delattr__(name)
        try:
            self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'Reset',
                name
            )
        except qubesadmin.exc.QubesDaemonNoResponseError:
            raise qubesadmin.exc.QubesPropertyAccessError(name)

        # unfortunately, this has to trigger an API call on the next read
        # since we don't know the default value
        self._clear_item(name)

    def _set_item(self, key, value, is_default):
        '''Set the cached value of a property'''
        self._values[key] = value
        if self._use_cache and key not in CONFLICTING_KEYS:
            object.__setattr__(self, key, value)
        if not is_default:
            self._explicit[key] = value
        elif key in self._explicit:
            del self._explicit[key]
        if key in self._update_needed:
            del self._update_needed[key]

    def _clear_item(self, key):
        '''Clear the cached value of a property'''
        if key in self._values:
            del self._values[key]
            if self._use_cache and key not in CONFLICTING_KEYS:
                object.__delattr__(self, key)
        if key in self._explicit:
            del self._explicit[key]
        if self._exhaustive:
            self._update_needed[key] = True

class WrapperObjectsCollection(object):
    '''Collection of simple named objects'''
    def __init__(self, app, list_method, object_class):
        '''
        Construct manager of named wrapper objects.

        :param app: Qubes() object
        :param list_method: name of API method used to list objects,
            must return simple "one name per line" list
        :param object_class: object class (callable) for wrapper objects,
            will be called with just two arguments: app and a name
        '''
        self.app = app
        self._list_method = list_method
        self._object_class = object_class
        #: names cache
        self._names_list = None
        #: returned objects cache
        self._objects = {}

    def clear_cache(self):
        '''Clear cached list of names'''
        self._names_list = None

    def refresh_cache(self, force=False):
        '''Refresh cached list of names'''
        if not force and self._names_list is not None:
            return
        list_data = self.app.qubesd_call('dom0', self._list_method)
        list_data = list_data.decode('ascii')
        assert list_data[-1] == '\n'
        self._names_list = [str(name) for name in list_data[:-1].splitlines()]

        for name, obj in list(self._objects.items()):
            if obj.name not in self._names_list:
                # Object no longer exists
                del self._objects[name]

    def __getitem__(self, item):
        if not self.app.blind_mode and item not in self:
            raise KeyError(item)
        if item not in self._objects:
            self._objects[item] = self._object_class(self.app, item)
        return self._objects[item]

    def __contains__(self, item):
        self.refresh_cache()
        return item in self._names_list

    def __iter__(self):
        self.refresh_cache()
        for obj in self._names_list:
            yield self[obj]

    def keys(self):
        '''Get list of names.'''
        self.refresh_cache()
        return self._names_list.copy()
