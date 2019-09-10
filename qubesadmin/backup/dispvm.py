#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2019 Marek Marczykowski-Górecki
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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Handle backup extraction using DisposableVM"""
import datetime
import logging
import string

import subprocess
#import typing
import qubesadmin
import qubesadmin.exc
import qubesadmin.utils
import qubesadmin.vm

LOCKFILE = '/var/run/qubes/backup-paranoid-restore.lock'

Option = collections.namedtuple('Option', ('opts', 'handler'))

# Convenient functions for 'handler' value of Option object
#  (see RestoreInDisposableVM.arguments):

def handle_store_true(option, value):
    """Handle argument enabling an option (action="store_true")"""
    if value:
        return [option.opts[0]]
    return []


def handle_store_false(option, value):
    """Handle argument disabling an option (action="false")"""
    if not value:
        return [option.opts[0]]
    return []

def handle_verbose(option, value):
    """Handle argument --quiet / --verbose options (action="count")"""
    if option.opts[0] == '--verbose':
        value -= 1  # verbose defaults to 1
    return [option.opts[0]] * value


def handle_store(option, value):
    """Handle argument with arbitrary string value (action="store")"""
    if value:
        return [option.opts[0], str(value)]
    return []


def handle_append(option, value):
    """Handle argument with a list of values (action="append")"""
    return itertools.chain(*([option.opts[0], v] for v in value))


def skip(_option, _value):
    """Skip argument"""
    return []


def handle_unsupported(option, value):
    """Reject argument as unsupported"""
    if value:
        raise NotImplementedError(
            '{} option is not supported with --paranoid-mode'.format(
                option.opts[0]))
    return []

class RestoreInDisposableVM:
    """Perform backup restore with actual archive extraction isolated
    within DisposableVM"""
    #dispvm: typing.Optional[qubesadmin.vm.QubesVM]

    #: map of args attr -> original option
    arguments = {
        'quiet': Option(('--quiet', '-q'), handle_verbose),
        'verbose': Option(('--verbose', '-v'), handle_verbose),
        'verify_only': Option(('--verify-only',), handle_store_true),
        'skip_broken': Option(('--skip-broken',), handle_store_true),
        'ignore_missing': Option(('--ignore-missing',), handle_store_true),
        'skip_conflicting': Option(('--skip-conflicting',), handle_store_true),
        'rename_conflicting': Option(('--rename-conflicting',),
            handle_store_true),
        'exclude': Option(('--exclude', '-x'), handle_append),
        'dom0_home': Option(('--skip-dom0-home',), handle_store_false),
        'ignore_username_mismatch': Option(('--ignore-username-mismatch',),
            handle_store_true),
        'ignore_size_limit': Option(('--ignore-size-limit',),
            handle_store_true),
        'compression': Option(('--compression-filter', '-Z'), handle_store),
        'appvm': Option(('--dest-vm', '-d'), handle_store),
        'pass_file': Option(('--passphrase-file', '-p'), handle_unsupported),
        'location_is_service': Option(('--location-is-service',),
            handle_store_true),
        'paranoid_mode': Option(('--paranoid-mode', '--plan-b',), skip),
        # make the verification easier, those don't really matter
        'help': Option(('--help', '-h'), skip),
        'force_root': Option(('--force-root',), skip),
    }

    def __init__(self, app, args):
        """

        :param app: Qubes() instance
        :param args: namespace instance as with qvm-backup-restore arguments
        parsed. See :py:module:`qubesadmin.tools.qvm_backup_restore`.
        """
        self.app = app
        self.args = args

        # only one backup restore is allowed at the time, use constant names
        #: name of DisposableVM using to extract the backup
        self.dispvm_name = 'disp-backup-restore'
        #: tag given to this DisposableVM - qrexec policy is configured for it
        self.dispvm_tag = 'backup-restore-mgmt'
        #: tag automatically added to restored VMs
        self.restored_tag = 'backup-restore-in-progress'
        #: tag added to a VM storing the backup archive
        self.storage_tag = 'backup-restore-storage'

        self.terminal_app = ('xterm', '-hold', '-title', 'Backup restore', '-e')

        self.dispvm = None

        if args.appvm:
            self.backup_storage_vm = self.app.domains[args.appvm]
        else:
            self.backup_storage_vm = self.app.domains['dom0']

        self.storage_access_proc = None
        self.storage_access_id = None
        self.log = logging.getLogger('qubesadmin.backup.dispvm')

    def clear_old_tags(self):
        """Remove tags from old restore operation"""
        for domain in self.app.domains:
            domain.tags.discard(self.restored_tag)
            domain.tags.discard(self.dispvm_tag)
            domain.tags.discard(self.storage_tag)

    def create_dispvm(self):
        """Create DisposableVM used to restore"""
        self.dispvm = self.app.add_new_vm('DispVM', self.dispvm_name, 'red',
                                          template=self.app.management_dispvm)
        self.dispvm.auto_cleanup = True
        self.dispvm.features['tag-created-vm-with'] = self.restored_tag

    def register_backup_source(self):
        """Tell backup archive holding VM we want this content.

        This function registers a backup source, receives a token needed to
        access it (stored in *storage_access_id* attribute). The access is
        revoked when connection referenced in *storage_access_proc* attribute
        is closed.
        """
        self.storage_access_proc = self.backup_storage_vm.run_service(
            'qubes.RegisterBackupLocation', stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)
        self.storage_access_proc.stdin.write(
            (self.args.backup_location.
             replace("\r", "").replace("\n", "") + "\n").encode())
        self.storage_access_proc.stdin.flush()
        storage_access_id = self.storage_access_proc.stdout.readline().strip()
        allowed_chars = (string.ascii_letters + string.digits).encode()
        if not storage_access_id or \
                not all(c in allowed_chars for c in storage_access_id):
            if self.storage_access_proc.returncode == 127:
                raise qubesadmin.exc.QubesException(
                    'Backup source registration failed - qubes-core-agent '
                    'package too old?')
            raise qubesadmin.exc.QubesException(
                'Backup source registration failed - got invalid id')
        self.storage_access_id = storage_access_id.decode('ascii')
        # keep connection open, closing it invalidates the access

        self.backup_storage_vm.tags.add(self.storage_tag)

    def invalidate_backup_access(self):
        """Revoke access to backup archive"""
        self.backup_storage_vm.tags.discard(self.storage_tag)
        self.storage_access_proc.stdin.close()
        self.storage_access_proc.wait()

    def prepare_inner_args(self):
        """Prepare arguments for inner (in-DispVM) qvm-backup-restore command"""
        new_options = []
        new_positional_args = []

        for attr, opt in self.arguments.items():
            if not hasattr(self.args, attr):
                continue
            new_options.extend(opt.handler(opt, getattr(self.args, attr)))

        new_options.append('--location-is-service')

        # backup location, replace by qrexec service to be called
        new_positional_args.append(
            'qubes.RestoreById+' + self.storage_access_id)
        if self.args.vms:
            new_positional_args.extend(self.args.vms)

        return new_options + new_positional_args

    def finalize_tags(self):
        """Make sure all the restored VMs are marked with
        restored-from-backup-xxx tag, then remove backup-restore-in-progress
        tag"""
        self.app.domains.clear_cache()
        for domain in self.app.domains:
            if 'backup-restore-in-progress' not in domain.tags:
                continue
            if not any(t.startswith('restored-from-backup-')
                       for t in domain.tags):
                self.log.warning('Restored domain %s was not tagged with '
                                 'restored-from-backup-* tag',
                                 domain.name)
                # add fallback tag
                domain.tags.add('restored-from-backup-at-{}'.format(
                    datetime.date.strftime(datetime.date.today(), '%F')))
            domain.tags.discard('backup-restore-in-progress')

    def run(self):
        """Run the backup restore operation"""
        lock = qubesadmin.utils.LockFile(LOCKFILE, True)
        lock.acquire()
        try:
            self.create_dispvm()
            self.clear_old_tags()
            self.register_backup_source()
            args = self.prepare_inner_args()
            self.dispvm.start()
            self.dispvm.run_service_for_stdio('qubes.WaitForSession')
            self.dispvm.tags.add(self.dispvm_tag)
            self.dispvm.run_with_args(*self.terminal_app,
                                      'qvm-backup-restore', *args,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            if e.returncode == 127:
                raise qubesadmin.exc.QubesException(
                    'qvm-backup-restore tool or {} '
                    'missing in {} template, install qubes-core-admin-client '
                    'package there'.format(self.terminal_app[0],
                                           self.dispvm.template.template.name)
                )
            raise qubesadmin.exc.QubesException(
                'qvm-backup-restore failed with {}'.format(e.returncode))
        finally:
            if self.dispvm is not None:
                # first revoke permission, then cleanup
                self.dispvm.tags.discard(self.dispvm_tag)
                # autocleanup removes the VM
                try:
                    self.dispvm.kill()
                except qubesadmin.exc.QubesVMNotStartedError:
                    # delete it manually
                    del self.app.domains[self.dispvm]
            self.finalize_tags()
            lock.release()
