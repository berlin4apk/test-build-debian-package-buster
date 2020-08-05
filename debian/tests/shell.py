#!/usr/bin/env python3

# Copyright 2019 Canonical Ltd.
# Authors:
# - dann frazier <dann.frazier@canonical.com>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import atexit
import os
import pexpect
import shutil
import sys
import tempfile


ArchImageMap = {
    'AARCH64': ['/usr/share/AAVMF/AAVMF_CODE.fd',
                '/usr/share/AAVMF/AAVMF_VARS.fd'],
    'ARM': ['/usr/share/AAVMF/AAVMF32_CODE.fd',
            '/usr/share/AAVMF/AAVMF32_VARS.fd'],
    'X64': ['/usr/share/OVMF/OVMF_CODE.fd',
            '/usr/share/OVMF/OVMF_VARS.fd']
}


def cleanup_file(f):
    os.unlink(f)


def spawn_qemu(arch):
    if arch == 'X64':
        cmd = ['/usr/bin/qemu-system-x86_64']
    elif arch in ['AARCH64', 'ARM']:
        cmd = ['/usr/bin/qemu-system-aarch64']
    else:
        raise ValueError

    # Based on the args used by ovmf-vars-generator
    cmd = cmd + ['-no-user-config', '-nodefaults', '-m', '256',
                 '-smp', '2,sockets=2,cores=1,threads=1', '-display', 'none',
                 '-serial', 'stdio']

    if arch == 'X64':
        cmd = cmd + ['-machine', 'pc,accel=tcg']
        cmd = cmd + ['-chardev', 'pty,id=charserial1',
                     '-device', 'isa-serial,chardev=charserial1,id=serial1']
    elif arch in ['AARCH64', 'ARM']:
        cmd = cmd + ['-machine', 'virt', '-cpu']
        if arch == 'AARCH64':
            cmd = cmd + ['cortex-a57']
        elif arch == 'ARM':
            cmd = cmd + ['cortex-a15']
        else:
            raise ValueError
        cmd = cmd + ['-device', 'virtio-serial-device']

    codepath = ArchImageMap[arch][0]
    (varsfile, varspath) = tempfile.mkstemp()
    shutil.copy(ArchImageMap[arch][1], varspath)
    atexit.register(cleanup_file, varspath)

    cmd = cmd + [
        '-drive',
        'file=%s,if=pflash,format=raw,unit=0,readonly=on' % (codepath),
        '-drive',
        'file=%s,if=pflash,format=raw,unit=1,readonly=off' % (varspath),
        ]

    return pexpect.spawn(' '.join(cmd))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test EDK2 images in QEMU.')
    parser.add_argument('--arch', dest='arch')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    child = spawn_qemu(args.arch)
    if args.debug:
        child.logfile = sys.stdout.buffer
    try:
        while True:
            i = child.expect(
                [
                    'Press .* or any other key to continue',
                    'Shell> '
                ],
                timeout=60,
            )
            if i == 0:
                child.sendline('\x1b')
                continue
            if i == 1:
                child.sendline('reset -s')
                break
    except (pexpect.EOF, pexpect.TIMEOUT) as err:
        sys.stderr.write("%s\n" % (err))
