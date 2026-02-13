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

'''Parser for core2 qubes.xml'''

import ast
import io
import typing
import xml.parsers
import logging
import lxml.etree
from lxml.etree import _Element

from qubesadmin.firewall import Rule, Action, Proto, DstHost, SpecialTarget
import qubesadmin.backup
from qubesadmin.vm import QubesVM

service_to_feature = {
    'ntpd': 'service.ntpd',
    'qubes-update-check': 'check-updates',
    'meminfo-writer': 'service.meminfo-writer',
}

class Core2VM(qubesadmin.backup.BackupVM):
    '''VM object'''
    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        super().__init__()
        self.backup_content = False

    @property
    def included_in_backup(self) -> bool:
        return self.backup_content

    @staticmethod
    def rule_from_xml_v1(node: _Element, action: str) -> Rule:
        '''Parse single rule in old XML format (pre Qubes 4.0)

        :param node: XML node for the rule
        :param action: action to apply (in old format it wasn't part of the
            rule itself)
        '''
        netmask = node.get('netmask')
        if netmask is None:
            netmask = 32
        else:
            netmask = int(netmask)
        address = node.get('address')
        if address:
            dsthost = DstHost(address, netmask)
        else:
            dsthost = None

        proto = node.get('proto')

        port = node.get('port')
        toport = node.get('toport')
        if port and toport:
            dstports = port + '-' + toport
        elif port:
            dstports = port
        else:
            dstports = None

        # backward compatibility: protocol defaults to TCP if port is specified
        if dstports and not proto:
            proto = 'tcp'

        if proto == 'any':
            proto = None

        expire = node.get('expire')

        kwargs = {
            'action': action,
        }
        if dsthost:
            kwargs['dsthost'] = dsthost
        if dstports:
            kwargs['dstports'] = dstports
        if proto:
            kwargs['proto'] = proto
        if expire:
            kwargs['expire'] = expire

        return Rule(None, **kwargs)


    def handle_firewall_xml(self, vm: QubesVM, stream: io.BytesIO) -> None:
        '''Load old (Qubes < 4.0) firewall XML format'''
        try:
            tree = lxml.etree.parse(stream)  # pylint: disable=no-member
            xml_root = tree.getroot()
            policy_v1 = xml_root.get('policy')
            assert policy_v1 in ('allow', 'deny')
            default_policy_is_accept = (policy_v1 == 'allow')
            rules: list[Rule] = []

            def _translate_action(key: str) -> str:
                '''Translate action name'''
                if xml_root.get(key, policy_v1) == 'allow':
                    return Action.accept
                return Action.drop

            rules.append(Rule(None,
                action=_translate_action('dns'),
                specialtarget=SpecialTarget('dns')))

            rules.append(Rule(None,
                action=_translate_action('icmp'),
                proto=Proto.icmp))

            if default_policy_is_accept:
                rule_action = Action.drop
            else:
                rule_action = Action.accept

            for element in xml_root:
                rule = self.rule_from_xml_v1(element, rule_action)
                rules.append(rule)
            if default_policy_is_accept:
                rules.append(Rule(None, action='accept'))
            else:
                rules.append(Rule(None, action='drop'))

            vm.firewall.rules = rules
        except:  # pylint: disable=bare-except
            vm.log.exception('Failed to set firewall')

    def handle_notes_txt(self, vm: QubesVM, stream: io.BytesIO) -> None:
        '''Qube notes did not exist at this time'''
        raise NotImplementedError  # pragma: no cover


