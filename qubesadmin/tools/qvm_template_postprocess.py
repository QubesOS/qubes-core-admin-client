#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2016  Marek Marczykowski-Górecki
#                                       <marmarek@invisiblethingslab.com>
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

''' Tool for importing rpm-installed template'''

import asyncio
import glob
import os

import shutil
import subprocess

import sys

import grp

import qubesadmin
import qubesadmin.exc
import qubesadmin.tools
try:
    # pylint: disable=wrong-import-position
    import qubesadmin.events.utils
    have_events = True
except ImportError:
    have_events = False

parser = qubesadmin.tools.QubesArgumentParser(
    description='Postprocess template package')
parser.add_argument('--really', action='store_true', default=False,
    help='Really perform the action, YOU SHOULD REALLY KNOW WHAT YOU ARE DOING')
parser.add_argument('--skip-start', action='store_true',
    help='Do not start the VM - do not retrieve menu entries etc.')
parser.add_argument('--keep-source', action='store_true',
    help='Do not remove source data (*dir* directory) after import')
parser.add_argument('--no-installed-by-rpm', action='store_true',
    help='Do not set installed_by_rpm')
parser.add_argument('--allow-pv', action='store_true',
    help='Allow setting virt_mode to pv in configuration file.')
parser.add_argument('--pool',
    help='Specify pool to store created VMs in.')
parser.add_argument('action', choices=['post-install', 'pre-remove'],
    help='Action to perform')
parser.add_argument('name', action='store',
    help='Template name')
parser.add_argument('dir', action='store',
    help='Template directory')


