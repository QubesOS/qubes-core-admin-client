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

'''Qubes backup'''

import collections
import errno
import fcntl
import functools
import grp
import logging
import multiprocessing
from multiprocessing import Queue, Process
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import termios
import time

import qubesadmin
import qubesadmin.vm
from qubesadmin.devices import DeviceAssignment
from qubesadmin.exc import QubesException
from qubesadmin.utils import size_to_human

# must be picklable
QUEUE_FINISHED = "!!!FINISHED"
QUEUE_ERROR = "!!!ERROR"

HEADER_FILENAME = 'backup-header'
DEFAULT_CRYPTO_ALGORITHM = 'aes-256-cbc'
# 'scrypt' is not exactly HMAC algorithm, but a tool we use to
# integrity-protect the data
DEFAULT_HMAC_ALGORITHM = 'scrypt'
DEFAULT_COMPRESSION_FILTER = 'gzip'
# Maximum size of error message get from process stderr (including VM process)
MAX_STDERR_BYTES = 1024
# header + qubes.xml max size
HEADER_QUBES_XML_MAX_SIZE = 1024 * 1024
# hmac file max size - regardless of backup format version!
HMAC_MAX_SIZE = 4096

BLKSIZE = 512

_re_alphanum = re.compile(r'^[A-Za-z0-9-]*$')

class BackupCanceledError(QubesException):
    '''Exception raised when backup/restore was cancelled'''
    def __init__(self, msg, tmpdir=None):
        super(BackupCanceledError, self).__init__(msg)
        self.tmpdir = tmpdir

class BackupHeader(object):
    '''Structure describing backup-header file included as the first file in
    backup archive
    '''
    header_keys = {
        'version': 'version',
        'encrypted': 'encrypted',
        'compressed': 'compressed',
        'compression-filter': 'compression_filter',
        'crypto-algorithm': 'crypto_algorithm',
        'hmac-algorithm': 'hmac_algorithm',
        'backup-id': 'backup_id'
    }
    bool_options = ['encrypted', 'compressed']
    int_options = ['version']

    def __init__(self,
            header_data=None,
            version=None,
            encrypted=None,
            compressed=None,
            compression_filter=None,
            hmac_algorithm=None,
            crypto_algorithm=None,
            backup_id=None):
        # repeat the list to help code completion...
        self.version = version
        self.encrypted = encrypted
        self.compressed = compressed
        # Options introduced in backup format 3+, which always have a header,
        # so no need for fallback in function parameter
        self.compression_filter = compression_filter
        self.hmac_algorithm = hmac_algorithm
        self.crypto_algorithm = crypto_algorithm
        self.backup_id = backup_id

        if header_data is not None:
            self.load(header_data)

    def load(self, untrusted_header_text):
        """Parse backup header file.

        :param untrusted_header_text: header content
        :type untrusted_header_text: basestring

        .. warning::
            This function may be exposed to not yet verified header,
            so is security critical.
        """
        try:
            untrusted_header_text = untrusted_header_text.decode('ascii')
        except UnicodeDecodeError:
            raise QubesException(
                "Non-ASCII characters in backup header")
        for untrusted_line in untrusted_header_text.splitlines():
            if untrusted_line.count('=') != 1:
                raise QubesException("Invalid backup header")
            key, value = untrusted_line.strip().split('=', 1)
            if not _re_alphanum.match(key):
                raise QubesException("Invalid backup header ("
                                                   "key)")
            if key not in self.header_keys.keys():
                # Ignoring unknown option
                continue
            if not _re_alphanum.match(value):
                raise QubesException("Invalid backup header ("
                                                 "value)")
            if getattr(self, self.header_keys[key]) is not None:
                raise QubesException(
                    "Duplicated header line: {}".format(key))
            if key in self.bool_options:
                value = value.lower() in ["1", "true", "yes"]
            elif key in self.int_options:
                value = int(value)
            setattr(self, self.header_keys[key], value)

        self.validate()

    def validate(self):
        '''Validate header data, according to header version'''
        if self.version == 1:
            # header not really present
            pass
        elif self.version in [2, 3, 4]:
            expected_attrs = ['version', 'encrypted', 'compressed',
                'hmac_algorithm']
            if self.encrypted and self.version < 4:
                expected_attrs += ['crypto_algorithm']
            if self.version >= 3 and self.compressed:
                expected_attrs += ['compression_filter']
            if self.version >= 4:
                expected_attrs += ['backup_id']
            for key in expected_attrs:
                if getattr(self, key) is None:
                    raise QubesException(
                        "Backup header lack '{}' info".format(key))
        else:
            raise QubesException(
                "Unsupported backup version {}".format(self.version))

    def save(self, filename):
        '''Save backup header into a file'''
        with open(filename, "w") as f_header:
            # make sure 'version' is the first key
            f_header.write('version={}\n'.format(self.version))
            for key, attr in self.header_keys.items():
                if key == 'version':
                    continue
                if getattr(self, attr) is None:
                    continue
                f_header.write("{!s}={!s}\n".format(key, getattr(self, attr)))

def launch_proc_with_pty(args, stdin=None, stdout=None, stderr=None, echo=True):
    """Similar to pty.fork, but handle stdin/stdout according to parameters
    instead of connecting to the pty

    :return tuple (subprocess.Popen, pty_master)
    """

    def set_ctty(ctty_fd, master_fd):
        '''Set controlling terminal'''
        os.setsid()
        os.close(master_fd)
        fcntl.ioctl(ctty_fd, termios.TIOCSCTTY, 0)
        if not echo:
            termios_p = termios.tcgetattr(ctty_fd)
            # termios_p.c_lflags
            termios_p[3] &= ~termios.ECHO
            termios.tcsetattr(ctty_fd, termios.TCSANOW, termios_p)
    (pty_master, pty_slave) = os.openpty()
    p = subprocess.Popen(args, stdin=stdin, stdout=stdout,
        stderr=stderr,
        preexec_fn=lambda: set_ctty(pty_slave, pty_master))
    os.close(pty_slave)
    return p, open(pty_master, 'wb+', buffering=0)

def launch_scrypt(action, input_name, output_name, passphrase):
    '''
    Launch 'scrypt' process, pass passphrase to it and return
    subprocess.Popen object.

    :param action: 'enc' or 'dec'
    :param input_name: input path or '-' for stdin
    :param output_name: output path or '-' for stdout
    :param passphrase: passphrase
    :return: subprocess.Popen object
    '''
    command_line = ['scrypt', action, input_name, output_name]
    (p, pty) = launch_proc_with_pty(command_line,
        stdin=subprocess.PIPE if input_name == '-' else None,
        stdout=subprocess.PIPE if output_name == '-' else None,
        stderr=subprocess.PIPE,
        echo=False)
    if action == 'enc':
        prompts = (b'Please enter passphrase: ', b'Please confirm passphrase: ')
    else:
        prompts = (b'Please enter passphrase: ',)
    for prompt in prompts:
        actual_prompt = p.stderr.read(len(prompt))
        if actual_prompt != prompt:
            raise QubesException(
                'Unexpected prompt from scrypt: {}'.format(actual_prompt))
        pty.write(passphrase.encode('utf-8') + b'\n')
        pty.flush()
    # save it here, so garbage collector would not close it (which would kill
    #  the child)
    p.pty = pty
    return p

