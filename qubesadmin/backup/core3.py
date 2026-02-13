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

'''Parser for core3 qubes.xml'''
import io
import xml.parsers.expat
import logging
import lxml.etree

import qubesadmin.backup
import qubesadmin.firewall
from qubesadmin import device_protocol
from lxml.etree import _Element

from qubesadmin.vm import QubesVM


class Core3VM(qubesadmin.backup.BackupVM):
    '''VM object'''
    # pylint: disable=too-few-public-methods
    @property
    def included_in_backup(self) -> bool:
        return self.backup_path is not None

    def handle_firewall_xml(self, vm: QubesVM, stream: io.BytesIO) -> None:
        '''Load new (Qubes >= 4.0) firewall XML format'''
        try:
            tree = lxml.etree.parse(stream)  # pylint: disable=no-member
            xml_root = tree.getroot()
            rules = []
            for rule_node in xml_root.findall('./rules/rule'):
                rule_opts = {}
                for rule_opt in rule_node.findall('./properties/property'):
                    rule_opts[rule_opt.get('name')] = rule_opt.text
                rules.append(qubesadmin.firewall.Rule(None, **rule_opts))

            vm.firewall.rules = rules
        except:  # pylint: disable=bare-except
            vm.log.exception('Failed to set firewall')

    def handle_notes_txt(self, vm: QubesVM, stream: io.BytesIO) -> None:
        '''Load new (Qubes >= 4.2) notes'''
        try:
            vm.set_notes(stream.read().decode())
        except:  # pylint: disable=bare-except
            vm.log.exception('Failed to set notes')

class Core3Qubes(qubesadmin.backup.BackupApp):
    '''Parsed qubes.xml'''
    def __init__(self, store: str | None=None):
        if store is None:
            raise ValueError("store path required")
        self.log = logging.getLogger('qubesadmin.backup.core3')
        self.labels = {}
        super().__init__(store)

    @staticmethod
    def get_property(xml_obj: _Element, prop: str) -> str | None:
        '''Get property of given object (XML node)

        Object can be any PropertyHolder serialized to XML - in practice
        :py:class:`BaseVM` or :py:class:`Qubes`.
        '''
        xml_prop = xml_obj.findall('./property[@name=\'{}\']'.format(prop))
        if not xml_prop:
            raise KeyError(prop)
        return xml_prop[0].text

    def load_labels(self, labels_element: _Element) -> None:
        '''Load labels table'''
        for node in labels_element.findall('label'):
            ident = node.get('id')
            assert ident is not None
            self.labels[ident] = node.text
            self.labels[node.text] = node.text


    def load_globals(self, globals_element: _Element) -> None:
        '''Load global settings

        :param globals_element: XML element containing global settings
        '''
        for node in globals_element.findall('property'):
            name = node.get('name')
            assert name is not None
            self.globals[name] = node.text

    def import_core3_vm(self, element: _Element) -> None:
        '''Parse a single VM from given XML node

        This method load only VM properties not depending on other VMs
        (other than template). VM connections are set later.
        :param element: XML node
        '''
        vm = Core3VM()
        vm.klass = element.get('class')

        for node in element.findall('./properties/property'):
            name = node.get('name')
            assert name is not None
            vm.properties[name] = node.text

        for node in element.findall('./features/feature'):
            name = node.get('name')
            assert name is not None
            vm.features[name] = False if node.text is None else node.text

        for node in element.findall('./tags/tag'):
            name = node.get('name')
            assert name is not None
            vm.tags.add(name)

        for bus_node in element.findall('./devices'):
            bus_name = bus_node.get('class')
            assert bus_name is not None
            for node in bus_node.findall('./device'):
                backend_domain = node.get('backend-domain')
                port_id = node.get('id')
                options = {}
                for opt_node in node.findall('./option'):
                    opt_name = opt_node.get('name')
                    options[opt_name] = opt_node.text
                options['required'] = device_protocol.qbool(
                    node.get('required', 'yes'))
                vm.devices[bus_name][(backend_domain, port_id)] = options

        # extract base properties
        if vm.klass == 'AdminVM':
            vm.name = 'dom0'
        else:
            vm.name = vm.properties.pop('name')
        vm.label = self.labels[vm.properties.pop('label')]
        vm.template = vm.properties.pop('template', None)
        # skip UUID and qid, will be generated during restore
        vm.properties.pop('uuid', None)
        vm.properties.pop('qid', None)

        if vm.features.pop('backup-content', False):
            vm.backup_path = vm.features.pop('backup-path', None)
            vm.size = vm.features.pop('backup-size', 0)

        self.domains[vm.name] = vm

    def load(self) -> bool | None:
        with open(self.store, encoding='utf-8') as fh:
            try:
                # pylint: disable=no-member
                tree = lxml.etree.parse(fh)
            except (EnvironmentError,  # pylint: disable=broad-except
                    xml.parsers.expat.ExpatError) as err:
                self.log.error(err)
                return False

        self.load_labels(tree.find('./labels'))

        for element in tree.findall('./domains/domain'):
            self.import_core3_vm(element)

        # and load other defaults (default netvm, updatevm etc)
        self.load_globals(tree.find('./properties'))
