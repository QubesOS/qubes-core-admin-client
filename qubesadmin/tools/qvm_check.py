# pylint: disable=too-few-public-methods

#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
# Copyright (C) 2019 Frédéric Pierret <frederic.pierret@qubes-os.org>
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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
""" Exits sucessfull if the provided domain(s) exist, else returns failure """

import sys

import qubesadmin.tools
import qubesadmin.vm

class QvmCheckVmNameAction(qubesadmin.tools.VmNameAction):
    """ Action for parsing one or multiple valid/invalid VMNAMEs """

    def __init__(self, option_strings, nargs=1, dest='vmnames', help=None,
                 **kwargs):
        # pylint: disable=redefined-builtin
        super().__init__(option_strings, dest=dest, help=help,
                                           nargs=nargs, **kwargs)

    def parse_qubes_app(self, parent_parser, namespace):
        # pylint: disable=arguments-renamed
        assert hasattr(namespace, 'app')
        setattr(namespace, 'domains', [])
        setattr(namespace, 'invalid_domains', [])
        app = namespace.app
        if hasattr(namespace, 'all_domains') and namespace.all_domains:
            namespace.domains = [
                vm
                for vm in app.domains
                if not vm.klass == 'AdminVM' and
                   vm.name not in namespace.exclude
            ]
        else:
            if hasattr(namespace, 'exclude') and namespace.exclude:
                parent_parser.error('--exclude can only be used with --all')

            for vm_name in getattr(namespace, self.dest):
                try:
                    namespace.domains += [app.domains[vm_name]]
                except KeyError:
                    namespace.invalid_domains += [vm_name]


class QvmCheckArgumentParser(qubesadmin.tools.QubesArgumentParser):
    """ Extended argument parser for qvm-check to collect invalid domains """
    def __init__(self, description):
        super().__init__(description=description, vmname_nargs=None)
        vm_name_group = qubesadmin.tools.VmNameGroup(
                self, required='+', vm_action=QvmCheckVmNameAction)
        self._mutually_exclusive_groups.append(vm_name_group)


parser = QvmCheckArgumentParser(description=__doc__)
parser.add_argument("--running", action="store_true", dest="running",
                    default=False,
                    help="Determine if (any of given) VM is running")
parser.add_argument("--paused", action="store_true", dest="paused",
                    default=False,
                    help="Determine if (any of given) VM is paused")
parser.add_argument("--template", action="store_true", dest="template",
                    default=False,
                    help="Determine if (any of given) VM is a template")
parser.add_argument("--networked", action="store_true", dest="networked",
                    default=False,
                    help="Determine if (any of given) VM can reach network")


def print_msg(log, domains, status):
    """Print message in appropriate form about given valid domain(s)"""
    if not domains:
        log.info("None of qubes: {!s}".format(', '.join(status)))
    else:
        for vm in sorted(list(domains)):
            log.info("{!s}: {!s}".format(vm.name, ', '.join(status)))


def get_filters(args):
    """Get status and check functions"""
    filters = []

    if args.running:
        filters.append({'status': 'running', 'check': lambda x: x.is_running()})
    if args.paused:
        filters.append({'status': 'paused', 'check': lambda x: x.is_paused()})
    if args.template:
        filters.append(
            {'status': 'template', 'check': lambda x: x.klass == 'TemplateVM'})
    if args.networked:
        filters.append(
            {'status': 'networked', 'check': lambda x: x.is_networked()})

    return filters


def main(args=None, app=None):
    """Main function of qvm-check tool"""
    args = parser.parse_args(args, app=app)
    domains = args.domains
    invalid_domains = set(args.invalid_domains)
    return_code = 0

    log = args.app.log
    log.name = "qvm-check"

    status = []
    filters = get_filters(args)
    filtered_domains = set(domains)
    if filters:
        for filt in filters:
            status.append(filt['status'])
            check = filt['check']
            filtered_domains = filtered_domains.intersection(
                [vm for vm in domains if check(vm)])

        if set(domains) & set(filtered_domains) != set(domains):
            if not filtered_domains:
                return_code = 1
            else:
                return_code = 3

        if args.verbose:
            print_msg(log, filtered_domains, status)
    else:
        if not domains:
            return_code = 1
        elif args.verbose:
            print_msg(log, domains, ["exists"])

    if invalid_domains:
        if args.verbose:
            for vm in invalid_domains:
                log.warning("{!s}: {!s}".format(vm, 'non-existent!'))
        return_code = 1

    return return_code


if __name__ == '__main__':
    sys.exit(main())