class ExtractWorker3(Process):
    '''Process for handling inner tar layer of backup archive'''
    # pylint: disable=too-many-instance-attributes
    def __init__(self, queue, base_dir, passphrase, encrypted,
                 progress_callback, vmproc=None,
                 compressed=False, crypto_algorithm=DEFAULT_CRYPTO_ALGORITHM,
                 compression_filter=None, verify_only=False, handlers=None):
        '''Start inner tar extraction worker

        The purpose of this class is to process files extracted from outer
        archive layer and pass to appropriate handlers. Input files are given
        through a queue. Insert :py:obj:`QUEUE_FINISHED` or
        :py:obj:`QUEUE_ERROR` to end data processing (either cleanly,
        or forcefully).

        Handlers are given as a map filename -> (data_func, size_func),
        where data_func is called with file-like object to process,
        and size_func is called with file size as argument. Note that
        data_func and size_func may be called simultaneusly, in a different
        processes.

        :param multiprocessing.Queue queue: a queue with filenames to
        process; those files needs to be given as full path, inside *base_dir*
        :param str base_dir: directory where all files to process live
        :param str passphrase: passphrase to decrypt the data
        :param bool encrypted: is encryption applied?
        :param callable progress_callback: report extraction progress
        :param subprocess.Popen vmproc: process extracting outer layer,
        given here to monitor
        it for failures (when it exits with non-zero exit code, inner layer
        processing is stopped)
        :param bool compressed: is the data compressed?
        :param str crypto_algorithm: encryption algorithm, either `scrypt` or an
        algorithm supported by openssl
        :param str compression_filter: compression program, `gzip` by default
        :param bool verify_only: only verify data integrity, do not extract
        :param dict handlers: handlers for actual data
        '''
        super(ExtractWorker3, self).__init__()
        #: queue with files to extract
        self.queue = queue
        #: paths on the queue are relative to this dir
        self.base_dir = base_dir
        #: passphrase to decrypt/authenticate data
        self.passphrase = passphrase
        #: handlers for files; it should be dict filename -> (data_function,
        # size_function),
        # where data_function will get file-like object as the only argument and
        # might be called in a separate process (multiprocessing.Process),
        # and size_function will get file size (when known) in bytes
        self.handlers = handlers
        #: is the backup encrypted?
        self.encrypted = encrypted
        #: is the backup compressed?
        self.compressed = compressed
        #: what crypto algorithm is used for encryption?
        self.crypto_algorithm = crypto_algorithm
        #: only verify integrity, don't extract anything
        self.verify_only = verify_only
        #: progress
        self.blocks_backedup = 0
        #: inner tar layer extraction (subprocess.Popen instance)
        self.tar2_process = None
        #: current inner tar archive name
        self.tar2_current_file = None
        #: call size_func handler for this file when tar report it on stderr
        self.adjust_output_size = None
        #: decompressor subprocess.Popen instance
        self.decompressor_process = None
        #: decryptor subprocess.Popen instance
        self.decryptor_process = None
        #: data import multiprocessing.Process instance
        self.import_process = None
        #: callback reporting progress to UI
        self.progress_callback = progress_callback
        #: process (subprocess.Popen instance) feeding the data into
        # extraction tool
        self.vmproc = vmproc

        self.log = logging.getLogger('qubesadmin.backup.extract')
        self.stderr_encoding = sys.stderr.encoding or 'utf-8'
        self.tar2_stderr = []
        self.compression_filter = compression_filter

    @staticmethod
    def handle_streams(stream_in, streams_out, processes, size_limit=None,
            progress_callback=None):
        '''
        Copy stream_in to all streams_out and monitor all mentioned processes.
        If any of them terminate with non-zero code, interrupt the process. Copy
        at most `size_limit` data (if given).

        :param stream_in: file-like object to read data from
        :param streams_out: dict of file-like objects to write data to
        :param processes: dict of subprocess.Popen objects to monitor
        :param size_limit: int maximum data amount to process
        :param progress_callback: callable function to report progress, will be
            given copied data size (it should accumulate internally)
        :return: failed process name, failed stream name, "size_limit" or None (
            no error)
        '''
        buffer_size = 409600
        bytes_copied = 0
        while True:
            if size_limit:
                to_copy = min(buffer_size, size_limit - bytes_copied)
                if to_copy <= 0:
                    return "size_limit"
            else:
                to_copy = buffer_size
            buf = stream_in.read(to_copy)
            if not buf:
                # done
                return None

            if callable(progress_callback):
                progress_callback(len(buf))
            for name, stream in streams_out.items():
                if stream is None:
                    continue
                try:
                    stream.write(buf)
                except IOError:
                    return name
            bytes_copied += len(buf)

            for name, proc in processes.items():
                if proc is None:
                    continue
                if isinstance(proc, Process):
                    if not proc.is_alive() and proc.exitcode != 0:
                        return name
                elif proc.poll():
                    return name

    def collect_tar_output(self):
        '''Retrieve tar stderr and handle it appropriately

        Log errors, process file size if requested.
        This use :py:attr:`tar2_process`.
        '''
        if not self.tar2_process.stderr:
            return

        if self.tar2_process.poll() is None:
            try:
                new_lines = self.tar2_process.stderr \
                    .read(MAX_STDERR_BYTES).splitlines()
            except IOError as e:
                if e.errno == errno.EAGAIN:
                    return
                else:
                    raise
        else:
            new_lines = self.tar2_process.stderr.readlines()

        new_lines = [x.decode(self.stderr_encoding) for x in new_lines]

        msg_re = re.compile(r".*#[0-9].*restore_pipe")
        debug_msg = [msg for msg in new_lines if msg_re.match(msg)]
        self.log.debug('tar2_stderr: %s', '\n'.join(debug_msg))
        new_lines = [msg for msg in new_lines if not msg_re.match(msg)]
        if self.adjust_output_size:
            # search for first file size reported by tar after setting
            # self.adjust_output_size (so don't look at self.tar2_stderr)
            # this is used only when extracting single-file archive, so don't
            #  bother with checking file name
            file_size_re = re.compile(r"^[^ ]+ [^ ]+/[^ ]+ *([0-9]+) .*")
            for line in new_lines:
                match = file_size_re.match(line)
                if match:
                    file_size = match.groups()[0]
                    self.adjust_output_size(file_size)
                    self.adjust_output_size = None
        self.tar2_stderr += new_lines

    def run(self):
        try:
            self.__run__()
        except Exception:
            # Cleanup children
            for process in [self.decompressor_process,
                    self.decryptor_process,
                    self.tar2_process]:
                if process:
                    try:
                        process.terminate()
                    except OSError:
                        pass
                    process.wait()
            self.log.exception('ERROR')
            raise

    def handle_dir(self, dirname):
        ''' Relocate files in given director when it's already extracted

        :param dirname: directory path to handle (relative to backup root),
        without trailing slash
        '''
        for fname, (data_func, size_func) in self.handlers.items():
            if not fname.startswith(dirname + '/'):
                continue
            if not os.path.exists(fname):
                # for example firewall.xml
                continue
            if size_func is not None:
                size_func(os.path.getsize(fname))
            with open(fname, 'rb') as input_file:
                data_func(input_file)
            os.unlink(fname)
        shutil.rmtree(dirname)

    def cleanup_tar2(self, wait=True, terminate=False):
        '''Cleanup running :py:attr:`tar2_process`

        :param wait: wait for it termination, otherwise method exit early if
        process is still running
        :param terminate: terminate the process if still running
        '''
        if self.tar2_process is None:
            return
        if terminate:
            if self.import_process is not None:
                self.tar2_process.terminate()
            self.import_process.terminate()
        if wait:
            self.tar2_process.wait()
            if self.import_process is not None:
                self.import_process.join()
        elif self.tar2_process.poll() is None:
            return
        self.collect_tar_output()
        if self.tar2_process.stderr:
            self.tar2_process.stderr.close()
        if self.tar2_process.returncode != 0:
            self.log.error(
                "ERROR: unable to extract files for %s, tar "
                "output:\n  %s",
                    self.tar2_current_file,
                    "\n  ".join(self.tar2_stderr))
        else:
            # Finished extracting the tar file
            # if that was whole-directory archive, handle
            # relocated files now
            inner_name = self.tar2_current_file.rsplit('.', 1)[0] \
                .replace(self.base_dir + '/', '')
            if os.path.basename(inner_name) == '.':
                self.handle_dir(
                    os.path.dirname(inner_name))
            self.tar2_current_file = None
            self.adjust_output_size = None
        self.tar2_process = None

    @staticmethod
    def _data_func_wrapper(close_fds, data_func, data_stream):
        '''Close not needed file descriptors, then call data_func(
        data_stream).

        This is to prevent holding write end of a pipe in subprocess,
        preventing EOF transfer.
        '''
        for fd in close_fds:
            if fd == data_stream.fileno():
                continue
            try:
                os.close(fd)
            except OSError:
                pass
        return data_func(data_stream)


    def __run__(self):
        self.log.debug("Started sending thread")
        self.log.debug("Moving to dir " + self.base_dir)
        os.chdir(self.base_dir)

        filename = None

        input_pipe = None
        for filename in iter(self.queue.get, None):
            if filename in (QUEUE_FINISHED, QUEUE_ERROR):
                break

            assert isinstance(filename, str)

            self.log.debug("Extracting file " + filename)

            if filename.endswith('.000'):
                # next file
                if self.tar2_process is not None:
                    input_pipe.close()
                    self.cleanup_tar2(wait=True, terminate=False)

                inner_name = filename[:-len('.000')].replace(
                    self.base_dir + '/', '')
                redirect_stdout = None
                if os.path.basename(inner_name) == '.':
                    if (inner_name in self.handlers or
                            any(x.startswith(os.path.dirname(inner_name) + '/')
                            for x in self.handlers)):
                        tar2_cmdline = ['tar',
                            '-%s' % ("t" if self.verify_only else "x"),
                            inner_name]
                    else:
                        # ignore this directory
                        tar2_cmdline = None
                elif inner_name in self.handlers:
                    tar2_cmdline = ['tar',
                        '-%svvO' % ("t" if self.verify_only else "x"),
                        inner_name]
                    redirect_stdout = subprocess.PIPE
                else:
                    # no handlers for this file, ignore it
                    tar2_cmdline = None

                if tar2_cmdline is None:
                    # ignore the file
                    os.remove(filename)
                    continue

                if self.compressed:
                    if self.compression_filter:
                        tar2_cmdline.insert(-1,
                                            "--use-compress-program=%s" %
                                            self.compression_filter)
                    else:
                        tar2_cmdline.insert(-1, "--use-compress-program=%s" %
                                            DEFAULT_COMPRESSION_FILTER)

                self.log.debug("Running command " + str(tar2_cmdline))
                if self.encrypted:
                    # Start decrypt
                    self.decryptor_process = subprocess.Popen(
                        ["openssl", "enc",
                         "-d",
                         "-" + self.crypto_algorithm,
                         "-pass",
                         "pass:" + self.passphrase],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE)

                    self.tar2_process = subprocess.Popen(
                        tar2_cmdline,
                        stdin=self.decryptor_process.stdout,
                        stdout=redirect_stdout,
                        stderr=subprocess.PIPE)
                    self.decryptor_process.stdout.close()
                    input_pipe = self.decryptor_process.stdin
                else:
                    self.tar2_process = subprocess.Popen(
                        tar2_cmdline,
                        stdin=subprocess.PIPE,
                        stdout=redirect_stdout,
                        stderr=subprocess.PIPE)
                    input_pipe = self.tar2_process.stdin

                if inner_name in self.handlers:
                    assert redirect_stdout is subprocess.PIPE
                    data_func, size_func = self.handlers[inner_name]
                    self.import_process = multiprocessing.Process(
                        target=self._data_func_wrapper,
                        args=([input_pipe.fileno()],
                        data_func, self.tar2_process.stdout))
                    self.import_process.start()
                    self.tar2_process.stdout.close()
                    self.adjust_output_size = size_func

                fcntl.fcntl(self.tar2_process.stderr.fileno(), fcntl.F_SETFL,
                            fcntl.fcntl(self.tar2_process.stderr.fileno(),
                                        fcntl.F_GETFL) | os.O_NONBLOCK)
                self.tar2_stderr = []
            elif not self.tar2_process:
                # Extracting of the current archive failed, skip to the next
                # archive
                os.remove(filename)
                continue
            else:
                (basename, ext) = os.path.splitext(self.tar2_current_file)
                previous_chunk_number = int(ext[1:])
                expected_filename = basename + '.%03d' % (
                    previous_chunk_number+1)
                if expected_filename != filename:
                    self.cleanup_tar2(wait=True, terminate=True)
                    self.log.error(
                        'Unexpected file in archive: %s, expected %s',
                            filename, expected_filename)
                    os.remove(filename)
                    continue
                self.log.debug("Releasing next chunck")

            self.tar2_current_file = filename

            input_file = open(filename, 'rb')

            run_error = self.handle_streams(
                input_file,
                {'target': input_pipe},
                {'vmproc': self.vmproc,
                 'addproc': self.tar2_process,
                 'data_import': self.import_process,
                 'decryptor': self.decryptor_process,
                },
                progress_callback=self.progress_callback)
            input_file.close()
            if run_error:
                if run_error == "target":
                    self.collect_tar_output()
                    details = "\n".join(self.tar2_stderr)
                else:
                    details = "%s failed" % run_error
                if self.decryptor_process:
                    self.decryptor_process.terminate()
                    self.decryptor_process.wait()
                    self.decryptor_process = None
                self.log.error('Error while processing \'%s\': %s',
                    self.tar2_current_file, details)
                self.cleanup_tar2(wait=True, terminate=True)

            # Delete the file as we don't need it anymore
            self.log.debug('Removing file %s', filename)
            os.remove(filename)

        if self.tar2_process is not None:
            input_pipe.close()
            if filename == QUEUE_ERROR:
                if self.decryptor_process:
                    self.decryptor_process.terminate()
                    self.decryptor_process.wait()
                    self.decryptor_process = None
            self.cleanup_tar2(terminate=(filename == QUEUE_ERROR))

        self.log.debug('Finished extracting thread')


