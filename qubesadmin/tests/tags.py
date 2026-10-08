# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

# pylint: disable=missing-docstring

from operator import contains
from unittest.mock import Mock, call, patch

from qubesadmin.exc import PermissionDenied
import qubesadmin.tests
import qubesadmin.tags

class TC_00_Tags(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n' \
            b'test-vm3 class=AppVM state=Running\n'
        self.vm = self.app.domains['test-vm']
        self.tags = qubesadmin.tags.Tags(self.vm)

    def test_000_list(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.List', None, None)] = \
            b'0\0tag1\ntag2\n'
        self.assertEqual(sorted(self.tags),
            ['tag1', 'tag2'])
        self.assertAllCalled()

    def test_010_get(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Get', 'tag1', None)] = \
            b'0\x001'
        self.assertIn('tag1', self.tags)
        self.assertAllCalled()

    def test_011_get_missing(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Get', 'tag1', None)] = \
            b'0\x000'
        self.assertNotIn('tag1', self.tags)
        self.assertAllCalled()

    def test_020_set(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Set', 'tag1', None)] = b'0\0'
        self.tags.add('tag1')
        self.assertAllCalled()

    def test_030_update(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Set', 'tag1', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Set', 'tag2', None)] = b'0\0'
        self.tags.update(['tag1', 'tag2'])
        self.assertAllCalled()

    def test_031_update_from_other(self):
        self.app.expected_calls[
            ('test-vm2', 'admin.vm.tag.List', None, None)] = \
            b'0\0tag3\ntag4\n'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Set', 'tag3', None)] = b'0\0'
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Set', 'tag4', None)] = b'0\0'
        self.tags.update(self.app.domains['test-vm2'].tags)
        self.assertAllCalled()

    def test_040_remove(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Remove', 'tag1', None)] = \
            b'0\0'
        self.tags.remove('tag1')
        self.assertAllCalled()

    def test_040_remove_missing(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Remove', 'tag1', None)] = \
            b'2\0QubesTagNotFoundError\0\0Tag not set for domain test-vm: ' \
            b'tag1\0'
        with self.assertRaises(KeyError):
            self.tags.remove('tag1')
        self.assertAllCalled()

    def test_050_discard(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Remove', 'tag1', None)] = \
            b'0\0'
        self.tags.discard('tag1')
        self.assertAllCalled()

    def test_051_discard_missing(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.tag.Remove', 'tag1', None)] = \
            b'2\0QubesTagNotFoundError\0\0Tag not set for domain test-vm: ' \
            b'tag1\0'
        self.tags.discard('tag1')
        self.assertAllCalled()


class TC_10_TagCache(qubesadmin.tests.QubesTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.app.cache_enabled = True
        self.vm = self.app.domains.get_blind('test-vm')

    def expect_read(self, method: str, response: bytes | list[bytes],
                    tag: str | None = None) -> None:
        self.app.expected_calls[
            ('test-vm', f'admin.vm.tag.{method}', tag, None)] = response

    def test_membership(self) -> None:
        for response, is_present in ((b'1', True), (b'0', False), (b'', False)):
            with self.subTest(response=response):
                self.vm.tags.clear_cache()
                self.app.actual_calls.clear()
                self.expect_read('Get', b'0\0' + response, 'tag')
                values = ['tag' in self.vm.tags for _ in range(2)]
                self.assertEqual(values, [is_present, is_present])
                self.assertEqual(len(self.app.actual_calls), 1)

    def test_lists(self) -> None:
        for names in ('second\nfirst\n', ''):
            with self.subTest(names=names):
                self.vm.tags.clear_cache()
                self.app.actual_calls.clear()
                self.expect_read('List', b'0\0' + names.encode())
                values = [list(self.vm.tags) for _ in range(2)]
                expected = names.splitlines()
                self.assertEqual(values, [expected, expected])
                self.assertEqual(len(self.app.actual_calls), 1)

    def test_filtered_methods_are_independent(self) -> None:
        self.expect_read('List', b'0\0listed\n')
        self.expect_read('Get', b'0\x001', 'omitted')
        self.expect_read('Get', b'0\x000', 'listed')
        self.assertEqual(list(self.vm.tags), ['listed'])
        values = [('omitted' in self.vm.tags, 'listed' in self.vm.tags)
                  for _ in range(2)]
        self.assertEqual(values, [(True, False), (True, False)])
        self.assertEqual(list(self.vm.tags), ['listed'])
        self.assertEqual(len(self.app.actual_calls), 3)

    def test_denied_list(self) -> None:
        self.expect_read('List', b'2\0PermissionDenied\0\0denied\0')
        self.expect_read('Get', b'0\x001', 'tag')
        for _ in range(2):
            with self.assertRaises(qubesadmin.exc.PermissionDenied):
                list(self.vm.tags)
        values = ['tag' in self.vm.tags for _ in range(2)]
        self.assertEqual(values, [True, True])
        self.assertEqual(len(self.app.actual_calls), 3)

    def test_errors_not_cached(self) -> None:
        for response, error_type, methods in (
                (b'2\0PermissionDenied\0\0denied\0',
                 qubesadmin.exc.PermissionDenied, ('Get',)),
                (b'', qubesadmin.exc.QubesDaemonAccessError, ('Get', 'List')),
                (b'invalid', qubesadmin.exc.QubesDaemonCommunicationError,
                 ('Get', 'List')),
                (b'2\0QubesVMNotFoundError\0\0gone\0',
                 qubesadmin.exc.QubesVMNotFoundError, ('Get', 'List'))):
            for method in methods:
                tag = 'tag' if method == 'Get' else None
                with self.subTest(response=response, method=method):
                    self.app.actual_calls.clear()
                    self.expect_read(method, response, tag)
                    for _ in range(2):
                        with self.assertRaises(error_type):
                            if tag is None:
                                list(self.vm.tags)
                            else:
                                contains(self.vm.tags, tag)
                    self.assertEqual(len(self.app.actual_calls), 2)

    def test_list_decoding_errors_not_cached(self) -> None:
        self.expect_read('List', b'0\0\xff')
        for _ in range(2):
            with self.assertRaises(UnicodeDecodeError):
                list(self.vm.tags)
        self.assertEqual(len(self.app.actual_calls), 2)

    def test_disabled_reads_are_not_cached(self) -> None:
        self.app.cache_enabled = False
        self.expect_read('Get', b'0\x001', 'tag')
        self.expect_read('List', b'0\0tag\n')
        for _ in range(2):
            contains(self.vm.tags, 'tag')
            list(self.vm.tags)
        self.assertEqual(len(self.app.actual_calls), 4)

    def test_vm_caches_are_independent(self) -> None:
        self.expect_read('Get', b'0\x001', 'tag')
        self.app.expected_calls[
            ('other-vm', 'admin.vm.tag.Get', 'tag', None)] = b'0\x000'
        other_vm = self.app.domains.get_blind('other-vm')
        values = ['tag' in vm.tags for vm in
                  (self.vm, other_vm, self.vm, other_vm)]
        self.assertEqual(values, [True, False, True, False])
        self.assertEqual(len(self.app.actual_calls), 2)

    def test_clear_cache(self) -> None:
        self.expect_read('Get', [b'0\x001', b'0\x000'], 'tag')
        self.expect_read('List', [b'0\0tag\n', b'0\0new\n'])
        contains(self.vm.tags, 'tag')
        list(self.vm.tags)
        self.vm.tags.clear_cache()
        self.assertEqual(len(self.app.actual_calls), 2)
        self.assertNotIn('tag', self.vm.tags)
        self.assertEqual(list(self.vm.tags), ['new'])
        self.assertEqual(len(self.app.actual_calls), 4)

    def read_membership_and_names(self) -> tuple[bool, list[str]]:
        return 'tag' in self.vm.tags, list(self.vm.tags)

    def test_writes_update_cache(self) -> None:
        self.expect_read('List', b'0\0other\n')
        self.expect_read('Get', b'0\x000', 'tag')
        self.assertEqual(self.read_membership_and_names(), (False, ['other']))
        self.expect_read('Set', b'0\0', 'tag')
        self.vm.tags.add('tag')
        self.assertEqual(self.read_membership_and_names(),
                         (True, ['other', 'tag']))
        self.expect_read('Remove', b'0\0', 'tag')
        self.vm.tags.remove('tag')
        self.assertEqual(self.read_membership_and_names(), (False, ['other']))
        self.assertEqual(len(self.app.actual_calls), 4)

    def test_failed_writes_keep_cache(self) -> None:
        for method, mutation in (('Set', self.vm.tags.add),
                                 ('Remove', self.vm.tags.remove)):
            with self.subTest(method=method):
                self.vm.tags.clear_cache()
                self.app.actual_calls.clear()
                self.expect_read('Get', b'0\x001', 'tag')
                self.expect_read('List', b'0\0tag\n')
                self.assertEqual(self.read_membership_and_names(),
                                 (True, ['tag']))
                self.expect_read(method, b'2\0PermissionDenied\0\0denied\0',
                                 'tag')
                with self.assertRaises(PermissionDenied):
                    mutation('tag')
                self.assertEqual(self.read_membership_and_names(),
                                 (True, ['tag']))
                self.assertEqual(len(self.app.actual_calls), 3)

    def test_update_discard_delegation(self) -> None:
        calls = Mock()
        with patch.object(self.vm.tags, 'add', calls.add), \
             patch.object(self.vm.tags, 'remove', calls.remove):
            self.vm.tags.update(['tag'])
            self.vm.tags.discard('tag')
        self.assertEqual(calls.mock_calls,
                         [call.add('tag'), call.remove('tag')])
