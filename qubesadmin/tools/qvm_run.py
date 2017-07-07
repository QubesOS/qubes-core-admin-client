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

''' qvm-run tool'''

import os
import sys

import subprocess

import qubesadmin.tools
import qubesadmin.exc

parser = qubesadmin.tools.QubesArgumentParser(vmname_nargs='+')

parser.add_argument('--user', '-u', metavar='USER',
    help='run command in a qube as USER (available only from dom0)')

parser.add_argument('--autostart', '--auto', '-a',
    action='store_true', default=True,
    help='option ignored, this is default')

parser.add_argument('--no-autostart', '--no-auto', '-n',
    action='store_false',
    help='do not autostart qube')

parser.add_argument('--pass-io', '-p',
    action='store_true', dest='passio', default=False,
    help='pass stdio from remote program')

parser.add_argument('--localcmd', metavar='COMMAND',
    help='with --pass-io, pass stdio to the given program')

parser.add_argument('--gui',
    action='store_true', default=True,
    help='run the command with GUI (default on)')

parser.add_argument('--no-gui', '--nogui',
    action='store_false', dest='gui',
    help='run the command without GUI')

parser.add_argument('--colour-output', '--color-output', metavar='COLOUR',
    action='store', dest='color_output', default=None,
    help='mark the qube output with given ANSI colour (ie. "31" for red)')

parser.add_argument('--colour-stderr', '--color-stderr', metavar='COLOUR',
    action='store', dest='color_stderr', default=None,
    help='mark the qube stderr with given ANSI colour (ie. "31" for red)')

parser.add_argument('--no-colour-output', '--no-color-output',
    action='store_false', dest='color_output',
    help='disable colouring the stdio')

parser.add_argument('--no-colour-stderr', '--no-color-stderr',
    action='store_false', dest='color_stderr',
    help='disable colouring the stderr')

parser.add_argument('--filter-escape-chars',
    action='store_true', dest='filter_esc',
    default=os.isatty(sys.stdout.fileno()),
    help='filter terminal escape sequences (default if output is terminal)')

parser.add_argument('--no-filter-escape-chars',
    action='store_false', dest='filter_esc',
    help='do not filter terminal escape sequences; DANGEROUS when output is a'
        ' terminal emulator')

parser.add_argument('--service',
    action='store_true', dest='service',
    help='run a qrexec service (named by COMMAND) instead of shell command')

parser.add_argument('cmd', metavar='COMMAND',
    help='command to run')

def main(args=None, app=None):
    '''Main function of qvm-run tool'''
    args = parser.parse_args(args, app=app)
    if args.color_output is None and args.filter_esc:
        args.color_output = '31'

    if args.color_output is None and os.isatty(sys.stderr.fileno()):
        args.color_stderr = 31

    if len(args.domains) > 1 and args.passio and not args.localcmd:
        parser.error('--passio cannot be used when more than 1 qube is chosen '
                     'and no --localcmd is used')
    if args.localcmd and not args.passio:
        parser.error('--localcmd have no effect without --pass-io')
    if args.color_output and not args.filter_esc:
        parser.error('--color-output must be used with --filter-escape-chars')

    retcode = 0
    run_kwargs = {}
    if not args.passio:
        run_kwargs['stdout'] = subprocess.DEVNULL
        run_kwargs['stderr'] = subprocess.DEVNULL
    else:
        # connect process output to stdout/err directly if --pass-io is given
        run_kwargs['stdout'] = None
        run_kwargs['stderr'] = None

    if isinstance(args.app, qubesadmin.app.QubesLocal) and \
            not args.passio and not args.localcmd and args.service:
        # wait=False works only in dom0; but it's still useful, to save on
        # simultaneous vchan connections
        run_kwargs['wait'] = False

    verbose = args.verbose - args.quiet
    if args.passio:
        verbose -= 1

    if args.color_output:
        sys.stdout.write('\033[0;{}m'.format(args.color_output))
        sys.stdout.flush()
    if args.color_stderr:
        sys.stderr.write('\033[0;{}m'.format(args.color_stderr))
        sys.stderr.flush()
    copy_proc = None
    try:
        procs = []
        for vm in args.domains:
            if not args.autostart and not vm.is_running():
                continue
            try:
                if verbose > 0:
                    if args.color_output:
                        print('\033[0mRunning \'{}\' on {}\033[0;{}m'.format(
                            args.cmd, vm.name, args.color_output),
                            file=sys.stderr)
                    else:
                        print('Running \'{}\' on {}'.format(args.cmd, vm.name),
                            file=sys.stderr)
                if args.gui:
                    wait_session = vm.run_service('qubes.WaitForSession',
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    wait_session.communicate(vm.default_user.encode())
                if args.service:
                    proc = vm.run_service(args.cmd,
                        user=args.user,
                        localcmd=args.localcmd,
                        filter_esc=args.filter_esc,
                        **run_kwargs)
                else:
                    proc = vm.run_service('qubes.VMShell',
                        user=args.user,
                        localcmd=args.localcmd,
                        filter_esc=args.filter_esc,
                        **run_kwargs)
                    proc.stdin.write(vm.prepare_input_for_vmshell(args.cmd))
                    proc.stdin.flush()
                if args.passio and not args.localcmd:
                    copy_proc = subprocess.Popen(['cat'], stdin=sys.stdin,
                        stdout=proc.stdin)
                    # keep the copying process running
                proc.stdin.close()
                procs.append(proc)
            except qubesadmin.exc.QubesException as e:
                if args.color_output:
                    sys.stdout.write('\033[0m')
                    sys.stdout.flush()
                vm.log.error(str(e))
                return -1
        for proc in procs:
            retcode = max(retcode, proc.wait())
    finally:
        if args.color_output:
            sys.stdout.write('\033[0m')
            sys.stdout.flush()
        if args.color_stderr:
            sys.stderr.write('\033[0m')
            sys.stderr.flush()
        if copy_proc is not None:
            copy_proc.terminate()

    return retcode


if __name__ == '__main__':
    sys.exit(main())