def get_supported_hmac_algo(hmac_algorithm=None):
    '''Generate a list of supported hmac algorithms

    :param hmac_algorithm: default algorithm, if given, it is placed as a
    first element
    '''
    # Start with provided default
    if hmac_algorithm:
        yield hmac_algorithm
    if hmac_algorithm != 'scrypt':
        yield 'scrypt'
    proc = subprocess.Popen(['openssl', 'list-message-digest-algorithms'],
                            stdout=subprocess.PIPE)
    try:
        for algo in proc.stdout.readlines():
            algo = algo.decode('ascii')
            if '=>' in algo:
                continue
            yield algo.strip()
    finally:
        proc.terminate()
        proc.wait()
        proc.stdout.close()

class BackupApp(object):
    '''Interface for backup collection'''
    # pylint: disable=too-few-public-methods
    def __init__(self, qubes_xml):
        '''Initialize BackupApp object and load qubes.xml into it'''
        self.store = qubes_xml
        self.domains = {}
        self.globals = {}
        self.load()

    def load(self):
        '''Load qubes.xml'''
        raise NotImplementedError

class BackupVM(object):
    '''Interface for a single VM in the backup'''
    # pylint: disable=too-few-public-methods
    def __init__(self):
        '''Initialize empty BackupVM object'''
        #: VM class
        self.klass = 'AppVM'
        #: VM name
        self.name = None
        #: VM template
        self.template = None
        #: VM label
        self.label = None
        #: VM properties
        self.properties = {}
        #: VM features (key/value), aka services in core2
        self.features = {}
        #: VM tags
        self.tags = set()
        #: VM devices - dict with key=devtype, value=dict of devices (
        # key=ident, value=options)
        self.devices = collections.defaultdict(dict)
        #: VM path in the backup
        self.backup_path = None
        #: size of the VM
        self.size = 0

    @property
    def included_in_backup(self):
        '''Report whether a VM is included in the backup'''
        return False

    def handle_firewall_xml(self, vm, stream):
        '''Import appropriate format of firewall.xml'''
        raise NotImplementedError

class BackupRestoreOptions(object):
    '''Options for restore operation'''
    # pylint: disable=too-few-public-methods
    def __init__(self):
        #: use default NetVM if the one referenced in backup do not exists on
        #  the host
        self.use_default_netvm = True
        #: set NetVM to "none" if the one referenced in backup do not exists
        # on the host
        self.use_none_netvm = False
        #: set template to default if the one referenced in backup do not
        # exists on the host
        self.use_default_template = True
        #: use default kernel if the one referenced in backup do not exists
        # on the host
        self.use_default_kernel = True
        #: restore dom0 home
        self.dom0_home = True
        #: restore dom0 home even if username is different
        self.ignore_username_mismatch = False
        #: do not restore data, only verify backup integrity
        self.verify_only = False
        #: automatically rename VM during restore, when it would conflict
        # with existing one
        self.rename_conflicting = True
        #: list of VM names to exclude
        self.exclude = []
        #: restore VMs into selected storage pool
        self.override_pool = None

