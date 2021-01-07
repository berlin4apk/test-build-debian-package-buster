#!/usr/bin/env python3

# Copyright 2019-2020 Canonical Ltd.
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

import pexpect
import shutil
import sys
import tempfile
import unittest


class BootToShellTest(unittest.TestCase):
    debug = False
    # Based on the args used by ovmf-vars-generator
    Qemu_Common_Params = [
        '-no-user-config', '-nodefaults',
        '-m', '256',
        '-smp', '2,sockets=2,cores=1,threads=1',
        '-display', 'none',
        '-serial', 'stdio',
    ]
    Qemu_Ovmf_Common_Params = [
        '-chardev', 'pty,id=charserial1',
        '-device', 'isa-serial,chardev=charserial1,id=serial1',
    ]
    Qemu_Qemu_Efi_Common_Params = [
        '-machine', 'virt',
        '-device', 'virtio-serial-device',
    ]

    class PflashParams:
        def __init__(self, code_path, vars_template_path):
            with tempfile.NamedTemporaryFile(delete=False) as varfile:
                self.varfile_path = varfile.name
                with open(vars_template_path, 'rb') as template:
                    shutil.copyfileobj(template, varfile)
                self.params = [
                    '-drive',
                    'file=%s,if=pflash,format=raw,unit=0,readonly=on' %
                    (code_path),
                    '-drive',
                    'file=%s,if=pflash,format=raw,unit=1,readonly=off' %
                    (varfile.name)
                ]

        def __del__(self):
            os.unlink(self.varfile_path)

    def run_cmd_check_shell(self, cmd):
        child = pexpect.spawn(' '.join(cmd))

        if self.debug:
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
                    child.sendline('reset -s\r')
                    break
        except (pexpect.EOF, pexpect.TIMEOUT) as err:
            self.fail("%s\n" % (err))

    def test_aavmf(self):
        cmd = [
            'qemu-system-aarch64',
            '-cpu', 'cortex-a57',
        ] + self.Qemu_Common_Params + self.Qemu_Qemu_Efi_Common_Params
        pflash = self.PflashParams(
            '/usr/share/AAVMF/AAVMF_CODE.fd',
            '/usr/share/AAVMF/AAVMF_VARS.fd',
        )
        cmd = cmd + pflash.params
        self.run_cmd_check_shell(cmd)

    def test_aavmf32(self):
        cmd = [
            'qemu-system-aarch64',
            '-cpu', 'cortex-a15',
        ] + self.Qemu_Common_Params + self.Qemu_Qemu_Efi_Common_Params
        pflash = self.PflashParams(
            '/usr/share/AAVMF/AAVMF32_CODE.fd',
            '/usr/share/AAVMF/AAVMF32_VARS.fd',
        )
        cmd = cmd + pflash.params
        self.run_cmd_check_shell(cmd)

    def test_ovmf_pc(self):
        cmd = [
            'qemu-system-x86_64',
            '-machine', 'pc,accel=tcg'
        ] + self.Qemu_Common_Params + self.Qemu_Ovmf_Common_Params
        pflash = self.PflashParams(
            '/usr/share/OVMF/OVMF_CODE.fd',
            '/usr/share/OVMF/OVMF_VARS.fd',
        )
        cmd = cmd + pflash.params
        self.run_cmd_check_shell(cmd)

    def test_ovmf_q35(self):
        cmd = [
            'qemu-system-x86_64',
            '-machine', 'q35,accel=tcg'
        ] + self.Qemu_Common_Params + self.Qemu_Ovmf_Common_Params
        pflash = self.PflashParams(
            '/usr/share/OVMF/OVMF_CODE.fd',
            '/usr/share/OVMF/OVMF_VARS.fd',
        )
        cmd = cmd + pflash.params
        self.run_cmd_check_shell(cmd)

    def test_ovmf_secboot(self):
        cmd = [
            'qemu-system-x86_64',
            '-machine', 'q35,accel=tcg',
            '-global', 'ICH9-LPC.disable_s3=1',
        ] + self.Qemu_Common_Params + self.Qemu_Ovmf_Common_Params
        pflash = self.PflashParams(
            '/usr/share/OVMF/OVMF_CODE.secboot.fd',
            '/usr/share/OVMF/OVMF_VARS.fd',
        )
        cmd = cmd + pflash.params
        self.run_cmd_check_shell(cmd)

    def test_ovmf_ms(self):
        cmd = [
            'qemu-system-x86_64',
            '-machine', 'q35,accel=tcg',
            '-global', 'ICH9-LPC.disable_s3=1',
        ] + self.Qemu_Common_Params + self.Qemu_Ovmf_Common_Params
        pflash = self.PflashParams(
            '/usr/share/OVMF/OVMF_CODE.ms.fd',
            '/usr/share/OVMF/OVMF_VARS.ms.fd',
        )
        cmd = cmd + pflash.params
        self.run_cmd_check_shell(cmd)

    def test_ovmf_4m(self):
        cmd = [
            'qemu-system-x86_64',
            '-machine', 'q35,accel=tcg'
        ] + self.Qemu_Common_Params + self.Qemu_Ovmf_Common_Params
        pflash = self.PflashParams(
            '/usr/share/OVMF/OVMF_CODE_4M.fd',
            '/usr/share/OVMF/OVMF_VARS_4M.fd',
        )
        cmd = cmd + pflash.params
        self.run_cmd_check_shell(cmd)

    def test_ovmf_4m_secboot(self):
        cmd = [
            'qemu-system-x86_64',
            '-machine', 'q35,accel=tcg',
        ] + self.Qemu_Common_Params + self.Qemu_Ovmf_Common_Params
        pflash = self.PflashParams(
            '/usr/share/OVMF/OVMF_CODE_4M.secboot.fd',
            '/usr/share/OVMF/OVMF_VARS_4M.fd',
        )
        cmd = cmd + pflash.params
        self.run_cmd_check_shell(cmd)

    def test_ovmf_4m_ms(self):
        cmd = [
            'qemu-system-x86_64',
            '-machine', 'q35,accel=tcg',
        ] + self.Qemu_Common_Params + self.Qemu_Ovmf_Common_Params
        pflash = self.PflashParams(
            '/usr/share/OVMF/OVMF_CODE_4M.ms.fd',
            '/usr/share/OVMF/OVMF_VARS_4M.ms.fd',
        )
        cmd = cmd + pflash.params
        self.run_cmd_check_shell(cmd)

    def test_ovmf32_4m_secboot(self):
        cmd = [
            'qemu-system-i386',
            '-machine', 'q35,accel=tcg'
        ] + self.Qemu_Common_Params + self.Qemu_Ovmf_Common_Params
        pflash = self.PflashParams(
            '/usr/share/OVMF/OVMF32_CODE_4M.secboot.fd',
            '/usr/share/OVMF/OVMF32_VARS_4M.fd',
        )
        cmd = cmd + pflash.params
        self.run_cmd_check_shell(cmd)


if __name__ == '__main__':
    unittest.main(verbosity=2)
