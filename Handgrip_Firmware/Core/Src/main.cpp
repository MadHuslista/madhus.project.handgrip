/**
 ******************************************************************************
 * @file    main.cpp
 * @author  Nicolas Schiappacasse <nicolaschiappacase@gmail.com>
 * @date    03/2026
 * @brief   Main file for the project.
 *
 ******************************************************************************
 */

/** @addtogroup HandGrip
 * @{
 */
/** @addtogroup Application
 * @{
 */
/** @addtogroup Main
 * @{
 */
/**
 * @defgroup PUBLIC_Definitions          PUBLIC constants
 * @defgroup PUBLIC_Macros               PUBLIC macros
 * @defgroup PUBLIC_Types                PUBLIC data-types
 * @defgroup PUBLIC_API                  PUBLIC API
 * @defgroup PUBLIC_WEAK                 PUBLIC Weak API
 * @defgroup PRIVATE_TUNABLES            Private compile-time tunables
 * @defgroup PRIVATE_Definitions         Private constants
 * @defgroup PRIVATE_Macros              Private macros
 * @defgroup PRIVATE_Types               Private data-types
 * @defgroup PRIVATE_Data                Private data / variables
 * @defgroup PRIVATE_Functions           Private functions
 * @defgroup PRIVATE_Weak                Private Weak functions
 */

#include <Arduino.h>
#include <stdlib.h>
#include <stdint.h>

#include "HX711.h"      /* https://github.com/RobTillaart/HX711 */
#include "TimerOne.h"   /* https://github.com/PaulStoffregen/TimerOne */

#include "fifo_buffer.h"  
#include "config.h"


/*----------------------------------------------------------------------------*/
/** @addtogroup PRIVATE_TUNABLES                                              */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

#define GPIO_DATA_PIN    2U
#define GPIO_CLOCK_PIN   3U

#define SERIAL_BAUD_RATE 115200U

#define MAX_FIFO_SIZE    80U 

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PRIVATE_Definitions                                           */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PRIVATE_Macros                                                */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PRIVATE_Types                                                 */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/**
 * @brief Sensor sample structure.
 */
typedef struct
{
    float    value_gr;      /**< Sensor value */
    uint32_t timestamp_us;  /**< Timestamp in microseconds */
    int32_t  seq;           /**< Sequence number; <-1> if error */
} SensorSample;

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PRIVATE_Functions                                             */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** Prototype for the interrupt handler */
void sample_scale(void);

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PRIVATE_Data                                                  */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** HX711 scale object */
HX711 _scale;

/** Sensor sample FIFO buffer */
FIFObuf<SensorSample>   _sensor_fifo(MAX_FIFO_SIZE);
uint8_t                 _sensor_fifo_status = 0;
uint32_t                _seq = 0;

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_API                                                    */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/**
 * @brief Setup the application.
 */
void setup()
{
    //  Serial port
    Serial.begin(SERIAL_BAUD_RATE);

    // HX711 scale
    _scale.begin(GPIO_DATA_PIN, GPIO_CLOCK_PIN);
    _scale.set_scale(SCALE_FACTOR);
    _scale.set_offset(SCALE_OFFSET);

    // Set Timer based Interrupt for sampling
    Timer1.initialize(SAMPLING_PERIOD_US);
    Timer1.attachInterrupt(sample_scale);

}


/**
 * @brief Main loop.
 * @note This function runs magnitudes faster than the sampling interrupt.
 */
void loop()
{
    SensorSample read_sample;
    read_sample = _sensor_fifo.pop();
    /* If timestamp is 0 => fifo is empty */
    if (read_sample.timestamp_us != 0) 
    {
        int32_t seq = _sensor_fifo_status ? read_sample.seq : -1;
        /* Format for LSL Bridge: D,<seq>,<timestamp_us>,<value>\n */
        Serial.print("D,");
        Serial.print(seq);
        Serial.print(",");
        Serial.print(read_sample.timestamp_us);
        Serial.print(",");
        Serial.print(read_sample.value_gr);
        Serial.print("\n");
    }
}

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_WEAK                                                   */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PRIVATE_Functions                                             */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/**
 * @brief Interrupt handler for the HX711 scale.
 * @note Reads one raw sample from the scale and pushes it to the FIFO buffer.
 */
void sample_scale(void)
{
    SensorSample save_sample;
    save_sample.timestamp_us = micros();
    save_sample.value_gr = _scale.get_units(1);
    save_sample.seq = _seq;
    _seq++;
    _sensor_fifo_status = _sensor_fifo.push(save_sample);
}


/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PRIVATE_Weak                                                  */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/*----------------------------------------------------------------------------*/
/** @} */
/*--->> END: Private Functions <<---------------------------------------------*/

/** @} */
/** @} */
/** @} */
