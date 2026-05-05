/**
 ******************************************************************************
 * @file    config.h
 * @author  Nicolas Schiappacasse <nicolaschiappacase@gmail.com>
 * @date    05/2026
 * @brief   Calibration-ready Handgrip firmware configuration.
 *
 * The firmware emits the D2 calibration payload expected by the LSL_Bridge 
 * and by the Handgrip_Calibration module:
 *
 *   M2,<schema>,<fw_version>,<git_sha>,<hx711_rate_hz>,<scale_factor>,<scale_offset>,<unit>
 *   D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
 *
 * Raw counts are always present so that calibration fits are not contaminated
 * by mutable firmware scale/offset settings. The current_units field is a
 * convenience/sanity channel computed from the same constants that will later be
 * updated from the calibration report.
 ******************************************************************************
 */
#ifndef _INC_CONFIG_H_
#define _INC_CONFIG_H_

/** @addtogroup HandGrip
 * @{
 */
/** @addtogroup Application
 * @{
 */
/** @addtogroup Config
 * @{
 */

#include <stdbool.h>

/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_Definitions                                            */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** --------------------- > Serial Communication < -------------------------- */

/** Serial port baud rate. */
#define SERIAL_BAUD_RATE               115200U


/** ----------------------> Sampling < -------------------------------------- */

/**
 * HX711 calibration constants using the common HX711 convention:
 *
 *   current_units = (raw_count - SCALE_OFFSET) / SCALE_FACTOR
 *
 * Handgrip_Calibration exports recommended firmware constants in this form.
 * During initial characterization keep SCALE_FACTOR=1 and SCALE_OFFSET=0 so
 * current_units mirrors raw_count while raw_count remains authoritative.
 */
#define SCALE_FACTOR                   1.0F
#define SCALE_OFFSET                   0.0F

/** Sampling period in microseconds - 5000us = 5ms = 200Hz
 *  Empirical máximum frequency for the HX711 is 92Hz
 *  Sampling is done at >= 2 x 92Hz allows for non-blocking reads on IRQ. 
 *  If sensor is not ready, 200Hz ensure that the new sample will be captured
 *  within the next IRQ.
 */
#define SAMPLING_PERIOD_US             5000U


/** ----------------------> Payload Schema < -------------------------------- */

/** Payload schema. Only schema 2 is supported by this upgraded release. */
#define HANDGRIP_PAYLOAD_SCHEMA        2U

/** Status bitfield emitted in D2 frames. */
#define HANDGRIP_STATUS_OK             0x0000U
#define HANDGRIP_STATUS_FIFO_OVERFLOW  0x0001U
#define HANDGRIP_STATUS_HX711_NOTREADY 0x0002U
#define HANDGRIP_STATUS_SCALE_INVALID  0x0004U

/** Human-readable physical unit for current_units. 
 *  Recommended calibration unit is Newtons. */
#define HANDGRIP_FORCE_UNIT            "N"

/** --------------------- > Metadata < -------------------------------------- */

/** Firmware semantic version printed in the M2 boot metadata line. */
#define HANDGRIP_FIRMWARE_VERSION      "2.0.0-calibration-schema"

/** Build/source identifier. Override at compile time with -DFIRMWARE_GIT_SHA=\"...\" if desired. */
#ifndef HANDGRIP_FIRMWARE_GIT_SHA
#define HANDGRIP_FIRMWARE_GIT_SHA      "unknown"
#endif

/** Nominal/expected HX711 output rate used only for metadata. */
#define HX711_EXPECTED_OUTPUT_RATE_HZ  93.0F



/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_Types                                                  */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_Data                                                  */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_API                                                    */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_WEAK                                                   */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/*----------------------------------------------------------------------------*/
/** @} */
/*--->> END: PUBLIC API <<----------------------------------------------------*/

/** @} */
/** @} */
/** @} */

#endif   // _INC_CONFIG_H_
