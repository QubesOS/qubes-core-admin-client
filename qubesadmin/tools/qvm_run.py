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
import contextlib
import os
import signal
import subprocess
import sys

import multiprocessing

import select

import qubesadmin.exc
from qubesadmin.toolparsers.qvm_run import get_parser

def copy_stdin(stream):
    '''Copy stdin to *stream*'''
    # multiprocessing.Process have sys.stdin connected to /dev/null, use fd 0
    #  directly
    while True:
        try:
            # select so this code works even if fd 0 is non-blocking
            select.select([0], [], [])
            data = os.read(0, 65536)
            if data is None or data == b'':
                break
            stream.write(data)
            stream.flush()
        except KeyboardInterrupt:
            break
    stream.close()

def print_no_color(msg, file, color):
    '''Print a *msg* to *file* without coloring it.
    Namely reset to base color first, print a message, then restore color.
    '''
    if color:
        print('\033[0m{}\033[0;{}m'.format(msg, color), file=file)
    else:
        print(msg, file=file)


def run_command_single(args, vm):
    '''Handle a single VM to run the command in'''
    run_kwargs = {}
    if not args.passio:
        run_kwargs['stdout'] = subprocess.DEVNULL
        run_kwargs['stderr'] = subprocess.DEVNULL
    elif args.localcmd:
        run_kwargs['stdin'] = subprocess.PIPE
        run_kwargs['stdout'] = subprocess.PIPE
        run_kwargs['stderr'] = None
    else:
        # connect process output to stdout/err directly if --pass-io is given
        run_kwargs['stdout'] = None
        run_kwargs['stderr'] = None
        if args.filter_esc:
            run_kwargs['filter_esc'] = True

    if isinstance(args.app, qubesadmin.app.QubesLocal) and \
            not args.passio and \
            not args.localcmd and \
            args.service and \
            not args.dispvm:
        # wait=False works only in dom0; but it's still useful, to save on
        # simultaneous vchan connections
        run_kwargs['wait'] = False

    copy_proc = None
    local_proc = None
    if args.service:
        service = args.cmd
    else:
        service = 'qubes.VMShell'
        if args.gui and args.dispvm:
            service += '+WaitForSession'
    proc = vm.run_service(service,
        user=args.user,
        **run_kwargs)
    if not args.service:
        proc.stdin.write(vm.prepare_input_for_vmshell(args.cmd))
        proc.stdin.flush()
    if args.localcmd:
        local_proc = subprocess.Popen(args.localcmd,
            shell=True,
            stdout=proc.stdin,
            stdin=proc.stdout)
        # stdin is closed below
        proc.stdout.close()
    elif args.passio:
        copy_proc = multiprocessing.Process(target=copy_stdin,
            args=(proc.stdin,))
        copy_proc.start()
        # keep the copying process running
    proc.stdin.close()
    return proc, copy_proc, local_proc


def main(args=None, app=None):
    '''Main function of qvm-run tool'''
    parser = get_parser()
    args = parser.parse_args(args, app=app)
    if args.passio:
        if args.color_output is None and args.filter_esc:
            args.color_output = 31

        if args.color_stderr is None and os.isatty(sys.stderr.fileno()):
            args.color_stderr = 31

    if len(args.domains) > 1 and args.passio and not args.localcmd:
        parser.error('--passio cannot be used when more than 1 qube is chosen '
                     'and no --localcmd is used')
    if args.localcmd and not args.passio:
        parser.error('--localcmd have no effect without --pass-io')
    if args.color_output and not args.filter_esc:
        parser.error('--color-output must be used with --filter-escape-chars')

    retcode = 0

    verbose = args.verbose - args.quiet
    if args.passio:
        verbose -= 1

    # --all and --exclude are handled by QubesArgumentParser
    domains = args.domains
    dispvm = None
    if args.dispvm:
        if args.exclude:
            parser.error('Cannot use --exclude with --dispvm')
        dispvm = qubesadmin.vm.DispVM.from_appvm(args.app,
            None if args.dispvm is True else args.dispvm)
        domains = [dispvm]
    elif args.all_domains:
        # --all consider only running VMs
        domains = [vm for vm in domains if vm.is_running()]
    if args.color_output:
        sys.stdout.write('\033[0;{}m'.format(args.color_output))
        sys.stdout.flush()
    if args.color_stderr:
        sys.stderr.write('\033[0;{}m'.format(args.color_stderr))
        sys.stderr.flush()
    copy_proc = None
    try:
        procs = []
        for vm in domains:
            if not args.autostart and not vm.is_running():
                if verbose > 0:
                    print_no_color('Qube \'{}\' not started'.format(vm.name),
                        file=sys.stderr, color=args.color_stderr)
                retcode = max(retcode, 1)
                continue
            try:
                if verbose > 0:
                    print_no_color(
                        'Running \'{}\' on {}'.format(args.cmd, vm.name),
                        file=sys.stderr, color=args.color_stderr)
                if args.gui and not args.dispvm:
                    wait_session = vm.run_service('qubes.WaitForSession',
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try:
                        wait_session.communicate(vm.default_user.encode())
                    except KeyboardInterrupt:
                        with contextlib.suppress(ProcessLookupError):
                            wait_session.send_signal(signal.SIGINT)
                        break
                proc, copy_proc, local_proc = run_command_single(args, vm)
                procs.append((vm, proc))
                if local_proc:
                    procs.append((vm, local_proc))
            except qubesadmin.exc.QubesException as e:
                if args.color_output:
                    sys.stdout.write('\033[0m')
                    sys.stdout.flush()
                vm.log.error(str(e))
                return -1
        try:
            for vm, proc in procs:
                this_retcode = proc.wait()
                if this_retcode and verbose > 0:
                    print_no_color(
                        '{}: command failed with code: {}'.format(
                            vm.name, this_retcode),
                        file=sys.stderr, color=args.color_stderr)
                retcode = max(retcode, proc.wait())
        except KeyboardInterrupt:
            for vm, proc in procs:
                with contextlib.suppress(ProcessLookupError):
                    proc.send_signal(signal.SIGINT)
            for vm, proc in procs:
                retcode = max(retcode, proc.wait())
    finally:
        if dispvm:
            dispvm.cleanup()
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
