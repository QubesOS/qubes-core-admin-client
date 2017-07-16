# vim: fileencoding=utf-8

import os
import setuptools
import sys

exclude=[]
if sys.version_info[0:2] < (3, 4):
    exclude += ['qubesadmin.tools', 'qubesadmin.tests.tools']
    exclude += ['qubesadmin.backup', 'qubesadmin.tests.backup']
if sys.version_info[0:2] < (3, 5):
    exclude += ['qubesadmin.events']

# don't import: import * is unreliable and there is no need, since this is
# compile time and we have source files
def get_console_scripts():
    if sys.version_info[0:2] >= (3, 4):
        for filename in os.listdir('./qubesadmin/tools'):
            basename, ext = os.path.splitext(os.path.basename(filename))
            if basename in ['__init__', 'dochelpers'] or ext != '.py':
                continue
            yield '{} = qubesadmin.tools.{}:main'.format(
                basename.replace('_', '-'), basename)


if __name__ == '__main__':
    setuptools.setup(
        name='qubesadmin',
        version=open('version').read().strip(),
        author='Invisible Things Lab',
        author_email='marmarek@invisiblethingslab.com',
        description='Qubes Admin API package',
        license='LGPL2.1+',
        url='https://www.qubes-os.org/',
        packages=setuptools.find_packages(exclude=exclude),
        package_data={
            'qubesadmin.tests.backup': ['*.xml'],
        },
        entry_points={
            'console_scripts': list(get_console_scripts()),
            'qubesadmin.vm': [
                'AppVM = qubesadmin.vm:AppVM',
                'TemplateVM = qubesadmin.vm:TemplateVM',
                'StandaloneVM = qubesadmin.vm:StandaloneVM',
                'AdminVM = qubesadmin.vm:AdminVM',
                'DispVM = qubesadmin.vm:DispVM',
            ],
        },

        )
