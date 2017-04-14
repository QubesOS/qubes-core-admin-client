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

''' GUI daemon launcher tool'''

import os
import signal
import subprocess

import asyncio

import qubesmgmt
import qubesmgmt.events
import qubesmgmt.tools

GUI_DAEMON_PATH = '/usr/bin/qubes-guid'
QUBES_ICON_DIR = '/usr/share/icons/hicolor/128x128/devices'


class GUILauncher(object):
    '''Launch GUI daemon for VMs'''
    def __init__(self, app: qubesmgmt.app.QubesBase):
        ''' Initialize GUILauncher.

        :param app: :py:class:`qubesmgmt.Qubes` instance
        '''
        self.app = app
        self.started_processes = {}

    @staticmethod
    def kde_guid_args(vm):
        '''Return KDE-specific arguments for gui-daemon, if applicable'''

        guid_cmd = []
        # Avoid using environment variables for checking the current session,
        #  because this script may be called with cleared env (like with sudo).
        if subprocess.check_output(
                ['xprop', '-root', '-notype', 'KWIN_RUNNING']) == \
                b'KWIN_RUNNING = 0x1\n':
            # native decoration plugins is used, so adjust window properties
            # accordingly
            guid_cmd += ['-T']  # prefix window titles with VM name
            # get owner of X11 session
            session_owner = None
            for line in subprocess.check_output(['xhost']).splitlines():
                if line == b'SI:localuser:root':
                    pass
                elif line.startswith(b'SI:localuser:'):
                    session_owner = line.split(b':')[2].decode()
            if session_owner is not None:
                data_dir = os.path.expanduser(
                    '~{}/.local/share'.format(session_owner))
            else:
                # fallback to current user
                data_dir = os.path.expanduser('~/.local/share')

            guid_cmd += ['-p',
                '_KDE_NET_WM_COLOR_SCHEME=s:{}'.format(
                    os.path.join(data_dir,
                        'qubes-kde', vm.label.name + '.colors'))]
        return guid_cmd

    def common_guid_args(self, vm):
        '''Common qubes-guid arguments for PV(H), HVM and Stubdomain'''

        guid_cmd = [GUI_DAEMON_PATH,
            '-N', vm.name,
            '-c', vm.label.color,
            '-i', os.path.join(QUBES_ICON_DIR, vm.label.icon) + '.png',
            '-l', str(vm.label.index)]

        if vm.debug:
            guid_cmd += ['-v', '-v']
            #       elif not verbose:
        else:
            guid_cmd += ['-q']

        guid_cmd += self.kde_guid_args(vm)
        return guid_cmd

    @staticmethod
    def guid_pidfile(xid):
        '''Helper function to construct a pidfile path'''
        return '/var/run/qubes/guid-running.{}'.format(xid)

    def start_gui_for_vm(self, vm):
        '''Start GUI daemon (qubes-guid) connected directly to a VM

        This function is a coroutine.
        '''
        guid_cmd = self.common_guid_args(vm)
        guid_cmd.extend(['-d', str(vm.xid)])

        if vm.hvm:
            guid_cmd.extend(['-n'])

            if vm.features.check_with_template('rpc-clipboard', False):
                guid_cmd.extend(['-Q'])

            stubdom_guid_pidfile = self.guid_pidfile(vm.stubdom_xid)
            if not vm.debug and os.path.exists(stubdom_guid_pidfile):
                # Terminate stubdom guid once "real" gui agent connects
                with open(stubdom_guid_pidfile, 'r') as pidfile:
                    stubdom_guid_pid = pidfile.read().strip()
                guid_cmd += ['-K', stubdom_guid_pid]

        return asyncio.create_subprocess_exec(*guid_cmd)

    def start_gui_for_stubdomain(self, vm):
        '''Start GUI daemon (qubes-guid) connected to a stubdomain

        This function is a coroutine.
        '''
        guid_cmd = self.common_guid_args(vm)
        guid_cmd.extend(['-d', str(vm.stubdom_xid), '-t', str(vm.xid)])

        return asyncio.create_subprocess_exec(*guid_cmd)

    @asyncio.coroutine
    def start_gui(self, vm, force_stubdom=False):
        '''Start GUI daemon regardless of start event.

        This function is a coroutine.

        :param vm: VM for which GUI daemon should be started
        :param force_stubdom: Force GUI daemon for stubdomain, even if the
        one for target AppVM is running.
        '''
        if not vm.features.check_with_template('gui', True):
            return

        vm.log.info('Starting GUI')
        if vm.hvm:
            if force_stubdom or not os.path.exists(self.guid_pidfile(vm.xid)):
                if not os.path.exists(self.guid_pidfile(vm.stubdom_xid)):
                    yield from self.start_gui_for_stubdomain(vm)

        if not os.path.exists(self.guid_pidfile(vm.xid)):
            yield from self.start_gui_for_vm(vm)

    def on_domain_spawn(self, vm, _event, **kwargs):
        '''Handler of 'domain-spawn' event, starts GUI daemon for stubdomain'''
        if not vm.features.check_with_template('gui', True):
            return
        if vm.hvm and kwargs.get('start_guid', 'True') == 'True':
            asyncio.ensure_future(self.start_gui_for_stubdomain(vm))

    def on_domain_start(self, vm, _event, **kwargs):
        '''Handler of 'domain-start' event, starts GUI daemon for actual VM'''
        if not vm.features.check_with_template('gui', True):
            return
        if kwargs.get('start_guid', 'True') == 'True':
            asyncio.ensure_future(self.start_gui_for_vm(vm))

    def on_connection_established(self, _subject, _event, **_kwargs):
        '''Handler of 'connection-established' event, used to launch GUI
        daemon for domains started before this tool. '''
        for vm in self.app.domains:
            if isinstance(vm, qubesmgmt.vm.AdminVM):
                continue
            if vm.is_running():
                asyncio.ensure_future(self.start_gui(vm))

    def register_events(self, events):
        '''Register domain startup events in app.events dispatcher'''
        events.add_handler('domain-spawn', self.on_domain_spawn)
        events.add_handler('domain-start', self.on_domain_start)
        events.add_handler('connection-established',
            self.on_connection_established)


parser = qubesmgmt.tools.QubesArgumentParser(
    description='forceful shutdown of a domain', vmname_nargs='*')
parser.add_argument('--watch', action='store_true',
    help='Keep watching for further domains startups, must be used with --all')


def main(args=None):
    ''' Main function of qvm-start-gui tool'''
    args = parser.parse_args(args)
    if args.watch and not args.all_domains:
        parser.error('--watch option must be used with --all')
    launcher = GUILauncher(args.app)
    if args.watch:
        loop = asyncio.get_event_loop()
        events = qubesmgmt.events.EventsDispatcher(args.app)
        launcher.register_events(events)

        events_listener = asyncio.ensure_future(events.listen_for_events())

        for signame in ('SIGINT', 'SIGTERM'):
            loop.add_signal_handler(getattr(signal, signame),
                events_listener.cancel)  # pylint: disable=no-member

        loop.run_until_complete(events_listener)
        loop.stop()
        loop.run_forever()
        loop.close()
    else:
        loop = asyncio.get_event_loop()
        tasks = []
        for vm in args.domains:
            if vm.is_running():
                tasks.append(asyncio.ensure_future(launcher.start_gui(vm)))
        if tasks:
            loop.run_until_complete(asyncio.wait(tasks))
        loop.stop()
        loop.run_forever()
        loop.close()


if __name__ == '__main__':
    main()
