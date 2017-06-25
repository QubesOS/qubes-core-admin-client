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


class Tags(object):
    '''Manager of the tags.

    Tags are simple: tag either can be present on qube or not. Tag is a
    simple string consisting of ASCII alphanumeric characters, plus `_` and
    `-`.
    '''
    # pylint: disable=too-few-public-methods

    def __init__(self, vm):
        super(Tags, self).__init__()
        self.vm = vm

    def remove(self, elem):
        '''Remove a tag'''
        self.vm.qubesd_call(self.vm.name, 'admin.vm.tag.Remove', elem)

    def add(self, elem):
        '''Add a tag'''
        self.vm.qubesd_call(self.vm.name, 'admin.vm.tag.Set', elem)

    def update(self, *others):
        '''Add tags from iterable(s)'''
        for other in others:
            for elem in other:
                self.add(elem)

    def discard(self, elem):
        '''Remove a tag if present'''
        try:
            self.remove(elem)
        except KeyError:
            pass

    def __iter__(self):
        qubesd_response = self.vm.qubesd_call(self.vm.name,
            'admin.vm.tag.List')
        return iter(qubesd_response.decode('utf-8').splitlines())

    def __contains__(self, elem):
        '''Does the VM have a tag'''
        response = self.vm.qubesd_call(self.vm.name, 'admin.vm.tag.Get', elem)
        return response == b'1'
