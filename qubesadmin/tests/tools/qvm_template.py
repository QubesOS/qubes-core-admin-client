from unittest import mock
import argparse
import asyncio
import datetime
import io
import os
import pathlib
import subprocess
import tempfile

import rpm

import qubesadmin.tests
import qubesadmin.tools.qvm_template

class TC_00_qvm_template(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_000_verify_rpm_success(self):
        ts = mock.MagicMock()
        # Just return a dict instead of rpm.hdr
        hdr = {
            rpm.RPMTAG_SIGPGP: 'xxx', # non-empty
            rpm.RPMTAG_SIGGPG: 'xxx', # non-empty
        }
        ts.hdrFromFdno.return_value = hdr
        ret = qubesadmin.tools.qvm_template.verify_rpm('/dev/null', ts)
        ts.hdrFromFdno.assert_called_once()
        self.assertEqual(hdr, ret)
        self.assertAllCalled()

    def test_001_verify_rpm_nosig_fail(self):
        ts = mock.MagicMock()
        # Just return a dict instead of rpm.hdr
        hdr = {
            rpm.RPMTAG_SIGPGP: None, # empty
            rpm.RPMTAG_SIGGPG: None, # empty
        }
        ts.hdrFromFdno.return_value = hdr
        ret = qubesadmin.tools.qvm_template.verify_rpm('/dev/null', ts)
        ts.hdrFromFdno.assert_called_once()
        self.assertEqual(ret, None)
        self.assertAllCalled()

    def test_002_verify_rpm_nosig_success(self):
        ts = mock.MagicMock()
        # Just return a dict instead of rpm.hdr
        hdr = {
            rpm.RPMTAG_SIGPGP: None, # empty
            rpm.RPMTAG_SIGGPG: None, # empty
        }
        ts.hdrFromFdno.return_value = hdr
        ret = qubesadmin.tools.qvm_template.verify_rpm('/dev/null', ts, True)
        ts.hdrFromFdno.assert_called_once()
        self.assertEqual(ret, hdr)
        self.assertAllCalled()

    def test_003_verify_rpm_badsig_fail(self):
        ts = mock.MagicMock()
        def f(*args):
            raise rpm.error('public key not trusted')
        ts.hdrFromFdno.side_effect = f
        ret = qubesadmin.tools.qvm_template.verify_rpm('/dev/null', ts)
        ts.hdrFromFdno.assert_called_once()
        self.assertEqual(ret, None)
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

    def add_new_vm_side_effect(self, *args, **kwargs):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=TemplateVM state=Halted\n'
        self.app.domains.clear_cache()
        return self.app.domains['test-vm']

    @mock.patch('os.remove')
    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.rpm_transactionset')
    def test_100_install_local_success(
            self,
            mock_ts,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename,
            mock_remove):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = b'0\0'
        build_time = '2020-09-01 22:30:00' # 1598970600
        install_time = '2020-09-01 23:30:00.508230'
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
        mock_time.today.return_value = \
            datetime.datetime.fromisoformat(install_time)
        with mock.patch('builtins.open', mock.mock_open()) as mock_open, \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/usr/share/qubes/repo-templates/keys',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            qubesadmin.tools.qvm_template.install(args, self.app)
            # Lock file created
            self.assertEqual(mock_open.mock_calls, [
                mock.call('/var/tmp/qvm-template.lck', 'x'),
                mock.call().__enter__(),
                mock.call().__exit__(None, None, None)
            ])
        # Keyring created
        self.assertEqual(mock_ts.mock_calls, [
            mock.call('/usr/share/qubes/repo-templates/keys')
        ])
        # Package verified
        self.assertEqual(mock_verify.mock_calls, [
            mock.call(path, mock_ts('/usr/share/qubes/repo-templates/keys'),
                False)
        ])
        # Attempt to get download list
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        # Nothing downloaded
        self.assertEqual(mock_dl.mock_calls, [
            mock.call(args, self.app, path_override='/var/cache/qvm-template',
                dl_list={}, suffix='.unverified', version_selector=selector)
        ])
        # Package is extracted
        self.assertEqual(mock_extract.mock_calls, [
            mock.call('test-vm', path, '/var/tmp/qvm-template-tmpdir')
        ])
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
        # Lock file removed
        self.assertEqual(mock_remove.mock_calls, [
            mock.call('/var/tmp/qvm-template.lck')
        ])
        self.assertAllCalled()

    @mock.patch('os.remove')
    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.rpm_transactionset')
    def test_101_install_local_postprocargs_success(
            self,
            mock_ts,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename,
            mock_remove):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = b'0\0'
        build_time = '2020-09-01 22:30:00' # 1598970600
        install_time = '2020-09-01 23:30:00.508230'
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
        mock_time.today.return_value = \
            datetime.datetime.fromisoformat(install_time)
        with mock.patch('builtins.open', mock.mock_open()) as mock_open, \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/usr/share/qubes/repo-templates/keys',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                yes=False,
                allow_pv=True,
                pool='my-pool'
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            qubesadmin.tools.qvm_template.install(args, self.app)
            # Lock file created
            self.assertEqual(mock_open.mock_calls, [
                mock.call('/var/tmp/qvm-template.lck', 'x'),
                mock.call().__enter__(),
                mock.call().__exit__(None, None, None)
            ])
        # Keyring created
        self.assertEqual(mock_ts.mock_calls, [
            mock.call('/usr/share/qubes/repo-templates/keys')
        ])
        # Package verified
        self.assertEqual(mock_verify.mock_calls, [
            mock.call(path, mock_ts('/usr/share/qubes/repo-templates/keys'),
                False)
        ])
        # Attempt to get download list
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        # Nothing downloaded
        self.assertEqual(mock_dl.mock_calls, [
            mock.call(args, self.app, path_override='/var/cache/qvm-template',
                dl_list={}, suffix='.unverified', version_selector=selector)
        ])
        # Package is extracted
        self.assertEqual(mock_extract.mock_calls, [
            mock.call('test-vm', path, '/var/tmp/qvm-template-tmpdir')
        ])
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
        # Lock file removed
        self.assertEqual(mock_remove.mock_calls, [
            mock.call('/var/tmp/qvm-template.lck')
        ])
        self.assertAllCalled()

    @mock.patch('os.remove')
    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.rpm_transactionset')
    def test_102_install_local_badsig_fail(
            self,
            mock_ts,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename,
            mock_remove):
        mock_verify.return_value = None
        mock_time = mock.Mock(wraps=datetime.datetime)
        with mock.patch('builtins.open', mock.mock_open()) as mock_open, \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/usr/share/qubes/repo-templates/keys',
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
            # Lock file created
            self.assertEqual(mock_open.mock_calls, [
                mock.call('/var/tmp/qvm-template.lck', 'x'),
                mock.call().__enter__(),
                mock.call().__exit__(None, None, None)
            ])
            # Check error message
            self.assertTrue('verification failed' in mock_err.getvalue())
        # Keyring created
        self.assertEqual(mock_ts.mock_calls, [
            mock.call('/usr/share/qubes/repo-templates/keys')
        ])
        # Package verified
        self.assertEqual(mock_verify.mock_calls, [
            mock.call(path, mock_ts('/usr/share/qubes/repo-templates/keys'),
                False)
        ])
        # Should not be executed:
        self.assertEqual(mock_dl_list.mock_calls, [])
        self.assertEqual(mock_dl.mock_calls, [])
        self.assertEqual(mock_extract.mock_calls, [])
        self.assertEqual(mock_confirm.mock_calls, [])
        self.assertEqual(mock_call.mock_calls, [])
        self.assertEqual(mock_rename.mock_calls, [])
        # Lock file removed
        self.assertEqual(mock_remove.mock_calls, [
            mock.call('/var/tmp/qvm-template.lck')
        ])
        self.assertAllCalled()

    @mock.patch('os.remove')
    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.rpm_transactionset')
    def test_103_install_local_exists_fail(
            self,
            mock_ts,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename,
            mock_remove):
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
        with mock.patch('builtins.open', mock.mock_open()) as mock_open, \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/usr/share/qubes/repo-templates/keys',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            qubesadmin.tools.qvm_template.install(args, self.app)
            # Lock file created
            self.assertEqual(mock_open.mock_calls, [
                mock.call('/var/tmp/qvm-template.lck', 'x'),
                mock.call().__enter__(),
                mock.call().__exit__(None, None, None)
            ])
            # Check warning message
            self.assertTrue('already installed' in mock_err.getvalue())
        # Keyring created
        self.assertEqual(mock_ts.mock_calls, [
            mock.call('/usr/share/qubes/repo-templates/keys')
        ])
        # Package verified
        self.assertEqual(mock_verify.mock_calls, [
            mock.call(path, mock_ts('/usr/share/qubes/repo-templates/keys'),
                False)
        ])
        # Attempt to get download list
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        # Nothing downloaded
        self.assertEqual(mock_dl.mock_calls, [
            mock.call(args, self.app, path_override='/var/cache/qvm-template',
                dl_list={}, suffix='.unverified', version_selector=selector)
        ])
        # Should not be executed:
        self.assertEqual(mock_extract.mock_calls, [])
        self.assertEqual(mock_confirm.mock_calls, [])
        self.assertEqual(mock_call.mock_calls, [])
        self.assertEqual(mock_rename.mock_calls, [])
        # Lock file removed
        self.assertEqual(mock_remove.mock_calls, [
            mock.call('/var/tmp/qvm-template.lck')
        ])
        self.assertAllCalled()

    @mock.patch('os.remove')
    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.rpm_transactionset')
    def test_104_install_local_badpkgname_fail(
            self,
            mock_ts,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename,
            mock_remove):
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
        with mock.patch('builtins.open', mock.mock_open()) as mock_open, \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/usr/share/qubes/repo-templates/keys',
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
            # Lock file created
            self.assertEqual(mock_open.mock_calls, [
                mock.call('/var/tmp/qvm-template.lck', 'x'),
                mock.call().__enter__(),
                mock.call().__exit__(None, None, None)
            ])
            # Check error message
            self.assertTrue('Illegal package name' in mock_err.getvalue())
        # Keyring created
        self.assertEqual(mock_ts.mock_calls, [
            mock.call('/usr/share/qubes/repo-templates/keys')
        ])
        # Package verified
        self.assertEqual(mock_verify.mock_calls, [
            mock.call(path, mock_ts('/usr/share/qubes/repo-templates/keys'),
                False)
        ])
        # Should not be executed:
        self.assertEqual(mock_dl_list.mock_calls, [])
        self.assertEqual(mock_dl.mock_calls, [])
        self.assertEqual(mock_extract.mock_calls, [])
        self.assertEqual(mock_confirm.mock_calls, [])
        self.assertEqual(mock_call.mock_calls, [])
        self.assertEqual(mock_rename.mock_calls, [])
        # Lock file removed
        self.assertEqual(mock_remove.mock_calls, [
            mock.call('/var/tmp/qvm-template.lck')
        ])
        self.assertAllCalled()

    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.rpm_transactionset')
    def test_105_install_local_existinginstance_fail(
            self,
            mock_ts,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename):
        mock_time = mock.Mock(wraps=datetime.datetime)
        with mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/usr/share/qubes/repo-templates/keys',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            pathlib.Path('/var/tmp/qvm-template.lck').touch()
            try:
                with self.assertRaises(SystemExit), \
                        mock.patch('os.remove') as mock_remove:
                    qubesadmin.tools.qvm_template.install(args, self.app)
                    self.assertEqual(mock_remove.mock_calls, [])
            finally:
                # Lock file not removed
                self.assertTrue(os.path.exists('/var/tmp/qvm-template.lck'))
                os.remove('/var/tmp/qvm-template.lck')
            # Check error message
            self.assertTrue('another instance of qvm-template is running' \
                in mock_err.getvalue())
        # Should not be executed:
        self.assertEqual(mock_ts.mock_calls, [])
        self.assertEqual(mock_verify.mock_calls, [])
        self.assertEqual(mock_dl_list.mock_calls, [])
        self.assertEqual(mock_dl.mock_calls, [])
        self.assertEqual(mock_extract.mock_calls, [])
        self.assertEqual(mock_confirm.mock_calls, [])
        self.assertEqual(mock_call.mock_calls, [])
        self.assertEqual(mock_rename.mock_calls, [])
        self.assertAllCalled()

    @mock.patch('os.remove')
    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.rpm_transactionset')
    def test_106_install_local_badpath_fail(
            self,
            mock_ts,
            mock_verify,
            mock_dl_list,
            mock_dl,
            mock_extract,
            mock_confirm,
            mock_call,
            mock_mkdirs,
            mock_rename,
            mock_remove):
        mock_time = mock.Mock(wraps=datetime.datetime)
        with mock.patch('builtins.open', mock.mock_open()) as mock_open, \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            path = '/var/tmp/ShOulD-NoT-ExIsT.rpm'
            args = argparse.Namespace(
                templates=[path],
                keyring='/usr/share/qubes/repo-templates/keys',
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
            # Lock file created
            self.assertEqual(mock_open.mock_calls, [
                mock.call('/var/tmp/qvm-template.lck', 'x'),
                mock.call().__enter__(),
                mock.call().__exit__(None, None, None)
            ])
            # Check error message
            self.assertTrue(f"RPM file '{path}' not found" \
                in mock_err.getvalue())
        # Keyring created
        self.assertEqual(mock_ts.mock_calls, [
            mock.call('/usr/share/qubes/repo-templates/keys')
        ])
        # Should not be executed:
        self.assertEqual(mock_verify.mock_calls, [])
        self.assertEqual(mock_dl_list.mock_calls, [])
        self.assertEqual(mock_dl.mock_calls, [])
        self.assertEqual(mock_extract.mock_calls, [])
        self.assertEqual(mock_confirm.mock_calls, [])
        self.assertEqual(mock_call.mock_calls, [])
        self.assertEqual(mock_rename.mock_calls, [])
        # Lock file removed
        self.assertEqual(mock_remove.mock_calls, [
            mock.call('/var/tmp/qvm-template.lck')
        ])
        self.assertAllCalled()
