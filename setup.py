# vim: fileencoding=utf-8

import setuptools
import sys

exclude=[]
if sys.version_info[0:2] < (3, 5):
    exclude = ['qubesadmin.events', 'qubesadmin.tools', 'qubesadmin.tests.tools']

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
        entry_points={
            'qubesadmin.vm': [
                'AppVM = qubesadmin.vm:AppVM',
                'TemplateVM = qubesadmin.vm:TemplateVM',
                'StandaloneVM = qubesadmin.vm:StandaloneVM',
                'AdminVM = qubesadmin.vm:AdminVM',
                'DispVM = qubesadmin.vm:DispVM',
            ],
        },

        )
