/** @file
  Machine Check features.

  Copyright (c) 2017 - 2018, Intel Corporation. All rights reserved.<BR>
  This program and the accompanying materials
  are licensed and made available under the terms and conditions of the BSD License
  which accompanies this distribution.  The full text of the license may be found at
  http://opensource.org/licenses/bsd-license.php

  THE PROGRAM IS DISTRIBUTED UNDER THE BSD LICENSE ON AN "AS IS" BASIS,
  WITHOUT WARRANTIES OR REPRESENTATIONS OF ANY KIND, EITHER EXPRESS OR IMPLIED.

**/

#include "CpuCommonFeatures.h"

/**
  Detects if Machine Check Exception feature supported on current processor.

  @param[in]  ProcessorNumber  The index of the CPU executing this function.
  @param[in]  CpuInfo          A pointer to the REGISTER_CPU_FEATURE_INFORMATION
                               structure for the CPU executing this function.
  @param[in]  ConfigData       A pointer to the configuration buffer returned
                               by CPU_FEATURE_GET_CONFIG_DATA.  NULL if
                               CPU_FEATURE_GET_CONFIG_DATA was not provided in
                               RegisterCpuFeature().

  @retval TRUE     Machine Check Exception feature is supported.
  @retval FALSE    Machine Check Exception feature is not supported.

  @note This service could be called by BSP/APs.
**/
BOOLEAN
EFIAPI
MceSupport (
  IN UINTN                             ProcessorNumber,
  IN REGISTER_CPU_FEATURE_INFORMATION  *CpuInfo,
  IN VOID                              *ConfigData  OPTIONAL
  )
{
  return (CpuInfo->CpuIdVersionInfoEdx.Bits.MCE == 1);
}

/**
  Initializes Machine Check Exception feature to specific state.

  @param[in]  ProcessorNumber  The index of the CPU executing this function.
  @param[in]  CpuInfo          A pointer to the REGISTER_CPU_FEATURE_INFORMATION
                               structure for the CPU executing this function.
  @param[in]  ConfigData       A pointer to the configuration buffer returned
                               by CPU_FEATURE_GET_CONFIG_DATA.  NULL if
                               CPU_FEATURE_GET_CONFIG_DATA was not provided in
                               RegisterCpuFeature().
  @param[in]  State            If TRUE, then the Machine Check Exception feature must be enabled.
                               If FALSE, then the Machine Check Exception feature must be disabled.

  @retval RETURN_SUCCESS       Machine Check Exception feature is initialized.

  @note This service could be called by BSP only.
**/
RETURN_STATUS
EFIAPI
MceInitialize (
  IN UINTN                             ProcessorNumber,
  IN REGISTER_CPU_FEATURE_INFORMATION  *CpuInfo,
  IN VOID                              *ConfigData,  OPTIONAL
  IN BOOLEAN                           State
  )
{
  //
  // Set MCE bit in CR4
  //
  CPU_REGISTER_TABLE_WRITE_FIELD (
    ProcessorNumber,
    ControlRegister,
    4,
    IA32_CR4,
    Bits.MCE,
    (State) ? 1 : 0
    );
  return RETURN_SUCCESS;
}

/**
  Detects if Machine Check Architecture feature supported on current processor.

  @param[in]  ProcessorNumber  The index of the CPU executing this function.
  @param[in]  CpuInfo          A pointer to the REGISTER_CPU_FEATURE_INFORMATION
                               structure for the CPU executing this function.
  @param[in]  ConfigData       A pointer to the configuration buffer returned
                               by CPU_FEATURE_GET_CONFIG_DATA.  NULL if
                               CPU_FEATURE_GET_CONFIG_DATA was not provided in
                               RegisterCpuFeature().

  @retval TRUE     Machine Check Architecture feature is supported.
  @retval FALSE    Machine Check Architecture feature is not supported.

  @note This service could be called by BSP/APs.
**/
BOOLEAN
EFIAPI
McaSupport (
  IN UINTN                             ProcessorNumber,
  IN REGISTER_CPU_FEATURE_INFORMATION  *CpuInfo,
  IN VOID                              *ConfigData  OPTIONAL
  )
{
  if (!MceSupport (ProcessorNumber, CpuInfo, ConfigData)) {
    return FALSE;
  }
  return (CpuInfo->CpuIdVersionInfoEdx.Bits.MCA == 1);
}

