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

# pylint: disable=missing-docstring

import qubesadmin.tests.vm


class TC_00_Actions(qubesadmin.tests.vm.VMTestCase):
    def test_000_start(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Start', None, None)] = \
            b'0\x00'
        self.vm.start()
        self.assertAllCalled()

    def test_001_shutdown(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Shutdown', None, None)] = \
            b'0\x00'
        self.vm.shutdown()
        self.assertAllCalled()

    def test_002_kill(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Kill', None, None)] = \
            b'0\x00'
        self.vm.kill()
        self.assertAllCalled()

    def test_003_pause(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Pause', None, None)] = \
            b'0\x00'
        self.vm.pause()
        self.assertAllCalled()

    def test_004_unpause(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Unpause', None, None)] = \
            b'0\x00'
        self.vm.unpause()
        self.assertAllCalled()

    def test_005_suspend(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Suspend', None, None)] = \
            b'0\x00'
        self.vm.suspend()
        self.assertAllCalled()

    def test_006_resume(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.Resume', None, None)] = \
            b'0\x00'
        self.vm.resume()
        self.assertAllCalled()

    def test_010_run_linux(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate', 'os', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature \'os\' not set\x00'
        self.vm.run('some command')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {}),
            ('test-vm', 'qubes.VMShell', b'some command; exit\n'),
        ])

    def test_011_run_windows(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate', 'os', None)] = \
            b'0\x00Windows'
        self.vm.run('some command')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {}),
            ('test-vm', 'qubes.VMShell', b'some command& exit\n'),
        ])

    def test_015_run_with_args_shell(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate', 'vmexec',
             None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00' \
            b'Feature \'vmexec\' not set\x00'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate', 'os', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00Feature \'os\' not set\x00'
        self.vm.run_with_args('some', 'argument with spaces',
            'and $pecial; chars')
        self.assertEqual(self.app.service_calls, [
            ('test-vm', 'qubes.VMShell', {}),
            ('test-vm', 'qubes.VMShell',
                b'some \'argument with spaces\' \'and $pecial; chars\'; '
                b'exit\n'),
        ])

    def test_016_run_with_args_exec(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.CheckWithTemplate', 'vmexec',
             None)] = \
            b'0\x001'
        self.vm.run_with_args('some', 'argument with spaces',
            'and $pecial; chars')
        self.assertEqual(self.app.service_calls, [
            ('test-vm',
             'qubes.VMExec+some+argument-20with-20spaces+and-20-24'
             'pecial-3B-20chars',
             {}),
            ('test-vm',
             'qubes.VMExec+some+argument-20with-20spaces+and-20-24'
             'pecial-3B-20chars',
             b''),
        ])
