from unittest import mock
import argparse
import asyncio
import datetime
import io
import os
import pathlib
import subprocess
import tempfile

import fcntl
import rpm

import qubesadmin.tests
import qubesadmin.tools.qvm_template

class TC_00_qvm_template(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        # Print str(list) directly so that the output is consistent no matter
        # which implementation of `column` we use
        self.mock_table = mock.patch('qubesadmin.tools.print_table')
        mock_table = self.mock_table.start()
        def print_table(table, *args):
            print(str(table))
        mock_table.side_effect = print_table

        super().setUp()

    def tearDown(self):
        self.mock_table.stop()
        super().tearDown()

    @mock.patch('rpm.TransactionSet')
    @mock.patch('subprocess.check_call')
    @mock.patch('subprocess.check_output')
    def test_000_verify_rpm_success(self, mock_proc, mock_call, mock_ts):
        # Just return a dict instead of rpm.hdr
        hdr = {
            rpm.RPMTAG_SIGPGP: 'xxx', # non-empty
            rpm.RPMTAG_SIGGPG: 'xxx', # non-empty
        }
        mock_ts.return_value.hdrFromFdno.return_value = hdr
        mock_proc.return_value = b'dummy.rpm: digests signatures OK\n'
        ret = qubesadmin.tools.qvm_template.verify_rpm('/dev/null',
            ['/path/to/key'])
        mock_call.assert_called_once()
        mock_proc.assert_called_once()
        self.assertEqual(hdr, ret)
        self.assertAllCalled()

    @mock.patch('rpm.TransactionSet')
    @mock.patch('subprocess.check_call')
    @mock.patch('subprocess.check_output')
    def test_001_verify_rpm_nosig_fail(self, mock_proc, mock_call, mock_ts):
        # Just return a dict instead of rpm.hdr
        hdr = {
            rpm.RPMTAG_SIGPGP: None, # empty
            rpm.RPMTAG_SIGGPG: None, # empty
        }
        mock_ts.return_value.hdrFromFdno.return_value = hdr
        mock_proc.return_value = b'dummy.rpm: digests OK\n'
        with self.assertRaises(Exception) as e:
            qubesadmin.tools.qvm_template.verify_rpm('/dev/null',
                ['/path/to/key'])
        mock_call.assert_called_once()
        mock_proc.assert_called_once()
        self.assertIn('Signature verification failed', e.exception.args[0])
        mock_ts.assert_not_called()
        self.assertAllCalled()

    @mock.patch('rpm.TransactionSet')
    @mock.patch('subprocess.check_call')
    @mock.patch('subprocess.check_output')
    def test_002_verify_rpm_nosig_success(self, mock_proc, mock_call, mock_ts):
        # Just return a dict instead of rpm.hdr
        hdr = {
            rpm.RPMTAG_SIGPGP: None, # empty
            rpm.RPMTAG_SIGGPG: None, # empty
        }
        mock_ts.return_value.hdrFromFdno.return_value = hdr
        mock_proc.return_value = b'dummy.rpm: digests OK\n'
        ret = qubesadmin.tools.qvm_template.verify_rpm('/dev/null',
            ['/path/to/key'], True)
        mock_proc.assert_not_called()
        mock_call.assert_not_called()
        self.assertEqual(ret, hdr)
        self.assertAllCalled()

    @mock.patch('rpm.TransactionSet')
    @mock.patch('subprocess.check_call')
    @mock.patch('subprocess.check_output')
    def test_003_verify_rpm_badsig_fail(self, mock_proc, mock_call, mock_ts):
        mock_proc.side_effect = subprocess.CalledProcessError(1,
            ['rpmkeys', '--checksig'], b'/dev/null: digests SIGNATURES NOT OK\n')
        with self.assertRaises(Exception) as e:
            qubesadmin.tools.qvm_template.verify_rpm('/dev/null',
                ['/path/to/key'])
        mock_call.assert_called_once()
        mock_proc.assert_called_once()
        self.assertIn('Signature verification failed', e.exception.args[0])
        mock_ts.assert_not_called()
        self.assertAllCalled()

    @mock.patch('subprocess.Popen')
    def test_010_extract_rpm_success(self, mock_popen):
        pipe = mock.Mock()
        mock_popen.return_value.stdout = pipe
        mock_popen.return_value.wait.return_value = 0
        with tempfile.NamedTemporaryFile() as fd, \
                tempfile.TemporaryDirectory() as dir:
            path = fd.name
            dirpath = dir
            ret = qubesadmin.tools.qvm_template.extract_rpm(
                'test-vm', path, dirpath)
        self.assertEqual(ret, True)
        self.assertEqual(mock_popen.mock_calls, [
            mock.call(['rpm2cpio', path], stdout=subprocess.PIPE),
            mock.call([
                    'cpio',
                    '-idm',
                    '-D',
                    dirpath,
                    './var/lib/qubes/vm-templates/test-vm/*'
                ], stdin=pipe, stdout=subprocess.DEVNULL),
            mock.call().wait(),
            mock.call().wait()
        ])
        self.assertAllCalled()

    @mock.patch('subprocess.Popen')
    def test_011_extract_rpm_fail(self, mock_popen):
        pipe = mock.Mock()
        mock_popen.return_value.stdout = pipe
        mock_popen.return_value.wait.return_value = 1
        with tempfile.NamedTemporaryFile() as fd, \
                tempfile.TemporaryDirectory() as dir:
            path = fd.name
            dirpath = dir
            ret = qubesadmin.tools.qvm_template.extract_rpm(
                'test-vm', path, dirpath)
        self.assertEqual(ret, False)
        self.assertEqual(mock_popen.mock_calls, [
            mock.call(['rpm2cpio', path], stdout=subprocess.PIPE),
            mock.call([
                    'cpio',
                    '-idm',
                    '-D',
                    dirpath,
                    './var/lib/qubes/vm-templates/test-vm/*'
                ], stdin=pipe, stdout=subprocess.DEVNULL),
            mock.call().wait()
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.get_keys')
    def test_090_install_lock(self, mock_get_keys):
        class SuccessError(Exception):
            pass
        mock_get_keys.side_effect = SuccessError
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'):
            with self.subTest('not locked'):
                with self.assertRaises(SuccessError):
                    # args don't matter
                    qubesadmin.tools.qvm_template.install(mock.MagicMock(), None)
                self.assertFalse(os.path.exists('/tmp/test.lock'))

            with self.subTest('lock exists but unlocked'):
                with open('/tmp/test.lock', 'w') as f:
                    with self.assertRaises(SuccessError):
                        # args don't matter
                        qubesadmin.tools.qvm_template.install(mock.MagicMock(), None)
                self.assertFalse(os.path.exists('/tmp/test.lock'))
            with self.subTest('locked'):
                with open('/tmp/test.lock', 'w') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    with self.assertRaises(
                            qubesadmin.tools.qvm_template.AlreadyRunning):
                        # args don't matter
                        qubesadmin.tools.qvm_template.install(mock.MagicMock(), None)
                    # and not cleaned up then
                    self.assertTrue(os.path.exists('/tmp/test.lock'))

    def add_new_vm_side_effect(self, *args, **kwargs):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.domains.clear_cache()
        return self.app.domains['test-vm']

    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    def test_100_install_local_success(
            self,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = b'0\0'
        build_time = '2020-09-01 14:30:00' # 1598970600
        install_time = '2020-09-01 15:30:00'
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '2'),
                ('version', '4.1'),
                ('release', '2020'),
                ('reponame', '@commandline'),
                ('buildtime', build_time),
                ('installtime', install_time),
                ('license', 'GPL'),
                ('url', 'https://qubes-os.org'),
                ('summary', 'Summary'),
                ('description', 'Desc|desc')]:
            self.app.expected_calls[(
                'test-vm',
                'admin.vm.feature.Set',
                f'template-{key}',
                val.encode())] = b'0\0'
        mock_verify.return_value = {
            rpm.RPMTAG_NAME        : 'qubes-template-test-vm',
            rpm.RPMTAG_BUILDTIME   : 1598970600,
            rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
            rpm.RPMTAG_EPOCHNUM    : 2,
            rpm.RPMTAG_LICENSE     : 'GPL',
            rpm.RPMTAG_RELEASE     : '2020',
            rpm.RPMTAG_SUMMARY     : 'Summary',
            rpm.RPMTAG_URL         : 'https://qubes-os.org',
            rpm.RPMTAG_VERSION     : '4.1'
        }
        mock_dl_list.return_value = {}
        mock_call.side_effect = self.add_new_vm_side_effect
        mock_time = mock.Mock(wraps=datetime.datetime)
        mock_time.now.return_value = \
            datetime.datetime(2020, 9, 1, 15, 30, tzinfo=datetime.timezone.utc)
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/tmp',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            qubesadmin.tools.qvm_template.install(args, self.app)
        # Attempt to get download list
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        # Nothing downloaded
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/tmp/qvm-template-tmpdir',
            dl_list={}, suffix='.unverified', version_selector=selector)
        # Package is extracted
        mock_extract.assert_called_with('test-vm', path,
            '/var/tmp/qvm-template-tmpdir')
        # No packages overwritten, so no confirm needed
        self.assertEqual(mock_confirm.mock_calls, [])
        # qvm-template-postprocess is called
        self.assertEqual(mock_call.mock_calls, [
            mock.call([
                'qvm-template-postprocess',
                '--really',
                '--no-installed-by-rpm',
                'post-install',
                'test-vm',
                '/var/tmp/qvm-template-tmpdir'
                    '/var/lib/qubes/vm-templates/test-vm'
            ])
        ])
        # Cache directory created
        self.assertEqual(mock_mkdirs.mock_calls, [
            mock.call(args.cachedir, exist_ok=True)
        ])
        # No templates downloaded, thus no renames needed
        self.assertEqual(mock_rename.mock_calls, [])
        self.assertAllCalled()

    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    def test_101_install_local_postprocargs_success(
            self,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = b'0\0'
        build_time = '2020-09-01 14:30:00' # 1598970600
        install_time = '2020-09-01 15:30:00'
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '2'),
                ('version', '4.1'),
                ('release', '2020'),
                ('reponame', '@commandline'),
                ('buildtime', build_time),
                ('installtime', install_time),
                ('license', 'GPL'),
                ('url', 'https://qubes-os.org'),
                ('summary', 'Summary'),
                ('description', 'Desc|desc')]:
            self.app.expected_calls[(
                'test-vm',
                'admin.vm.feature.Set',
                f'template-{key}',
                val.encode())] = b'0\0'
        mock_verify.return_value = {
            rpm.RPMTAG_NAME        : 'qubes-template-test-vm',
            rpm.RPMTAG_BUILDTIME   : 1598970600,
            rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
            rpm.RPMTAG_EPOCHNUM    : 2,
            rpm.RPMTAG_LICENSE     : 'GPL',
            rpm.RPMTAG_RELEASE     : '2020',
            rpm.RPMTAG_SUMMARY     : 'Summary',
            rpm.RPMTAG_URL         : 'https://qubes-os.org',
            rpm.RPMTAG_VERSION     : '4.1'
        }
        mock_dl_list.return_value = {}
        mock_call.side_effect = self.add_new_vm_side_effect
        mock_time = mock.Mock(wraps=datetime.datetime)
        mock_time.now.return_value = \
            datetime.datetime(2020, 9, 1, 15, 30, tzinfo=datetime.timezone.utc)
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/tmp',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                yes=False,
                allow_pv=True,
                pool='my-pool'
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            qubesadmin.tools.qvm_template.install(args, self.app)
        # Attempt to get download list
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        # Nothing downloaded
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/tmp/qvm-template-tmpdir',
            dl_list={}, suffix='.unverified', version_selector=selector)
        # Package is extracted
        mock_extract.assert_called_with('test-vm', path,
            '/var/tmp/qvm-template-tmpdir')
        # No packages overwritten, so no confirm needed
        self.assertEqual(mock_confirm.mock_calls, [])
        # qvm-template-postprocess is called
        self.assertEqual(mock_call.mock_calls, [
            mock.call([
                'qvm-template-postprocess',
                '--really',
                '--no-installed-by-rpm',
                '--allow-pv',
                '--pool',
                'my-pool',
                'post-install',
                'test-vm',
                '/var/tmp/qvm-template-tmpdir'
                    '/var/lib/qubes/vm-templates/test-vm'
            ])
        ])
        # Cache directory created
        self.assertEqual(mock_mkdirs.mock_calls, [
            mock.call(args.cachedir, exist_ok=True)
        ])
        # No templates downloaded, thus no renames needed
        self.assertEqual(mock_rename.mock_calls, [])
        self.assertAllCalled()

    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    def test_102_install_local_badsig_fail(
            self,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename):
        mock_verify.return_value = None
        mock_time = mock.Mock(wraps=datetime.datetime)
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/tmp',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            # Should raise parser.error
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.install(args, self.app)
            # Check error message
            self.assertTrue('verification failed' in mock_err.getvalue())
        # Should not be executed:
        self.assertEqual(mock_dl_list.mock_calls, [])
        self.assertEqual(mock_dl.mock_calls, [])
        self.assertEqual(mock_extract.mock_calls, [])
        self.assertEqual(mock_confirm.mock_calls, [])
        self.assertEqual(mock_call.mock_calls, [])
        self.assertEqual(mock_rename.mock_calls, [])
        self.assertAllCalled()

    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    def test_103_install_local_exists_fail(
            self,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        mock_verify.return_value = {
            rpm.RPMTAG_NAME        : 'qubes-template-test-vm',
            rpm.RPMTAG_BUILDTIME   : 1598970600,
            rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
            rpm.RPMTAG_EPOCHNUM    : 2,
            rpm.RPMTAG_LICENSE     : 'GPL',
            rpm.RPMTAG_RELEASE     : '2020',
            rpm.RPMTAG_SUMMARY     : 'Summary',
            rpm.RPMTAG_URL         : 'https://qubes-os.org',
            rpm.RPMTAG_VERSION     : '4.1'
        }
        mock_dl_list.return_value = {}
        mock_time = mock.Mock(wraps=datetime.datetime)
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/tmp',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            qubesadmin.tools.qvm_template.install(args, self.app)
            # Check warning message
            self.assertTrue('already installed' in mock_err.getvalue())
        # Attempt to get download list
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        # Nothing downloaded
        self.assertEqual(mock_dl.mock_calls, [
            mock.call(args, self.app, path_override='/var/tmp/qvm-template-tmpdir',
                dl_list={}, suffix='.unverified', version_selector=selector)
        ])
        # Should not be executed:
        self.assertEqual(mock_extract.mock_calls, [])
        self.assertEqual(mock_confirm.mock_calls, [])
        self.assertEqual(mock_call.mock_calls, [])
        self.assertEqual(mock_rename.mock_calls, [])
        self.assertAllCalled()

    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    def test_104_install_local_badpkgname_fail(
            self,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename):
        mock_verify.return_value = {
            rpm.RPMTAG_NAME        : 'Xqubes-template-test-vm',
            rpm.RPMTAG_BUILDTIME   : 1598970600,
            rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
            rpm.RPMTAG_EPOCHNUM    : 2,
            rpm.RPMTAG_LICENSE     : 'GPL',
            rpm.RPMTAG_RELEASE     : '2020',
            rpm.RPMTAG_SUMMARY     : 'Summary',
            rpm.RPMTAG_URL         : 'https://qubes-os.org',
            rpm.RPMTAG_VERSION     : '4.1'
        }
        mock_time = mock.Mock(wraps=datetime.datetime)
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/tmp',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.install(args, self.app)
            # Check error message
            self.assertTrue('Illegal package name' in mock_err.getvalue())
        # Should not be executed:
        self.assertEqual(mock_dl_list.mock_calls, [])
        self.assertEqual(mock_dl.mock_calls, [])
        self.assertEqual(mock_extract.mock_calls, [])
        self.assertEqual(mock_confirm.mock_calls, [])
        self.assertEqual(mock_call.mock_calls, [])
        self.assertEqual(mock_rename.mock_calls, [])
        self.assertAllCalled()

    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    def test_106_install_local_badpath_fail(
            self,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename):
        mock_time = mock.Mock(wraps=datetime.datetime)
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            path = '/var/tmp/ShOulD-NoT-ExIsT.rpm'
            args = argparse.Namespace(
                templates=[path],
                keyring='/tmp',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.install(args, self.app)
            # Check error message
            self.assertTrue(f"RPM file '{path}' not found" \
                in mock_err.getvalue())
        # Should not be executed:
        self.assertEqual(mock_verify.mock_calls, [])
        self.assertEqual(mock_dl_list.mock_calls, [])
        self.assertEqual(mock_dl.mock_calls, [])
        self.assertEqual(mock_extract.mock_calls, [])
        self.assertEqual(mock_confirm.mock_calls, [])
        self.assertEqual(mock_call.mock_calls, [])
        self.assertEqual(mock_rename.mock_calls, [])
        self.assertAllCalled()

    def test_110_qrexec_payload_refresh_success(self):
        with tempfile.NamedTemporaryFile() as repo_conf1, \
                tempfile.NamedTemporaryFile() as repo_conf2:
            repo_str1 = \
'''[qubes-templates-itl]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl
metalink = https://yum.qubes-os.org/r$releasever/templates-itl/repodata/repomd.xml.metalink
enabled = 1
fastestmirror = 1
metadata_expire = 7d
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
'''
            repo_str2 = \
'''[qubes-templates-itl-testing]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl-testing
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl-testing
metalink = https://yum.qubes-os.org/r$releasever/templates-itl-testing/repodata/repomd.xml.metalink
enabled = 0
fastestmirror = 1
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
'''
            repo_conf1.write(repo_str1.encode())
            repo_conf1.flush()
            repo_conf2.write(repo_str2.encode())
            repo_conf2.flush()
            args = argparse.Namespace(
                enablerepo=['repo1', 'repo2'],
                disablerepo=['repo3', 'repo4', 'repo5'],
                repoid=[],
                releasever='4.1',
                repo_files=[repo_conf1.name, repo_conf2.name]
            )
            res = qubesadmin.tools.qvm_template.qrexec_payload(args, self.app,
                'qubes-template-fedora-32', True)
            self.assertEqual(res,
'''--enablerepo=repo1
--enablerepo=repo2
--disablerepo=repo3
--disablerepo=repo4
--disablerepo=repo5
--refresh
--releasever=4.1
qubes-template-fedora-32
---
''' + repo_str1 + '\n' + repo_str2 + '\n')
        self.assertAllCalled()

    def test_111_qrexec_payload_norefresh_success(self):
        with tempfile.NamedTemporaryFile() as repo_conf1:
            repo_str1 = \
'''[qubes-templates-itl]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl
metalink = https://yum.qubes-os.org/r$releasever/templates-itl/repodata/repomd.xml.metalink
enabled = 1
fastestmirror = 1
metadata_expire = 7d
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
'''
            repo_conf1.write(repo_str1.encode())
            repo_conf1.flush()
            args = argparse.Namespace(
                enablerepo=[],
                disablerepo=[],
                repoid=['repo1', 'repo2'],
                releasever='4.1',
                repo_files=[repo_conf1.name]
            )
            res = qubesadmin.tools.qvm_template.qrexec_payload(args, self.app,
                'qubes-template-fedora-32', False)
            self.assertEqual(res,
'''--repoid=repo1
--repoid=repo2
--releasever=4.1
qubes-template-fedora-32
---
''' + repo_str1 + '\n')
        self.assertAllCalled()

    def test_112_qrexec_payload_specnewline_fail(self):
        with tempfile.NamedTemporaryFile() as repo_conf1:
            repo_str1 = \
'''[qubes-templates-itl]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl
metalink = https://yum.qubes-os.org/r$releasever/templates-itl/repodata/repomd.xml.metalink
enabled = 1
fastestmirror = 1
metadata_expire = 7d
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
'''
            repo_conf1.write(repo_str1.encode())
            repo_conf1.flush()
            args = argparse.Namespace(
                enablerepo=[],
                disablerepo=[],
                repoid=['repo1', 'repo2'],
                releasever='4.1',
                repo_files=[repo_conf1.name]
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                with self.assertRaises(SystemExit):
                    qubesadmin.tools.qvm_template.qrexec_payload(args,
                        self.app, 'qubes-template-fedora\n-32', False)
                # Check error message
                self.assertTrue('Malformed template name'
                    in mock_err.getvalue())
                self.assertTrue("argument should not contain '\\n'"
                    in mock_err.getvalue())
        self.assertAllCalled()

    def test_113_qrexec_payload_enablereponewline_fail(self):
        with tempfile.NamedTemporaryFile() as repo_conf1:
            repo_str1 = \
'''[qubes-templates-itl]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl
metalink = https://yum.qubes-os.org/r$releasever/templates-itl/repodata/repomd.xml.metalink
enabled = 1
fastestmirror = 1
metadata_expire = 7d
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
'''
            repo_conf1.write(repo_str1.encode())
            repo_conf1.flush()
            args = argparse.Namespace(
                enablerepo=['repo\n0'],
                disablerepo=[],
                repoid=['repo1', 'repo2'],
                releasever='4.1',
                repo_files=[repo_conf1.name]
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                with self.assertRaises(SystemExit):
                    qubesadmin.tools.qvm_template.qrexec_payload(args,
                        self.app, 'qubes-template-fedora-32', False)
                # Check error message
                self.assertTrue('Malformed --enablerepo'
                    in mock_err.getvalue())
                self.assertTrue("argument should not contain '\\n'"
                    in mock_err.getvalue())
        self.assertAllCalled()

    def test_114_qrexec_payload_disablereponewline_fail(self):
        with tempfile.NamedTemporaryFile() as repo_conf1:
            repo_str1 = \
'''[qubes-templates-itl]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl
metalink = https://yum.qubes-os.org/r$releasever/templates-itl/repodata/repomd.xml.metalink
enabled = 1
fastestmirror = 1
metadata_expire = 7d
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
'''
            repo_conf1.write(repo_str1.encode())
            repo_conf1.flush()
            args = argparse.Namespace(
                enablerepo=[],
                disablerepo=['repo\n0'],
                repoid=['repo1', 'repo2'],
                releasever='4.1',
                repo_files=[repo_conf1.name]
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                with self.assertRaises(SystemExit):
                    qubesadmin.tools.qvm_template.qrexec_payload(args,
                        self.app, 'qubes-template-fedora-32', False)
                    # Check error message
                    self.assertTrue('Malformed --disablerepo'
                        in mock_err.getvalue())
                    self.assertTrue("argument should not contain '\\n'"
                        in mock_err.getvalue())
        self.assertAllCalled()

    def test_115_qrexec_payload_repoidnewline_fail(self):
        with tempfile.NamedTemporaryFile() as repo_conf1:
            repo_str1 = \
'''[qubes-templates-itl]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl
metalink = https://yum.qubes-os.org/r$releasever/templates-itl/repodata/repomd.xml.metalink
enabled = 1
fastestmirror = 1
metadata_expire = 7d
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
'''
            repo_conf1.write(repo_str1.encode())
            repo_conf1.flush()
            args = argparse.Namespace(
                enablerepo=[],
                disablerepo=[],
                repoid=['repo\n1', 'repo2'],
                releasever='4.1',
                repo_files=[repo_conf1.name]
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                with self.assertRaises(SystemExit):
                    qubesadmin.tools.qvm_template.qrexec_payload(args,
                        self.app, 'qubes-template-fedora-32', False)
                # Check error message
                self.assertTrue('Malformed --repoid'
                    in mock_err.getvalue())
                self.assertTrue("argument should not contain '\\n'"
                    in mock_err.getvalue())
        self.assertAllCalled()

    def test_116_qrexec_payload_releasevernewline_fail(self):
        with tempfile.NamedTemporaryFile() as repo_conf1:
            repo_str1 = \
'''[qubes-templates-itl]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl
metalink = https://yum.qubes-os.org/r$releasever/templates-itl/repodata/repomd.xml.metalink
enabled = 1
fastestmirror = 1
metadata_expire = 7d
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
'''
            repo_conf1.write(repo_str1.encode())
            repo_conf1.flush()
            args = argparse.Namespace(
                enablerepo=[],
                disablerepo=[],
                repoid=['repo1', 'repo2'],
                releasever='4\n.1',
                repo_files=[repo_conf1.name]
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                with self.assertRaises(SystemExit):
                    qubesadmin.tools.qvm_template.qrexec_payload(args,
                        self.app, 'qubes-template-fedora-32', False)
                # Check error message
                self.assertTrue('Malformed --releasever'
                    in mock_err.getvalue())
                self.assertTrue("argument should not contain '\\n'"
                    in mock_err.getvalue())
        self.assertAllCalled()

    def test_117_qrexec_payload_specdash_fail(self):
        with tempfile.NamedTemporaryFile() as repo_conf1:
            repo_str1 = \
'''[qubes-templates-itl]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl
metalink = https://yum.qubes-os.org/r$releasever/templates-itl/repodata/repomd.xml.metalink
enabled = 1
fastestmirror = 1
metadata_expire = 7d
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
'''
            repo_conf1.write(repo_str1.encode())
            repo_conf1.flush()
            args = argparse.Namespace(
                enablerepo=[],
                disablerepo=[],
                repoid=['repo1', 'repo2'],
                releasever='4.1',
                repo_files=[repo_conf1.name]
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                with self.assertRaises(SystemExit):
                    qubesadmin.tools.qvm_template.qrexec_payload(args,
                        self.app, '---', False)
                # Check error message
                self.assertTrue('Malformed template name'
                    in mock_err.getvalue())
                self.assertTrue("argument should not be '---'"
                    in mock_err.getvalue())
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_120_qrexec_repoquery_success(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template\n for fedora-32\n|
qubes-template-fedora-32|1|4.2|20200201|qubes-templates-itl-testing|2048576|2020-02-23 04:56|GPLv2|https://qubes-os.org/?|Qubes template for fedora-32 v2|Qubes template\n for fedora-32 v2\n|
'''
        res = qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
            'qubes-template-fedora-32')
        self.assertEqual(res, [
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template\n for fedora-32\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '1',
                '4.2',
                '20200201',
                'qubes-templates-itl-testing',
                2048576,
                datetime.datetime(2020, 2, 23, 4, 56),
                'GPLv2',
                'https://qubes-os.org/?',
                'Qubes template for fedora-32 v2',
                'Qubes template\n for fedora-32 v2\n'
            )
        ])
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_121_qrexec_repoquery_refresh_success(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template\n for fedora-32\n|
qubes-template-fedora-32|1|4.2|20200201|qubes-templates-itl-testing|2048576|2020-02-23 04:56|GPLv2|https://qubes-os.org/?|Qubes template for fedora-32 v2|Qubes template\n for fedora-32 v2\n|
'''
        res = qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
            'qubes-template-fedora-32', True)
        self.assertEqual(res, [
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template\n for fedora-32\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '1',
                '4.2',
                '20200201',
                'qubes-templates-itl-testing',
                2048576,
                datetime.datetime(2020, 2, 23, 4, 56),
                'GPLv2',
                'https://qubes-os.org/?',
                'Qubes template for fedora-32 v2',
                'Qubes template\n for fedora-32 v2\n'
            )
        ])
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', True)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_122_qrexec_repoquery_ignorenonspec_success(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-debian-10|1|4.2|20200201|qubes-templates-itl-testing|2048576|2020-02-23 04:56|GPLv2|https://qubes-os.org/?|Qubes template for debian-10|Qubes template for debian-10\n|
qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template for fedora-32\n|
'''
        res = qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
            'qubes-template-fedora-32')
        self.assertEqual(res, [
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template for fedora-32\n'
            )
        ])
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_123_qrexec_repoquery_ignorebadname_success(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''template-fedora-32|1|4.2|20200201|qubes-templates-itl-testing|2048576|2020-02-23 04:56|GPLv2|https://qubes-os.org/?|Qubes template for fedora-32 v2|Qubes template\n for fedora-32 v2\n|
qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template for fedora-32\n|
'''
        res = qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
            'qubes-template-fedora-32')
        self.assertEqual(res, [
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template for fedora-32\n'
            )
        ])
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_124_qrexec_repoquery_searchfail_fail(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        with mock.patch('qubesadmin.tests.TestProcess.wait') \
                as mock_wait:
            mock_wait.return_value = 1
            with self.assertRaises(ConnectionError):
                qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
                    'qubes-template-fedora-32')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_125_qrexec_repoquery_extrafield_fail(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-fedora-32|1|4.2|20200201|qubes-templates-itl-testing|2048576|2020-02-23 04:56|GPLv2|https://qubes-os.org/?|Qubes template for fedora-32 v2|Extra field|Qubes template\n for fedora-32 v2\n|
qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template for fedora-32\n|
'''
        with self.assertRaisesRegex(ConnectionError,
                "unexpected data format"):
            qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
                'qubes-template-fedora-32')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_125_qrexec_repoquery_missingfield_fail(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-fedora-32|1|4.2|20200201|qubes-templates-itl-testing|2048576|2020-02-23 04:56|GPLv2|Qubes template for fedora-32 v2|Qubes template\n for fedora-32 v2\n|
qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template for fedora-32\n|
'''
        with self.assertRaisesRegex(ConnectionError,
                "unexpected data format"):
            qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
                'qubes-template-fedora-32')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_126_qrexec_repoquery_badfieldname_fail(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-fedora-(32)|1|4.2|20200201|qubes-templates-itl-testing|2048576|2020-02-23 04:56|GPLv2|https://qubes-os.org/?|Qubes template for fedora-32 v2|Qubes template\n for fedora-32 v2\n|
qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template for fedora-32\n|
'''
        with self.assertRaisesRegex(ConnectionError,
                "unexpected data format"):
            qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
                'qubes-template-fedora-32')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_126_qrexec_repoquery_badfieldepoch_fail(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-fedora-32|!1|4.2|20200201|qubes-templates-itl-testing|2048576|2020-02-23 04:56|GPLv2|https://qubes-os.org/?|Qubes template for fedora-32 v2|Qubes template\n for fedora-32 v2\n|
qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template for fedora-32\n|
'''
        with self.assertRaisesRegex(ConnectionError,
                "unexpected data format"):
            qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
                'qubes-template-fedora-32')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_126_qrexec_repoquery_badfieldreponame_fail(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-fedora-32|1|4.2|20200201|qubes-templates-itl-<testing>|2048576|2020-02-23 04:56|GPLv2|https://qubes-os.org/?|Qubes template for fedora-32 v2|Qubes template\n for fedora-32 v2\n|
qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template for fedora-32\n|
'''
        with self.assertRaisesRegex(ConnectionError,
                "unexpected data format"):
            qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
                'qubes-template-fedora-32')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_126_qrexec_repoquery_badfielddlsize_fail(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-fedora-32|1|4.2|20200201|qubes-templates-itl-testing|2048a576|2020-02-23 04:56|GPLv2|https://qubes-os.org/?|Qubes template for fedora-32 v2|Qubes template\n for fedora-32 v2\n|
qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template for fedora-32\n|
'''
        with self.assertRaisesRegex(ConnectionError,
                "unexpected data format"):
            qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
                'qubes-template-fedora-32')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_126_qrexec_repoquery_badfielddate_fail(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-fedora-32|1|4.2|20200201|qubes-templates-itl-testing|2048576|2020-02-23|GPLv2|https://qubes-os.org/?|Qubes template for fedora-32 v2|Qubes template\n for fedora-32 v2\n|
qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template for fedora-32\n|
'''
        with self.assertRaisesRegex(ConnectionError,
                "unexpected data format"):
            qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
                'qubes-template-fedora-32')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_payload')
    def test_126_qrexec_repoquery_license_fail(self, mock_payload):
        args = argparse.Namespace(updatevm='test-vm')
        mock_payload.return_value = 'str1\nstr2'
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
                ('test-vm', 'qubes.TemplateSearch')] = \
b'''qubes-template-fedora-32|1|4.2|20200201|qubes-templates-itl-testing|2048576|2020-02-23 04:56|GPLv2:)|https://qubes-os.org/?|Qubes template for fedora-32 v2|Qubes template\n for fedora-32 v2\n|
qubes-template-fedora-32|0|4.1|20200101|qubes-templates-itl|1048576|2020-01-23 04:56|GPL|https://qubes-os.org|Qubes template for fedora-32|Qubes template for fedora-32\n|
'''
        with self.assertRaisesRegex(ConnectionError,
                "unexpected data format"):
            qubesadmin.tools.qvm_template.qrexec_repoquery(args, self.app,
                'qubes-template-fedora-32')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.TemplateSearch',
                {'filter_esc': True, 'stdout': subprocess.PIPE}),
            ('test-vm', 'qubes.TemplateSearch', b'str1\nstr2')
        ])
        self.assertEqual(mock_payload.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32', False)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_130_get_dl_list_latest_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '1',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template\n for fedora-32\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '0',
                '4.2',
                '20200201',
                'qubes-templates-itl-testing',
                2048576,
                datetime.datetime(2020, 2, 23, 4, 56),
                'GPLv2',
                'https://qubes-os.org/?',
                'Qubes template for fedora-32 v2',
                'Qubes template\n for fedora-32 v2\n'
            )
        ]
        args = argparse.Namespace(
            templates=['some.local.file.rpm', 'fedora-32']
        )
        ret = qubesadmin.tools.qvm_template.get_dl_list(args, self.app)
        self.assertEqual(ret, {
            'fedora-32': qubesadmin.tools.qvm_template.DlEntry(
                ('1', '4.1', '20200101'), 'qubes-templates-itl', 1048576)
        })
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_131_get_dl_list_latest_notfound_fail(self, mock_query):
        mock_query.return_value = []
        args = argparse.Namespace(
            templates=['some.local.file.rpm', 'fedora-31']
        )
        with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.get_dl_list(args, self.app)
            self.assertTrue('not found' in mock_err.getvalue())
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-31')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_132_get_dl_list_multimerge0_success(self, mock_query):
        counter = 0
        def f(*args):
            nonlocal counter
            counter += 1
            if counter == 1:
                return [
                    qubesadmin.tools.qvm_template.Template(
                        'fedora-32',
                        '0',
                        '4.2',
                        '20200201',
                        'qubes-templates-itl-testing',
                        2048576,
                        datetime.datetime(2020, 2, 23, 4, 56),
                        'GPLv2',
                        'https://qubes-os.org/?',
                        'Qubes template for fedora-32 v2',
                        'Qubes template\n for fedora-32 v2\n'
                    )
                ]
            return [
                qubesadmin.tools.qvm_template.Template(
                    'fedora-32',
                    '1',
                    '4.1',
                    '20200101',
                    'qubes-templates-itl',
                    1048576,
                    datetime.datetime(2020, 1, 23, 4, 56),
                    'GPL',
                    'https://qubes-os.org',
                    'Qubes template for fedora-32',
                    'Qubes template\n for fedora-32\n'
                )
            ]
        mock_query.side_effect = f
        args = argparse.Namespace(
            templates=['some.local.file.rpm', 'fedora-32:0', 'fedora-32:1']
        )
        ret = qubesadmin.tools.qvm_template.get_dl_list(args, self.app)
        self.assertEqual(ret, {
            'fedora-32': qubesadmin.tools.qvm_template.DlEntry(
                ('1', '4.1', '20200101'), 'qubes-templates-itl', 1048576)
        })
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32:0'),
            mock.call(args, self.app, 'qubes-template-fedora-32:1')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_132_get_dl_list_multimerge1_success(self, mock_query):
        counter = 0
        def f(*args):
            nonlocal counter
            counter += 1
            if counter == 1:
                return [
                    qubesadmin.tools.qvm_template.Template(
                        'fedora-32',
                        '2',
                        '4.2',
                        '20200201',
                        'qubes-templates-itl-testing',
                        2048576,
                        datetime.datetime(2020, 2, 23, 4, 56),
                        'GPLv2',
                        'https://qubes-os.org/?',
                        'Qubes template for fedora-32 v2',
                        'Qubes template\n for fedora-32 v2\n'
                    )
                ]
            return [
                qubesadmin.tools.qvm_template.Template(
                    'fedora-32',
                    '1',
                    '4.1',
                    '20200101',
                    'qubes-templates-itl',
                    1048576,
                    datetime.datetime(2020, 1, 23, 4, 56),
                    'GPL',
                    'https://qubes-os.org',
                    'Qubes template for fedora-32',
                    'Qubes template\n for fedora-32\n'
                )
            ]
        mock_query.side_effect = f
        args = argparse.Namespace(
            templates=['some.local.file.rpm', 'fedora-32:2', 'fedora-32:1']
        )
        ret = qubesadmin.tools.qvm_template.get_dl_list(args, self.app)
        self.assertEqual(ret, {
            'fedora-32': qubesadmin.tools.qvm_template.DlEntry(
                ('2', '4.2', '20200201'),
                'qubes-templates-itl-testing',
                2048576)
        })
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-fedora-32:2'),
            mock.call(args, self.app, 'qubes-template-fedora-32:1')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_133_get_dl_list_reinstall_success(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-name',
            None)] = b'0\0test-vm'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-epoch',
            None)] = b'0\x000'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-version',
            None)] = b'0\x004.2'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-release',
            None)] = b'0\x0020200201'
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '1',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.2',
                '20200201',
                'qubes-templates-itl-testing',
                2048576,
                datetime.datetime(2020, 2, 23, 4, 56),
                'GPLv2',
                'https://qubes-os.org/?',
                'Qubes template for test-vm v2',
                'Qubes template\n for test-vm v2\n'
            )
        ]
        args = argparse.Namespace(
            templates=['some.local.file.rpm', 'test-vm']
        )
        ret = qubesadmin.tools.qvm_template.get_dl_list(args, self.app,
            qubesadmin.tools.qvm_template.VersionSelector.REINSTALL)
        self.assertEqual(ret, {
            'test-vm': qubesadmin.tools.qvm_template.DlEntry(
                ('0', '4.2', '20200201'),
                'qubes-templates-itl-testing',
                2048576
            )
        })
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-test-vm')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_134_get_dl_list_reinstall_nolocal_fail(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00'
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '1',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.2',
                '20200201',
                'qubes-templates-itl-testing',
                2048576,
                datetime.datetime(2020, 2, 23, 4, 56),
                'GPLv2',
                'https://qubes-os.org/?',
                'Qubes template for test-vm v2',
                'Qubes template\n for test-vm v2\n'
            )
        ]
        args = argparse.Namespace(templates=['test-vm'])
        with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.get_dl_list(args, self.app,
                    qubesadmin.tools.qvm_template.VersionSelector.REINSTALL)
            self.assertTrue('not already installed' in mock_err.getvalue())
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-test-vm')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_135_get_dl_list_reinstall_nonmanaged_fail(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '1',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.2',
                '20200201',
                'qubes-templates-itl-testing',
                2048576,
                datetime.datetime(2020, 2, 23, 4, 56),
                'GPLv2',
                'https://qubes-os.org/?',
                'Qubes template for test-vm v2',
                'Qubes template\n for test-vm v2\n'
            )
        ]
        args = argparse.Namespace(templates=['test-vm'])
        def qubesd_call(dest, method,
                arg=None, payload=None, payload_stream=None,
                orig_func=self.app.qubesd_call):
            if method == 'admin.vm.feature.Get':
                raise KeyError
            return orig_func(dest, method, arg, payload, payload_stream)
        with mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                mock.patch.object(self.app, 'qubesd_call') as mock_call:
            mock_call.side_effect = qubesd_call
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.get_dl_list(args, self.app,
                    qubesadmin.tools.qvm_template.VersionSelector.REINSTALL)
            self.assertTrue('not managed' in mock_err.getvalue())
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-test-vm')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_135_get_dl_list_reinstall_nonmanagednoname_fail(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-name',
            None)] = b'0\0test-vm-2'
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '1',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.2',
                '20200201',
                'qubes-templates-itl-testing',
                2048576,
                datetime.datetime(2020, 2, 23, 4, 56),
                'GPLv2',
                'https://qubes-os.org/?',
                'Qubes template for test-vm v2',
                'Qubes template\n for test-vm v2\n'
            )
        ]
        args = argparse.Namespace(templates=['test-vm'])
        with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.get_dl_list(args, self.app,
                    qubesadmin.tools.qvm_template.VersionSelector.REINSTALL)
            self.assertTrue('not managed' in mock_err.getvalue())
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-test-vm')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_136_get_dl_list_downgrade_success(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-name',
            None)] = b'0\0test-vm'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-epoch',
            None)] = b'0\x000'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-version',
            None)] = b'0\x004.3'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-release',
            None)] = b'0\x0020200201'
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.2',
                '20200201',
                'qubes-templates-itl-testing',
                2048576,
                datetime.datetime(2020, 2, 23, 4, 56),
                'GPLv2',
                'https://qubes-os.org/?',
                'Qubes template for test-vm v2',
                'Qubes template\n for test-vm v2\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '1',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            )
        ]
        args = argparse.Namespace(templates=['test-vm'])
        ret = qubesadmin.tools.qvm_template.get_dl_list(args, self.app,
            qubesadmin.tools.qvm_template.VersionSelector.LATEST_LOWER)
        self.assertEqual(ret, {
            'test-vm': qubesadmin.tools.qvm_template.DlEntry(
                ('0', '4.2', '20200201'),
                'qubes-templates-itl-testing',
                2048576
            )
        })
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-test-vm')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_137_get_dl_list_downgrade_nonmanaged_fail(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-name',
            None)] = b'0\0test-vm-2'
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.2',
                '20200201',
                'qubes-templates-itl-testing',
                2048576,
                datetime.datetime(2020, 2, 23, 4, 56),
                'GPLv2',
                'https://qubes-os.org/?',
                'Qubes template for test-vm v2',
                'Qubes template\n for test-vm v2\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '1',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            )
        ]
        args = argparse.Namespace(templates=['test-vm'])
        with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.get_dl_list(args, self.app,
                    qubesadmin.tools.qvm_template.VersionSelector.REINSTALL)
            self.assertTrue('not managed' in mock_err.getvalue())
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-test-vm')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_138_get_dl_list_downgrade_notfound_skip(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-name',
            None)] = b'0\0test-vm'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-epoch',
            None)] = b'0\x000'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-version',
            None)] = b'0\x004.3'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-release',
            None)] = b'0\x0020200201'
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '1',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            )
        ]
        args = argparse.Namespace(templates=['test-vm'])
        with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            ret = qubesadmin.tools.qvm_template.get_dl_list(args, self.app,
                qubesadmin.tools.qvm_template.VersionSelector.LATEST_LOWER)
            self.assertTrue('lowest version' in mock_err.getvalue())
        self.assertEqual(ret, {})
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-test-vm')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_139_get_dl_list_upgrade_success(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-name',
            None)] = b'0\0test-vm'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-epoch',
            None)] = b'0\x000'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-version',
            None)] = b'0\x004.3'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-release',
            None)] = b'0\x0020200201'
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '1',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            )
        ]
        args = argparse.Namespace(templates=['test-vm'])
        ret = qubesadmin.tools.qvm_template.get_dl_list(args, self.app,
            qubesadmin.tools.qvm_template.VersionSelector.LATEST_HIGHER)
        self.assertEqual(ret, {
            'test-vm': qubesadmin.tools.qvm_template.DlEntry(
                ('1', '4.1', '20200101'), 'qubes-templates-itl', 1048576
            )
        })
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-test-vm')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_140_get_dl_list_downgrade_notfound_skip(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-name',
            None)] = b'0\0test-vm'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-epoch',
            None)] = b'0\x000'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-version',
            None)] = b'0\x004.3'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-release',
            None)] = b'0\x0020200201'
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            )
        ]
        args = argparse.Namespace(templates=['test-vm'])
        with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            ret = qubesadmin.tools.qvm_template.get_dl_list(args, self.app,
                qubesadmin.tools.qvm_template.VersionSelector.LATEST_HIGHER)
            self.assertTrue('highest version' in mock_err.getvalue())
        self.assertEqual(ret, {})
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-test-vm')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_141_get_dl_list_reinstall_notfound_fail(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-name',
            None)] = b'0\0test-vm'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-epoch',
            None)] = b'0\x000'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-version',
            None)] = b'0\x004.3'
        self.app.expected_calls[(
            'test-vm',
            'admin.vm.feature.Get',
            f'template-release',
            None)] = b'0\x0020200201'
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for test-vm\n'
            )
        ]
        args = argparse.Namespace(templates=['test-vm'])
        with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.get_dl_list(args, self.app,
                    qubesadmin.tools.qvm_template.VersionSelector.REINSTALL)
            self.assertTrue('Same version' in mock_err.getvalue())
            self.assertTrue('not found' in mock_err.getvalue())
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'qubes-template-test-vm')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_150_list_templates_installed_success(self, mock_query):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n' \
            b'test-vm-2 class=TemplateVM state=Halted\n' \
            b'non-spec class=TemplateVM state=Halted\n'
        build_time = '2020-09-01 14:30:00' # 1598970600
        install_time = '2020-09-01 15:30:00'
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '2'),
                ('version', '4.1'),
                ('release', '2020'),
                ('reponame', '@commandline'),
                ('buildtime', build_time),
                ('installtime', install_time),
                ('license', 'GPL'),
                ('url', 'https://qubes-os.org'),
                ('summary', 'Summary'),
                ('description', 'Desc|desc')]:
            self.app.expected_calls[(
                'test-vm',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [('name', 'test-vm-2-not-managed')]:
            self.app.expected_calls[(
                'test-vm-2',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [
                ('name', 'non-spec'),
                ('epoch', '0'),
                ('version', '4.3'),
                ('release', '20200201')]:
            self.app.expected_calls[(
                'non-spec',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        args = argparse.Namespace(
            all=False,
            installed=True,
            available=False,
            extras=False,
            upgrades=False,
            machine_readable=False,
            machine_readable_json=False,
            templates=['test-vm*']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out, \
                mock.patch.object(self.app.domains['test-vm'],
                    'get_disk_utilization') as mock_disk:
            mock_disk.return_value = 1234321
            qubesadmin.tools.qvm_template.list_templates(
                args, self.app, 'list')
            self.assertEqual(mock_out.getvalue(),
'''Installed Templates
[('test-vm', '2:4.1-2020', '@commandline')]
''')
            self.assertEqual(mock_disk.mock_calls, [mock.call()])
        self.assertEqual(mock_query.mock_calls, [])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_151_list_templates_available_success(self, mock_query):
        counter = 0
        def f(*args):
            nonlocal counter
            counter += 1
            if counter == 1:
                return [
                    qubesadmin.tools.qvm_template.Template(
                        'fedora-32',
                        '0',
                        '4.2',
                        '20200201',
                        'qubes-templates-itl-testing',
                        2048576,
                        datetime.datetime(2020, 2, 23, 4, 56),
                        'GPLv2',
                        'https://qubes-os.org/?',
                        'Qubes template for fedora-32 v2',
                        'Qubes template\n for fedora-32 v2\n'
                    )
                ]
            return [
                qubesadmin.tools.qvm_template.Template(
                    'fedora-31',
                    '1',
                    '4.1',
                    '20200101',
                    'qubes-templates-itl',
                    1048576,
                    datetime.datetime(2020, 1, 23, 4, 56),
                    'GPL',
                    'https://qubes-os.org',
                    'Qubes template for fedora-31',
                    'Qubes template\n for fedora-31\n'
                )
            ]
        mock_query.side_effect = f
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=True,
            extras=False,
            upgrades=False,
            machine_readable=False,
            machine_readable_json=False,
            templates=['fedora-32', 'fedora-31']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out:
            qubesadmin.tools.qvm_template.list_templates(
                args, self.app, 'list')
            # Order not determinstic because of sets
            expected = [
                ('fedora-31', '1:4.1-20200101', 'qubes-templates-itl'),
                ('fedora-32', '0:4.2-20200201', 'qubes-templates-itl-testing')
            ]
            self.assertTrue(mock_out.getvalue() == \
f'''Available Templates
{str([expected[1], expected[0]])}
''' \
                    or mock_out.getvalue() == \
f'''Available Templates
{str([expected[0], expected[1]])}
''')
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'fedora-32'),
            mock.call(args, self.app, 'fedora-31')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_151_list_templates_available_all_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'fedora-31',
                '1',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            )
        ]
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=True,
            extras=False,
            upgrades=False,
            machine_readable=False,
            machine_readable_json=False,
            templates=[]
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out:
            qubesadmin.tools.qvm_template.list_templates(
                args, self.app, 'list')
            self.assertEqual(mock_out.getvalue(),
'''Available Templates
[('fedora-31', '1:4.1-20200101', 'qubes-templates-itl')]
''')
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_152_list_templates_extras_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n' \
            b'test-vm-2 class=TemplateVM state=Halted\n' \
            b'test-vm-3 class=TemplateVM state=Halted\n' \
            b'non-spec class=TemplateVM state=Halted\n'
        for key, val in [('name', 'test-vm')]:
            self.app.expected_calls[(
                'test-vm',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [
                ('name', 'test-vm-2'),
                ('epoch', '1'),
                ('version', '4.0'),
                ('release', '2019'),
                ('reponame', 'qubes-template-itl'),
                ('buildtime', '2020-09-02 14:30:00'),
                ('installtime', '2020-09-02 15:30:00'),
                ('license', 'GPLv2'),
                ('url', 'https://qubes-os.org/?'),
                ('summary', 'Summary2'),
                ('description', 'Desc|desc|2')]:
            self.app.expected_calls[(
                'test-vm-2',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [('name', 'test-vm-3-non-managed')]:
            self.app.expected_calls[(
                'test-vm-3',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [
                ('name', 'non-spec'),
                ('epoch', '1'),
                ('version', '4.0'),
                ('release', '2019')]:
            self.app.expected_calls[(
                'non-spec',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=False,
            extras=True,
            upgrades=False,
            machine_readable=False,
            machine_readable_json=False,
            templates=['test-vm*']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out, \
                mock.patch.object(self.app.domains['test-vm-2'],
                    'get_disk_utilization') as mock_disk:
            mock_disk.return_value = 1234321
            qubesadmin.tools.qvm_template.list_templates(
                args, self.app, 'list')
            self.assertEqual(mock_out.getvalue(),
'''Extra Templates
[('test-vm-2', '1:4.0-2019', 'qubes-template-itl')]
''')
            self.assertEqual(mock_disk.mock_calls, [mock.call()])
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'test-vm*')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_153_list_templates_upgrades_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm-3',
                '0',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n' \
            b'test-vm-2 class=TemplateVM state=Halted\n' \
            b'test-vm-3 class=TemplateVM state=Halted\n'
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '1'),
                ('version', '4.0'),
                ('release', '2019')]:
            self.app.expected_calls[(
                'test-vm',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [
                ('name', 'test-vm-2'),
                ('epoch', '1'),
                ('version', '4.0'),
                ('release', '2019')]:
            self.app.expected_calls[(
                'test-vm-2',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [('name', 'test-vm-3-non-managed')]:
            self.app.expected_calls[(
                'test-vm-3',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=False,
            extras=False,
            upgrades=True,
            machine_readable=False,
            machine_readable_json=False,
            templates=['test-vm*']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out, \
                mock.patch.object(self.app.domains['test-vm-2'],
                    'get_disk_utilization') as mock_disk:
            mock_disk.return_value = 1234321
            qubesadmin.tools.qvm_template.list_templates(
                args, self.app, 'list')
            self.assertEqual(mock_out.getvalue(),
'''Available Upgrades
[('test-vm', '2:4.1-2020', 'qubes-templates-itl')]
''')
            self.assertEqual(mock_disk.mock_calls, [])
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'test-vm*')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def __test_list_templates_all_success(self, operation,
            args, expected, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm-2 class=TemplateVM state=Halted\n'
        for key, val in [
                ('name', 'test-vm-2'),
                ('epoch', '1'),
                ('version', '4.0'),
                ('release', '2019'),
                ('reponame', '@commandline'),
                ('buildtime', '2020-09-02 14:30:00'),
                ('installtime', '2020-09-02 15:30:00'),
                ('license', 'GPL'),
                ('url', 'https://qubes-os.org'),
                ('summary', 'Summary'),
                ('description', 'Desc|desc')]:
            self.app.expected_calls[(
                'test-vm-2',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out, \
                mock.patch.object(self.app.domains['test-vm-2'],
                    'get_disk_utilization') as mock_disk:
            mock_disk.return_value = 1234321
            qubesadmin.tools.qvm_template.list_templates(
                args, self.app, operation)
            self.assertEqual(mock_out.getvalue(), expected)
            self.assertEqual(mock_disk.mock_calls, [mock.call()])
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app, 'test-vm*')
        ])
        self.assertAllCalled()

    def test_154_list_templates_all_success(self):
        args = argparse.Namespace(
            all=True,
            installed=False,
            available=False,
            extras=False,
            upgrades=False,
            machine_readable=False,
            machine_readable_json=False,
            templates=['test-vm*']
        )
        expected = \
'''Installed Templates
[('test-vm-2', '1:4.0-2019', '@commandline')]
Available Templates
[('test-vm', '2:4.1-2020', 'qubes-templates-itl')]
'''
        self.__test_list_templates_all_success('list', args, expected)

    def test_155_list_templates_all_implicit_success(self):
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=False,
            extras=False,
            upgrades=False,
            machine_readable=False,
            machine_readable_json=False,
            templates=['test-vm*']
        )
        expected = \
'''Installed Templates
[('test-vm-2', '1:4.0-2019', '@commandline')]
Available Templates
[('test-vm', '2:4.1-2020', 'qubes-templates-itl')]
'''
        self.__test_list_templates_all_success('list', args, expected)

    def test_156_list_templates_info_all_success(self):
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=False,
            extras=False,
            upgrades=False,
            machine_readable=False,
            machine_readable_json=False,
            templates=['test-vm*']
        )
        expected = \
'''Installed Templates
[('Name', ':', 'test-vm-2'), ('Epoch', ':', '1'), ('Version', ':', '4.0'), ('Release', ':', '2019'), ('Size', ':', '1.2 MiB'), ('Repository', ':', '@commandline'), ('Buildtime', ':', '2020-09-02 14:30:00'), ('Install time', ':', '2020-09-02 15:30:00'), ('URL', ':', 'https://qubes-os.org'), ('License', ':', 'GPL'), ('Summary', ':', 'Summary'), ('Description', ':', 'Desc'), ('', ':', 'desc'), (' ', ' ', ' ')]
Available Templates
[('Name', ':', 'test-vm'), ('Epoch', ':', '2'), ('Version', ':', '4.1'), ('Release', ':', '2020'), ('Size', ':', '1.0 MiB'), ('Repository', ':', 'qubes-templates-itl'), ('Buildtime', ':', '2020-09-01 14:30:00+00:00'), ('URL', ':', 'https://qubes-os.org'), ('License', ':', 'GPL'), ('Summary', ':', 'Qubes template for fedora-31'), ('Description', ':', 'Qubes template'), ('', ':', ' for fedora-31'), (' ', ' ', ' ')]
'''
        self.__test_list_templates_all_success('info', args, expected)

    def test_157_list_templates_list_all_machinereadable_success(self):
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=False,
            extras=False,
            upgrades=False,
            machine_readable=True,
            machine_readable_json=False,
            templates=['test-vm*']
        )
        expected = \
'''installed|test-vm-2|1:4.0-2019|@commandline
available|test-vm|2:4.1-2020|qubes-templates-itl
'''
        self.__test_list_templates_all_success('list', args, expected)

    def test_158_list_templates_info_all_machinereadable_success(self):
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=False,
            extras=False,
            upgrades=False,
            machine_readable=True,
            machine_readable_json=False,
            templates=['test-vm*']
        )
        expected = \
'''installed|test-vm-2|1|4.0|2019|@commandline|1234321|2020-09-02 14:30:00|2020-09-02 15:30:00|GPL|https://qubes-os.org|Summary|Desc|desc
available|test-vm|2|4.1|2020|qubes-templates-itl|1048576|2020-09-01 14:30:00||GPL|https://qubes-os.org|Qubes template for fedora-31|Qubes template| for fedora-31|
'''
        self.__test_list_templates_all_success('info', args, expected)

    def test_159_list_templates_list_all_machinereadablejson_success(self):
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=False,
            extras=False,
            upgrades=False,
            machine_readable=False,
            machine_readable_json=True,
            templates=['test-vm*']
        )
        expected = \
'''{"installed": [{"name": "test-vm-2", "evr": "1:4.0-2019", "reponame": "@commandline"}], "available": [{"name": "test-vm", "evr": "2:4.1-2020", "reponame": "qubes-templates-itl"}]}
'''
        self.__test_list_templates_all_success('list', args, expected)

    def test_160_list_templates_info_all_machinereadablejson_success(self):
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=False,
            extras=False,
            upgrades=False,
            machine_readable=False,
            machine_readable_json=True,
            templates=['test-vm*']
        )
        expected = \
r'''{"installed": [{"name": "test-vm-2", "epoch": "1", "version": "4.0", "release": "2019", "reponame": "@commandline", "size": "1234321", "buildtime": "2020-09-02 14:30:00", "installtime": "2020-09-02 15:30:00", "license": "GPL", "url": "https://qubes-os.org", "summary": "Summary", "description": "Desc\ndesc"}], "available": [{"name": "test-vm", "epoch": "2", "version": "4.1", "release": "2020", "reponame": "qubes-templates-itl", "size": "1048576", "buildtime": "2020-09-01 14:30:00", "installtime": "", "license": "GPL", "url": "https://qubes-os.org", "summary": "Qubes template for fedora-31", "description": "Qubes template\n for fedora-31\n"}]}
'''
        self.__test_list_templates_all_success('info', args, expected)

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_161_list_templates_noresults_fail(self, mock_query):
        mock_query.return_value = []
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=True,
            extras=False,
            upgrades=False,
            machine_readable=False,
            machine_readable_json=False,
            templates=[]
        )
        with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.list_templates(
                    args, self.app, 'list')
            self.assertTrue('No matching templates' in mock_err.getvalue())
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_170_search_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '0',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Older Qubes template for fedora-31',
                'Older Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'should-not-match-3',
                '0',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org/test-vm',
                'Qubes template for fedora-31',
                'test-vm Qubes template\n for fedora-31\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm-2 class=TemplateVM state=Halted\n'
        for key, val in [
                ('name', 'test-vm-2'),
                ('epoch', '1'),
                ('version', '4.0'),
                ('release', '2019'),
                ('reponame', '@commandline'),
                ('buildtime', '2020-09-02 14:30:00'),
                ('license', 'GPL'),
                ('url', 'https://qubes-os.org'),
                ('summary', 'Summary'),
                ('description', 'Desc|desc')]:
            self.app.expected_calls[(
                'test-vm-2',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        args = argparse.Namespace(
            all=False,
            templates=['test-vm']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out, \
                mock.patch.object(self.app.domains['test-vm-2'],
                    'get_disk_utilization') as mock_disk:
            mock_disk.return_value = 1234321
            qubesadmin.tools.qvm_template.search(args, self.app)
            self.assertEqual(mock_out.getvalue(),
'''=== Name Exactly Matched: test-vm ===
test-vm : Qubes template for fedora-31
=== Name Matched: test-vm ===
test-vm-2 : Summary
''')
            self.assertEqual(mock_disk.mock_calls, [mock.call()])
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_171_search_summary_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-template',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm :)',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-template-exact',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'test-vm',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm-2',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for test-vm-2',
                'Qubes template\n for fedora-31\n'
            ),
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00'
        args = argparse.Namespace(
            all=False,
            templates=['test-vm']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out:
            qubesadmin.tools.qvm_template.search(args, self.app)
            self.assertEqual(mock_out.getvalue(),
'''=== Name & Summary Matched: test-vm ===
test-vm : Qubes template for test-vm
test-vm-2 : Qubes template for test-vm-2
=== Summary Matched: test-vm ===
test-template : Qubes template for test-vm :)
=== Summary Exactly Matched: test-vm ===
test-template-exact : test-vm
''')
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_172_search_namesummaryexact_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-template-exact',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'test-vm',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'test-vm',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm-2',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'test-vm',
                'Qubes template\n for fedora-31\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00'
        args = argparse.Namespace(
            all=False,
            templates=['test-vm']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out:
            qubesadmin.tools.qvm_template.search(args, self.app)
            self.assertEqual(mock_out.getvalue(),
'''=== Name & Summary Exactly Matched: test-vm ===
test-vm : test-vm
=== Name & Summary Matched: test-vm ===
test-vm-2 : test-vm
=== Summary Exactly Matched: test-vm ===
test-template-exact : test-vm
''')
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_173_search_multiquery_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-template-exact',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'test-vm',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'test-vm',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'should-not-match',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Summary',
                'test-vm Qubes template\n for fedora-31\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00'
        args = argparse.Namespace(
            all=False,
            templates=['test-vm', 'test-template']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out:
            qubesadmin.tools.qvm_template.search(args, self.app)
            self.assertEqual(mock_out.getvalue(),
'''=== Name & Summary Matched: test-template, test-vm ===
test-template-exact : test-vm
''')
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_174_search_multiquery_exact_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'summary',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'summary',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'test-vm Summary',
                'Qubes template\n for fedora-31\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00'
        args = argparse.Namespace(
            all=False,
            templates=['test-vm', 'summary']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out:
            qubesadmin.tools.qvm_template.search(args, self.app)
            self.assertEqual(mock_out.getvalue(),
'''=== Name & Summary Matched: summary, test-vm ===
summary : test-vm Summary
=== Name & Summary Exactly Matched: summary, test-vm ===
test-vm : summary
''')
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_175_search_all_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org/keyword-url',
                'summary',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm-exact',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'test-vm Summary',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm-exac2',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'test-vm-exac2',
                'test-vm Summary',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'test-vm-2',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'test-vm Summary',
                'keyword-desc'
            ),
            qubesadmin.tools.qvm_template.Template(
                'should-not-match',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Summary',
                'Description'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00'
        args = argparse.Namespace(
            all=True,
            templates=['test-vm-exact', 'test-vm-exac2',
                'keyword-url', 'keyword-desc']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out:
            qubesadmin.tools.qvm_template.search(args, self.app)
            self.assertEqual(mock_out.getvalue(),
'''=== Name & URL Exactly Matched: test-vm-exac2 ===
test-vm-exac2 : test-vm Summary
=== Name Exactly Matched: test-vm-exact ===
test-vm-exact : test-vm Summary
=== Description Exactly Matched: keyword-desc ===
test-vm-2 : test-vm Summary
=== URL Matched: keyword-url ===
test-vm : summary
''')
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_176_search_wildcard_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'test-vm',
                '2',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'should-not-match-3',
                '0',
                '4.1',
                '2020',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 9, 1, 14, 30,
                    tzinfo=datetime.timezone.utc),
                'GPL',
                'https://qubes-os.org/test-vm',
                'Qubes template for fedora-31',
                'test-vm Qubes template\n for fedora-31\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00'
        args = argparse.Namespace(
            all=False,
            templates=['t?st-vm']
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out:
            qubesadmin.tools.qvm_template.search(args, self.app)
            self.assertEqual(mock_out.getvalue(),
'''=== Name Matched: t?st-vm ===
test-vm : Qubes template for fedora-31
''')
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_180_download_success(self, mock_qrexec, mock_dllist):
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=1
            )
            qubesadmin.tools.qvm_template.download(args, self.app, dir, {
                    'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                        ('1', '2', '3'), 'qubes-templates-itl', 1048576),
                    'fedora-32': qubesadmin.tools.qvm_template.DlEntry(
                        ('0', '1', '2'),
                        'qubes-templates-itl-testing',
                        2048576)
                }, '.unverified')
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    dir + '/qubes-template-fedora-31-1:2-3.rpm.unverified',
                    1048576),
                mock.call(args, self.app, 'qubes-template-fedora-32-0:1-2',
                    dir + '/qubes-template-fedora-32-0:1-2.rpm.unverified',
                    2048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])
            self.assertTrue(all(
                [x.endswith('.unverified') for x in os.listdir(dir)]))

    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_181_download_success_nosuffix(self, mock_qrexec, mock_dllist):
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=1,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                qubesadmin.tools.qvm_template.download(args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                    })
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    dir + '/qubes-template-fedora-31-1:2-3.rpm',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])

    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_182_download_success_getdllist(self, mock_qrexec, mock_dllist):
        mock_dllist.return_value = {
            'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                ('1', '2', '3'), 'qubes-templates-itl', 1048576)
        }
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=1
            )
            qubesadmin.tools.qvm_template.download(args, self.app,
                dir, None, '.unverified',
                qubesadmin.tools.qvm_template.VersionSelector.LATEST_LOWER)
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    dir + '/qubes-template-fedora-31-1:2-3.rpm.unverified',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [
                mock.call(args, self.app,
                    version_selector=\
                        qubesadmin.tools.qvm_template.\
                        VersionSelector.LATEST_LOWER)
            ])
            self.assertTrue(all(
                [x.endswith('.unverified') for x in os.listdir(dir)]))

    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_183_download_success_downloaddir(self, mock_qrexec, mock_dllist):
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=1,
                downloaddir=dir
            )
            qubesadmin.tools.qvm_template.download(args, self.app, None, {
                    'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                        ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                }, '.unverified')
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    dir + '/qubes-template-fedora-31-1:2-3.rpm.unverified',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])
            self.assertTrue(all(
                [x.endswith('.unverified') for x in os.listdir(dir)]))

    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_184_download_success_exists(self, mock_qrexec, mock_dllist):
        with tempfile.TemporaryDirectory() as dir:
            with open(os.path.join(
                        dir, 'qubes-template-fedora-31-1:2-3.rpm.unverified'),
                    'w') as _:
                pass
            args = argparse.Namespace(
                retries=1,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                qubesadmin.tools.qvm_template.download(args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576),
                        'fedora-32': qubesadmin.tools.qvm_template.DlEntry(
                            ('0', '1', '2'),
                            'qubes-templates-itl-testing',
                            2048576)
                    }, '.unverified')
                self.assertTrue('already exists, skipping'
                    in mock_err.getvalue())
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-32-0:1-2',
                    dir + '/qubes-template-fedora-32-0:1-2.rpm.unverified',
                    2048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])
            self.assertTrue(all(
                [x.endswith('.unverified') for x in os.listdir(dir)]))

    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_185_download_success_existsmove(self, mock_qrexec, mock_dllist):
        with tempfile.TemporaryDirectory() as dir:
            with open(os.path.join(
                        dir, 'qubes-template-fedora-31-1:2-3.rpm'),
                    'w') as _:
                pass
            args = argparse.Namespace(
                retries=1,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                qubesadmin.tools.qvm_template.download(args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                    }, '.unverified')
                self.assertTrue('already exists, skipping'
                    in mock_err.getvalue())
            self.assertEqual(mock_qrexec.mock_calls, [])
            self.assertEqual(mock_dllist.mock_calls, [])
            self.assertTrue(os.path.exists(
                dir + '/qubes-template-fedora-31-1:2-3.rpm.unverified'))
            self.assertTrue(all(
                [x.endswith('.unverified') for x in os.listdir(dir)]))

    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_186_download_success_existsnosuffix(self, mock_qrexec, mock_dllist):
        with tempfile.TemporaryDirectory() as dir:
            with open(os.path.join(
                        dir, 'qubes-template-fedora-31-1:2-3.rpm'),
                    'w') as _:
                pass
            args = argparse.Namespace(
                retries=1,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                qubesadmin.tools.qvm_template.download(args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                    })
                self.assertTrue('already exists, skipping'
                    in mock_err.getvalue())
            self.assertEqual(mock_qrexec.mock_calls, [])
            self.assertEqual(mock_dllist.mock_calls, [])
            self.assertTrue(os.path.exists(
                dir + '/qubes-template-fedora-31-1:2-3.rpm'))

    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_187_download_success_retry(self, mock_qrexec, mock_dllist):
        counter = 0
        def f(*args):
            nonlocal counter
            counter += 1
            if counter == 1:
                raise ConnectionError
        mock_qrexec.side_effect = f
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=2,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                    mock.patch('os.remove') as mock_rm:
                qubesadmin.tools.qvm_template.download(args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                    })
                self.assertTrue('retrying...' in mock_err.getvalue())
                self.assertEqual(mock_rm.mock_calls, [
                    mock.call(dir + '/qubes-template-fedora-31-1:2-3.rpm')
                ])
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    dir + '/qubes-template-fedora-31-1:2-3.rpm',
                    1048576),
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    dir + '/qubes-template-fedora-31-1:2-3.rpm',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])

    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_188_download_fail_retry(self, mock_qrexec, mock_dllist):
        counter = 0
        def f(*args):
            nonlocal counter
            counter += 1
            if counter <= 3:
                raise ConnectionError
        mock_qrexec.side_effect = f
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=3,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                    mock.patch('os.remove') as mock_rm:
                with self.assertRaises(SystemExit):
                    qubesadmin.tools.qvm_template.download(
                        args, self.app, None, {
                            'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                                ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                        })
                self.assertEqual(mock_err.getvalue().count('retrying...'), 2)
                self.assertTrue('download failed' in mock_err.getvalue())
                self.assertEqual(mock_rm.mock_calls, [
                    mock.call(dir + '/qubes-template-fedora-31-1:2-3.rpm'),
                    mock.call(dir + '/qubes-template-fedora-31-1:2-3.rpm'),
                    mock.call(dir + '/qubes-template-fedora-31-1:2-3.rpm')
                ])
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    dir + '/qubes-template-fedora-31-1:2-3.rpm',
                    1048576),
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    dir + '/qubes-template-fedora-31-1:2-3.rpm',
                    1048576),
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    dir + '/qubes-template-fedora-31-1:2-3.rpm',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])

    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_189_download_fail_interrupt(self, mock_qrexec, mock_dllist):
        def f(*args):
            raise RuntimeError
        mock_qrexec.side_effect = f
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=3,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                    mock.patch('os.remove') as mock_rm:
                with self.assertRaises(RuntimeError):
                    qubesadmin.tools.qvm_template.download(
                        args, self.app, None, {
                            'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                                ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                        })
                self.assertEqual(mock_rm.mock_calls, [
                    mock.call(dir + '/qubes-template-fedora-31-1:2-3.rpm')
                ])
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    dir + '/qubes-template-fedora-31-1:2-3.rpm',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])