/**
  Initializes Machine Check Architecture feature to specific state.

  @param[in]  ProcessorNumber  The index of the CPU executing this function.
  @param[in]  CpuInfo          A pointer to the REGISTER_CPU_FEATURE_INFORMATION
                               structure for the CPU executing this function.
  @param[in]  ConfigData       A pointer to the configuration buffer returned
                               by CPU_FEATURE_GET_CONFIG_DATA.  NULL if
                               CPU_FEATURE_GET_CONFIG_DATA was not provided in
                               RegisterCpuFeature().
  @param[in]  State            If TRUE, then the Machine Check Architecture feature must be enabled.
                               If FALSE, then the Machine Check Architecture feature must be disabled.

  @retval RETURN_SUCCESS       Machine Check Architecture feature is initialized.

  @note This service could be called by BSP only.
**/
RETURN_STATUS
EFIAPI
McaInitialize (
  IN UINTN                             ProcessorNumber,
  IN REGISTER_CPU_FEATURE_INFORMATION  *CpuInfo,
  IN VOID                              *ConfigData,  OPTIONAL
  IN BOOLEAN                           State
  )
{
  MSR_IA32_MCG_CAP_REGISTER  McgCap;
  UINT32                     BankIndex;

  if (State) {
    McgCap.Uint64 = AsmReadMsr64 (MSR_IA32_MCG_CAP);
    for (BankIndex = 0; BankIndex < (UINT32) McgCap.Bits.Count; BankIndex++) {
      CPU_REGISTER_TABLE_WRITE64 (
        ProcessorNumber,
        Msr,
        MSR_IA32_MC0_CTL + BankIndex * 4,
        MAX_UINT64
        );
    }

    if (PcdGetBool (PcdIsPowerOnReset)) {
      for (BankIndex = 0; BankIndex < (UINTN) McgCap.Bits.Count; BankIndex++) {
        CPU_REGISTER_TABLE_WRITE64 (
          ProcessorNumber,
          Msr,
          MSR_IA32_MC0_STATUS + BankIndex * 4,
          0
          );
      }
    }
  }

  return RETURN_SUCCESS;
}

/**
  Detects if IA32_MCG_CTL feature supported on current processor.

  @param[in]  ProcessorNumber  The index of the CPU executing this function.
  @param[in]  CpuInfo          A pointer to the REGISTER_CPU_FEATURE_INFORMATION
                               structure for the CPU executing this function.
  @param[in]  ConfigData       A pointer to the configuration buffer returned
                               by CPU_FEATURE_GET_CONFIG_DATA.  NULL if
                               CPU_FEATURE_GET_CONFIG_DATA was not provided in
                               RegisterCpuFeature().

  @retval TRUE     IA32_MCG_CTL feature is supported.
  @retval FALSE    IA32_MCG_CTL feature is not supported.

  @note This service could be called by BSP/APs.
**/
BOOLEAN
EFIAPI
McgCtlSupport (
  IN UINTN                             ProcessorNumber,
  IN REGISTER_CPU_FEATURE_INFORMATION  *CpuInfo,
  IN VOID                              *ConfigData  OPTIONAL
  )
{
  MSR_IA32_MCG_CAP_REGISTER  McgCap;

  if (!McaSupport (ProcessorNumber, CpuInfo, ConfigData)) {
    return FALSE;
  }
  McgCap.Uint64 = AsmReadMsr64 (MSR_IA32_MCG_CAP);
  return (McgCap.Bits.MCG_CTL_P == 1);
}

