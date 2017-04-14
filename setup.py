# vim: fileencoding=utf-8

import setuptools
import sys

exclude=[]
if sys.version_info[0:2] < (3, 5):
    exclude = ['qubesmgmt.events', 'qubesmgmt.tools', 'qubesmgmt.tests.tools']

if __name__ == '__main__':
    setuptools.setup(
        name='qubesmgmt',
        version=open('version').read().strip(),
        author='Invisible Things Lab',
        author_email='marmarek@invisiblethingslab.com',
        description='Qubes mgmt API package',
        license='LGPL2.1+',
        url='https://www.qubes-os.org/',
        packages=setuptools.find_packages(exclude=exclude),
        entry_points={
            'qubesmgmt.vm': [
                'AppVM = qubesmgmt.vm:AppVM',
                'TemplateVM = qubesmgmt.vm:TemplateVM',
                'StandaloneVM = qubesmgmt.vm:StandaloneVM',
                'AdminVM = qubesmgmt.vm:AdminVM',
                'DispVM = qubesmgmt.vm:DispVM',
            ],
        },

        )
