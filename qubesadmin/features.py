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


class Features(object):
    '''Manager of the features.

    Features can have three distinct values: no value (not present in mapping,
    which is closest thing to :py:obj:`None`), empty string (which is
    interpreted as :py:obj:`False`) and non-empty string, which is
    :py:obj:`True`. Anything assigned to the mapping is coerced to strings,
    however if you assign instances of :py:class:`bool`, they are converted as
    described above. Be aware that assigning the number `0` (which is considered
    false in Python) will result in string `'0'`, which is considered true.
    '''
    # pylint: disable=too-few-public-methods

    def __init__(self, vm):
        super().__init__()
        self.vm = vm

    def __delitem__(self, key):
        self.vm.qubesd_call(self.vm.name, 'admin.vm.feature.Remove', key)

    def __setitem__(self, key, value):
        if isinstance(value, bool):
            # False value needs to be serialized as empty string
            self.vm.qubesd_call(self.vm.name, 'admin.vm.feature.Set', key,
                b'1' if value else b'')
        else:
            self.vm.qubesd_call(self.vm.name, 'admin.vm.feature.Set', key,
                str(value).encode())

    def __getitem__(self, item):
        return self.vm.qubesd_call(
            self.vm.name, 'admin.vm.feature.Get', item).decode('utf-8')

    def __iter__(self):
        qubesd_response = self.vm.qubesd_call(self.vm.name,
            'admin.vm.feature.List')
        return iter(qubesd_response.decode('utf-8').splitlines())

    keys = __iter__

    def items(self):
        '''Return iterable of pairs (feature, value)'''
        for key in self:
            yield key, self[key]

    _NO_DEFAULT = object()

    def get(self, item, default=_NO_DEFAULT):
        '''Get a feature, return default value if missing.'''
        try:
            return self[item]
        except KeyError:
            if default is self._NO_DEFAULT:
                raise
            return default

    def check_with_template(self, feature, default=_NO_DEFAULT):
        ''' Check if the vm's template has the specified feature. '''
        try:
            qubesd_response = self.vm.qubesd_call(
                self.vm.name, 'admin.vm.feature.CheckWithTemplate', feature)
            return qubesd_response.decode('utf-8')
        except KeyError:
            if default is self._NO_DEFAULT:
                raise
            return default
