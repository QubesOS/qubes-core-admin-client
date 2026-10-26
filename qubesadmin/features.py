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

'''VM features interface'''
from __future__ import annotations

import typing
from typing import TypeVar
from collections.abc import Iterator, Generator

from qubesadmin.exc import QubesFeatureNotFoundError

if typing.TYPE_CHECKING:
    from qubesadmin.vm import QubesVM

T = TypeVar('T')

class Features:
    '''Manager of the features.

    Features can have three distinct values: no value (not present in mapping,
    which is closest thing to :py:obj:`None`), empty string (which is
    interpreted as :py:obj:`False`) and non-empty string, which is
    :py:obj:`True`. Anything assigned to the mapping is coerced to strings,
    however if you assign instances of :py:class:`bool`, they are converted as
    described above. Be aware that assigning the number `0` (which is considered
    false in Python) will result in string `'0'`, which is considered true.
    '''

    def __init__(self, vm: QubesVM):
        super().__init__()
        self.vm = vm
        self._values_cache: dict[str, str] = {}
        self._missing_cache: dict[str, str] = {}
        self._names_cache: list[str] | None = None

    def clear_cache(self) -> None:
        '''Discard cached direct values, missing features and feature names.'''
        self._values_cache.clear()
        self._missing_cache.clear()
        self._names_cache = None

    def record_value(self, key: str, value: str) -> None:
        '''Cache a feature value confirmed by qubesd.'''
        if not self.vm.app.cache_enabled:
            return
        self._missing_cache.pop(key, None)
        self._values_cache[key] = value
        if self._names_cache is not None and key not in self._names_cache:
            self._names_cache.append(key)

    def record_removal(self, key: str) -> None:
        '''Drop a feature that qubesd confirmed as removed.'''
        if not self.vm.app.cache_enabled:
            return
        self._values_cache.pop(key, None)
        if self._names_cache is not None and key in self._names_cache:
            self._names_cache.remove(key)

    def __delitem__(self, key: str) -> None:
        self.vm.qubesd_call(self.vm.name, 'admin.vm.feature.Remove', key)
        self.record_removal(key)

    def __setitem__(self, key: str, value: object) -> None:
        if isinstance(value, bool):
            # False value needs to be serialized as empty string
            serialized = '1' if value else ''
        else:
            serialized = str(value)
        self.vm.qubesd_call(self.vm.name, 'admin.vm.feature.Set', key,
                            serialized.encode())
        self.record_value(key, serialized)

    def __getitem__(self, item: str) -> str:
        if item in self._values_cache:
            return self._values_cache[item]
        if item in self._missing_cache:
            raise QubesFeatureNotFoundError(
                self._missing_cache[item].replace('%', '%%'))
        try:
            value = self.vm.qubesd_call(
                self.vm.name, 'admin.vm.feature.Get', item).decode('utf-8')
        except QubesFeatureNotFoundError as error:
            if self.vm.app.cache_enabled:
                self._missing_cache[item] = error.args[0]
            raise
        if self.vm.app.cache_enabled:
            self._values_cache[item] = value
        return value

    def __iter__(self) -> Iterator[str]:
        if self._names_cache is not None:
            return iter(self._names_cache)
        qubesd_response = self.vm.qubesd_call(self.vm.name,
            'admin.vm.feature.List')
        names = qubesd_response.decode('utf-8').splitlines()
        if self.vm.app.cache_enabled:
            self._names_cache = names
        return iter(names)

    keys = __iter__

    def items(self) -> Generator[tuple[str, str]]:
        '''Return iterable of pairs (feature, value)'''
        for key in self:
            yield key, self[key]

    NO_DEFAULT = object()

    @typing.overload
    def get(self, item: str) -> str | None: ...
    @typing.overload
    def get(self, item: str, default: T) -> str | T: ...
    # Overloaded to handle default None return type
    def get(self, item: str, default: object = None) -> object:
        '''Get a feature, return default value if missing.'''
        try:
            return self[item]
        except KeyError:
            if default is self.NO_DEFAULT:
                raise
            return default

    @typing.overload
    def check_with_template(self, item: str) -> str | None: ...
    @typing.overload
    def check_with_template(self, item: str, default: T) -> str | T: ...
    # Overloaded to handle default None return type
    def check_with_template(self, feature: str,
                            default: object = None) -> object:
        ''' Check if the vm's template has the specified feature. '''
        try:
            qubesd_response = self.vm.qubesd_call(
                self.vm.name, 'admin.vm.feature.CheckWithTemplate', feature)
            return qubesd_response.decode('utf-8')
        except KeyError:
            if default is self.NO_DEFAULT:
                raise
            return default
