/**
 ******************************************************************************
 * @file    config.h
 * @author  Nicolas Schiappacasse <nicolaschiappacase@gmail.com>
 * @date    03/2026
 * @brief   Config file for the project.
 *
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

/** Sampling period in microseconds - 5000us = 5ms = 200Hz
 *  Empirical máximum frequency for the HX711 is 92Hz
 *  Sampling is done at >= 2 x 92Hz allows for non-blocking reads on IRQ. 
 *  If sensor is not ready, 200Hz ensure that the new sample will be captured
 *  within the next IRQ.
 */
#define SAMPLING_PERIOD_US      5000U

/** Set Calibration flag to 1 (true) to calibrate the scale, 0 (false) to run the application
 *  This will take a few seconds to complete
 */
#define CALIBRATE_SCALE_MODE    1U

/** Scale factor to convert raw counts to kg
 *  This value is obtained from the calibration process
 */
#define SCALE_FACTOR            1.0F

/** Offset to be subtracted from the raw counts before scaling
 *  This value is obtained from the calibration process
 */
#define SCALE_OFFSET            0.0F


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

#endif   //  _INC_CONFIG_H_
