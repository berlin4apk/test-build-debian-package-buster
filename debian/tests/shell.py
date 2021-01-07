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

import enum
import os.path
import pexpect
import shutil
import subprocess
import sys
import tempfile
import unittest

DPKG_ARCH = subprocess.check_output(
    ['dpkg', '--print-architecture']
).decode().rstrip()


class FatFsImage:
    def __init__(self, size_in_mb):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            self.path = f.name

        subprocess.check_call(
            [
                'dd', 'if=/dev/zero', 'of=%s' % (self.path),
                'count=0', 'bs=1M', 'seek=64', 'status=none'
            ]
        )
        subprocess.check_call(['mkdosfs', '-F', '32', self.path])

    def __del__(self):
        os.unlink(self.path)

    def mkdir(self, dir):
        subprocess.run(['mmd', '-i', self.path, dir])

    def insert_file(self, src, dest):
        subprocess.check_call(
            [
                'mcopy', '-i', self.path, src, '::%s' % (dest)
            ]
        )


class EfiBootableIsoImage:
    def __init__(self, eltorito_img):
        with tempfile.TemporaryDirectory() as iso_root:
            eltorito_iso_root = os.path.join('boot', 'grub')
            eltorito_iso_path = os.path.join(eltorito_iso_root, 'efi.img')
            eltorito_local_root = os.path.join(iso_root, eltorito_iso_root)
            eltorito_local_path = os.path.join(iso_root, eltorito_iso_path)

            os.makedirs(eltorito_local_root)
            shutil.copyfile(eltorito_img.path, eltorito_local_path)

            with tempfile.NamedTemporaryFile(delete=False) as f:
                self.path = f.name

            subprocess.check_call(
                [
                    'xorriso', '-as', 'mkisofs', '-J', '-l',
                    '-c', 'boot/boot.cat',
                    '-partition_offset', '16', '-append_partition', '2',
                    '0xef', eltorito_local_path,
                    '-e', '--interval:appended_partition_2:all::',
                    '-no-emul-boot', '-o', self.path, iso_root
                ]
            )

    def __del__(self):
        os.unlink(self.path)


def create_efi_bootable_iso(efi_arch, use_signed):
    EfiArchToGrubArch = {
        'X64': "x86_64",
        'AA64': "arm64",
    }
    efi_img = FatFsImage(64)
    removable_media_path = os.path.join(
        'EFI', 'BOOT', 'BOOT%s.EFI' % (efi_arch.upper())
    )
    parent_dirs = removable_media_path.split(os.path.sep)[:-1]
    for dir_idx in range(1, len(parent_dirs)+1):
        next_dir = os.path.sep.join(parent_dirs[:dir_idx])
        efi_img.mkdir(next_dir)
    efi_ext = 'efi'
    grub_subdir = "%s-efi" % EfiArchToGrubArch[efi_arch.upper()]
    if use_signed:
        efi_ext = "%s.signed" % (efi_ext)
        grub_subdir = "%s-signed" % (grub_subdir)

    shim_src = os.path.join(
        os.path.sep, 'usr', 'lib', 'shim',
        'shim%s.%s' % (efi_arch.lower(), efi_ext)
    )
    grub_src = os.path.join(
        os.path.sep, 'usr', 'lib', 'grub',
        '%s' % (grub_subdir),
        "" if use_signed else "monolithic",
        'grub%s.%s' % (efi_arch.lower(), efi_ext)
    )
    grub_dest = os.path.join(
        'EFI', 'BOOT', 'GRUB%s.EFI' % (efi_arch.upper())
    )
    efi_img.insert_file(shim_src, removable_media_path)
    efi_img.insert_file(grub_src, grub_dest)

    return EfiBootableIsoImage(efi_img)


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
                    continue
        except pexpect.EOF:
            return
        except pexpect.TIMEOUT as err:
            self.fail("%s\n" % (err))

    def run_cmd_check_secure_boot(self, cmd, should_verify):
        class State(enum.Enum):
            PRE_EXEC = 1
            POST_EXEC = 2

        child = pexpect.spawn(' '.join(cmd))

        if self.debug:
            child.logfile = sys.stdout.buffer
        try:
            state = State.PRE_EXEC
            while True:
                i = child.expect(
                    [
                        'Press .* or any other key to continue',
                        'Shell> ',
                        "FS0:\\\\> ",
                        'grub> ',
                        'Command Error Status: Access Denied',
                    ],
                    timeout=60,
                )
                if i == 0:
                    child.sendline('\x1b')
                    continue
                if i == 1:
                    child.sendline('fs0:\r')
                    continue
                if i == 2:
                    if state == State.PRE_EXEC:
                        child.sendline('\\efi\\boot\\bootx64.efi\r')
                        state = State.POST_EXEC
                    elif state == State.POST_EXEC:
                        child.sendline('reset -s\r')
                    continue
                if i == 3:
                    child.sendline('halt\r')
                    verified = True
                    continue
                if i == 4:
                    verified = False
                    continue
        except pexpect.TIMEOUT as err:
            self.fail("%s\n" % (err))
        except pexpect.EOF:
            pass
        self.assertEqual(should_verify, verified)

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

    @unittest.skipUnless(DPKG_ARCH == 'amd64', "amd64-only")
    def test_ovmf_ms_secure_boot_signed(self):
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
        iso = create_efi_bootable_iso('X64', use_signed=True)
        cmd = cmd + ['-drive', 'file=%s,format=raw' % (iso.path)]
        self.run_cmd_check_secure_boot(cmd, True)

    @unittest.skipUnless(DPKG_ARCH == 'amd64', "amd64-only")
    def test_ovmf_ms_secure_boot_unsigned(self):
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
        iso = create_efi_bootable_iso('X64', use_signed=False)
        cmd = cmd + ['-drive', 'file=%s,format=raw' % (iso.path)]
        self.run_cmd_check_secure_boot(cmd, False)

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

    @unittest.skipUnless(DPKG_ARCH == 'amd64', "amd64-only")
    def test_ovmf_4m_ms_secure_boot_signed(self):
        cmd = [
            'qemu-system-x86_64',
            '-machine', 'q35,accel=tcg',
        ] + self.Qemu_Common_Params + self.Qemu_Ovmf_Common_Params
        pflash = self.PflashParams(
            '/usr/share/OVMF/OVMF_CODE_4M.ms.fd',
            '/usr/share/OVMF/OVMF_VARS_4M.ms.fd',
        )
        cmd = cmd + pflash.params
        iso = create_efi_bootable_iso('X64', use_signed=True)
        cmd = cmd + ['-drive', 'file=%s,format=raw' % (iso.path)]
        self.run_cmd_check_secure_boot(cmd, True)

    @unittest.skipUnless(DPKG_ARCH == 'amd64', "amd64-only")
    def test_ovmf_4m_ms_secure_boot_unsigned(self):
        cmd = [
            'qemu-system-x86_64',
            '-machine', 'q35,accel=tcg',
        ] + self.Qemu_Common_Params + self.Qemu_Ovmf_Common_Params
        pflash = self.PflashParams(
            '/usr/share/OVMF/OVMF_CODE_4M.ms.fd',
            '/usr/share/OVMF/OVMF_VARS_4M.ms.fd',
        )
        cmd = cmd + pflash.params
        iso = create_efi_bootable_iso('X64', use_signed=False)
        cmd = cmd + ['-drive', 'file=%s,format=raw' % (iso.path)]
        self.run_cmd_check_secure_boot(cmd, False)

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
