# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

'''VM tags interface'''
from __future__ import annotations
from collections.abc import Iterator

import typing
if typing.TYPE_CHECKING:
    from qubesadmin.vm import QubesVM


class Tags:
    '''Manager of the tags.

    Tags are simple: tag either can be present on qube or not. Tag is a
    simple string consisting of ASCII alphanumeric characters, plus `_` and
    `-`.
    '''

    def __init__(self, vm: QubesVM):
        super().__init__()
        self.vm = vm
        self._membership_cache: dict[str, bool] = {}
        self._names_cache: list[str] | None = None

    def clear_cache(self) -> None:
        '''Discard cached tag membership and tag names.'''
        self._membership_cache.clear()
        self._names_cache = None

    def record_membership(self, elem: str, is_present: bool) -> None:
        '''Cache tag membership confirmed by qubesd.'''
        if not self.vm.app.cache_enabled:
            return
        self._membership_cache[elem] = is_present
        if self._names_cache is None:
            return
        if is_present and elem not in self._names_cache:
            self._names_cache.append(elem)
        if not is_present and elem in self._names_cache:
            self._names_cache.remove(elem)

    def remove(self, elem: str) -> None:
        '''Remove a tag'''
        self.vm.qubesd_call(self.vm.name, 'admin.vm.tag.Remove', elem)
        self.record_membership(elem, False)

    def add(self, elem: str) -> None:
        '''Add a tag'''
        self.vm.qubesd_call(self.vm.name, 'admin.vm.tag.Set', elem)
        self.record_membership(elem, True)

    def update(self, *others) -> None:
        '''Add tags from iterable(s)'''
        for other in others:
            for elem in other:
                self.add(elem)

    def discard(self, elem: str) -> None:
        '''Remove a tag if present'''
        try:
            self.remove(elem)
        except KeyError:
            pass

    def __iter__(self) -> Iterator[str]:
        if self._names_cache is not None:
            return iter(self._names_cache)
        qubesd_response = self.vm.qubesd_call(self.vm.name,
            'admin.vm.tag.List')
        names = qubesd_response.decode('utf-8').splitlines()
        if self.vm.app.cache_enabled:
            self._names_cache = names
        return iter(names)

    def __contains__(self, elem: str) -> bool:
        '''Does the VM have a tag'''
        if elem in self._membership_cache:
            return self._membership_cache[elem]
        response = self.vm.qubesd_call(self.vm.name, 'admin.vm.tag.Get', elem)
        is_present = response == b'1'
        if self.vm.app.cache_enabled:
            self._membership_cache[elem] = is_present
        return is_present
