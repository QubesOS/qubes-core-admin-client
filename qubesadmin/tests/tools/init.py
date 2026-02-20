#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2015  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2015  Wojtek Porczyk <woju@invisiblethingslab.com>
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

import argparse

import qubesadmin
import qubesadmin.tools

import qubesadmin.tests

class TC_00_PropertyAction(qubesadmin.tests.QubesTestCase):
    def test_000_default(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--property', '-p',
            action=qubesadmin.tools.PropertyAction)
        parser.set_defaults(properties={'defaultprop': 'defaultvalue'})

        args = parser.parse_args([])
        self.assertIn(
            ('defaultprop', 'defaultvalue'), args.properties.items())

    def test_001_set_prop(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--property', '-p',
            action=qubesadmin.tools.PropertyAction)

        args = parser.parse_args(['-p', 'testprop=testvalue'])
        self.assertIn(
            ('testprop', 'testvalue'), args.properties.items())

    def test_002_set_prop_2(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--property', '-p',
            action=qubesadmin.tools.PropertyAction)
        parser.set_defaults(properties={'defaultprop': 'defaultvalue'})

        args = parser.parse_args(
            ['-p', 'testprop=testvalue', '-p', 'testprop2=testvalue2'])
        self.assertEqual(
            {'testprop': 'testvalue', 'testprop2': 'testvalue2'} | \
            args.properties,
            args.properties)

    def test_003_set_prop_with_default(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--property', '-p',
            action=qubesadmin.tools.PropertyAction)
        parser.set_defaults(properties={'defaultprop': 'defaultvalue'})

        args = parser.parse_args(['-p', 'testprop=testvalue'])
        self.assertEqual(
            {'testprop': 'testvalue', 'defaultprop': 'defaultvalue'} | \
            args.properties,
            args.properties)

    def test_003_set_prop_override_default(self):
        # pylint: disable=invalid-name
        parser = argparse.ArgumentParser()
        parser.add_argument('--property', '-p',
            action=qubesadmin.tools.PropertyAction)
        parser.set_defaults(properties={'testprop': 'defaultvalue'})

        args = parser.parse_args(['-p', 'testprop=testvalue'])
        self.assertIn(
            ('testprop', 'testvalue'),
            args.properties.items())


class TC_01_SinglePropertyAction(qubesadmin.tests.QubesTestCase):
    def test_000_help(self):
        parser = argparse.ArgumentParser()
        action = parser.add_argument('--testprop', '-T',
            action=qubesadmin.tools.SinglePropertyAction)
        self.assertIn('testprop', action.help)

    def test_001_help_const(self):
        parser = argparse.ArgumentParser()
        action = parser.add_argument('--testprop', '-T',
            action=qubesadmin.tools.SinglePropertyAction,
            const='testvalue')
        self.assertIn('testvalue', action.help)

    def test_100_default(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--testprop', '-T',
            action=qubesadmin.tools.SinglePropertyAction)
        parser.set_defaults(properties={'testprop': 'defaultvalue'})

        args = parser.parse_args([])
        self.assertIn(
            ('testprop', 'defaultvalue'), args.properties.items())

    def test_101_set_prop(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--testprop', '-T',
            action=qubesadmin.tools.SinglePropertyAction)
        args = parser.parse_args(['-T', 'testvalue'])
        self.assertIn(
            ('testprop', 'testvalue'), args.properties.items())

    def test_102_set_prop_dest(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--testprop', '-T', dest='otherprop',
            action=qubesadmin.tools.SinglePropertyAction)
        args = parser.parse_args(['-T', 'testvalue'])
        self.assertIn(
            ('otherprop', 'testvalue'), args.properties.items())

    def test_103_set_prop_const(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--testprop', '-T',
            action=qubesadmin.tools.SinglePropertyAction,
            const='testvalue')
        args = parser.parse_args(['-T'])
        self.assertIn(
            ('testprop', 'testvalue'), args.properties.items())

    def test_104_set_prop_const_override(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--testprop', '-T',
            action=qubesadmin.tools.SinglePropertyAction,
            const='testvalue')
        args = parser.parse_args(['-T', 'override'])
        self.assertIn(
            ('testprop', 'override'), args.properties.items())

    def test_105_set_prop_positional(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('testprop',
            action=qubesadmin.tools.SinglePropertyAction)
        args = parser.parse_args(['testvalue'])
        self.assertIn(
            ('testprop', 'testvalue'), args.properties.items())
