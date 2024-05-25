import re
from unittest import mock, skipUnless
import argparse
import datetime
import io
import os
import subprocess
import tempfile
from shutil import which

import fcntl
import rpm

import qubesadmin.tests
import qubesadmin.tools.qvm_template

def gen_rpm(sign: bool, cb):
    import tempfile, sys, os.path
    with tempfile.TemporaryDirectory() as d:
        if d[0] != '/':
            raise AssertionError('Temporary directory not absolute?')
        with open(os.path.join(d, 'dummy.spec'), 'wb') as h:
            h.write(b"""\
Name:		qubes-template-invalid
Version:	0.0.0
Release:	1
Summary:	Dummy uninstallable template package
License:	CC0
BuildArch:	noarch
%install
# Force the package to be large, so that rpmcanon will report progress
# information before being done
mkdir -p -m 0700 -- "$RPM_BUILD_ROOT" &&
exec dd if=/dev/urandom status=none count=1 bs=1M "of=$RPM_BUILD_ROOT/nonsense"

%description
%files
/nonsense
""")
        subprocess.check_call([
            'rpmbuild',
            '--macros=/usr/lib/rpm/macros',
            '-ba',
            # RPM gets really confused if this is a relative path, so use the
            # built-in Lua interpreter to avoid trying to figure out the correct
            # escaping.
            '--define=_topdir %{lua:print(posix.getcwd())}',
            '--quiet',
            'dummy.spec',
        ], cwd=d, stdout=subprocess.DEVNULL)
        subprocess.check_call([
            'gpg',
            '--homedir=.',
            '--passphrase=',
            '--batch',
            '--quiet',
            '--quick-generate-key',
            'test@example.com',
            'rsa',
            'sign',
        ], cwd=d, stdout=subprocess.DEVNULL)
        if sign:
            subprocess.check_call([
                'rpmsign',
                '--addsign',
                '--macros=/usr/lib/rpm/macros',
                '--define=_gpg_name test@example.com',
                './RPMS/noarch/qubes-template-invalid-0.0.0-1.noarch.rpm',
            ], cwd=d, env={'GNUPGHOME': '.'}, stdout=subprocess.DEVNULL)
        subprocess.check_call([
            'gpg',
            '--homedir=.',
            '--export',
            '--armor',
            '--output=pub.asc',
            'test@example.com',
        ], cwd=d)
        cb(os.path.join(d, 'pub.asc'), os.path.join(d, 'RPMS/noarch/qubes-template-invalid-0.0.0-1.noarch.rpm'))

