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

import qubesadmin.exc

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
        # the cache is maintained by EventsDispatcher(),
        # through helper functions in QubesBase()
        self._properties_cache = {}

    def clear_cache(self):
        """
        Clear property cache.
        """
        self._properties_cache = {}

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
        if not self.app:
            raise NotImplementedError
        if dest is None:
            dest = self._method_dest
        if (
            getattr(self, "_redirect_dispvm_calls", False)
            and dest.startswith("@dispvm")
        ):
            if dest.startswith("@dispvm:"):
                dest = dest[len("@dispvm:") :]
            else:
                dest = getattr(self.app, "default_dispvm", None)
                if dest:
                    dest = dest.name
        # have the actual implementation at Qubes() instance
        return self.app.qubesd_call(dest, method, arg, payload,
            payload_stream)

    @staticmethod
    def _parse_qubesd_response(response_data):
        '''Parse response from qubesd.

        In case of success, return actual data. In case of error,
        raise appropriate exception.
        '''

        if response_data == b'':
            raise qubesadmin.exc.QubesDaemonAccessError(
                'Got empty response from qubesd. See journalctl in dom0 for '
                'details.')

        if response_data[0:2] == b'\x30\x00':
            return response_data[2:]
        if response_data[0:2] == b'\x32\x00':
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

    def property_is_default(self, item):
        '''
        Check if given property have default value

        :param str item: name of property
        :return: bool
        '''
        if item.startswith('_'):
            raise AttributeError(item)
        # pre-fill cache if enabled
        if self.app.cache_enabled and not self._properties_cache:
            self._fetch_all_properties()
        # cached value
        if item in self._properties_cache:
            return self._properties_cache[item][0]
        # cached properties list
        if self._properties is not None and item not in self._properties:
            raise AttributeError(item)
        try:
            property_str = self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'Get',
                item,
                None)
        except (qubesadmin.exc.QubesDaemonAccessError,
                qubesadmin.exc.QubesVMNotFoundError):
            raise qubesadmin.exc.QubesPropertyAccessError(item)
        is_default, value = self._deserialize_property(property_str)
        if self.app.cache_enabled:
            self._properties_cache[item] = (is_default, value)
        return is_default

    def property_get_default(self, item):
        '''
        Get default property value, regardless of the current value

        :param str item: name of property
        :return: default value
        '''
        if item.startswith('_'):
            raise AttributeError(item)
        try:
            property_str = self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'GetDefault',
                item,
                None)
        except (qubesadmin.exc.QubesDaemonAccessError,
                qubesadmin.exc.QubesVMNotFoundError):
            raise qubesadmin.exc.QubesPropertyAccessError(item)
        if not property_str:
            raise AttributeError(item + ' has no default')
        (prop_type, value) = property_str.split(b' ', 1)
        return self._parse_type_value(prop_type, value)

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
        if item.startswith('_'):
            raise AttributeError(item)
        # pre-fill cache if enabled
        if self.app.cache_enabled and not self._properties_cache:
            self._fetch_all_properties()
        # cached value
        if item in self._properties_cache:
            value = self._properties_cache[item][1]
            if value is AttributeError:
                raise AttributeError(item)
            return value
        # cached properties list
        if self._properties is not None and item not in self._properties:
            raise AttributeError(item)
        try:
            property_str = self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'Get',
                item,
                None)
        except (qubesadmin.exc.QubesDaemonNoResponseError,
                qubesadmin.exc.QubesVMNotFoundError):
            raise qubesadmin.exc.QubesPropertyAccessError(item)
        is_default, value = self._deserialize_property(property_str)
        if self.app.cache_enabled:
            self._properties_cache[item] = (is_default, value)
        if value is AttributeError:
            raise AttributeError(item)
        return value

    def _deserialize_property(self, api_response):
        """
        Deserialize property.Get response format
        :param api_response: bytes, as retrieved from qubesd
        :return: tuple(is_default, value)
        """
        (default, prop_type, value) = api_response.split(b' ', 2)
        assert default.startswith(b'default=')
        is_default_str = default.split(b'=')[1]
        is_default = is_default_str.decode('ascii') == "True"
        value = self._parse_type_value(prop_type, value)
        return is_default, value

    def _parse_type_value(self, prop_type, value):
        '''
        Parse `type=... ...` qubesd response format. Return a value of
        appropriate type.

        :param bytes prop_type: 'type=...' part of the response (including
            `type=` prefix)
        :param bytes value: 'value' part of the response
        :return: parsed value
        '''
        # pylint: disable=too-many-return-statements
        prop_type = prop_type.decode('ascii')
        if not prop_type.startswith('type='):
            raise qubesadmin.exc.QubesDaemonCommunicationError(
                'Invalid type prefix received: {}'.format(prop_type))
        (_, prop_type) = prop_type.split('=', 1)
        value = value.decode()
        if prop_type == 'str':
            return str(value)
        if prop_type == 'bool':
            if value == '':
                return AttributeError
            return value == "True"
        if prop_type == 'int':
            if value == '':
                return AttributeError
            return int(value)
        if prop_type == 'vm':
            if value == '':
                return None
            return self.app.domains.get_blind(value)
        if prop_type == 'label':
            if value == '':
                return None
            return self.app.labels.get_blind(value)
        raise qubesadmin.exc.QubesDaemonCommunicationError(
            'Received invalid value type: {}'.format(prop_type))

    def _fetch_all_properties(self):
        """
        Retrieve all properties values at once using (prefix).property.GetAll
        method. If it succeed, save retrieved values in the properties cache.
        If the request fails (for example because of qrexec policy), do nothing.
        Exceptions when parsing received value are not handled.

        :return: None
        """

        def unescape(line):
            """Handle \\-escaped values, generates a list of character codes"""
            escaped = False
            for char in line:
                if escaped:
                    assert char in (ord('n'), ord('\\'))
                    if char == ord('n'):
                        yield ord('\n')
                    elif char == ord('\\'):
                        yield char
                    escaped = False
                elif char == ord('\\'):
                    escaped = True
                else:
                    yield char
            assert not escaped

        try:
            properties_str = self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'GetAll',
                None,
                None)
        except qubesadmin.exc.QubesDaemonNoResponseError:
            return
        for line in properties_str.splitlines():
            # decode newlines
            line = bytes(unescape(line))
            name, property_str = line.split(b' ', 1)
            name = name.decode()
            is_default, value = self._deserialize_property(property_str)
            self._properties_cache[name] = (is_default, value)
        self._properties = list(self._properties_cache.keys())

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
                if hasattr(class_, "__annotations__"):
                    for key in class_.__annotations__:
                        props.add(key)
            cls._local_properties_set = props

        return cls._local_properties_set

    def __setattr__(self, key, value):
        if key.startswith('_') or key in self._local_properties():
            return super().__setattr__(key, value)
        if value is qubesadmin.DEFAULT:
            try:
                self.qubesd_call(
                    self._method_dest,
                    self._method_prefix + 'Reset',
                    key,
                    None)
            except (qubesadmin.exc.QubesDaemonNoResponseError,
                    qubesadmin.exc.QubesVMNotFoundError):
                raise qubesadmin.exc.QubesPropertyAccessError(key)
        else:
            if isinstance(value, qubesadmin.vm.QubesVM):
                value = value.name
            if value is None:
                value = ''
            try:
                self.qubesd_call(
                    self._method_dest,
                    self._method_prefix + 'Set',
                    key,
                    str(value).encode('utf-8'))
            except (qubesadmin.exc.QubesDaemonNoResponseError,
                    qubesadmin.exc.QubesVMNotFoundError):
                raise qubesadmin.exc.QubesPropertyAccessError(key)

    def __delattr__(self, name):
        if name.startswith('_') or name in self._local_properties():
            return super().__delattr__(name)
        try:
            self.qubesd_call(
                self._method_dest,
                self._method_prefix + 'Reset',
                name
            )
        except (qubesadmin.exc.QubesDaemonNoResponseError,
                qubesadmin.exc.QubesVMNotFoundError):
            raise qubesadmin.exc.QubesPropertyAccessError(name)


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

    def clear_cache(self, invalidate_name=None):
        """Clear cached list of names.
        If *invalidate_name* is given, remove that object from cache
        explicitly too.
        """
        self._names_list = None
        if invalidate_name:
            self._objects.pop(invalidate_name, None)

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
        return self.get_blind(item)

    def get_blind(self, item):
        '''
        Get a property without downloading the list
        and checking if it's present
        '''
        if item not in self._objects:
            self._objects[item] = self._object_class(self.app, item)
        return self._objects[item]

    def __contains__(self, item):
        self.refresh_cache()
        return item in self._names_list

    def __iter__(self):
        self.refresh_cache()
        yield from self._names_list

    def keys(self):
        '''Get list of names.'''
        self.refresh_cache()
        return list(self._names_list)

    def items(self):
        '''Get list of (key, value) pairs'''
        self.refresh_cache()
        return [(key, self.get_blind(key)) for key in self._names_list]

    def values(self):
        '''Get list of objects'''
        self.refresh_cache()
        return [self.get_blind(key) for key in self._names_list]