class BackupRestore(object):
    """Usage:

    >>> restore_op = BackupRestore(...)
    >>> # adjust restore_op.options here
    >>> restore_info = restore_op.get_restore_info()
    >>> # manipulate restore_info to select VMs to restore here
    >>> restore_op.restore_do(restore_info)
    """

    class VMToRestore(object):
        '''Information about a single VM to be restored'''
        # pylint: disable=too-few-public-methods
        #: VM excluded from restore by user
        EXCLUDED = object()
        #: VM with such name already exists on the host
        ALREADY_EXISTS = object()
        #: NetVM used by the VM does not exists on the host
        MISSING_NETVM = object()
        #: TemplateVM used by the VM does not exists on the host
        MISSING_TEMPLATE = object()
        #: Kernel used by the VM does not exists on the host
        MISSING_KERNEL = object()

        def __init__(self, vm):
            assert isinstance(vm, BackupVM)
            self.vm = vm
            self.name = vm.name
            self.subdir = vm.backup_path
            self.size = vm.size
            self.problems = set()
            self.template = vm.template
            if vm.properties.get('netvm', None):
                self.netvm = vm.properties['netvm']
            else:
                self.netvm = None
            self.orig_template = None
            self.restored_vm = None

        @property
        def good_to_go(self):
            '''Is the VM ready for restore?'''
            return len(self.problems) == 0

    class Dom0ToRestore(VMToRestore):
        '''Information about dom0 home to restore'''
        # pylint: disable=too-few-public-methods
        #: backup was performed on system with different dom0 username
        USERNAME_MISMATCH = object()

        def __init__(self, vm, subdir=None):
            super(BackupRestore.Dom0ToRestore, self).__init__(vm)
            if subdir:
                self.subdir = subdir
            self.username = os.path.basename(subdir)

    def __init__(self, app, backup_location, backup_vm, passphrase):
        super(BackupRestore, self).__init__()

        #: qubes.Qubes instance
        self.app = app

        #: options how the backup should be restored
        self.options = BackupRestoreOptions()

        #: VM from which backup should be retrieved
        self.backup_vm = backup_vm
        if backup_vm and backup_vm.qid == 0:
            self.backup_vm = None

        #: backup path, inside VM pointed by :py:attr:`backup_vm`
        self.backup_location = backup_location

        #: passphrase protecting backup integrity and optionally decryption
        self.passphrase = passphrase

        #: temporary directory used to extract the data before moving to the
        # final location
        self.tmpdir = tempfile.mkdtemp(prefix="restore", dir="/var/tmp")

        #: list of processes (Popen objects) to kill on cancel
        self.processes_to_kill_on_cancel = []

        #: is the backup operation canceled
        self.canceled = False

        #: report restore progress, called with one argument - percents of
        # data restored
        # FIXME: convert to float [0,1]
        self.progress_callback = None

        self.log = logging.getLogger('qubesadmin.backup')

        #: basic information about the backup
        self.header_data = self._retrieve_backup_header()

        #: VMs included in the backup
        self.backup_app = self._process_qubes_xml()

    def _start_retrieval_process(self, filelist, limit_count, limit_bytes):
        """Retrieve backup stream and extract it to :py:attr:`tmpdir`

        :param filelist: list of files to extract; listing directory name
        will extract the whole directory; use empty list to extract the whole
        archive
        :param limit_count: maximum number of files to extract
        :param limit_bytes: maximum size of extracted data
        :return: a touple of (Popen object of started process, file-like
        object for reading extracted files list, file-like object for reading
        errors)
        """

        vmproc = None
        if self.backup_vm is not None:
            # If APPVM, STDOUT is a PIPE
            vmproc = self.backup_vm.run_service('qubes.Restore')
            vmproc.stdin.write(
                (self.backup_location.replace("\r", "").replace("\n",
                    "") + "\n").encode())
            vmproc.stdin.flush()

            # Send to tar2qfile the VMs that should be extracted
            vmproc.stdin.write((" ".join(filelist) + "\n").encode())
            vmproc.stdin.flush()
            self.processes_to_kill_on_cancel.append(vmproc)

            backup_stdin = vmproc.stdout
            tar1_command = ['/usr/libexec/qubes/qfile-dom0-unpacker',
                            str(os.getuid()), self.tmpdir, '-v']
        else:
            backup_stdin = open(self.backup_location, 'rb')

            tar1_command = ['tar',
                            '-ixv',
                            '-C', self.tmpdir] + filelist

        tar1_env = os.environ.copy()
        tar1_env['UPDATES_MAX_BYTES'] = str(limit_bytes)
        tar1_env['UPDATES_MAX_FILES'] = str(limit_count)
        self.log.debug("Run command" + str(tar1_command))
        command = subprocess.Popen(
            tar1_command,
            stdin=backup_stdin,
            stdout=vmproc.stdin if vmproc else subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=tar1_env)
        backup_stdin.close()
        self.processes_to_kill_on_cancel.append(command)

        # qfile-dom0-unpacker output filelist on stderr
        # and have stdout connected to the VM), while tar output filelist
        # on stdout
        if self.backup_vm:
            filelist_pipe = command.stderr
            # let qfile-dom0-unpacker hold the only open FD to the write end of
            # pipe, otherwise qrexec-client will not receive EOF when
            # qfile-dom0-unpacker terminates
            vmproc.stdin.close()
        else:
            filelist_pipe = command.stdout

        if self.backup_vm:
            error_pipe = vmproc.stderr
        else:
            error_pipe = command.stderr
        return command, filelist_pipe, error_pipe

    def _verify_hmac(self, filename, hmacfile, algorithm=None):
        '''Verify hmac of a file using given algorithm.

        If algorithm is not specified, use the one from backup header (
        :py:attr:`header_data`).

        Raise :py:exc:`QubesException` on failure, return :py:obj:`True` on
        success.

        'scrypt' algorithm is supported only for header file; hmac file is
        encrypted (and integrity protected) version of plain header.

        :param filename: path to file to be verified
        :param hmacfile: path to hmac file for *filename*
        :param algorithm: override algorithm
        '''
        def load_hmac(hmac_text):
            '''Parse hmac output by openssl.

            Return just hmac, without filename and other metadata.
            '''
            if any(ord(x) not in range(128) for x in hmac_text):
                raise QubesException(
                    "Invalid content of {}".format(hmacfile))
            hmac_text = hmac_text.strip().split("=")
            if len(hmac_text) > 1:
                hmac_text = hmac_text[1].strip()
            else:
                raise QubesException(
                    "ERROR: invalid hmac file content")

            return hmac_text
        if algorithm is None:
            algorithm = self.header_data.hmac_algorithm
        passphrase = self.passphrase.encode('utf-8')
        self.log.debug("Verifying file %s", filename)

        if os.stat(os.path.join(self.tmpdir, hmacfile)).st_size > \
                HMAC_MAX_SIZE:
            raise QubesException('HMAC file {} too large'.format(
                hmacfile))

        if hmacfile != filename + ".hmac":
            raise QubesException(
                "ERROR: expected hmac for {}, but got {}".
                format(filename, hmacfile))

        if algorithm == 'scrypt':
            # in case of 'scrypt' _verify_hmac is only used for backup header
            assert filename == HEADER_FILENAME
            self._verify_and_decrypt(hmacfile, HEADER_FILENAME + '.dec')
            f_name = os.path.join(self.tmpdir, filename)
            with open(f_name, 'rb') as f_one:
                with open(f_name + '.dec', 'rb') as f_two:
                    if f_one.read() != f_two.read():
                        raise QubesException(
                            'Invalid hmac on {}'.format(filename))
                    else:
                        return True

        with open(os.path.join(self.tmpdir, filename), 'rb') as f_input:
            hmac_proc = subprocess.Popen(
                ["openssl", "dgst", "-" + algorithm, "-hmac", passphrase],
                stdin=f_input,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            hmac_stdout, hmac_stderr = hmac_proc.communicate()

        if hmac_stderr:
            raise QubesException(
                "ERROR: verify file {0}: {1}".format(filename, hmac_stderr))
        else:
            self.log.debug("Loading hmac for file %s", filename)
            with open(os.path.join(self.tmpdir, hmacfile), 'r',
                    encoding='ascii') as f_hmac:
                hmac = load_hmac(f_hmac.read())

            if hmac and load_hmac(hmac_stdout.decode('ascii')) == hmac:
                os.unlink(os.path.join(self.tmpdir, hmacfile))
                self.log.debug(
                    "File verification OK -> Sending file %s", filename)
                return True
            else:
                raise QubesException(
                    "ERROR: invalid hmac for file {0}: {1}. "
                    "Is the passphrase correct?".
                    format(filename, load_hmac(hmac_stdout.decode('ascii'))))

    def _verify_and_decrypt(self, filename, output=None):
        '''Handle scrypt-wrapped file

        Decrypt the file, and verify its integrity - both tasks handled by
        'scrypt' tool. Filename (without extension) is also validated.

        :param filename: Input file name (relative to :py:attr:`tmpdir`),
        needs to have `.enc` or `.hmac` extension
        :param output: Output file name (relative to :py:attr:`tmpdir`),
        use :py:obj:`None` to use *filename* without extension
        :return: *filename* without extension
        '''
        assert filename.endswith('.enc') or filename.endswith('.hmac')
        fullname = os.path.join(self.tmpdir, filename)
        (origname, _) = os.path.splitext(filename)
        if output:
            fulloutput = os.path.join(self.tmpdir, output)
        else:
            fulloutput = os.path.join(self.tmpdir, origname)
        if origname == HEADER_FILENAME:
            passphrase = u'{filename}!{passphrase}'.format(
                filename=origname,
                passphrase=self.passphrase)
        else:
            passphrase = u'{backup_id}!{filename}!{passphrase}'.format(
                backup_id=self.header_data.backup_id,
                filename=origname,
                passphrase=self.passphrase)
        try:
            p = launch_scrypt('dec', fullname, fulloutput, passphrase)
        except OSError as err:
            raise QubesException('failed to decrypt {}: {!s}'.format(
                fullname, err))
        (_, stderr) = p.communicate()
        if hasattr(p, 'pty'):
            p.pty.close()
        if p.returncode != 0:
            os.unlink(fulloutput)
            raise QubesException('failed to decrypt {}: {}'.format(
                fullname, stderr))
        # encrypted file is no longer needed
        os.unlink(fullname)
        return origname

    def _retrieve_backup_header_files(self, files, allow_none=False):
        '''Retrieve backup header.

        Start retrieval process (possibly involving network access from
        another VM). Returns a collection of retrieved file paths.
        '''
        (retrieve_proc, filelist_pipe, error_pipe) = \
            self._start_retrieval_process(
                files, len(files), 1024 * 1024)
        filelist = filelist_pipe.read()
        filelist_pipe.close()
        retrieve_proc_returncode = retrieve_proc.wait()
        if retrieve_proc in self.processes_to_kill_on_cancel:
            self.processes_to_kill_on_cancel.remove(retrieve_proc)
        extract_stderr = error_pipe.read(MAX_STDERR_BYTES)
        error_pipe.close()

        # wait for other processes (if any)
        for proc in self.processes_to_kill_on_cancel:
            if proc.wait() != 0:
                raise QubesException(
                    "Backup header retrieval failed (exit code {})".format(
                        proc.wait())
                )

        if retrieve_proc_returncode != 0:
            if not filelist and 'Not found in archive' in extract_stderr:
                if allow_none:
                    return None
                else:
                    raise QubesException(
                        "unable to read the qubes backup file {0} ({1}): {2}".
                        format(
                            self.backup_location,
                            retrieve_proc.wait(),
                            extract_stderr
                        ))
        actual_files = filelist.decode('ascii').splitlines()
        if sorted(actual_files) != sorted(files):
            raise QubesException(
                'unexpected files in archive: got {!r}, expected {!r}'.format(
                    actual_files, files
                ))
        for fname in files:
            if not os.path.exists(os.path.join(self.tmpdir, fname)):
                if allow_none:
                    return None
                else:
                    raise QubesException(
                        'Unable to retrieve file {} from backup {}: {}'.format(
                            fname, self.backup_location, extract_stderr
                        )
                    )
        return files

    def _retrieve_backup_header(self):
        """Retrieve backup header and qubes.xml. Only backup header is
        analyzed, qubes.xml is left as-is
        (not even verified/decrypted/uncompressed)

        :return header_data
        :rtype :py:class:`BackupHeader`
        """

        if not self.backup_vm and os.path.exists(
                os.path.join(self.backup_location, 'qubes.xml')):
            # backup format version 1 doesn't have header
            header_data = BackupHeader()
            header_data.version = 1
            return header_data

        header_files = self._retrieve_backup_header_files(
            ['backup-header', 'backup-header.hmac'], allow_none=True)

        if not header_files:
            # R2-Beta3 didn't have backup header, so if none is found,
            # assume it's version=2 and use values present at that time
            header_data = BackupHeader(
                version=2,
                # place explicitly this value, because it is what format_version
                # 2 have
                hmac_algorithm='SHA1',
                crypto_algorithm='aes-256-cbc',
                # TODO: set encrypted to something...
            )
        else:
            filename = HEADER_FILENAME
            hmacfile = HEADER_FILENAME + '.hmac'
            self.log.debug("Got backup header and hmac: %s, %s",
                filename, hmacfile)

            file_ok = False
            hmac_algorithm = DEFAULT_HMAC_ALGORITHM
            for hmac_algo in get_supported_hmac_algo(hmac_algorithm):
                try:
                    if self._verify_hmac(filename, hmacfile, hmac_algo):
                        file_ok = True
                        break
                except QubesException as err:
                    self.log.debug(
                        'Failed to verify %s using %s: %r',
                            hmacfile, hmac_algo, err)
                    # Ignore exception here, try the next algo
            if not file_ok:
                raise QubesException(
                    "Corrupted backup header (hmac verification "
                    "failed). Is the password correct?")
            filename = os.path.join(self.tmpdir, filename)
            with open(filename, 'rb') as f_header:
                header_data = BackupHeader(f_header.read())
            os.unlink(filename)

        return header_data

    def _start_inner_extraction_worker(self, queue, handlers):
        """Start a worker process, extracting inner layer of bacup archive,
        extract them to :py:attr:`tmpdir`.
        End the data by pushing QUEUE_FINISHED or QUEUE_ERROR to the queue.

        :param queue :py:class:`Queue` object to handle files from
        """

        # Setup worker to extract encrypted data chunks to the restore dirs
        # Create the process here to pass it options extracted from
        # backup header
        extractor_params = {
            'queue': queue,
            'base_dir': self.tmpdir,
            'passphrase': self.passphrase,
            'encrypted': self.header_data.encrypted,
            'compressed': self.header_data.compressed,
            'crypto_algorithm': self.header_data.crypto_algorithm,
            'verify_only': self.options.verify_only,
            'progress_callback': self.progress_callback,
            'handlers': handlers,
        }
        self.log.debug(
            'Starting extraction worker in %s, file handlers map: %s',
            self.tmpdir, repr(handlers))
        format_version = self.header_data.version
        if format_version in [3, 4]:
            extractor_params['compression_filter'] = \
                self.header_data.compression_filter
            if format_version == 4:
                # encryption already handled
                extractor_params['encrypted'] = False
            extract_proc = ExtractWorker3(**extractor_params)
        else:
            raise NotImplementedError(
                "Backup format version %d not supported" % format_version)
        extract_proc.start()
        return extract_proc

    @staticmethod
    def _save_qubes_xml(path, stream):
        '''Handler for qubes.xml.000 content - just save the data to a file'''
        with open(path, 'wb') as f_qubesxml:
            f_qubesxml.write(stream.read())

    def _process_qubes_xml(self):
        """Verify, unpack and load qubes.xml. Possibly convert its format if
        necessary. It expect that :py:attr:`header_data` is already populated,
        and :py:meth:`retrieve_backup_header` was called.
        """
        if self.header_data.version == 1:
            raise NotImplementedError('Backup format version 1 not supported')
        elif self.header_data.version in [2, 3]:
            self._retrieve_backup_header_files(
                ['qubes.xml.000', 'qubes.xml.000.hmac'])
            self._verify_hmac("qubes.xml.000", "qubes.xml.000.hmac")
        else:
            self._retrieve_backup_header_files(['qubes.xml.000.enc'])
            self._verify_and_decrypt('qubes.xml.000.enc')

        queue = Queue()
        queue.put("qubes.xml.000")
        queue.put(QUEUE_FINISHED)

        qubes_xml_path = os.path.join(self.tmpdir, 'qubes-restored.xml')
        handlers = {
            'qubes.xml': (
                functools.partial(self._save_qubes_xml, qubes_xml_path),
                None)
            }
        extract_proc = self._start_inner_extraction_worker(queue, handlers)
        extract_proc.join()
        if extract_proc.exitcode != 0:
            raise QubesException(
                "unable to extract the qubes backup. "
                "Check extracting process errors.")

        if self.header_data.version in [2, 3]:
            from qubesadmin.backup.core2 import Core2Qubes
            backup_app = Core2Qubes(qubes_xml_path)
        elif self.header_data.version in [4]:
            from qubesadmin.backup.core3 import Core3Qubes
            backup_app = Core3Qubes(qubes_xml_path)
        else:
            raise QubesException(
                'Unsupported qubes.xml format version: {}'.format(
                    self.header_data.version))
        # Not needed anymore - all the data stored in backup_app
        os.unlink(qubes_xml_path)
        return backup_app

    def _restore_vm_data(self, vms_dirs, vms_size, handlers):
        '''Restore data of VMs

        :param vms_dirs: list of directories to extract (skip others)
        :param vms_size: expected size (abort if source stream exceed this
        value)
        :param handlers: handlers for restored files - see
        :py:class:`ExtractWorker3` for details
        '''
        # Currently each VM consists of at most 7 archives (count
        # file_to_backup calls in backup_prepare()), but add some safety
        # margin for further extensions. Each archive is divided into 100MB
        # chunks. Additionally each file have own hmac file. So assume upper
        # limit as 2*(10*COUNT_OF_VMS+TOTAL_SIZE/100MB)
        limit_count = str(2 * (10 * len(vms_dirs) +
                               int(vms_size / (100 * 1024 * 1024))))

        self.log.debug("Working in temporary dir: %s", self.tmpdir)
        self.log.info("Extracting data: %s to restore", size_to_human(vms_size))

        # retrieve backup from the backup stream (either VM, or dom0 file)
        (retrieve_proc, filelist_pipe, error_pipe) = \
            self._start_retrieval_process(
                vms_dirs, limit_count, vms_size)

        to_extract = Queue()

        # extract data retrieved by retrieve_proc
        extract_proc = self._start_inner_extraction_worker(
            to_extract, handlers)

        try:
            filename = None
            hmacfile = None
            nextfile = None
            while True:
                if self.canceled:
                    break
                if not extract_proc.is_alive():
                    retrieve_proc.terminate()
                    retrieve_proc.wait()
                    if retrieve_proc in self.processes_to_kill_on_cancel:
                        self.processes_to_kill_on_cancel.remove(retrieve_proc)
                    # wait for other processes (if any)
                    for proc in self.processes_to_kill_on_cancel:
                        proc.wait()
                    break
                if nextfile is not None:
                    filename = nextfile
                else:
                    filename = filelist_pipe.readline().decode('ascii').strip()

                self.log.debug("Getting new file: %s", filename)

                if not filename or filename == "EOF":
                    break

                # if reading archive directly with tar, wait for next filename -
                # tar prints filename before processing it, so wait for
                # the next one to be sure that whole file was extracted
                if not self.backup_vm:
                    nextfile = filelist_pipe.readline().decode('ascii').strip()

                if self.header_data.version in [2, 3]:
                    if not self.backup_vm:
                        hmacfile = nextfile
                        nextfile = filelist_pipe.readline().\
                            decode('ascii').strip()
                    else:
                        hmacfile = filelist_pipe.readline().\
                            decode('ascii').strip()

                    if self.canceled:
                        break

                    self.log.debug("Getting hmac: %s", hmacfile)
                    if not hmacfile or hmacfile == "EOF":
                        # Premature end of archive, either of tar1_command or
                        # vmproc exited with error
                        break
                else:  # self.header_data.version == 4
                    if not filename.endswith('.enc'):
                        raise qubesadmin.exc.QubesException(
                            'Invalid file extension found in archive: {}'.
                            format(filename))

                if not any(filename.startswith(x) for x in vms_dirs):
                    self.log.debug("Ignoring VM not selected for restore")
                    os.unlink(os.path.join(self.tmpdir, filename))
                    if hmacfile:
                        os.unlink(os.path.join(self.tmpdir, hmacfile))
                    continue

                if self.header_data.version in [2, 3]:
                    self._verify_hmac(filename, hmacfile)
                else:
                    # _verify_and_decrypt will write output to a file with
                    # '.enc' extension cut off. This is safe because:
                    # - `scrypt` tool will override output, so if the file was
                    # already there (received from the VM), it will be removed
                    # - incoming archive extraction will refuse to override
                    # existing file, so if `scrypt` already created one,
                    # it can not be manipulated by the VM
                    # - when the file is retrieved from the VM, it appears at
                    # the final form - if it's visible, VM have no longer
                    # influence over its content
                    #
                    # This all means that if the file was correctly verified
                    # + decrypted, we will surely access the right file
                    filename = self._verify_and_decrypt(filename)
                to_extract.put(os.path.join(self.tmpdir, filename))

            if self.canceled:
                raise BackupCanceledError("Restore canceled",
                                          tmpdir=self.tmpdir)

            if retrieve_proc.wait() != 0:
                raise QubesException(
                    "unable to read the qubes backup file {0}: {1}"
                    .format(self.backup_location, error_pipe.read(
                        MAX_STDERR_BYTES)))
            # wait for other processes (if any)
            for proc in self.processes_to_kill_on_cancel:
                proc.wait()
                if proc.returncode != 0:
                    raise QubesException(
                        "Backup completed, "
                        "but VM sending it reported an error (exit code {})".
                        format(proc.returncode))

            if filename and filename != "EOF":
                raise QubesException(
                    "Premature end of archive, the last file was %s" % filename)
        except:
            to_extract.put(QUEUE_ERROR)
            extract_proc.join()
            raise
        else:
            to_extract.put(QUEUE_FINISHED)
        finally:
            error_pipe.close()
            filelist_pipe.close()

        self.log.debug("Waiting for the extraction process to finish...")
        extract_proc.join()
        self.log.debug("Extraction process finished with code: %s",
            extract_proc.exitcode)
        if extract_proc.exitcode != 0:
            raise QubesException(
                "unable to extract the qubes backup. "
                "Check extracting process errors.")

    def new_name_for_conflicting_vm(self, orig_name, restore_info):
        '''Generate new name for conflicting VM

        Add a number suffix, until the name is unique. If no unique name can
        be found using this strategy, return :py:obj:`None`
        '''
        number = 1
        if len(orig_name) > 29:
            orig_name = orig_name[0:29]
        new_name = orig_name
        while (new_name in restore_info.keys() or
               new_name in [x.name for x in restore_info.values()] or
               new_name in self.app.domains):
            new_name = str('{}{}'.format(orig_name, number))
            number += 1
            if number == 100:
                # give up
                return None
        return new_name

    def restore_info_verify(self, restore_info):
        '''Verify restore info - validate VM dependencies, name conflicts
        etc.
        '''
        for vm in restore_info.keys():
            if vm in ['dom0']:
                continue

            vm_info = restore_info[vm]
            assert isinstance(vm_info, self.VMToRestore)

            vm_info.problems.clear()
            if vm in self.options.exclude:
                vm_info.problems.add(self.VMToRestore.EXCLUDED)

            if not self.options.verify_only and \
                    vm_info.name in self.app.domains:
                if self.options.rename_conflicting:
                    new_name = self.new_name_for_conflicting_vm(
                        vm, restore_info
                    )
                    if new_name is not None:
                        vm_info.name = new_name
                    else:
                        vm_info.problems.add(self.VMToRestore.ALREADY_EXISTS)
                else:
                    vm_info.problems.add(self.VMToRestore.ALREADY_EXISTS)

            # check template
            if vm_info.template:
                template_name = vm_info.template
                try:
                    host_template = self.app.domains[template_name]
                except KeyError:
                    host_template = None
                present_on_host = (host_template and
                    isinstance(host_template, qubesadmin.vm.TemplateVM))
                present_in_backup = (template_name in restore_info.keys() and
                    restore_info[template_name].good_to_go and
                    restore_info[template_name].vm.klass ==
                    'TemplateVM')
                if not present_on_host and not present_in_backup:
                    if self.options.use_default_template and \
                            self.app.default_template:
                        if vm_info.orig_template is None:
                            vm_info.orig_template = template_name
                        vm_info.template = self.app.default_template.name
                    else:
                        vm_info.problems.add(
                            self.VMToRestore.MISSING_TEMPLATE)

            # check netvm
            if vm_info.vm.properties.get('netvm', None) is not None:
                netvm_name = vm_info.netvm

                try:
                    netvm_on_host = self.app.domains[netvm_name]
                except KeyError:
                    netvm_on_host = None

                present_on_host = (netvm_on_host is not None
                        and netvm_on_host.provides_network)
                present_in_backup = (netvm_name in restore_info.keys() and
                    restore_info[netvm_name].good_to_go and
                    restore_info[netvm_name].vm.properties.get(
                        'provides_network', False))
                if not present_on_host and not present_in_backup:
                    if self.options.use_default_netvm:
                        del vm_info.vm.properties['netvm']
                    elif self.options.use_none_netvm:
                        vm_info.netvm = None
                    else:
                        vm_info.problems.add(self.VMToRestore.MISSING_NETVM)

        return restore_info

    def get_restore_info(self):
        '''Get restore info

        Return information about what is included in the backup.
        That dictionary can be adjusted to select what VM should be restore.
        '''
        # Format versions:
        #  1 - Qubes R1, Qubes R2 beta1, beta2
        #  2 - Qubes R2 beta3+
        #  3 - Qubes R2+
        #  4 - Qubes R4+

        vms_to_restore = {}

        for vm in self.backup_app.domains.values():
            if vm.klass == 'AdminVM':
                # Handle dom0 as special case later
                continue
            if vm.included_in_backup:
                self.log.debug("%s is included in backup", vm.name)

                vms_to_restore[vm.name] = self.VMToRestore(vm)

                if vm.template is not None:
                    templatevm_name = vm.template
                    vms_to_restore[vm.name].template = templatevm_name

        vms_to_restore = self.restore_info_verify(vms_to_restore)

        # ...and dom0 home
        if self.options.dom0_home and \
                self.backup_app.domains['dom0'].included_in_backup:
            vm = self.backup_app.domains['dom0']
            vms_to_restore['dom0'] = self.Dom0ToRestore(vm)
            local_user = grp.getgrnam('qubes').gr_mem[0]

            if vms_to_restore['dom0'].username != local_user:
                if not self.options.ignore_username_mismatch:
                    vms_to_restore['dom0'].problems.add(
                        self.Dom0ToRestore.USERNAME_MISMATCH)

        return vms_to_restore

    @staticmethod
    def get_restore_summary(restore_info):
        '''Return a ASCII formatted table with restore info summary'''
        fields = {
            "name": {'func': lambda vm: vm.name},

            "type": {'func': lambda vm: vm.klass},

            "template": {'func': lambda vm:
                'n/a' if vm.template is None else vm.template},

            "netvm": {'func': lambda vm:
                '(default)' if 'netvm' not in vm.properties else
                '-' if vm.properties['netvm'] is None else
                vm.properties['netvm']},

            "label": {'func': lambda vm: vm.label},
        }

        fields_to_display = ['name', 'type', 'template',
            'netvm', 'label']

        # First calculate the maximum width of each field we want to display
        total_width = 0
        for field in fields_to_display:
            fields[field]['max_width'] = len(field)
            for vm_info in restore_info.values():
                if vm_info.vm:
                    # noinspection PyUnusedLocal
                    field_len = len(str(fields[field]["func"](vm_info.vm)))
                    if field_len > fields[field]['max_width']:
                        fields[field]['max_width'] = field_len
            total_width += fields[field]['max_width']

        summary = ""
        summary += "The following VMs are included in the backup:\n"
        summary += "\n"

        # Display the header
        for field in fields_to_display:
            # noinspection PyTypeChecker
            fmt = "{{0:-^{0}}}-+".format(fields[field]["max_width"] + 1)
            summary += fmt.format('-')
        summary += "\n"
        for field in fields_to_display:
            # noinspection PyTypeChecker
            fmt = "{{0:>{0}}} |".format(fields[field]["max_width"] + 1)
            summary += fmt.format(field)
        summary += "\n"
        for field in fields_to_display:
            # noinspection PyTypeChecker
            fmt = "{{0:-^{0}}}-+".format(fields[field]["max_width"] + 1)
            summary += fmt.format('-')
        summary += "\n"

        for vm_info in restore_info.values():
            assert isinstance(vm_info, BackupRestore.VMToRestore)
            # Skip non-VM here
            if not vm_info.vm:
                continue
            # noinspection PyUnusedLocal
            summary_line = ""
            for field in fields_to_display:
                # noinspection PyTypeChecker
                fmt = "{{0:>{0}}} |".format(fields[field]["max_width"] + 1)
                summary_line += fmt.format(fields[field]["func"](vm_info.vm))

            if BackupRestore.VMToRestore.EXCLUDED in vm_info.problems:
                summary_line += " <-- Excluded from restore"
            elif BackupRestore.VMToRestore.ALREADY_EXISTS in vm_info.problems:
                summary_line += \
                    " <-- A VM with the same name already exists on the host!"
            elif BackupRestore.VMToRestore.MISSING_TEMPLATE in \
                    vm_info.problems:
                summary_line += " <-- No matching template on the host " \
                     "or in the backup found!"
            elif BackupRestore.VMToRestore.MISSING_NETVM in \
                    vm_info.problems:
                summary_line += " <-- No matching netvm on the host " \
                     "or in the backup found!"
            else:
                if vm_info.template != vm_info.vm.template:
                    summary_line += " <-- Template change to '{}'".format(
                        vm_info.template)
                if vm_info.name != vm_info.vm.name:
                    summary_line += " <-- Will be renamed to '{}'".format(
                        vm_info.name)

            summary += summary_line + "\n"

        if 'dom0' in restore_info.keys():
            summary_line = ""
            for field in fields_to_display:
                # noinspection PyTypeChecker
                fmt = "{{0:>{0}}} |".format(fields[field]["max_width"] + 1)
                if field == "name":
                    summary_line += fmt.format("Dom0")
                elif field == "type":
                    summary_line += fmt.format("Home")
                else:
                    summary_line += fmt.format("")
            if BackupRestore.Dom0ToRestore.USERNAME_MISMATCH in \
                    restore_info['dom0'].problems:
                summary_line += " <-- username in backup and dom0 mismatch"

            summary += summary_line + "\n"

        return summary

    @staticmethod
    def _templates_first(vms):
        '''Sort templates befor other VM types (AppVM etc)'''
        def key_function(instance):
            '''Key function for :py:func:`sorted`'''
            if isinstance(instance, BackupVM):
                return instance.klass == 'TemplateVM'
            elif hasattr(instance, 'vm'):
                return key_function(instance.vm)
            return 0
        return sorted(vms,
            key=key_function,
            reverse=True)


    def _handle_dom0(self, backup_path):
        '''Extract dom0 home'''
        local_user = grp.getgrnam('qubes').gr_mem[0]
        home_dir = pwd.getpwnam(local_user).pw_dir
        backup_dom0_home_dir = os.path.join(self.tmpdir, backup_path)
        restore_home_backupdir = "home-pre-restore-{0}".format(
            time.strftime("%Y-%m-%d-%H%M%S"))

        self.log.info("Restoring home of user '%s'...", local_user)
        self.log.info("Existing files/dirs backed up in '%s' dir",
            restore_home_backupdir)
        os.mkdir(home_dir + '/' + restore_home_backupdir)
        for f_name in os.listdir(backup_dom0_home_dir):
            home_file = home_dir + '/' + f_name
            if os.path.exists(home_file):
                os.rename(home_file,
                    home_dir + '/' + restore_home_backupdir + '/' + f_name)
            if self.header_data.version == 1:
                subprocess.call(
                    ["cp", "-nrp", "--reflink=auto",
                        backup_dom0_home_dir + '/' + f_name, home_file])
            elif self.header_data.version >= 2:
                shutil.move(backup_dom0_home_dir + '/' + f_name, home_file)
        retcode = subprocess.call(['sudo', 'chown', '-R',
            local_user, home_dir])
        if retcode != 0:
            self.log.error("*** Error while setting home directory owner")

    def _handle_appmenus_list(self, vm, stream):
        '''Handle whitelisted-appmenus.list file'''
        try:
            subprocess.check_call(
                ['qvm-appmenus', '--set-whitelist=-', vm.name],
                stdin=stream)
        except subprocess.CalledProcessError:
            self.log.exception('Failed to set application list for %s', vm.name)

    def restore_do(self, restore_info):
        '''

        High level workflow:
        1. Create VMs object in host collection (qubes.xml)
        2. Create them on disk (vm.create_on_disk)
        3. Restore VM data, overriding/converting VM files
        4. Apply possible fixups and save qubes.xml

        :param restore_info:
        :return:
        '''

        if self.header_data.version == 1:
            raise NotImplementedError('Backup format version 1 not supported')

        restore_info = self.restore_info_verify(restore_info)

        self._restore_vms_metadata(restore_info)

        # Perform VM restoration in backup order
        vms_dirs = []
        handlers = {}
        vms_size = 0
        for vm_info in self._templates_first(restore_info.values()):
            vm = vm_info.restored_vm
            if vm and vm_info.subdir:
                vms_size += int(vm_info.size)
                vms_dirs.append(vm_info.subdir)
                for name, volume in vm.volumes.items():
                    if not volume.save_on_stop:
                        continue
                    data_func = volume.import_data
                    size_func = volume.resize
                    handlers[os.path.join(vm_info.subdir, name + '.img')] = \
                        (data_func, size_func)
                handlers[os.path.join(vm_info.subdir, 'firewall.xml')] = (
                    functools.partial(vm_info.vm.handle_firewall_xml, vm), None)
                handlers[os.path.join(vm_info.subdir,
                    'whitelisted-appmenus.list')] = (
                    functools.partial(self._handle_appmenus_list, vm), None)

        if 'dom0' in restore_info.keys() and \
                restore_info['dom0'].good_to_go:
            vms_dirs.append(os.path.dirname(restore_info['dom0'].subdir))
            vms_size += restore_info['dom0'].size
            handlers[restore_info['dom0'].subdir] = (self._handle_dom0, None)
        try:
            self._restore_vm_data(vms_dirs=vms_dirs, vms_size=vms_size,
                handlers=handlers)
        except QubesException:
            if self.options.verify_only:
                raise
            else:
                self.log.warning(
                    "Some errors occurred during data extraction, "
                    "continuing anyway to restore at least some "
                    "VMs")

        if self.options.verify_only:
            shutil.rmtree(self.tmpdir)
            return

        if self.canceled:
            raise BackupCanceledError("Restore canceled",
                                      tmpdir=self.tmpdir)

        shutil.rmtree(self.tmpdir)
        self.log.info("-> Done. Please install updates for all the restored "
                      "templates.")

    def _restore_vms_metadata(self, restore_info):
        '''Restore VM metadata

        Create VMs, set their properties etc.
        '''
        vms = {}
        for vm_info in restore_info.values():
            assert isinstance(vm_info, self.VMToRestore)
            if not vm_info.vm:
                continue
            if not vm_info.good_to_go:
                continue
            vm = vm_info.vm
            vms[vm.name] = vm

        # First load templates, then other VMs
        for vm in self._templates_first(vms.values()):
            if self.canceled:
                return
            self.log.info("-> Restoring %s...", vm.name)
            kwargs = {}
            if vm.template:
                template = restore_info[vm.name].template
                # handle potentially renamed template
                if template in restore_info \
                        and restore_info[template].good_to_go:
                    template = restore_info[template].name
                kwargs['template'] = template

            new_vm = None
            vm_name = restore_info[vm.name].name

            try:
                # first only create VMs, later setting may require other VMs
                # be already created
                new_vm = self.app.add_new_vm(
                    vm.klass,
                    name=vm_name,
                    label=vm.label,
                    pool=self.options.override_pool,
                    **kwargs)
            except Exception:  # pylint: disable=broad-except
                self.log.exception('Error restoring VM %s, skipping', vm.name)
                if new_vm:
                    del self.app.domains[new_vm.name]
                continue

            restore_info[vm.name].restored_vm = new_vm

        for vm in vms.values():
            if self.canceled:
                return

            new_vm = restore_info[vm.name].restored_vm
            if not new_vm:
                # skipped/failed
                continue

            for prop, value in vm.properties.items():
                # exclude VM references - handled manually according to
                # restore options
                if prop in ['template', 'netvm', 'default_dispvm']:
                    continue
                try:
                    setattr(new_vm, prop, value)
                except Exception:  # pylint: disable=broad-except
                    self.log.exception('Error setting %s.%s to %s',
                        vm.name, prop, value)

            for feature, value in vm.features.items():
                try:
                    new_vm.features[feature] = value
                except Exception:  # pylint: disable=broad-except
                    self.log.exception('Error setting %s.features[%s] to %s',
                        vm.name, feature, value)

            for tag in vm.tags:
                try:
                    new_vm.tags.add(tag)
                except Exception:  # pylint: disable=broad-except
                    self.log.exception('Error adding tag %s to %s',
                        tag, vm.name)

            for bus in vm.devices:
                for backend_domain, ident in vm.devices[bus]:
                    options = vm.devices[bus][(backend_domain, ident)]
                    assignment = DeviceAssignment(
                        backend_domain=backend_domain,
                        ident=ident,
                        options=options,
                        persistent=True)
                    try:
                        new_vm.devices[bus].attach(assignment)
                    except Exception:  # pylint: disable=broad-except
                        self.log.exception('Error attaching device %s:%s to %s',
                            bus, ident, vm.name)

        # Set VM dependencies - only non-default setting
        for vm in vms.values():
            vm_info = restore_info[vm.name]
            vm_name = vm_info.name
            try:
                host_vm = self.app.domains[vm_name]
            except KeyError:
                # Failed/skipped VM
                continue

            if 'netvm' in vm.properties:
                if vm_info.netvm in restore_info:
                    value = restore_info[vm_info.netvm].name
                else:
                    value = vm_info.netvm

                try:
                    host_vm.netvm = value
                except Exception:  # pylint: disable=broad-except
                    self.log.exception('Error setting %s.%s to %s',
                        vm.name, 'netvm', value)

            if 'default_dispvm' in vm.properties:
                if vm.properties['default_dispvm'] in restore_info:
                    value = restore_info[vm.properties[
                        'default_dispvm']].name
                else:
                    value = vm.properties['default_dispvm']

                try:
                    host_vm.default_dispvm = value
                except Exception:  # pylint: disable=broad-except
                    self.log.exception('Error setting %s.%s to %s',
                        vm.name, 'default_dispvm', value)
