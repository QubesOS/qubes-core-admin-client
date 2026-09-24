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

from functools import partial
from operator import delitem, setitem
from unittest.mock import patch

import qubesadmin.features
from qubesadmin.exc import PermissionDenied, QubesFeatureNotFoundError
import qubesadmin.tests


class TC_00_Features(qubesadmin.tests.QubesTestCase):
    def setUp(self):
        super().setUp()
        self.app.expected_calls[('dom0', 'admin.vm.List', None, None)] = \
            b'0\0test-vm class=AppVM state=Running\n' \
            b'test-vm2 class=AppVM state=Running\n' \
            b'test-vm3 class=AppVM state=Running\n'
        self.vm = self.app.domains['test-vm']
        self.features = qubesadmin.features.Features(self.vm)

    def test_000_list(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.List', None, None)] = \
            b'0\0feature1\nfeature2\n'
        self.assertEqual(sorted(self.vm.features.keys()),
            ['feature1', 'feature2'])
        self.assertAllCalled()

    def test_010_get(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Get', 'feature1', None)] = \
            b'0\0value1'
        self.assertEqual(self.vm.features['feature1'], 'value1')
        self.assertAllCalled()

    def test_011_get_none(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Get', 'feature1', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00feature1\x00'
        with self.assertRaises(KeyError):
            # pylint: disable=pointless-statement
            self.vm.features['feature1']
        self.assertAllCalled()

    def test_012_get_none(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Get', 'feature1', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00feature1\x00'
        with self.assertRaises(KeyError):
            self.vm.features.get('feature1', self.vm.features.NO_DEFAULT)
        self.assertAllCalled()

    def test_013_get_default(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Get', 'feature1', None)] = \
            b'2\x00QubesFeatureNotFoundError\x00\x00feature1\x00'
        self.assertEqual(self.vm.features.get('feature1', 'other'), 'other')
        self.assertAllCalled()

    def test_020_set(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'feature1', b'value')] = \
            b'0\0'
        self.vm.features['feature1'] = 'value'
        self.assertAllCalled()

    def test_021_set_bool(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'feature1', b'1')] = \
            b'0\0'
        self.vm.features['feature1'] = True
        self.assertAllCalled()

    def test_022_set_bool_false(self):
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'feature1', b'')] = \
            b'0\0'
        self.vm.features['feature1'] = False
        self.assertAllCalled()


class TC_10_FeatureCache(qubesadmin.tests.QubesTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.app.cache_enabled = True
        self.vm = self.app.domains.get_blind('test-vm')

    def expect_read(self, method: str, response: bytes | list[bytes],
                    feature: str | None = None) -> None:
        self.app.expected_calls[
            ('test-vm', f'admin.vm.feature.{method}', feature, None)] = response

    def test_direct_values(self) -> None:
        for value in ('value', '', '0'):
            with self.subTest(value=value):
                self.vm.features.clear_cache()
                self.app.actual_calls.clear()
                self.expect_read('Get', b'0\0' + value.encode(), 'feature')
                values = [self.vm.features['feature'] for _ in range(2)]
                self.assertEqual(
                    f'{values!r}; calls={len(self.app.actual_calls)}',
                    f'{[value, value]!r}; calls=1')

    def test_missing_defaults(self) -> None:
        self.expect_read('Get',
            b'2\0QubesFeatureNotFoundError\0\0missing feature\0', 'missing')
        values = (self.vm.features.get('missing'),
                  self.vm.features.get('missing', 'fallback'),
                  self.vm.features.get('missing', False))
        self.assertEqual(
            f'{values!r}; calls={len(self.app.actual_calls)}',
            "(None, 'fallback', False); calls=1")

    def test_lists(self) -> None:
        for names in ('second\nfirst\n', ''):
            with self.subTest(names=names):
                self.vm.features.clear_cache()
                self.app.actual_calls.clear()
                self.expect_read('List', b'0\0' + names.encode())
                first = ','.join(self.vm.features.keys())
                second = ','.join(self.vm.features)
                expected = ','.join(names.splitlines())
                self.assertEqual(
                    f'{first}; {second}; calls={len(self.app.actual_calls)}',
                    f'{expected}; {expected}; calls=1')

    def test_items_delegation(self) -> None:
        with patch.object(qubesadmin.features.Features, '__iter__',
                          return_value=iter(('second', 'first'))), \
             patch.object(qubesadmin.features.Features, '__getitem__',
                          side_effect=lambda feature: f'value-{feature}'):
            values = '; '.join(f'{key}={value}'
                               for key, value in self.vm.features.items())
        self.assertEqual(values, 'second=value-second; first=value-first')

    def test_filtered_list(self) -> None:
        self.expect_read('List', b'0\0visible\n')
        self.expect_read('Get', b'0\0readable', 'omitted')
        names = ','.join(self.vm.features)
        value = self.vm.features['omitted']
        cached_names = ','.join(self.vm.features)
        cached_value = self.vm.features['omitted']
        self.assertEqual(
            f'{names}; {value}; {cached_names}; {cached_value}; '
            f'calls={len(self.app.actual_calls)}',
            'visible; readable; visible; readable; calls=2')

    def test_denied_list(self) -> None:
        self.expect_read('List', b'2\0PermissionDenied\0\0denied\0')
        self.expect_read('Get', b'0\0readable', 'feature')
        for _ in range(2):
            with self.assertRaises(qubesadmin.exc.PermissionDenied):
                list(self.vm.features)
        values = [self.vm.features['feature'] for _ in range(2)]
        self.assertEqual(
            f'{values!r}; calls={len(self.app.actual_calls)}',
            "['readable', 'readable']; calls=3")

    def test_errors_not_cached(self) -> None:
        for response, error_type, methods in (
                (b'2\0PermissionDenied\0\0denied\0',
                 qubesadmin.exc.PermissionDenied, ('Get',)),
                (b'', qubesadmin.exc.QubesDaemonAccessError, ('Get', 'List')),
                (b'invalid', qubesadmin.exc.QubesDaemonCommunicationError,
                 ('Get', 'List')),
                (b'0\0\xff', UnicodeDecodeError, ('Get', 'List')),
                (b'2\0QubesVMNotFoundError\0\0gone\0',
                 qubesadmin.exc.QubesVMNotFoundError, ('Get', 'List'))):
            for method in methods:
                feature = 'feature' if method == 'Get' else None
                with self.subTest(response=response, method=method):
                    self.app.actual_calls.clear()
                    self.expect_read(method, response, feature)
                    for _ in range(2):
                        with self.assertRaises(error_type):
                            if feature is None:
                                list(self.vm.features)
                            else:
                                self.vm.features.get(
                                    feature, self.vm.features.NO_DEFAULT)
                    self.assertEqual(len(self.app.actual_calls), 2)

    def test_disabled_reads_are_not_cached(self) -> None:
        self.app.cache_enabled = False
        self.expect_read('Get', b'0\0value', 'feature')
        self.expect_read('List', b'0\0feature\n')
        for _ in range(2):
            self.vm.features.get('feature')
            list(self.vm.features)
        self.assertEqual(len(self.app.actual_calls), 4)

    def test_clear_cache(self) -> None:
        self.expect_read('Get', [b'0\0old', b'0\0new'], 'feature')
        self.expect_read('Get', [
            b'2\0QubesFeatureNotFoundError\0\0missing\0', b'0\0found'],
            'missing')
        self.expect_read('List', [b'0\0old\n', b'0\0new\n'])
        self.vm.features.get('feature')
        self.vm.features.get('missing')
        list(self.vm.features)
        self.vm.features.clear_cache()
        calls_after_clear = len(self.app.actual_calls)
        values = (self.vm.features['feature'], self.vm.features['missing'],
                  ','.join(self.vm.features))
        self.assertEqual(
            f'{values!r}; calls after clear={calls_after_clear}; '
            f'total calls={len(self.app.actual_calls)}',
            "('new', 'found', 'new'); calls after clear=3; total calls=6")

    def test_vm_caches_are_independent(self) -> None:
        self.expect_read('Get', b'0\0first', 'feature')
        self.app.expected_calls[
            ('other-vm', 'admin.vm.feature.Get', 'feature', None)] = b'0\0other'
        other_vm = self.app.domains.get_blind('other-vm')
        values = [vm.features['feature'] for vm in
                  (self.vm, other_vm, self.vm, other_vm)]
        self.assertEqual(
            f'{values!r}; calls={len(self.app.actual_calls)}',
            "['first', 'other', 'first', 'other']; calls=2")

    def read_value_and_names(self) -> str:
        return (f'{self.vm.features.get("feature")}, '
                f'{",".join(self.vm.features)}')

    def test_set_caches_serialized_value(self) -> None:
        for value, stored in (('write', 'write'), (True, '1'), (False, '')):
            with self.subTest(value=value):
                self.vm.features.clear_cache()
                self.app.actual_calls.clear()
                self.app.expected_calls[('test-vm', 'admin.vm.feature.Set',
                                         'feature', stored.encode())] = b'0\0'
                self.vm.features['feature'] = value
                self.assertEqual(
                    f'{self.vm.features["feature"]!r}; '
                    f'calls={len(self.app.actual_calls)}',
                    f'{stored!r}; calls=1')

    def test_writes_update_names_and_missing(self) -> None:
        self.expect_read('List', b'0\0other\n')
        self.expect_read('Get',
            b'2\0QubesFeatureNotFoundError\0\0missing\0', 'feature')
        before = self.read_value_and_names()
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Set', 'feature', b'write')] = b'0\0'
        self.vm.features['feature'] = 'write'
        after_set = self.read_value_and_names()
        self.app.expected_calls[
            ('test-vm', 'admin.vm.feature.Remove', 'feature', None)] = b'0\0'
        del self.vm.features['feature']
        after_removal = self.read_value_and_names()
        self.assertEqual(
            f'{before}; {after_set}; {after_removal}; '
            f'calls={len(self.app.actual_calls)}',
            'None, other; write, other,feature; None, other; calls=5')

    def test_failed_writes_keep_cache(self) -> None:
        for method, payload, mutation in (
                ('Set', b'write',
                 partial(setitem, self.vm.features, 'feature', 'write')),
                ('Remove', None,
                 partial(delitem, self.vm.features, 'feature'))):
            with self.subTest(method=method):
                self.vm.features.clear_cache()
                self.app.actual_calls.clear()
                self.expect_read('Get', b'0\0old', 'feature')
                self.expect_read('List', b'0\0feature\n')
                before = self.read_value_and_names()
                self.app.expected_calls[
                    ('test-vm', f'admin.vm.feature.{method}', 'feature',
                     payload)] = b'2\0PermissionDenied\0\0denied\0'
                with self.assertRaises(PermissionDenied):
                    mutation()
                self.assertEqual(
                    f'{before}; {self.read_value_and_names()}; '
                    f'calls={len(self.app.actual_calls)}',
                    'old, feature; old, feature; calls=3')

    def test_template_checks_always_use_server(self) -> None:
        self.expect_read('Get', b'0\0direct', 'feature')
        self.expect_read('CheckWithTemplate',
                         [b'0\0inherited', b'0\0changed'], 'feature')
        direct = self.vm.features['feature']
        inherited = [self.vm.features.check_with_template('feature')
                     for _ in range(2)]
        self.assertEqual(
            f'{direct}; {inherited!r}; calls={len(self.app.actual_calls)}',
            "direct; ['inherited', 'changed']; calls=3")

    def test_missing_template_checks_always_use_server(self) -> None:
        self.expect_read('CheckWithTemplate',
                         b'2\0QubesFeatureNotFoundError\0\0missing\0',
                         'feature')
        values = (self.vm.features.check_with_template('feature'),
                  self.vm.features.check_with_template('feature', 'default'))
        with self.assertRaises(QubesFeatureNotFoundError):
            self.vm.features.check_with_template(
                'feature', self.vm.features.NO_DEFAULT)
        self.assertEqual(
            f'{values!r}; calls={len(self.app.actual_calls)}',
            "(None, 'default'); calls=3")

    def test_cached_misses_raise_fresh_exceptions(self) -> None:
        for message in ('001', '²', '100% missing'):
            with self.subTest(message=message):
                self.vm.features.clear_cache()
                self.app.actual_calls.clear()
                self.expect_read('Get', b'2\0QubesFeatureNotFoundError\0\0' +
                                 message.replace('%', '%%').encode() + b'\0',
                                 'missing')
                with self.assertRaises(QubesFeatureNotFoundError) as first:
                    self.vm.features.get('missing', self.vm.features.NO_DEFAULT)
                with self.assertRaises(QubesFeatureNotFoundError) as second:
                    self.vm.features.get('missing', self.vm.features.NO_DEFAULT)
                self.assertEqual(
                    f'{first.exception}; {second.exception}; '
                    f'fresh={first.exception is not second.exception}; '
                    f'calls={len(self.app.actual_calls)}',
                    f'{message}; {message}; fresh=True; calls=1')