def get_root_img_size(source_dir):
    '''Extract size of root.img to be imported'''
    root_path = os.path.join(source_dir, 'root.img')
    # deal with both cases: split tar and non-split tar
    part_path = root_path + '.part.00'
    tar_path = root_path + '.tar'
    if os.path.exists(part_path) or os.path.exists(tar_path):
        # get just file root_size from the tar header
        path = part_path if os.path.exists(part_path) else tar_path
        p = subprocess.Popen(['tar', 'tvf', path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        (stdout, _) = p.communicate()
        # -rw-r--r-- 0/0      1073741824 1970-01-01 01:00 root.img
        root_size = int(stdout.split()[2])
    elif os.path.exists(root_path):
        root_size = os.path.getsize(root_path)
    else:
        raise qubesadmin.exc.QubesException('root.img not found')
    return root_size


def import_root_img(vm, source_dir):
    '''Import root.img into VM object'''

    # Try not break existing data in the volume in case of import failure. If
    #  volume needs to be extended, do it before import, if reduced - after.

    root_size = get_root_img_size(source_dir)
    if vm.volumes['root'].size < root_size:
        vm.volumes['root'].resize(root_size)

    root_path = os.path.join(source_dir, 'root.img')
    if os.path.exists(root_path + '.part.00'):
        input_files = glob.glob(root_path + '.part.*')
        cat = subprocess.Popen(['cat'] + sorted(input_files),
            stdout=subprocess.PIPE)
        tar = subprocess.Popen(['tar', 'xSOf', '-'],
            stdin=cat.stdout,
            stdout=subprocess.PIPE)
        cat.stdout.close()
        vm.volumes['root'].import_data(stream=tar.stdout)
        if tar.wait() != 0:
            raise qubesadmin.exc.QubesException('root.img extraction failed')
        if cat.wait() != 0:
            raise qubesadmin.exc.QubesException('root.img extraction failed')
    elif os.path.exists(root_path + '.tar'):
        tar = subprocess.Popen(['tar', 'xSOf', root_path + '.tar'],
            stdout=subprocess.PIPE)
        vm.volumes['root'].import_data(stream=tar.stdout)
        if tar.wait() != 0:
            raise qubesadmin.exc.QubesException('root.img extraction failed')
    elif os.path.exists(root_path):
        if vm.app.qubesd_connection_type == 'socket':
            # check if root.img was already overwritten, i.e. if the source
            # and destination paths are the same
            vid = vm.volumes['root'].vid
            pool = vm.app.pools[vm.volumes['root'].pool]
            if (pool.driver in ('file', 'file-reflink')
                    and root_path == os.path.join(pool.config['dir_path'],
                                                  vid + '.img')):
                vm.log.info('root.img already in place, do not re-import')
                return
        with open(root_path, 'rb') as root_file:
            vm.volumes['root'].import_data(stream=root_file)

    if vm.volumes['root'].size > root_size:
        try:
            vm.volumes['root'].resize(root_size)
        except qubesadmin.exc.QubesException as err:
            vm.log.warning(
                'Failed to resize root volume of {} from {} to {} after '
                'import: {}'.format(vm.name, vm.volumes['root'].size,
                    root_size, str(err)))


def reset_private_img(vm):
    '''Clear private volume'''
    vm.volumes['private'].clear_data()


def import_appmenus(vm, source_dir):
    '''Import appmenus settings into VM object (later: GUI VM)'''
    if os.getuid() == 0:
        try:
            qubes_group = grp.getgrnam('qubes')
            user = qubes_group.gr_mem[0]
            cmd_prefix = ['runuser', '-u', user, '--', 'env', 'DISPLAY=:0']
        except KeyError as e:
            vm.log.warning('Default user not found, not importing appmenus: ' +
                           str(e))
            return
    else:
        cmd_prefix = []

    # store the whitelists in VM features
    # separated by spaces should be ok as there should be no spaces in the file
    # name according to the FreeDesktop spec
    with open(os.path.join(source_dir, 'vm-whitelisted-appmenus.list'), 'r') \
            as fd:
        vm.features['default-menu-items'] = ' '.join([x.rstrip() for x in fd])
    with open(os.path.join(source_dir, 'whitelisted-appmenus.list'), 'r') \
            as fd:
        vm.features['menu-items'] = ' '.join([x.rstrip() for x in fd])
    with open(
            os.path.join(source_dir, 'netvm-whitelisted-appmenus.list'), 'r') \
            as fd:
        vm.features['netvm-menu-items'] = ' '.join([x.rstrip() for x in fd])

    # TODO: change this to qrexec calls to GUI VM, when GUI VM will be
    # implemented
    try:
        subprocess.check_call(cmd_prefix + ['qvm-appmenus',
            '--set-default-whitelist={}'.format(os.path.join(source_dir,
                'vm-whitelisted-appmenus.list')), vm.name])
        subprocess.check_call(cmd_prefix + ['qvm-appmenus',
            '--set-whitelist={}'.format(os.path.join(source_dir,
                'whitelisted-appmenus.list')), vm.name])
    except subprocess.CalledProcessError as e:
        vm.log.warning('Failed to set default application list: %s', e)

def parse_template_config(path):
    '''Parse template.conf from template package. (KEY=VALUE format)'''
    with open(path, 'r') as fd:
        return dict(line.rstrip('\n').split('=', 1) for line in fd)

@asyncio.coroutine
def call_postinstall_service(vm):
    '''Call qubes.PostInstall service

    And adjust related settings (netvm, features).
    '''
    # just created, so no need to save previous value - we know what it was
    vm.netvm = None
    # temporarily enable qrexec feature - so vm.start() will wait for it;
    # if start fails, rollback it
    vm.features['qrexec'] = True
    try:
        vm.start()
    except qubesadmin.exc.QubesException:
        del vm.features['qrexec']
    else:
        try:
            vm.run_service_for_stdio('qubes.PostInstall')
        except subprocess.CalledProcessError:
            vm.log.error('qubes.PostInstall service failed')
        vm.shutdown()
        if have_events:
            try:
                # pylint: disable=no-member
                yield from asyncio.wait_for(
                    qubesadmin.events.utils.wait_for_domain_shutdown([vm]),
                    qubesadmin.config.defaults['shutdown_timeout'])
            except asyncio.TimeoutError:
                vm.kill()
        else:
            timeout = qubesadmin.config.defaults['shutdown_timeout']
            while timeout >= 0:
                if vm.is_halted():
                    break
                yield from asyncio.sleep(1)
                timeout -= 1
            if not vm.is_halted():
                try:
                    vm.kill()
                except qubesadmin.exc.QubesVMNotStartedError:
                    pass
    finally:
        vm.netvm = qubesadmin.DEFAULT


@asyncio.coroutine
def post_install(args):
    '''Handle post-installation tasks'''

    app = args.app
    vm_created = False
    # reinstall and running in dom0, using the same directory as qubes core
    local_reinstall = False
    try:
        # reinstall
        vm = app.domains[args.name]
        if app.qubesd_connection_type == 'socket' and \
                args.dir == '/var/lib/qubes/vm-templates/' + args.name:
            # VM exists and use use the same directory as target vm - on
            # final cleanup remove only some files, not the whole directory
            local_reinstall = True
    except KeyError:
        if app.qubesd_connection_type == 'socket' and \
                args.dir == '/var/lib/qubes/vm-templates/' + args.name:
            # vm.create_on_disk() need to create the directory on its own,
            # move it away from its way
            tmp_sourcedir = os.path.join('/var/lib/qubes/vm-templates',
                'tmp-' + args.name)
            shutil.move(args.dir, tmp_sourcedir)
            args.dir = tmp_sourcedir

        vm = app.add_new_vm('TemplateVM',
            name=args.name,
            label=qubesadmin.config.defaults['template_label'],
            pool=args.pool)
        vm_created = True

    vm.log.info('Importing data')
    try:
        import_root_img(vm, args.dir)
    except:
        # if data import fails, remove half-created VM
        if vm_created:
            del app.domains[vm.name]
        raise
    if not vm_created:
        vm.log.info('Clearing private volume')
        reset_private_img(vm)
    vm.installed_by_rpm = not args.no_installed_by_rpm
    import_appmenus(vm, args.dir)

    conf_path = os.path.join(args.dir, 'template.conf')
    if os.path.exists(conf_path):
        conf = parse_template_config(conf_path)
        # Import qvm-feature tags
        for key in (
                'no-monitor-layout',
                'pci-e820-host',
                'linux-stubdom',
                'gui',
                'gui-emulated'
                'qrexec'):
            if key in conf:
                if conf[key] == '1':
                    vm.features[key] = conf[key]
                else:
                    vm.log.warning(
                        'ignoring boolean config flags that are not \'1\'')
        for key in (
                'net.fake-ip',
                'net.fake-gateway',
                'net.fake-netmask'):
            if key in conf:
                vm.features[key] = conf[key]
        if 'virt-mode' in conf:
            if conf['virt-mode'] == 'pv' and args.allow_pv:
                vm.virt_mode = 'pv'
            elif conf['virt-mode'] == 'pv':
                vm.log.warning(
                    '--allow-pv not set, ignoring request to change virt-mode')
            elif conf['virt-mode'] in ('pvh', 'hvm'):
                vm.virt_mode = conf['virt-mode']

        if 'kernel' in conf:
            if conf['kernel'] == '':
                vm.kernel = ''
            else:
                vm.log.warning(
                    'Currently only supports setting kernel to (none)')

    if not args.skip_start:
        yield from call_postinstall_service(vm)

    if not args.keep_source:
        if local_reinstall:
            # remove only imported root img
            root_path = os.path.join(args.dir, 'root.img')
            for root_part in glob.glob(root_path + '.part.*'):
                os.unlink(root_part)
        else:
            shutil.rmtree(args.dir)
        # if running as root, tell underlying storage layer about just freed
        # data blocks
        if os.getuid() == 0:
            subprocess.call(['sync', '-f', os.path.dirname(args.dir)])
            subprocess.call(['fstrim', os.path.dirname(args.dir)])

    return 0


def pre_remove(args):
    '''Handle pre-removal tasks'''
    app = args.app
    try:
        tpl = app.domains[args.name]
    except KeyError:
        parser.error('No Qube with this name exists')
    for appvm in tpl.appvms:
        parser.error('Qube {} uses this template'.format(appvm.name))

    tpl.installed_by_rpm = False
    del app.domains[args.name]
    return 0


def is_chroot():
    '''Detect if running inside chroot'''
    try:
        stat_root = os.stat('/')
        stat_init_root = os.stat('/proc/1/root/.')
        return (
            stat_root.st_dev != stat_init_root.st_dev or
            stat_root.st_ino != stat_init_root.st_ino)
    except IOError:
        print('Stat failed, assuming not chroot', file=sys.stderr)
        return False


def main(args=None, app=None):
    '''Main function of qvm-template-postprocess'''
    args = parser.parse_args(args, app=app)

    if is_chroot():
        print('Running in chroot, ignoring request. Import template with:',
            file=sys.stderr)
        print(' '.join(sys.argv), file=sys.stderr)
        return

    if not args.really:
        parser.error('Do not call this tool directly.')
    if args.action == 'post-install':
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(post_install(args))
            loop.stop()
            loop.run_forever()
        finally:
            loop.close()
    elif args.action == 'pre-remove':
        pre_remove(args)
    else:
        parser.error('Unknown action')
    return 0

if __name__ == '__main__':
    sys.exit(main())