class Core2Qubes(qubesadmin.backup.BackupApp):
    '''Parsed qubes.xml'''
    def __init__(self, store: str | None=None):
        if store is None:
            raise ValueError("store path required")
        self.qid_map = {}
        self.log = logging.getLogger('qubesadmin.backup.core2')
        super().__init__(store)

    def load_globals(self, element: _Element) -> None:
        '''Load global settings

        :param element: XML element containing global settings (root node)
        '''
        default_netvm = element.get("default_netvm")
        if default_netvm is not None:
            self.globals['default_netvm'] = self.qid_map[int(default_netvm)] \
                if default_netvm != "None" else None

        # default_fw_netvm = element.get("default_fw_netvm")
        # if default_fw_netvm is not None:
        #     self.globals['default_fw_netvm'] = \
        #         self.qid_map[int(default_fw_netvm)] \
        #         if default_fw_netvm != "None" else None

        updatevm = element.get("updatevm")
        if updatevm is not None:
            self.globals['updatevm'] = self.qid_map[int(updatevm)] \
                if updatevm != "None" else None

        clockvm = element.get("clockvm")
        if clockvm is not None:
            self.globals['clockvm'] = self.qid_map[int(clockvm)] \
                if clockvm != "None" else None

        default_template = element.get("default_template")
        # TODO or should it be `if is not None: ... ?`
        assert default_template is not None
        self.globals['default_template'] = self.qid_map[int(default_template)] \
            if default_template.lower() != "none" else None


    def set_netvm_dependency(self, element: _Element) -> None:
        '''Set dependencies between VMs'''
        kwargs = {}
        attr_list = ("name", "uses_default_netvm", "netvm_qid")

        for attribute in attr_list:
            kwargs[attribute] = element.get(attribute)

        vm = self.domains[kwargs["name"]]

        # netvm property
        if element.get("uses_default_netvm") is None:
            uses_default_netvm = True
        else:
            uses_default_netvm = (element.get("uses_default_netvm") == "True")
        if not uses_default_netvm:
            netvm_qid = element.get("netvm_qid")
            if netvm_qid is None or netvm_qid == "none":
                vm.properties['netvm'] = None
            else:
                vm.properties['netvm'] = self.qid_map[int(netvm_qid)]

        # And DispVM netvm, translated to default_dispvm
        if element.get("uses_default_dispvm_netvm") is None:
            uses_default_dispvm_netvm = True
        else:
            uses_default_dispvm_netvm = (
                element.get("uses_default_dispvm_netvm") == "True")
        if not uses_default_dispvm_netvm:
            dispvm_netvm_qid = element.get("dispvm_netvm_qid")
            if dispvm_netvm_qid is None or dispvm_netvm_qid == "none":
                dispvm_netvm = None
            else:
                dispvm_netvm = self.qid_map[int(dispvm_netvm_qid)]
        else:
            dispvm_netvm = vm.properties.get('netvm', self.globals[
                'default_netvm'])

        if dispvm_netvm != self.globals['default_netvm']:
            if dispvm_netvm:
                dispvm_tpl_name = 'disp-{}'.format(dispvm_netvm)
            else:
                dispvm_tpl_name = 'disp-no-netvm'

            vm.properties['default_dispvm'] = dispvm_tpl_name

            if dispvm_tpl_name not in self.domains:
                vm = Core2VM()
                vm.name = dispvm_tpl_name
                vm.label = 'red'
                vm.properties['netvm'] = dispvm_netvm
                vm.properties['template_for_dispvms'] = True
                vm.backup_content = True
                vm.backup_path = None
                self.domains[vm.name] = vm
                # TODO: add support for #2075
            # TODO: set qrexec policy based on dispvm_netvm value

    def import_core2_vm(self, element: _Element) -> None:
        '''Parse a single VM from given XML node

        This method load only VM properties not depending on other VMs
        (other than template). VM connections are set later.
        :param element: XML node
        '''
        vm_class_name = typing.cast(str, element.tag)
        vm = Core2VM()
        vm.name = element.get('name')
        vm.label = element.get('label', 'red')
        self.domains[vm.name] = vm
        kwargs = {}
        if vm_class_name in ["QubesTemplateVm", "QubesTemplateHVm"]:
            vm.klass = "TemplateVM"
        elif element.get('qid') == '0':
            kwargs['dir_path'] = element.get('dir_path')
            vm.klass = "AdminVM"
        else:
            template_qid = element.get('template_qid')
            # TODO should that be a .get(..., 'none') ?
            assert template_qid is not None
            if template_qid.lower() == "none":
                kwargs['dir_path'] = element.get('dir_path')
                vm.klass = "StandaloneVM"
            else:
                kwargs['dir_path'] = element.get('dir_path')
                vm.template = \
                    self.qid_map[int(template_qid)]
                vm.klass = "AppVM"

        vm.backup_content = element.get('backup_content', False) == 'True'
        vm.backup_path = element.get('backup_path', None)
        vm.size = element.get('backup_size', 0)

        if vm.klass == 'AdminVM':
            # don't set any other dom0 property
            return

        # simple attributes
        for attr, default in {
            #'installed_by_rpm': 'False',
            'include_in_backups': 'True',
            'qrexec_timeout': '60',
            'vcpus': '2',
            'memory': '400',
            'maxmem': '4000',
            'default_user': 'user',
            'debug': 'False',
            'mac': None,
            'autostart': 'False'}.items():
            value = element.get(attr)
            if value and value != default:
                vm.properties[attr] = value
        # attributes with default value
        for attr in ["kernel", "kernelopts"]:
            value = element.get(attr)
            if value and value.lower() == "none":
                value = None
            value_is_default = element.get(
                "uses_default_{}".format(attr))
            if value_is_default and value_is_default.lower() != \
                    "true":
                vm.properties[attr] = value
        if "HVm" in vm_class_name:
            vm.properties['virt_mode'] = 'hvm'
            vm.properties['kernel'] = ''
            # Qubes 3.2 used MiniOS stubdomain (with qemu-traditional); keep
            # it this way, otherwise some OSes (Windows) will crash because
            # of substantial hardware change
            vm.features['linux-stubdom'] = False
        if vm_class_name in ('QubesNetVm', 'QubesProxyVm'):
            vm.properties['provides_network'] = True
        if vm_class_name == 'QubesNetVm':
            vm.properties['netvm'] = None
        if vm_class_name == 'QubesTemplateVm' or \
                (vm_class_name == 'QubesAppVm' and vm.template is None):
            # PV VMs in Qubes 3.x assumed gui-agent and qrexec-agent installed
            vm.features['qrexec'] = True
            vm.features['gui'] = True
        if element.get('internal', False) == 'True':
            vm.features['internal'] = True

        services = element.get('services')
        if services:
            services = ast.literal_eval(services)
        else:
            services = {}
        for service, value in services.items():
            feature = service
            for repl_service, repl_feature in \
                    service_to_feature.items():
                if repl_service == service:
                    feature = repl_feature
            vm.features[feature] = value

        pci_strictreset = element.get('pci_strictreset', True)
        # TODO there should be some kind of XML validation
        pcidevs = element.get('pcidevs')
        pcidevs_list = []
        if pcidevs:
            pcidevs_list = ast.literal_eval(pcidevs)
        for pcidev in pcidevs_list:
            port_id = pcidev.replace(':', '_')
            options = {'no-strict-reset': True} if not pci_strictreset else {}
            options['required'] = True
            vm.devices['pci'][('dom0', port_id)] = options

    def load(self) -> bool | None:
        assert self.store is not None
        with open(self.store, encoding='utf-8') as fh:
            try:
                # pylint: disable=no-member
                tree = lxml.etree.parse(fh)
            except (EnvironmentError,  # pylint: disable=broad-except
                    xml.parsers.expat.ExpatError) as err:
                self.log.error(err)
                return False

        self.globals['default_kernel'] = tree.getroot().get("default_kernel")

        vm_classes = ["AdminVm", "TemplateVm", "TemplateHVm",
            "AppVm", "HVm", "NetVm", "ProxyVm"]

        # First build qid->name map
        for vm_class_name in vm_classes:
            vms_of_class = tree.findall("Qubes" + vm_class_name)
            for element in vms_of_class:
                qid = element.get('qid', None)
                name = element.get('name', None)
                if qid and name:
                    self.qid_map[int(qid)] = name

        # Qubes R2 din't have dom0 in qubes.xml
        if 0 not in self.qid_map:
            vm = Core2VM()
            vm.name = 'dom0'
            vm.klass = 'AdminVM'
            vm.label = 'black'
            self.domains['dom0'] = vm
            self.qid_map[0] = 'dom0'

        # Then load all VMs - since we have qid_map, no need to preserve
        # specific load older.
        for vm_class_name in vm_classes:
            vms_of_class = tree.findall("Qubes" + vm_class_name)
            for element in vms_of_class:
                self.import_core2_vm(element)

        # ... and load other VMs
        for vm_class_name in ["AppVm", "HVm", "NetVm", "ProxyVm"]:
            vms_of_class = tree.findall("Qubes" + vm_class_name)
            # first non-template based, then template based
            sorted_vms_of_class = sorted(vms_of_class,
                key=lambda x: str(x.get('template_qid')).lower() != "none")
            for element in sorted_vms_of_class:
                self.import_core2_vm(element)

        # and load other defaults (default netvm, updatevm etc)
        self.load_globals(tree.getroot())

        # After importing all VMs, set netvm references, in the same order
        for vm_class_name in vm_classes:
            for element in tree.findall("Qubes" + vm_class_name):
                try:
                    self.set_netvm_dependency(element)
                except (ValueError, LookupError) as err:
                    self.log.error("VM %s: failed to set netvm dependency: %s",
                        element.get('name'), err)
