#
# Copyright 2019-2021 Canonical Ltd.
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
#

import enum
import os
import shutil
import tempfile


class Command:
    '''This is only intended to be a base class'''
    Qemu_Arch_Command = []
    # Based on the args used by ovmf-vars-generator
    Qemu_Common_Params = [
        '-no-user-config', '-nodefaults',
        '-m', '256',
        '-smp', '2,sockets=2,cores=1,threads=1',
        '-display', 'none',
        '-serial', 'stdio',
    ]
    Qemu_Arch_Params = []

    def __init__(self, code_path, vars_template_path):
        self.pflash = self.PflashParams(code_path, vars_template_path)
        self.command = self.Qemu_Arch_Command + \
            self.Qemu_Common_Params + \
            self.Qemu_Arch_Params + self.pflash.params

    def add_disk(self, path):
        self.command = self.command + [
            '-drive', 'file=%s,format=raw' % (path)
        ]

    def add_oem_string(self, type, string):
        string = string.replace(",", ",,")
        self.command = self.command + [
            '-smbios', f'type={type},value={string}'
        ]

    class PflashParams:
        '''
        Used to generate the appropriate -pflash arguments for QEMU. Mostly
        used as a fancy way to generate a per-instance vars file and have it
        be automatically cleaned up when the object is destroyed.
        '''
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


class OvmfFlavor(enum.Enum):
    MS = enum.auto()
    SECBOOT = enum.auto()


class OvmfCommand(Command):
    Qemu_Arch_Params = [
        '-chardev', 'pty,id=charserial1',
        '-device', 'isa-serial,chardev=charserial1,id=serial1',
    ]

    def __init__(self, flash_size_mb, flavor=None):
        if flash_size_mb == 2:
            size_ext = ''
        elif flash_size_mb == 4:
            size_ext = '_4M'
        else:
            raise Exception("Invalid flash size {}".format(flash_size_mb))

        if flash_size_mb == 2 and flavor in [
                OvmfFlavor.MS, OvmfFlavor.SECBOOT
        ]:
            # These legacy images are built with a 64-bit PEI phase that
            # currently does not support S3
            extra_qemu_args = ['-global', 'ICH9-LPC.disable_s3=1']
        else:
            extra_qemu_args = []

        if flavor == OvmfFlavor.MS:
            code_ext = vars_ext = '.ms'
        elif flavor == OvmfFlavor.SECBOOT:
            code_ext = '.secboot'
            vars_ext = ''
        elif flavor is None:
            code_ext = ''
            vars_ext = ''
        else:
            raise Exception("Invalid flavor")

        code_path = '/usr/share/OVMF/OVMF_CODE%s%s.fd' % (
            size_ext, code_ext
        )
        vars_template_path = '/usr/share/OVMF/OVMF_VARS%s%s.fd' % (
            size_ext, vars_ext
        )

        super().__init__(code_path, vars_template_path)
        self.command = self.command + extra_qemu_args


class OvmfPcCommand(OvmfCommand):
    Qemu_Arch_Command = [
        'qemu-system-x86_64',
        '-machine', 'pc,accel=tcg'
    ]


class OvmfQ35Command(OvmfCommand):
    Qemu_Arch_Command = [
        'qemu-system-x86_64',
        '-machine', 'q35,accel=tcg'
    ]


class Ovmf32Command(Command):
    Qemu_Arch_Command = [
        'qemu-system-i386',
        '-machine', 'q35,accel=tcg'
    ]

    def __init__(self):
        super().__init__(
            '/usr/share/OVMF/OVMF32_CODE_4M.secboot.fd',
            '/usr/share/OVMF/OVMF32_VARS_4M.fd',
        )


class QemuEfiCommand(Command):
    Qemu_Arch_Params = [
        '-machine', 'virt',
        '-device', 'virtio-serial-device',
    ]


class AavmfCommand(QemuEfiCommand):
    Qemu_Arch_Command = [
        'qemu-system-aarch64',
        '-cpu', 'cortex-a57',
    ]

    def __init__(self):
        super().__init__(
            '/usr/share/AAVMF/AAVMF_CODE.fd',
            '/usr/share/AAVMF/AAVMF_VARS.fd',
        )


class Aavmf32Command(QemuEfiCommand):
    Qemu_Arch_Command = [
        'qemu-system-aarch64',
        '-cpu', 'cortex-a15',
    ]

    def __init__(self):
        super().__init__(
            '/usr/share/AAVMF/AAVMF32_CODE.fd',
            '/usr/share/AAVMF/AAVMF32_VARS.fd',
        )
