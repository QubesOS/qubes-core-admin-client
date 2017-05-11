#!/usr/bin/python3

import os
import sys
sys.path.insert(0, os.path.abspath('../'))

import argparse
import qubesmgmt.dochelpers

parser = argparse.ArgumentParser(description='prepare new manpage for command')
parser.add_argument('command', metavar='COMMAND',
    help='program\'s command name; this should translate to '
        'qubesmgmt.tools.<command_name>')

def main():
    args = parser.parse_args()
    sys.stdout.write(qubesmgmt.dochelpers.prepare_manpage(args.command))

if __name__ == '__main__':
    main()