/**
  Initializes IA32_MCG_CTL feature to specific state.

  @param[in]  ProcessorNumber  The index of the CPU executing this function.
  @param[in]  CpuInfo          A pointer to the REGISTER_CPU_FEATURE_INFORMATION
                               structure for the CPU executing this function.
  @param[in]  ConfigData       A pointer to the configuration buffer returned
                               by CPU_FEATURE_GET_CONFIG_DATA.  NULL if
                               CPU_FEATURE_GET_CONFIG_DATA was not provided in
                               RegisterCpuFeature().
  @param[in]  State            If TRUE, then the IA32_MCG_CTL feature must be enabled.
                               If FALSE, then the IA32_MCG_CTL feature must be disabled.

  @retval RETURN_SUCCESS       IA32_MCG_CTL feature is initialized.

  @note This service could be called by BSP only.
**/
RETURN_STATUS
EFIAPI
McgCtlInitialize (
  IN UINTN                             ProcessorNumber,
  IN REGISTER_CPU_FEATURE_INFORMATION  *CpuInfo,
  IN VOID                              *ConfigData,  OPTIONAL
  IN BOOLEAN                           State
  )
{
  CPU_REGISTER_TABLE_WRITE64 (
    ProcessorNumber,
    Msr,
    MSR_IA32_MCG_CTL,
    (State)? MAX_UINT64 : 0
    );
  return RETURN_SUCCESS;
}

/**
  Detects if Local machine check exception feature supported on current
  processor.

  @param[in]  ProcessorNumber  The index of the CPU executing this function.
  @param[in]  CpuInfo          A pointer to the REGISTER_CPU_FEATURE_INFORMATION
                               structure for the CPU executing this function.
  @param[in]  ConfigData       A pointer to the configuration buffer returned
                               by CPU_FEATURE_GET_CONFIG_DATA.  NULL if
                               CPU_FEATURE_GET_CONFIG_DATA was not provided in
                               RegisterCpuFeature().

  @retval TRUE     Local machine check exception feature is supported.
  @retval FALSE    Local machine check exception feature is not supported.

  @note This service could be called by BSP/APs.
**/
BOOLEAN
EFIAPI
LmceSupport (
  IN UINTN                             ProcessorNumber,
  IN REGISTER_CPU_FEATURE_INFORMATION  *CpuInfo,
  IN VOID                              *ConfigData  OPTIONAL
  )
{
  MSR_IA32_MCG_CAP_REGISTER    McgCap;

  if (!McaSupport (ProcessorNumber, CpuInfo, ConfigData)) {
    return FALSE;
  }

  McgCap.Uint64 = AsmReadMsr64 (MSR_IA32_MCG_CAP);
  if (ProcessorNumber == 0) {
    DEBUG ((EFI_D_INFO, "LMCE eanble = %x\n", (BOOLEAN) (McgCap.Bits.MCG_LMCE_P != 0)));
  }
  return (BOOLEAN) (McgCap.Bits.MCG_LMCE_P != 0);
}

/**
  Initializes Local machine check exception feature to specific state.

  @param[in]  ProcessorNumber  The index of the CPU executing this function.
  @param[in]  CpuInfo          A pointer to the REGISTER_CPU_FEATURE_INFORMATION
                               structure for the CPU executing this function.
  @param[in]  ConfigData       A pointer to the configuration buffer returned
                               by CPU_FEATURE_GET_CONFIG_DATA.  NULL if
                               CPU_FEATURE_GET_CONFIG_DATA was not provided in
                               RegisterCpuFeature().
  @param[in]  State            If TRUE, then the Local machine check exception
                               feature must be enabled.
                               If FALSE, then the Local machine check exception
                               feature must be disabled.

  @retval RETURN_SUCCESS       Local machine check exception feature is initialized.

**/
RETURN_STATUS
EFIAPI
LmceInitialize (
  IN UINTN                             ProcessorNumber,
  IN REGISTER_CPU_FEATURE_INFORMATION  *CpuInfo,
  IN VOID                              *ConfigData,  OPTIONAL
  IN BOOLEAN                           State
  )
{
  MSR_IA32_FEATURE_CONTROL_REGISTER    *MsrRegister;

  ASSERT (ConfigData != NULL);
  MsrRegister = (MSR_IA32_FEATURE_CONTROL_REGISTER *) ConfigData;
  if (MsrRegister[ProcessorNumber].Bits.Lock == 0) {
    CPU_REGISTER_TABLE_WRITE_FIELD (
      ProcessorNumber,
      Msr,
      MSR_IA32_FEATURE_CONTROL,
      MSR_IA32_FEATURE_CONTROL_REGISTER,
      Bits.LmceOn,
      (State) ? 1 : 0
      );
  }
  return RETURN_SUCCESS;
}
