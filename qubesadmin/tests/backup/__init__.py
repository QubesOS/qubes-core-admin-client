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
import hashlib
import logging

import multiprocessing
import os

import shutil

import qubesadmin.backup.restore
import qubesadmin.exc
import qubesadmin.tests

SIGNATURE_LEN = 512

class BackupTestCase(qubesadmin.tests.QubesTestCase):
    class BackupErrorHandler(logging.Handler):
        def __init__(self, errors_queue, level=logging.NOTSET):
            super(BackupTestCase.BackupErrorHandler, self).__init__(level)
            self.errors_queue = errors_queue

        def emit(self, record):
            self.errors_queue.put(record.getMessage())

    def make_vm_name(self, name):
        try:
            return super(BackupTestCase, self).make_vm_name(name)
        except AttributeError:
            return 'test-' + name

    def setUp(self):
        super(BackupTestCase, self).setUp()
        self.error_detected = multiprocessing.Queue()
        self.log = logging.getLogger('qubesadmin.tests.backup')
        self.log.debug("Creating backupvm")

        self.backupdir = os.path.join(os.environ["HOME"], "test-backup")
        if os.path.exists(self.backupdir):
            shutil.rmtree(self.backupdir)
        os.mkdir(self.backupdir)

        self.error_handler = self.BackupErrorHandler(self.error_detected,
            level=logging.WARNING)
        backup_log = logging.getLogger('qubesadmin.backup')
        backup_log.addHandler(self.error_handler)

    def tearDown(self):
        super(BackupTestCase, self).tearDown()
        shutil.rmtree(self.backupdir)

        backup_log = logging.getLogger('qubes.backup')
        backup_log.removeHandler(self.error_handler)

    def fill_image(self, path, size=None, sparse=False, signature=b''):
        block_size = 4096

        self.log.debug("Filling %s" % path)
        f = open(path, 'wb+')
        if size is None:
            f.seek(0, 2)
            size = f.tell()
        f.seek(0)
        f.write(signature)
        f.write(b'\0' * (SIGNATURE_LEN - len(signature)))

        for block_num in range(int(size/block_size)):
            if sparse:
                f.seek(block_size, 1)
            f.write(b'a' * block_size)

        f.close()

    # NOTE: this was create_basic_vms
    def create_backup_vms(self, pool=None):
        template = self.app.default_template

        vms = []
        vmname = self.make_vm_name('test-net')
        self.log.debug("Creating %s" % vmname)
        testnet = self.app.add_new_vm('AppVM',
            name=vmname,
            label='red')
        testnet.provides_network = True
        testnet.create_on_disk(pool=pool)
        testnet.features['services/ntpd'] = True
        vms.append(testnet)
        self.fill_image(testnet.storage.export('private'), 20*1024*1024)

        vmname = self.make_vm_name('test1')
        self.log.debug("Creating %s" % vmname)
        testvm1 = self.app.add_new_vm('AppVM',
            name=vmname, template=template, label='red')
        testvm1.uses_default_netvm = False
        testvm1.netvm = testnet
        testvm1.create_on_disk(pool=pool)
        vms.append(testvm1)
        self.fill_image(testvm1.storage.export('private'), 100 * 1024 * 1024)

        vmname = self.make_vm_name('testhvm1')
        self.log.debug("Creating %s" % vmname)
        testvm2 = self.app.add_new_vm('StandaloneVM',
                                      name=vmname,
                                      label='red')
        testvm2.virt_mode = 'hvm'
        testvm2.create_on_disk(pool=pool)
        self.fill_image(testvm2.storage.export('root'), 1024 * 1024 * 1024, \
            True)
        vms.append(testvm2)

        vmname = self.make_vm_name('template')
        self.log.debug("Creating %s" % vmname)
        testvm3 = self.app.add_new_vm('TemplateVM',
            name=vmname, label='red')
        testvm3.create_on_disk(pool=pool)
        self.fill_image(testvm3.storage.export('root'), 100 * 1024 * 1024, True)
        vms.append(testvm3)

        vmname = self.make_vm_name('custom')
        self.log.debug("Creating %s" % vmname)
        testvm4 = self.app.add_new_vm('AppVM',
            name=vmname, template=testvm3, label='red')
        testvm4.create_on_disk(pool=pool)
        vms.append(testvm4)

        self.app.save()

        return vms

    def make_backup(self, vms, target=None, expect_failure=False, **kwargs):
        if target is None:
            target = self.backupdir
        try:
            backup = qubesadmin.backup.Backup(self.app, vms, **kwargs)
        except qubesadmin.exc.QubesException as e:
            if not expect_failure:
                self.fail("QubesException during backup_prepare: %s" % str(e))
            else:
                raise

        if 'passphrase' not in kwargs:
            backup.passphrase = 'qubes'
        backup.target_dir = target

        try:
            backup.backup_do()
        except qubesadmin.exc.QubesException as e:
            if not expect_failure:
                self.fail("QubesException during backup_do: %s" % str(e))
            else:
                raise

    def restore_backup(self, source=None, appvm=None, options=None,
                       expect_errors=None, manipulate_restore_info=None,
                       passphrase='qubes', force_compression_filter=None):
        if source is None:
            backupfile = os.path.join(self.backupdir,
                                      sorted(os.listdir(self.backupdir))[-1])
        else:
            backupfile = source

        with self.assertNotRaises(qubesadmin.exc.QubesException):
            restore_op = qubesadmin.backup.restore.BackupRestore(
                self.app, backupfile, appvm, passphrase,
                force_compression_filter=force_compression_filter)
            if options:
                for key, value in options.items():
                    setattr(restore_op.options, key, value)
            restore_info = restore_op.get_restore_info()
        if callable(manipulate_restore_info):
            restore_info = manipulate_restore_info(restore_info)
        self.log.debug(restore_op.get_restore_summary(restore_info))

        with self.assertNotRaises(qubesadmin.exc.QubesException):
            restore_op.restore_do(restore_info)

        errors = []
        if expect_errors is None:
            expect_errors = []
        else:
            self.assertFalse(self.error_detected.empty(),
                "Restore errors expected, but none detected")
        while not self.error_detected.empty():
            current_error = self.error_detected.get()
            if any(map(current_error.startswith, expect_errors)):
                continue
            errors.append(current_error)
        self.assertTrue(len(errors) == 0,
                         "Error(s) detected during backup_restore_do: %s" %
                         '\n'.join(errors))
        if not appvm and not os.path.isdir(backupfile):
            os.unlink(backupfile)

    def create_sparse(self, path, size, signature=b''):
        f = open(path, "wb")
        f.write(signature)
        f.write(b'\0' * (SIGNATURE_LEN - len(signature)))
        f.truncate(size)
        f.close()

    def vm_checksum(self, vms):
        hashes = {}
        for vm in vms:
            assert isinstance(vm, qubesadmin.vm.QubesVM)
            hashes[vm.name] = {}
            for name, volume in vm.volumes.items():
                if not volume.rw or not volume.save_on_stop:
                    continue
                vol_path = vm.storage.get_pool(volume).export(volume)
                hasher = hashlib.sha1()
                with open(vol_path, 'rb') as afile:
                    for buf in iter(lambda: afile.read(4096000), b''):
                        hasher.update(buf)
                hashes[vm.name][name] = hasher.hexdigest()
        return hashes

    def assertCorrectlyRestored(self, orig_vms, orig_hashes):
        ''' Verify if restored VMs are identical to those before backup.

        :param orig_vms: collection of original QubesVM objects
        :param orig_hashes: result of :py:meth:`vm_checksum` on original VMs,
            before backup
        :return:
        '''
        for vm in orig_vms:
            self.assertIn(vm.name, self.app.domains)
            restored_vm = self.app.domains[vm.name]
            for prop in ('name', 'kernel',
                    'memory', 'maxmem', 'kernelopts',
                    'services', 'vcpus', 'features'
                    'include_in_backups', 'default_user', 'qrexec_timeout',
                    'autostart', 'pci_strictreset', 'debug',
                    'internal'):
                if not hasattr(vm, prop):
                    continue
                self.assertEqual(
                    getattr(vm, prop), getattr(restored_vm, prop),
                    "VM {} - property {} not properly restored".format(
                        vm.name, prop))
            for prop in ('netvm', 'template', 'label'):
                if not hasattr(vm, prop):
                    continue
                orig_value = getattr(vm, prop)
                restored_value = getattr(restored_vm, prop)
                if orig_value and restored_value:
                    self.assertEqual(orig_value.name, restored_value.name,
                        "VM {} - property {} not properly restored".format(
                            vm.name, prop))
                else:
                    self.assertEqual(orig_value, restored_value,
                        "VM {} - property {} not properly restored".format(
                            vm.name, prop))
            for dev_class in vm.devices.keys():
                for dev in vm.devices[dev_class]:
                    self.assertIn(dev, restored_vm.devices[dev_class],
                        "VM {} - {} device not restored".format(
                            vm.name, dev_class))

            if orig_hashes:
                hashes = self.vm_checksum([restored_vm])[restored_vm.name]
                self.assertEqual(orig_hashes[vm.name], hashes,
                    "VM {} - disk images are not properly restored".format(
                        vm.name))