class re_str(str):
    def __eq__(self, other):
        return bool(re.match(self, other))

    def __hash__(self):
        return super().__hash__()

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
            rpm.RPMTAG_NAME: 'qubes-template-test-vm',
        }
        mock_ts.return_value.hdrFromFdno.return_value = hdr
        mock_proc.return_value = b'-: digests signatures OK\n'
        ret = qubesadmin.tools.qvm_template.verify_rpm('/dev/null',
            '/path/to/key', template_name='test-vm')
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
        mock_proc.return_value = b'-: digests OK\n'
        with self.assertRaises(Exception) as e:
            qubesadmin.tools.qvm_template.verify_rpm('/dev/null',
                '/path/to/key')
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
        mock_proc.return_value = b'-: digests OK\n'
        ret = qubesadmin.tools.qvm_template.verify_rpm('/dev/null',
            '/path/to/key', nogpgcheck=True)
        mock_proc.assert_not_called()
        mock_call.assert_not_called()
        self.assertEqual(ret, hdr)
        self.assertAllCalled()

    @mock.patch('rpm.TransactionSet')
    @mock.patch('subprocess.check_call')
    @mock.patch('subprocess.check_output')
    def test_003_verify_rpm_badsig_fail(self, mock_proc, mock_call, mock_ts):
        mock_proc.side_effect = subprocess.CalledProcessError(1,
            ['rpmkeys', '--checksig'], b'-: digests SIGNATURES NOT OK\n')
        with self.assertRaises(Exception) as e:
            qubesadmin.tools.qvm_template.verify_rpm('/dev/null',
                '/path/to/key')
        mock_call.assert_called_once()
        mock_proc.assert_called_once()
        self.assertIn('Signature verification failed', e.exception.args[0])
        mock_ts.assert_not_called()
        self.assertAllCalled()

    @mock.patch('rpm.TransactionSet')
    @mock.patch('subprocess.check_call')
    @mock.patch('subprocess.check_output')
    def test_004_verify_rpm_badname(self, mock_proc, mock_call, mock_ts):
        mock_proc.return_value = b'-: digests signatures OK\n'
        hdr = {
            rpm.RPMTAG_SIGPGP: 'xxx', # non-empty
            rpm.RPMTAG_SIGGPG: 'xxx', # non-empty
            rpm.RPMTAG_NAME: 'qubes-template-unexpected',
        }
        mock_ts.return_value.hdrFromFdno.return_value = hdr
        with self.assertRaises(
                qubesadmin.tools.qvm_template.SignatureVerificationError) as e:
            qubesadmin.tools.qvm_template.verify_rpm('/dev/null',
                '/path/to/key', template_name='test-vm')
        mock_call.assert_called_once()
        mock_proc.assert_called_once()
        self.assertIn('package does not match expected template name',
            e.exception.args[0])
        mock_ts.assert_called_once()
        self.assertAllCalled()

    @mock.patch('os.path.exists')
    @mock.patch('subprocess.Popen')
    @mock.patch('os.symlink')
    def test_010_extract_rpm_success(self, mock_symlink, mock_popen, mock_path_exists):
        mock_popen.return_value.__enter__.return_value = mock_popen.return_value
        pipe = mock.Mock()
        mock_popen.return_value.stdout = pipe
        mock_popen.return_value.wait.return_value = 0
        mock_popen.return_value.returncode = 0
        mock_path_exists.return_value = True
        with tempfile.NamedTemporaryFile() as fd, \
                tempfile.TemporaryDirectory() as dir:
            path = fd.name
            dirpath = dir
            ret = qubesadmin.tools.qvm_template.extract_rpm(
                'test-vm', path, dirpath)
        self.assertEqual(ret, True)
        self.assertEqual(mock_popen.mock_calls, [
            mock.call(['rpm2archive', '-'],
                stdin=mock.ANY,
                stdout=subprocess.PIPE),
            mock.call().__enter__(),
            mock.call([
                    'tar',
                    'xz',
                    '-C',
                    dirpath,
                    './var/lib/qubes/vm-templates/test-vm/',
                    '--exclude=root.img.part.?[!0]',
                    '--exclude=root.img.part.[!0]0',
                ], stdin=pipe, stdout=subprocess.DEVNULL),
            mock.call().__enter__(),
            mock.call().__exit__(None, None, None),
            mock.call().__exit__(None, None, None),
            mock.call([
                'truncate',
                '--size=512',
                dirpath + '//var/lib/qubes/vm-templates/test-vm/root.img.part.00'
            ]),
            mock.call().__enter__(),
            mock.call().__exit__(None, None, None),
        ])
        self.assertEqual(mock_symlink.mock_calls, [
            mock.call(path,
             dirpath + '//var/lib/qubes/vm-templates/test-vm/template.rpm')
        ])
        self.assertAllCalled()

    @mock.patch('os.path.exists')
    @mock.patch('subprocess.Popen')
    @mock.patch('os.symlink')
    def test_011_extract_rpm_fail(self, mock_symlink, mock_popen, mock_path_exists):
        for failing_call in range(1, 5):
            mock_popen.reset_mock()
            with self.subTest(failing_call=failing_call):
                pipe = mock.Mock()

                def side_effect(_, **__):
                    side_effect.call_count += 1
                    o = mock_popen.return_value
                    o.__enter__.return_value = o
                    o.stdout = pipe
                    o.returncode = (
                        1 if side_effect.call_count >= failing_call else
                        0
                    )
                    return o

                side_effect.call_count = 0

                mock_popen.side_effect = side_effect
                mock_path_exists.return_value = True

                def symlink_side_effect(_s, _d):
                    if failing_call >= 4:
                        raise OSError("Error")
                    return None
                mock_symlink.side_effect = symlink_side_effect

                with tempfile.NamedTemporaryFile() as fd, \
                        tempfile.TemporaryDirectory() as tmpdir:
                    path = fd.name
                    dirpath = tmpdir
                    ret = qubesadmin.tools.qvm_template.extract_rpm(
                        'test-vm', path, dirpath)
                self.assertEqual(ret, False)
                self.assertEqual(mock_popen.mock_calls, [
                    mock.call(['rpm2archive', '-'],
                        stdin=mock.ANY,
                        stdout=subprocess.PIPE),
                    mock.call().__enter__(),
                    mock.call([
                            'tar',
                            'xz',
                            '-C',
                            dirpath,
                            './var/lib/qubes/vm-templates/test-vm/',
                            '--exclude=root.img.part.?[!0]',
                            '--exclude=root.img.part.[!0]0',
                        ], stdin=pipe, stdout=subprocess.DEVNULL),
                    mock.call().__enter__(),
                    mock.call().__exit__(None, None, None),
                    mock.call().__exit__(None, None, None),
                ] + ([] if failing_call < 3 else [
                    mock.call([
                        'truncate',
                        '--size=512',
                        dirpath
                        + '//var/lib/qubes/vm-templates/test-vm/root.img.part.00'
                    ]),
                    mock.call().__enter__(),
                    mock.call().__exit__(None, None, None),
                ]))
                self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.get_keys_for_repos')
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
                keyring='/tmp/keyring.gpg',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                repo_files=[],
                releasever='4.1',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            qubesadmin.tools.qvm_template.install(args, self.app)
            # Downloaded package should not be removed
            self.assertTrue(os.path.exists(path))
        # Attempt to get download list
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        # Nothing downloaded
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/cache/qvm-template',
            dl_list={}, version_selector=selector)
        mock_verify.assert_called_once_with(template_file.name, '/tmp/keyring.gpg',
            nogpgcheck=False)
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
                repo_files=[],
                releasever='4.1',
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
            path_override='/var/cache/qvm-template',
            dl_list={}, version_selector=selector)
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
                repo_files=[],
                releasever='4.1',
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
                repo_files=[],
                releasever='4.1',
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
            mock.call(args, self.app,
                path_override='/var/cache/qvm-template',
                dl_list={}, version_selector=selector)
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
                repo_files=[],
                releasever='4.1',
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
                repo_files=[],
                releasever='4.1',
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

    @mock.patch('os.remove')
    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    def test_107_install_download_success(
            self,
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
        build_time = '2020-09-01 14:30:00' # 1598970600
        install_time = '2020-09-01 15:30:00'
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '2'),
                ('version', '4.1'),
                ('release', '2020'),
                ('reponame', 'qubes-templates-itl'),
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
        mock_dl.return_value = {'test-vm': {
            rpm.RPMTAG_NAME        : 'qubes-template-test-vm',
            rpm.RPMTAG_BUILDTIME   : 1598970600,
            rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
            rpm.RPMTAG_EPOCHNUM    : 2,
            rpm.RPMTAG_LICENSE     : 'GPL',
            rpm.RPMTAG_RELEASE     : '2020',
            rpm.RPMTAG_SUMMARY     : 'Summary',
            rpm.RPMTAG_URL         : 'https://qubes-os.org',
            rpm.RPMTAG_VERSION     : '4.1'
        }}
        dl_list = {
            'test-vm': qubesadmin.tools.qvm_template.DlEntry(
                ('1', '4.1', '20200101'), 'qubes-templates-itl', 1048576)
        }
        mock_dl_list.return_value = dl_list
        mock_call.side_effect = self.add_new_vm_side_effect
        mock_time = mock.Mock(wraps=datetime.datetime)
        mock_time.now.return_value = \
            datetime.datetime(2020, 9, 1, 15, 30, tzinfo=datetime.timezone.utc)
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            args = argparse.Namespace(
                templates='test-vm',
                keyring='/tmp/keyring.gpg',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                repo_files=[],
                releasever='4.1',
                yes=False,
                keep_cache=False,
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
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/cache/qvm-template',
            dl_list=dl_list, version_selector=selector)
        # download already verify the package internally
        self.assertEqual(mock_verify.mock_calls, [])
        # Package is extracted
        mock_extract.assert_called_with('test-vm',
            '/var/cache/qvm-template/qubes-template-test-vm-1:4.1-20200101.rpm',
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
        # Downloaded template is removed
        self.assertEqual(mock_remove.mock_calls, [
            mock.call('/var/cache/qvm-template/' \
                'qubes-template-test-vm-1:4.1-20200101.rpm'),
            mock.call('/tmp/test.lock')
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
    def test_108_install_download_fail_exists(
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
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        mock_dl.return_value = {'test-vm': {
            rpm.RPMTAG_NAME        : 'qubes-template-test-vm',
            rpm.RPMTAG_BUILDTIME   : 1598970600,
            rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
            rpm.RPMTAG_EPOCHNUM    : 2,
            rpm.RPMTAG_LICENSE     : 'GPL',
            rpm.RPMTAG_RELEASE     : '2020',
            rpm.RPMTAG_SUMMARY     : 'Summary',
            rpm.RPMTAG_URL         : 'https://qubes-os.org',
            rpm.RPMTAG_VERSION     : '4.1'
        }}
        dl_list = {
            'test-vm': qubesadmin.tools.qvm_template.DlEntry(
                ('1', '4.1', '20200101'), 'qubes-templates-itl', 1048576)
        }
        mock_dl_list.return_value = dl_list
        mock_time = mock.Mock(wraps=datetime.datetime)
        mock_time.now.return_value = \
            datetime.datetime(2020, 9, 1, 15, 30, tzinfo=datetime.timezone.utc)
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            args = argparse.Namespace(
                templates='test-vm',
                keyring='/tmp/keyring.gpg',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                repo_files=[],
                releasever='4.1',
                yes=False,
                keep_cache=True,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            qubesadmin.tools.qvm_template.install(args, self.app)
            self.assertIn('already installed, skipping', mock_err.getvalue())
        # Attempt to get download list
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        # Nothing downloaded nor installed
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/cache/qvm-template',
            dl_list={}, version_selector=selector)
        mock_verify.assert_not_called()
        mock_extract.assert_not_called()
        mock_confirm.assert_not_called()
        mock_call.assert_not_called()
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
    def test_109_install_fail_extract(
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
        # Extraction error
        mock_extract.return_value = False
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/tmp/keyring.gpg',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                repo_files=[],
                releasever='4.1',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            with self.assertRaises(Exception) as e:
                qubesadmin.tools.qvm_template.install(args, self.app)
        self.assertIn('Failed to extract', e.exception.args[0])

        # Attempt to get download list
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        # Nothing downloaded
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/cache/qvm-template',
            dl_list={}, version_selector=selector)
        mock_verify.assert_called_once_with(template_file.name,
            '/tmp/keyring.gpg',
            nogpgcheck=False)
        # Package is (attempted to be) extracted
        mock_extract.assert_called_with('test-vm', path,
            '/var/tmp/qvm-template-tmpdir')
        # No packages overwritten, so no confirm needed
        self.assertEqual(mock_confirm.mock_calls, [])
        # No VM created
        mock_call.assert_not_called()
        # Cache directory created
        self.assertEqual(mock_mkdirs.mock_calls, [
            mock.call(args.cachedir, exist_ok=True)
        ])
        # No templates downloaded, thus no renames needed
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
                repos=[('enablerepo', 'repo1'), ('enablerepo', 'repo2'),
                       ('disablerepo', 'repo3'), ('disablerepo', 'repo4'),
                       ('disablerepo', 'repo5')],
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
                repos=[('repoid', 'repo1'), ('repoid', 'repo2')],
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
                repos=[('repoid', 'repo1'), ('repoid', 'repo2')],
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
                repos=[('enablerepo', 'repo\n0'),
                       ('repoid', 'repo1'), ('repoid', 'repo2')],
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
                repos=[('disablereporepo', 'repo\n0'),
                       ('repoid', 'repo1'), ('repoid', 'repo2')],
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
                repos=[('repoid', 'repo\n1'), ('repoid', 'repo2')],
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
                repos=[('repoid', 'repo1'), ('repoid', 'repo2')],
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
                repos=[('repoid', 'repo1'), ('repoid', 'repo2')],
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
            all_versions=True,
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
            all_versions=True,
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
            mock.call(args, self.app, 'qubes-template-fedora-32'),
            mock.call(args, self.app, 'qubes-template-fedora-31')
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_151_list_templates_available_all_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'fedora-31',
                '1',
                '4.1',
                '20190101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2019, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
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
            ),
        ]
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=True,
            extras=False,
            upgrades=False,
            all_versions=True,
            machine_readable=False,
            machine_readable_json=False,
            templates=[]
        )
        with mock.patch('sys.stdout', new=io.StringIO()) as mock_out:
            qubesadmin.tools.qvm_template.list_templates(
                args, self.app, 'list')
            self.assertEqual(mock_out.getvalue(),
'''Available Templates
[('fedora-31', '1:4.1-20190101', 'qubes-templates-itl'), ('fedora-31', '1:4.1-20200101', 'qubes-templates-itl')]
''')
        self.assertEqual(mock_query.mock_calls, [
            mock.call(args, self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.qrexec_repoquery')
    def test_151_list_templates_available_only_latest_success(self, mock_query):
        mock_query.return_value = [
            qubesadmin.tools.qvm_template.Template(
                'fedora-31',
                '1',
                '4.1',
                '20190101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2019, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
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
            ),
        ]
        args = argparse.Namespace(
            all=False,
            installed=False,
            available=True,
            extras=False,
            upgrades=False,
            all_versions=False,
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
            all_versions=True,
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
            mock.call(args, self.app, 'qubes-template-test-vm*')
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
            all_versions=True,
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
            mock.call(args, self.app, 'qubes-template-test-vm*')
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
            mock.call(args, self.app, 'qubes-template-test-vm*')
        ])
        self.assertAllCalled()

    def test_154_list_templates_all_success(self):
        args = argparse.Namespace(
            all=True,
            installed=False,
            available=False,
            extras=False,
            upgrades=False,
            all_versions=True,
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
            all_versions=True,
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
            all_versions=True,
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
            all_versions=True,
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
            all_versions=True,
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
            all_versions=True,
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
            all_versions=True,
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
            all_versions=True,
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

    def _mock_qrexec_download(self, args, app, spec, path,
                              key, dlsize=None, refresh=False):
        self.assertFalse(os.path.exists(path),
            '{} should not exist before'.format(path))
        # just create an empty file
        with open(path, 'wb') as f:
            if f is not None:
                f.truncate(dlsize)

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_180_download_success(self, mock_qrexec, mock_dllist,
                                  mock_verify_rpm):
        mock_qrexec.side_effect = self._mock_qrexec_download
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
                retries=1
            )
            pkgs = qubesadmin.tools.qvm_template.download(args, self.app, dir, {
                    'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                        ('1', '2', '3'), 'qubes-templates-itl', 1048576),
                    'fedora-32': qubesadmin.tools.qvm_template.DlEntry(
                        ('0', '1', '2'),
                        'qubes-templates-itl-testing',
                        2048576)
                })
            self.assertIn('fedora-31', pkgs)
            self.assertIn('fedora-32', pkgs)
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    1048576),
                mock.call(args, self.app, 'qubes-template-fedora-32-0:1-2',
                    re_str(dir + '/.*/qubes-template-fedora-32-0:1-2.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    2048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])
            self.assertEqual(mock_verify_rpm.mock_calls, [
                mock.call(re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                          '/tmp/keyring.gpg', template_name='fedora-31'),
                mock.call(re_str(dir + '/.*/qubes-template-fedora-32-0:1-2.rpm.UNTRUSTED'),
                          '/tmp/keyring.gpg', template_name='fedora-32'),
            ])

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_181_download_success_nosuffix(self, mock_qrexec, mock_dllist,
                                           mock_verify_rpm):
        mock_qrexec.side_effect = self._mock_qrexec_download
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=1,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                pkgs = qubesadmin.tools.qvm_template.download(args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                    })
            self.assertIn('fedora-31', pkgs)
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])
            self.assertEqual(mock_verify_rpm.mock_calls, [
                mock.call(re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                          '/tmp/keyring.gpg', template_name='fedora-31'),
            ])

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_182_download_success_getdllist(self, mock_qrexec, mock_dllist,
                                            mock_verify_rpm):
        mock_qrexec.side_effect = self._mock_qrexec_download
        mock_dllist.return_value = {
            'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                ('1', '2', '3'), 'qubes-templates-itl', 1048576)
        }
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=1,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
            )
            pkgs = qubesadmin.tools.qvm_template.download(args, self.app,
                dir, None,
                qubesadmin.tools.qvm_template.VersionSelector.LATEST_LOWER)
            self.assertIn('fedora-31', pkgs)
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [
                mock.call(args, self.app,
                    version_selector=\
                        qubesadmin.tools.qvm_template.\
                        VersionSelector.LATEST_LOWER)
            ])
            self.assertEqual(mock_verify_rpm.mock_calls, [
                mock.call(re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                          '/tmp/keyring.gpg', template_name='fedora-31'),
            ])

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_183_download_success_downloaddir(self, mock_qrexec, mock_dllist,
                                              mock_verify_rpm):
        mock_qrexec.side_effect = self._mock_qrexec_download
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=1,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
                downloaddir=dir
            )
            pkgs = qubesadmin.tools.qvm_template.download(args, self.app, None, {
                    'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                        ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                })
            self.assertIn('fedora-31', pkgs)
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_184_download_success_exists(self, mock_qrexec, mock_dllist,
                                         mock_verify_rpm):
        mock_qrexec.side_effect = self._mock_qrexec_download
        with tempfile.TemporaryDirectory() as dir:
            with open(os.path.join(
                        dir, 'qubes-template-fedora-31-1:2-3.rpm'),
                    'w') as _:
                pass
            args = argparse.Namespace(
                retries=1,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                pkgs = qubesadmin.tools.qvm_template.download(args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576),
                        'fedora-32': qubesadmin.tools.qvm_template.DlEntry(
                            ('0', '1', '2'),
                            'qubes-templates-itl-testing',
                            2048576)
                    })
                self.assertIn('fedora-31', pkgs)
                self.assertIn('fedora-32', pkgs)
                self.assertTrue('already exists, skipping'
                    in mock_err.getvalue())
            self.assertEqual(mock_verify_rpm.mock_calls, [
                mock.call(
                    dir + '/qubes-template-fedora-31-1:2-3.rpm',
                    '/tmp/keyring.gpg',
                    template_name='fedora-31',
                ),
                mock.call(
                    re_str(dir + '/.*/qubes-template-fedora-32-0:1-2.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    template_name='fedora-32',
                ),
            ])
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-32-0:1-2',
                    re_str(dir + '/.*/qubes-template-fedora-32-0:1-2.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    2048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_185_download_success_existsmove(self, mock_qrexec, mock_dllist,
                                             mock_verify_rpm):
        mock_qrexec.side_effect = self._mock_qrexec_download
        with tempfile.TemporaryDirectory() as dir:
            with open(os.path.join(
                        dir, 'qubes-template-fedora-31-1:2-3.rpm'),
                    'w') as _:
                pass
            args = argparse.Namespace(
                retries=1,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                pkgs = qubesadmin.tools.qvm_template.download(args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                    })
                self.assertIn('fedora-31', pkgs)
                self.assertTrue('already exists, skipping'
                    in mock_err.getvalue())
            self.assertEqual(mock_qrexec.mock_calls, [])
            self.assertEqual(mock_dllist.mock_calls, [])
            self.assertTrue(os.path.exists(
                dir + '/qubes-template-fedora-31-1:2-3.rpm'))

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_186_download_success_existsnosuffix(self, mock_qrexec, mock_dllist,
                                                 mock_verify_rpm):
        mock_qrexec.side_effect = self._mock_qrexec_download
        with tempfile.TemporaryDirectory() as dir:
            with open(os.path.join(
                        dir, 'qubes-template-fedora-31-1:2-3.rpm'),
                    'w') as _:
                pass
            args = argparse.Namespace(
                retries=1,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                pkgs = qubesadmin.tools.qvm_template.download(args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                    })
                self.assertIn('fedora-31', pkgs)
                self.assertTrue('already exists, skipping'
                    in mock_err.getvalue())
            self.assertEqual(mock_qrexec.mock_calls, [])
            self.assertEqual(mock_dllist.mock_calls, [])
            self.assertTrue(os.path.exists(
                dir + '/qubes-template-fedora-31-1:2-3.rpm'))

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_187_download_success_retry(self, mock_qrexec, mock_dllist,
                                        mock_verify_rpm):
        counter = 0
        def f(*args, **kwargs):
            nonlocal counter
            counter += 1
            if counter == 1:
                raise ConnectionError
            self._mock_qrexec_download(*args, **kwargs)
        mock_qrexec.side_effect = f
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=2,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err, \
                    mock.patch('os.remove') as mock_rm:
                pkgs = qubesadmin.tools.qvm_template.download(args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                    })
                self.assertIn('fedora-31', pkgs)
                self.assertTrue('retrying...' in mock_err.getvalue())
                self.assertEqual(mock_rm.mock_calls, [
                    mock.call(re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'))
                ])
            self.assertEqual(mock_verify_rpm.mock_calls, [
                mock.call(
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    template_name='fedora-31',
                ),
            ])
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    1048576),
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_188_download_fail_retry(self, mock_qrexec, mock_dllist,
                                     mock_verify_rpm):
        mock_qrexec.side_effect = self._mock_qrexec_download
        counter = 0
        def f(*args, **kwargs):
            nonlocal counter
            counter += 1
            if counter <= 3:
                raise ConnectionError
            self._mock_qrexec_download(*args, **kwargs)
        mock_qrexec.side_effect = f
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=3,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
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
                    mock.call(re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED')),
                    mock.call(re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED')),
                    mock.call(re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'))
                ])
            self.assertEqual(mock_verify_rpm.mock_calls, [])
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    1048576),
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    1048576),
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_189_download_fail_interrupt(self, mock_qrexec, mock_dllist,
                                         mock_verify_rpm):
        def f(*args):
            raise RuntimeError
        mock_qrexec.side_effect = f
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=3,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
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
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm'),
                    '/tmp/keyring.gpg',
                    1048576)
            ])
            self.assertEqual(mock_verify_rpm.mock_calls, [])
            self.assertEqual(mock_dllist.mock_calls, [])

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_190_download_fail_verify(self, mock_qrexec, mock_dllist,
                                         mock_verify_rpm):
        mock_qrexec.side_effect = self._mock_qrexec_download
        mock_verify_rpm.side_effect = \
            qubesadmin.tools.qvm_template.SignatureVerificationError

        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=3,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=True,  # make sure it gets ignored
                downloaddir=dir
            )
            with self.assertRaises(qubesadmin.tools.qvm_template.SignatureVerificationError):
                qubesadmin.tools.qvm_template.download(
                    args, self.app, None, {
                        'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                            ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                    })
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm'),
                    '/tmp/keyring.gpg',
                    1048576)
            ])
            self.assertEqual(mock_dllist.mock_calls, [])
            self.assertEqual(os.listdir(dir), [])
            self.assertEqual(mock_verify_rpm.mock_calls, [
                mock.call(re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                          '/tmp/keyring.gpg', template_name='fedora-31'),
            ])

    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.qrexec_download')
    def test_191_download_fail(self, mock_qrexec, mock_dllist,
                               mock_verify_rpm):
        def f(*args, **kwargs):
            raise ConnectionError
        mock_qrexec.side_effect = f
        with tempfile.TemporaryDirectory() as dir:
            args = argparse.Namespace(
                retries=1,
                repo_files=[],
                keyring='/tmp/keyring.gpg',
                releasever='4.1',
                nogpgcheck=False,
                downloaddir=dir
            )
            with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
                with self.assertRaises(SystemExit):
                    qubesadmin.tools.qvm_template.download(
                        args, self.app, None, {
                            'fedora-31': qubesadmin.tools.qvm_template.DlEntry(
                                ('1', '2', '3'), 'qubes-templates-itl', 1048576)
                        })
                self.assertEqual(mock_err.getvalue().count('retrying...'), 0)
                self.assertTrue('download failed' in mock_err.getvalue())
            self.assertEqual(mock_verify_rpm.mock_calls, [])
            self.assertEqual(mock_qrexec.mock_calls, [
                mock.call(args, self.app, 'qubes-template-fedora-31-1:2-3',
                    re_str(dir + '/.*/qubes-template-fedora-31-1:2-3.rpm.UNTRUSTED'),
                    '/tmp/keyring.gpg',
                    1048576),
            ])
            self.assertEqual(mock_dllist.mock_calls, [])

    def _mock_qrexec_download_short(self, args, app, spec, path,
                              key, dlsize=None, refresh=False):
        self.assertFalse(os.path.exists(path),
            '{} should not exist before'.format(path))
        # just create an empty file
        with open(path, 'wb') as f:
            if f is not None:
                f.truncate(dlsize // 2)

    @mock.patch('os.remove')
    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    def test_200_reinstall_success(
            self,
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
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        build_time = '2020-09-01 14:30:00' # 1598970600
        install_time = '2020-09-01 15:30:00'
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '2'),
                ('version', '4.1'),
                ('release', '2020')]:
            self.app.expected_calls[(
                'test-vm',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '2'),
                ('version', '4.1'),
                ('release', '2020'),
                ('reponame', 'qubes-templates-itl'),
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
        rpm_hdr = {
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
        mock_dl.return_value = {'test-vm': rpm_hdr}
        dl_list = {
            'test-vm': qubesadmin.tools.qvm_template.DlEntry(
                ('2', '4.1', '2020'), 'qubes-templates-itl', 1048576)
        }
        mock_dl_list.return_value = dl_list
        mock_call.side_effect = self.add_new_vm_side_effect
        mock_time = mock.Mock(wraps=datetime.datetime)
        mock_time.now.return_value = \
            datetime.datetime(2020, 9, 1, 15, 30, tzinfo=datetime.timezone.utc)
        selector = qubesadmin.tools.qvm_template.VersionSelector.REINSTALL
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir:
            args = argparse.Namespace(
                templates=['test-vm'],
                keyring='/tmp/keyring.gpg',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                repo_files=[],
                releasever='4.1',
                yes=False,
                keep_cache=True,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            qubesadmin.tools.qvm_template.install(args, self.app,
                version_selector=selector,
                override_existing=True)
        # Attempt to get download list
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/cache/qvm-template',
            dl_list=dl_list, version_selector=selector)
        # already verified by download()
        self.assertEqual(mock_verify.mock_calls, [])
        # Package is extracted
        mock_extract.assert_called_with('test-vm',
            '/var/cache/qvm-template/qubes-template-test-vm-2:4.1-2020.rpm',
            '/var/tmp/qvm-template-tmpdir')
        # Expect override confirmation
        self.assertEqual(mock_confirm.mock_calls,
            [mock.call(re_str(r'.*override changes.*:'), ['test-vm'])])
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
        # Downloaded package should not be removed
        self.assertEqual(mock_remove.mock_calls, [
            mock.call('/tmp/test.lock')
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
    def test_201_reinstall_fail_noversion(
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
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '2'),
                ('version', '4.1'),
                ('release', '2021')]:
            self.app.expected_calls[(
                'test-vm',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        rpm_hdr = {
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
        mock_dl.return_value = {'test-vm': rpm_hdr}
        dl_list = {
            'test-vm': qubesadmin.tools.qvm_template.DlEntry(
                ('1', '4.1', '2020'), 'qubes-templates-itl', 1048576)
        }
        mock_dl_list.return_value = dl_list
        selector = qubesadmin.tools.qvm_template.VersionSelector.REINSTALL
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                self.assertRaises(SystemExit) as e, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            args = argparse.Namespace(
                templates=['test-vm'],
                keyring='/tmp/keyring.gpg',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                repo_files=[],
                releasever='4.1',
                yes=False,
                keep_cache=True,
                allow_pv=False,
                pool=None
            )
            qubesadmin.tools.qvm_template.install(args, self.app,
                version_selector=selector,
                override_existing=True)
            self.assertIn(
                'Same version of template \'test-vm\' not found',
                mock_err.getvalue())
        # Attempt to get download list
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/cache/qvm-template',
            dl_list=dl_list, version_selector=selector)
        # already verified by download()
        self.assertEqual(mock_verify.mock_calls, [])
        # Expect override confirmation
        self.assertEqual(mock_confirm.mock_calls,
            [mock.call(re_str(r'.*override changes.*:'), ['test-vm'])])
        # Nothing extracted / installed
        mock_extract.assert_not_called()
        mock_call.assert_not_called()
        # Cache directory created
        self.assertEqual(mock_mkdirs.mock_calls, [
            mock.call(args.cachedir, exist_ok=True)
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
    def test_202_reinstall_local_success(
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
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        build_time = '2020-09-01 14:30:00' # 1598970600
        install_time = '2020-09-01 15:30:00'
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '2'),
                ('version', '4.1'),
                ('release', '2020')]:
            self.app.expected_calls[(
                'test-vm',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
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
        rpm_hdr = {
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
        mock_verify.return_value = rpm_hdr
        dl_list = {}
        mock_dl_list.return_value = dl_list
        mock_call.side_effect = self.add_new_vm_side_effect
        mock_time = mock.Mock(wraps=datetime.datetime)
        mock_time.now.return_value = \
            datetime.datetime(2020, 9, 1, 15, 30, tzinfo=datetime.timezone.utc)
        selector = qubesadmin.tools.qvm_template.VersionSelector.REINSTALL
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                mock.patch('datetime.datetime', new=mock_time), \
                mock.patch('tempfile.TemporaryDirectory') as mock_tmpdir, \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file:
            path = template_file.name
            args = argparse.Namespace(
                templates=[path],
                keyring='/tmp/keyring.gpg',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                repo_files=[],
                releasever='4.1',
                yes=False,
                allow_pv=False,
                pool=None
            )
            mock_tmpdir.return_value.__enter__.return_value = \
                '/var/tmp/qvm-template-tmpdir'
            qubesadmin.tools.qvm_template.install(args, self.app,
                version_selector=selector,
                override_existing=True)
            # Package is extracted
            mock_extract.assert_called_with(
                'test-vm',
                path,
                '/var/tmp/qvm-template-tmpdir')
            # Package verified
            self.assertEqual(mock_verify.mock_calls, [
                mock.call(path, '/tmp/keyring.gpg', nogpgcheck=False)
            ])
        # Attempt to get download list
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/cache/qvm-template',
            dl_list=dl_list, version_selector=selector)
        # Expect override confirmation
        self.assertEqual(mock_confirm.mock_calls,
            [mock.call(re_str(r'.*override changes.*:'), ['test-vm'])])
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
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_remove.main')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    def test_210_remove_success(self, mock_confirm, mock_remove):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\x00vm1 class=TemplateVM state=Halted\n'
            b'vm2 class=TemplateVM state=Halted\n'
        )
        args = argparse.Namespace(
            templates=['vm1', 'vm2'],
            yes=False
        )
        qubesadmin.tools.qvm_template.remove(args, self.app)
        self.assertEqual(mock_confirm.mock_calls,
            [mock.call(re_str(r'.*completely remove.*'), ['vm1', 'vm2'])])
        self.assertEqual(mock_remove.mock_calls, [
            mock.call(['--force', '--', 'vm1', 'vm2'], self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_kill.main')
    @mock.patch('qubesadmin.tools.qvm_remove.main')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    def test_211_remove_purge_disassoc_success(
            self,
            mock_confirm,
            mock_remove,
            mock_kill):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\x00vm1 class=TemplateVM state=Halted\n'
            b'vm2 class=TemplateVM state=Halted\n'
            b'vm3 class=TemplateVM state=Halted\n'
            b'vm4 class=TemplateVM state=Halted\n'
            b'dummy class=TemplateVM state=Halted\n'
            b'dummy-1 class=TemplateVM state=Halted\n'
        )
        self.app.expected_calls[
                ('dummy', 'admin.vm.feature.Get', 'template-dummy', None)] = \
            b'0\x000'
        self.app.expected_calls[
                ('dummy-1', 'admin.vm.feature.Get',
                    'template-dummy', None)] = \
            b'0\x001'
        self.app.expected_calls[
                ('vm2', 'admin.vm.property.Set',
                    'default_template', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm2', 'admin.vm.property.Set', 'template', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm3', 'admin.vm.property.Set', 'netvm', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm3', 'admin.vm.property.Set', 'template', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm4', 'admin.vm.property.Set', 'netvm', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm4', 'admin.vm.property.Set', 'template', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('dom0', 'admin.property.Set', 'updatevm', b'')] = \
            b'0\x00'
        args = argparse.Namespace(
            templates=['vm1'],
            yes=False
        )
        def deps(app, vm):
            if vm == 'vm1':
                return [(self.app.domains['vm2'], 'default_template'),
                        (self.app.domains['vm3'], 'netvm')]
            if vm == 'vm2' or vm == 'vm3':
                return [(self.app.domains['vm4'], 'netvm')]
            if vm == 'vm4':
                return [(None, 'updatevm')]
            return []
        with mock.patch('qubesadmin.utils.vm_dependencies') as mock_deps:
            mock_deps.side_effect = deps
            qubesadmin.tools.qvm_template.remove(args, self.app, purge=True)
            # Once for purge (dependency detection) and
            # one for disassoc (actually disassociating the dependencies
            self.assertEqual(mock_deps.mock_calls, [
                mock.call(self.app, self.app.domains['vm1']),
                mock.call(self.app, self.app.domains['vm2']),
                mock.call(self.app, self.app.domains['vm3']),
                mock.call(self.app, self.app.domains['vm4']),
                mock.call(self.app, self.app.domains['vm1']),
                mock.call(self.app, self.app.domains['vm2']),
                mock.call(self.app, self.app.domains['vm3']),
                mock.call(self.app, self.app.domains['vm4'])
            ])
        self.assertEqual(mock_confirm.mock_calls, [
            mock.call(re_str(r'.*completely remove.*'),
                ['vm1', 'vm2', 'vm3', 'vm4']),
            mock.call(re_str(r'.*completely remove.*'),
                ['vm1', 'vm2', 'vm3', 'vm4']),
            mock.call(re_str(r'.*completely remove.*'),
                ['vm1', 'vm2', 'vm3', 'vm4'])
        ])
        self.assertEqual(mock_remove.mock_calls, [
            mock.call(['--force', '--', 'vm1', 'vm2', 'vm3', 'vm4', 'dummy-1'],
                self.app)
        ])
        self.assertEqual(mock_kill.mock_calls, [
            mock.call(['--', 'vm1', 'vm2', 'vm3', 'vm4', 'dummy-1'], self.app)
        ])
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_kill.main')
    @mock.patch('qubesadmin.tools.qvm_remove.main')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    def test_212_remove_disassoc_success(
            self,
            mock_confirm,
            mock_remove,
            mock_kill):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\x00vm1 class=TemplateVM state=Halted\n'
            b'vm2 class=TemplateVM state=Halted\n'
            b'vm3 class=TemplateVM state=Halted\n'
            b'vm4 class=TemplateVM state=Halted\n'
            b'dummy class=TemplateVM state=Halted\n'
            b'dummy-1 class=TemplateVM state=Halted\n'
        )
        self.app.expected_calls[
                ('dummy', 'admin.vm.feature.Get', 'template-dummy', None)] = \
            b'0\x000'
        self.app.expected_calls[
                ('dummy-1', 'admin.vm.feature.Get',
                    'template-dummy', None)] = \
            b'0\x001'
        self.app.expected_calls[
                ('vm2', 'admin.vm.property.Set',
                    'default_template', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm2', 'admin.vm.property.Set', 'template', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm3', 'admin.vm.property.Set', 'netvm', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm3', 'admin.vm.property.Set', 'template', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm4', 'admin.vm.property.Set', 'netvm', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm4', 'admin.vm.property.Set', 'template', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('dom0', 'admin.property.Set', 'updatevm', b'')] = \
            b'0\x00'
        args = argparse.Namespace(
            templates=['vm1', 'vm2', 'vm3', 'vm4'],
            yes=False
        )
        def deps(app, vm):
            if vm == 'vm1':
                return [(self.app.domains['vm2'], 'default_template'),
                        (self.app.domains['vm3'], 'netvm')]
            if vm == 'vm2' or vm == 'vm3':
                return [(self.app.domains['vm4'], 'netvm')]
            if vm == 'vm4':
                return [(None, 'updatevm')]
            return []
        with mock.patch('qubesadmin.utils.vm_dependencies') as mock_deps:
            mock_deps.side_effect = deps
            qubesadmin.tools.qvm_template.remove(args, self.app, disassoc=True)
            self.assertEqual(mock_deps.mock_calls, [
                mock.call(self.app, self.app.domains['vm1']),
                mock.call(self.app, self.app.domains['vm2']),
                mock.call(self.app, self.app.domains['vm3']),
                mock.call(self.app, self.app.domains['vm4'])
            ])
        self.assertEqual(mock_confirm.mock_calls, [
            mock.call(re_str(r'.*completely remove.*'),
                ['vm1', 'vm2', 'vm3', 'vm4'])
        ])
        self.assertEqual(mock_remove.mock_calls, [
            mock.call(['--force', '--', 'vm1', 'vm2', 'vm3', 'vm4'],
                self.app)
        ])
        self.assertEqual(mock_kill.mock_calls, [
            mock.call(['--', 'vm1', 'vm2', 'vm3', 'vm4'], self.app)
        ])
        self.assertAllCalled()

    def test_213_remove_fail_nodomain(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00vm1 class=TemplateVM state=Halted\n'
        args = argparse.Namespace(
            templates=['vm0'],
            yes=False
        )
        with mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            with self.assertRaises(SystemExit):
                qubesadmin.tools.qvm_template.remove(args, self.app)
            self.assertTrue('no such domain:' in mock_err.getvalue())
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_kill.main')
    @mock.patch('qubesadmin.tools.qvm_remove.main')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    def test_214_remove_disassoc_success_newdummy(
            self,
            mock_confirm,
            mock_remove,
            mock_kill):
        def append_new_vm_side_effect(*args, **kwargs):
            self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] += \
                b'dummy-1 class=TemplateVM state=Halted\n'
            self.app.domains.clear_cache()
            return self.app.domains['dummy-1']
        self.app.add_new_vm = mock.Mock(side_effect=append_new_vm_side_effect)
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = (
            b'0\x00vm1 class=TemplateVM state=Halted\n'
            b'vm2 class=TemplateVM state=Halted\n'
            b'dummy class=TemplateVM state=Halted\n'
        )
        self.app.expected_calls[
                ('dummy', 'admin.vm.feature.Get', 'template-dummy', None)] = \
            b'0\x000'
        self.app.expected_calls[
                ('dummy-1', 'admin.vm.feature.Set',
                    'template-dummy', b'1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm2', 'admin.vm.property.Set',
                    'default_template', b'dummy-1')] = \
            b'0\x00'
        self.app.expected_calls[
                ('vm2', 'admin.vm.property.Set',
                    'template', b'dummy-1')] = \
            b'0\x00'
        args = argparse.Namespace(
            templates=['vm1'],
            yes=False
        )
        def deps(app, vm):
            if vm == 'vm1':
                return [(self.app.domains['vm2'], 'default_template')]
            return []
        with mock.patch('qubesadmin.utils.vm_dependencies') as mock_deps:
            mock_deps.side_effect = deps
            qubesadmin.tools.qvm_template.remove(args, self.app, disassoc=True)
            self.assertEqual(mock_deps.mock_calls, [
                mock.call(self.app, self.app.domains['vm1'])
            ])
        self.assertEqual(mock_confirm.mock_calls, [
            mock.call(re_str(r'.*completely remove.*'), ['vm1'])
        ])
        self.assertEqual(mock_remove.mock_calls, [
            mock.call(['--force', '--', 'vm1'], self.app)
        ])
        self.assertEqual(mock_kill.mock_calls, [
            mock.call(['--', 'vm1'], self.app)
        ])
        self.assertAllCalled()

    def test_220_get_keys_for_repos_success(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write(
b'''[qubes-templates-itl]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl
metalink = https://yum.qubes-os.org/r$releasever/templates-itl/repodata/repomd.xml.metalink
enabled = 1
fastestmirror = 1
metadata_expire = 7d
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
[qubes-templates-itl-testing-nokey]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl-testing
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl-testing
metalink = https://yum.qubes-os.org/r$releasever/templates-itl-testing/repodata/repomd.xml.metalink
enabled = 0
fastestmirror = 1
gpgcheck = 1
#gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary
[qubes-templates-itl-testing]
name = Qubes Templates repository
#baseurl = https://yum.qubes-os.org/r$releasever/templates-itl-testing
#baseurl = http://yum.qubesosfasa4zl44o4tws22di6kepyzfeqv3tg4e3ztknltfxqrymdad.onion/r$releasever/templates-itl-testing
metalink = https://yum.qubes-os.org/r$releasever/templates-itl-testing/repodata/repomd.xml.metalink
enabled = 0
fastestmirror = 1
gpgcheck = 1
gpgkey = file:///etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-$releasever-primary-testing
''')
            f.flush()
            ret = qubesadmin.tools.qvm_template.get_keys_for_repos(
                [f.name], 'r4.1')
            self.assertEqual(ret, {
                'qubes-templates-itl':
                    '/etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-r4.1-primary',
                'qubes-templates-itl-testing':
                    '/etc/qubes/repo-templates/keys/RPM-GPG-KEY-qubes-r4.1-primary-testing'
            })
            self.assertAllCalled()

    @mock.patch('os.rename')
    @mock.patch('os.makedirs')
    @mock.patch('subprocess.check_call')
    @mock.patch('qubesadmin.tools.qvm_template.confirm_action')
    @mock.patch('qubesadmin.tools.qvm_template.extract_rpm')
    @mock.patch('qubesadmin.tools.qvm_template.download')
    @mock.patch('qubesadmin.tools.qvm_template.get_dl_list')
    @mock.patch('qubesadmin.tools.qvm_template.verify_rpm')
    def test_220_downgrade_skip_lower(
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
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '2'),
                ('version', '4.1'),
                ('release', '2020')]:
            self.app.expected_calls[(
                'test-vm',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        rpm_hdr = {
            rpm.RPMTAG_NAME        : 'qubes-template-test-vm',
            rpm.RPMTAG_BUILDTIME   : 1598970600,
            rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
            rpm.RPMTAG_EPOCHNUM    : 2,
            rpm.RPMTAG_LICENSE     : 'GPL',
            rpm.RPMTAG_RELEASE     : '2021',
            rpm.RPMTAG_SUMMARY     : 'Summary',
            rpm.RPMTAG_URL         : 'https://qubes-os.org',
            rpm.RPMTAG_VERSION     : '4.1'
        }
        mock_verify.return_value = rpm_hdr
        mock_dl_list.return_value = {}
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST_LOWER
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            args = argparse.Namespace(
                templates=[template_file.name],
                keyring='/tmp/keyring.gpg',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                repo_files=[],
                releasever='4.1',
                yes=False,
                keep_cache=True,
                allow_pv=False,
                pool=None
            )
            qubesadmin.tools.qvm_template.install(args, self.app,
                version_selector=selector,
                override_existing=True)
            self.assertIn(
                'lower version already installed',
                mock_err.getvalue())
        # Attempt to get download list
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/cache/qvm-template',
            dl_list={}, version_selector=selector)
        self.assertEqual(mock_verify.mock_calls, [
            mock.call(template_file.name, '/tmp/keyring.gpg', nogpgcheck=False)
        ])
        # No confirmation since nothing needs to be done
        mock_confirm.assert_not_called()
        # Nothing extracted / installed
        mock_extract.assert_not_called()
        mock_call.assert_not_called()
        # Cache directory created
        self.assertEqual(mock_mkdirs.mock_calls, [
            mock.call(args.cachedir, exist_ok=True)
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
    def test_221_upgrade_skip_higher(
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
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        for key, val in [
                ('name', 'test-vm'),
                ('epoch', '2'),
                ('version', '4.1'),
                ('release', '2021')]:
            self.app.expected_calls[(
                'test-vm',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        rpm_hdr = {
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
        mock_verify.return_value = rpm_hdr
        mock_dl_list.return_value = {}
        selector = qubesadmin.tools.qvm_template.VersionSelector.LATEST_HIGHER
        with mock.patch('qubesadmin.tools.qvm_template.LOCK_FILE', '/tmp/test.lock'), \
                tempfile.NamedTemporaryFile(suffix='.rpm') as template_file, \
                mock.patch('sys.stderr', new=io.StringIO()) as mock_err:
            args = argparse.Namespace(
                templates=[template_file.name],
                keyring='/tmp/keyring.gpg',
                nogpgcheck=False,
                cachedir='/var/cache/qvm-template',
                repo_files=[],
                releasever='4.1',
                yes=False,
                keep_cache=True,
                allow_pv=False,
                pool=None
            )
            qubesadmin.tools.qvm_template.install(args, self.app,
                version_selector=selector,
                override_existing=True)
            self.assertIn(
                'higher version already installed',
                mock_err.getvalue())
        # Attempt to get download list
        self.assertEqual(mock_dl_list.mock_calls, [
            mock.call(args, self.app, version_selector=selector)
        ])
        mock_dl.assert_called_with(args, self.app,
            path_override='/var/cache/qvm-template',
            dl_list={}, version_selector=selector)
        self.assertEqual(mock_verify.mock_calls, [
            mock.call(template_file.name, '/tmp/keyring.gpg', nogpgcheck=False)
        ])
        # No confirmation since nothing needs to be done
        mock_confirm.assert_not_called()
        # Nothing extracted / installed
        mock_extract.assert_not_called()
        mock_call.assert_not_called()
        # Cache directory created
        self.assertEqual(mock_mkdirs.mock_calls, [
            mock.call(args.cachedir, exist_ok=True)
        ])
        self.assertAllCalled()

    def test_230_filter_version_latest(self):
        query_res = [
            qubesadmin.tools.qvm_template.Template(
                'fedora-31',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
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
                '0',
                '4.1',
                '20200102',
                'qubes-templates-itl-testing',
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
                '4.1',
                '20200102',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template\n for fedora-32\n'
            )
        ]
        results = qubesadmin.tools.qvm_template.filter_version(
            query_res,
            self.app
        )
        self.assertEqual(sorted(results), [
            qubesadmin.tools.qvm_template.Template(
                'fedora-31',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '0',
                '4.1',
                '20200102',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template\n for fedora-32\n'
            )
        ])
        self.assertAllCalled()

    def test_231_filter_version_reinstall(self):
        query_res = [
            qubesadmin.tools.qvm_template.Template(
                'fedora-31',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '0',
                '4.1',
                '20200102',
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
                '4.1',
                '20200102',
                'qubes-templates-itl-testing',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template\n for fedora-32\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00fedora-31 class=TemplateVM state=Halted\n' \
            b'fedora-32 class=TemplateVM state=Halted\n'
        for key, val in [
                ('name', 'fedora-31'),
                ('epoch', '0'),
                ('version', '4.1'),
                ('release', '20200101')]:
            self.app.expected_calls[(
                'fedora-31',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [
                ('name', 'fedora-32'),
                ('epoch', '0'),
                ('version', '4.1'),
                ('release', '20200101')]:
            self.app.expected_calls[(
                'fedora-32',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        results = qubesadmin.tools.qvm_template.filter_version(
            query_res,
            self.app,
            qubesadmin.tools.qvm_template.VersionSelector.REINSTALL
        )
        self.assertEqual(sorted(results), [
            qubesadmin.tools.qvm_template.Template(
                'fedora-31',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
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
            )
        ])
        self.assertAllCalled()

    def test_232_filter_version_upgrade(self):
        query_res = [
            qubesadmin.tools.qvm_template.Template(
                'fedora-31',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '0',
                '4.1',
                '20200102',
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
                '4.1',
                '20200102',
                'qubes-templates-itl-testing',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template\n for fedora-32\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00fedora-31 class=TemplateVM state=Halted\n' \
            b'fedora-32 class=TemplateVM state=Halted\n'
        for key, val in [
                ('name', 'fedora-31'),
                ('epoch', '0'),
                ('version', '4.1'),
                ('release', '20200101')]:
            self.app.expected_calls[(
                'fedora-31',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [
                ('name', 'fedora-32'),
                ('epoch', '0'),
                ('version', '4.1'),
                ('release', '20200101')]:
            self.app.expected_calls[(
                'fedora-32',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        results = qubesadmin.tools.qvm_template.filter_version(
            query_res,
            self.app,
            qubesadmin.tools.qvm_template.VersionSelector.LATEST_HIGHER
        )
        self.assertEqual(sorted(results), [
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '0',
                '4.1',
                '20200102',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template\n for fedora-32\n'
            )
        ])
        self.assertAllCalled()

    def test_233_filter_version_downgrade(self):
        query_res = [
            qubesadmin.tools.qvm_template.Template(
                'fedora-31',
                '0',
                '4.1',
                '20200101',
                'qubes-templates-itl',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-31',
                'Qubes template\n for fedora-31\n'
            ),
            qubesadmin.tools.qvm_template.Template(
                'fedora-32',
                '0',
                '4.1',
                '20200102',
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
                '4.1',
                '20200102',
                'qubes-templates-itl-testing',
                1048576,
                datetime.datetime(2020, 1, 23, 4, 56),
                'GPL',
                'https://qubes-os.org',
                'Qubes template for fedora-32',
                'Qubes template\n for fedora-32\n'
            )
        ]
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00fedora-31 class=TemplateVM state=Halted\n' \
            b'fedora-32 class=TemplateVM state=Halted\n'
        for key, val in [
                ('name', 'fedora-31'),
                ('epoch', '0'),
                ('version', '4.1'),
                ('release', '20200101')]:
            self.app.expected_calls[(
                'fedora-31',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        for key, val in [
                ('name', 'fedora-32'),
                ('epoch', '0'),
                ('version', '4.1'),
                ('release', '20200102')]:
            self.app.expected_calls[(
                'fedora-32',
                'admin.vm.feature.Get',
                f'template-{key}',
                None)] = b'0\0' + val.encode()
        results = qubesadmin.tools.qvm_template.filter_version(
            query_res,
            self.app,
            qubesadmin.tools.qvm_template.VersionSelector.LATEST_LOWER
        )
        self.assertEqual(sorted(results), [
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
            )
        ])
        self.assertAllCalled()

    @mock.patch('os.path.exists')
    def test_240_qubes_release(self, mock_exists):
        # /usr/share/qubes/marker-vm does not exist
        mock_exists.return_value = False
        marker_vm = '''
NAME=Qubes
VERSION="4.2 (R4.2)"
ID=qubes
# Some comments here
VERSION_ID=4.2
PRETTY_NAME="Qubes 4.2 (R4.2)"
ANSI_COLOR="0;31"
CPE_NAME="cpe:/o:ITL:qubes:4.2"
'''
        with mock.patch('builtins.open', mock.mock_open(read_data=marker_vm)) \
                as mock_open:
            ret = qubesadmin.tools.qvm_template.qubes_release()
            self.assertEqual(ret, '4.2')
            self.assertEqual(mock_exists.mock_calls, [
                mock.call('/usr/share/qubes/marker-vm')
            ])
            mock_open.assert_called_with('/etc/os-release', 'r',
                                         encoding='ascii')
        self.assertAllCalled()

    @mock.patch('os.path.exists')
    def test_241_qubes_release_quotes(self, mock_exists):
        # /usr/share/qubes/marker-vm does not exist
        mock_exists.return_value = False
        os_rel = '''
NAME=Qubes
VERSION="4.2 (R4.2)"
ID=qubes
# Some comments here
VERSION_ID="4.2"
PRETTY_NAME="Qubes 4.2 (R4.2)"
ANSI_COLOR="0;31"
CPE_NAME="cpe:/o:ITL:qubes:4.2"
'''
        with mock.patch('builtins.open', mock.mock_open(read_data=os_rel)) \
                as mock_open:
            ret = qubesadmin.tools.qvm_template.qubes_release()
            self.assertEqual(ret, '4.2')
            self.assertEqual(mock_exists.mock_calls, [
                mock.call('/usr/share/qubes/marker-vm')
            ])
            mock_open.assert_called_with('/etc/os-release', 'r',
                                         encoding='ascii')
        self.assertAllCalled()

    @mock.patch('os.path.exists')
    def test_242_qubes_release_quotes(self, mock_exists):
        # /usr/share/qubes/marker-vm does exist
        mock_exists.return_value = True
        marker_vm = '''
# This is just a marker file for Qubes OS VM.
# This VM have tools for Qubes version:
4.2
'''
        with mock.patch('builtins.open', mock.mock_open(read_data=marker_vm)) \
                as mock_open:
            ret = qubesadmin.tools.qvm_template.qubes_release()
            self.assertEqual(ret, '4.2')
            self.assertEqual(mock_exists.mock_calls, [
                mock.call('/usr/share/qubes/marker-vm')
            ])
            mock_open.assert_called_with('/usr/share/qubes/marker-vm', 'r',
                                         encoding='ascii')
        self.assertAllCalled()

    @skipUnless(which('rpmcanon'), 'rpmcanon not installed')
    def test_250_qrexec_download_success(self):
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        args = argparse.Namespace(
            repo_files=[],
            releasever='4.1',
            updatevm='test-vm',
            repos=[],
            quiet=True
        )
        def execute(pubkey, packagename):
            with open(packagename, 'rb') as s:
                b = self.app.expected_service_calls[
                    ('test-vm', 'qubes.TemplateDownload')] = s.read()
            with tempfile.NamedTemporaryFile() as fd:
                qubesadmin.tools.qvm_template.qrexec_download(
                    args, self.app, 'fedora-31:4.0', key=pubkey, path=fd.name)
                qubesadmin.tools.qvm_template.verify_rpm(fd.name, pubkey, template_name='invalid')
            with self.assertRaises(qubesadmin.tools.qvm_template.SignatureVerificationError):
                qubesadmin.tools.qvm_template.verify_rpm('/dev/null', pubkey, template_name='invalid')
        gen_rpm(True, execute)
        self.assertAllCalled()

    @skipUnless(which('rpmcanon'), 'rpmcanon not installed')
    def test_251_qrexec_download_fail(self):
        rand_bytes = os.urandom(128)
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00test-vm class=TemplateVM state=Halted\n'
        self.app.expected_service_calls[
            ('test-vm', 'qubes.TemplateDownload')] = rand_bytes
        args = argparse.Namespace(
            repo_files=[],
            releasever='4.1',
            updatevm='test-vm',
            repos=[],
            quiet=True
        )
        def execute(pubkey, packagename):
            with open(packagename, 'rb') as s:
                b = self.app.expected_service_calls[
                    ('test-vm', 'qubes.TemplateDownload')] = s.read()
            with tempfile.NamedTemporaryFile() as fd:
                with self.assertRaises(ConnectionError):
                    qubesadmin.tools.qvm_template.qrexec_download(
                        args, self.app, 'fedora-31:4.0', key=pubkey, path=fd.name)
        gen_rpm(False, execute)
        self.assertAllCalled()

    @mock.patch('qubesadmin.tools.qvm_template.repolist')
    def test_300_repo_files_glob(self, mock_repolist):
        with tempfile.TemporaryDirectory() as temp_dir:
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
            with open(temp_dir + '/first.repo', 'w') as f:
                f.write(repo_str1)
            with open(temp_dir + '/second.repo', 'w') as f:
                f.write(repo_str2)

            qubesadmin.tools.qvm_template.main(
                ['--updatevm=',
                 '--repo-files=' + temp_dir + '/*.repo', 'repolist'])
            mock_repolist.assert_called_once()

            self.assertCountEqual(
                [temp_dir + '/first.repo', temp_dir + '/second.repo'],
                mock_repolist.mock_calls[0][1][0].repo_files
            )
        self.assertAllCalled()

    @mock.patch('os.getuid')
    @mock.patch('subprocess.check_call')
    @mock.patch('rpm.TransactionSet')
    def test_400_migrate_from_rpmdb(self, mock_rpm_ts, mock_check_call, mock_getuid):
        mock_getuid.return_value = 0
        build_time = '2020-09-01 14:30:00'  # 1598970600
        install_time = '2020-09-01 13:30:00'  # 1598967000
        mock_rpm_ts.return_value.dbMatch.return_value = [
            {
                rpm.RPMTAG_NAME        : 'non-template',
                rpm.RPMTAG_BUILDTIME   : 1598970600,
                rpm.RPMTAG_INSTALLTIME : 1598967000,
                rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
                rpm.RPMTAG_EPOCHNUM    : 2,
                rpm.RPMTAG_LICENSE     : 'GPL',
                rpm.RPMTAG_RELEASE     : '2020',
                rpm.RPMTAG_SUMMARY     : 'Summary',
                rpm.RPMTAG_URL         : 'https://qubes-os.org',
                rpm.RPMTAG_VERSION     : '4.1'
            },
            {
                rpm.RPMTAG_NAME        : 'qubes-template-test-existing',
                rpm.RPMTAG_BUILDTIME   : 1598970600,
                rpm.RPMTAG_INSTALLTIME : 1598967000,
                rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
                rpm.RPMTAG_EPOCHNUM    : 2,
                rpm.RPMTAG_LICENSE     : 'GPL',
                rpm.RPMTAG_RELEASE     : '2020',
                rpm.RPMTAG_SUMMARY     : 'Summary',
                rpm.RPMTAG_URL         : 'https://qubes-os.org',
                rpm.RPMTAG_VERSION     : '4.1'
            },
            {
                rpm.RPMTAG_NAME        : 'qubes-template-test-migrated',
                rpm.RPMTAG_BUILDTIME   : 1598970600,
                rpm.RPMTAG_INSTALLTIME : 1598967000,
                rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
                rpm.RPMTAG_EPOCHNUM    : 2,
                rpm.RPMTAG_LICENSE     : 'GPL',
                rpm.RPMTAG_RELEASE     : '2020',
                rpm.RPMTAG_SUMMARY     : 'Summary',
                rpm.RPMTAG_URL         : 'https://qubes-os.org',
                rpm.RPMTAG_VERSION     : '4.1'
            },
            {
                rpm.RPMTAG_NAME        : 'qubes-template-test-removed',
                rpm.RPMTAG_BUILDTIME   : 1598970600,
                rpm.RPMTAG_INSTALLTIME : 1598967000,
                rpm.RPMTAG_DESCRIPTION : 'Desc\ndesc',
                rpm.RPMTAG_EPOCHNUM    : 2,
                rpm.RPMTAG_LICENSE     : 'GPL',
                rpm.RPMTAG_RELEASE     : '2020',
                rpm.RPMTAG_SUMMARY     : 'Summary',
                rpm.RPMTAG_URL         : 'https://qubes-os.org',
                rpm.RPMTAG_VERSION     : '4.1'
            },
        ]

        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\x00some-vm class=TemplateVM state=Halted\n' \
            b'test-existing class=TemplateVM state=Halted\n' \
            b'test-migrated class=TemplateVM state=Halted\n'
        for key, val in [
                ('name', 'test-existing'),
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
                'test-existing',
                'admin.vm.feature.Set',
                f'template-{key}',
                val.encode())] = b'0\0'
        self.app.expected_calls[(
            'test-existing',
            'admin.vm.property.Set',
            f'installed_by_rpm',
            b'False')] = b'0\0'
        self.app.expected_calls[(
            'test-migrated',
            'admin.vm.feature.Get',
            'template-name',
            None)] = b'0\0test-migrated'
        self.app.expected_calls[(
            'test-existing',
            'admin.vm.feature.Get',
            'template-name',
            None)] = b'2\0QubesFeatureNotFoundError\0\0No such feature\0'
        qubesadmin.tools.qvm_template.migrate_from_rpmdb(self.app)
        mock_check_call.assert_called_once_with([
            'rpm', '-e', '--justdb',
            'qubes-template-test-existing',
            'qubes-template-test-migrated',
            'qubes-template-test-removed'])
        self.assertAllCalled()
