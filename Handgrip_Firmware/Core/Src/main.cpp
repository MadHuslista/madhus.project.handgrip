/**
 ******************************************************************************
 * @file    main.cpp
 * @author  Nicolas Schiappacasse <nicolaschiappacase@gmail.com>
 * @date    05/2026
 * @brief   Calibration-ready Arduino Nano + HX711 acquisition firmware.
 *
 * Breaking schema upgrade:
 *   - Legacy `D,<seq>,<timestamp_us>,<value>` output was removed.
 *   - The firmware now emits explicit D2 frames with raw counts, interpreted
 *     units, sequence number, device timestamp, and status bits.
 *   - A metadata M2 line is emitted at boot so the LSL bridge/session manifest
 *     can capture firmware schema, constants, and expected HX711 rate.
 *
 * The firmware remains deliberately simple: acquire deterministic raw samples,
 * timestamp them with micros(), and send them over UART. Calibration session
 * ownership, markers, segmentation, fitting, and reports belong to the host-side
 * Handgrip_Calibration module.
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
/** @ingroup PRIVATE_TUNABLES                                                  */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** Pin mapping for HX711 scale */
#define GPIO_DATA_PIN    2U
#define GPIO_CLOCK_PIN   3U

/** FIFO depth for interrupt-to-loop handoff. */
#define MAX_FIFO_SIZE                  80U


/** @} */
/*----------------------------------------------------------------------------*/
/** @ingroup PRIVATE_Definitions                                               */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @ingroup PRIVATE_Macros                                                    */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @ingroup PRIVATE_Types                                                     */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/**
 * @brief Sensor sample structure.
 */
typedef struct
{
    int32_t  raw_count;       /**< HX711 raw ADC count, before scale/offset. */
    float    current_units;   /**< Convenience engineering value from config constants. */
    uint32_t timestamp_us;    /**< Device-local micros() timestamp. */
    uint32_t seq;             /**< Monotonic sequence number. */
    uint16_t status;          /**< HANDGRIP_STATUS_* bitfield. */
} SensorSample;

/** @} */
/*----------------------------------------------------------------------------*/
/** @cond DOXYGEN_SKIP_PROTOTYPES */
/* Prototype for the interrupt handler */
void sample_scale(void);

/* Prototypes for utility functions */
static float _raw_to_units(int32_t raw_count);
static void _emit_metadata(void);
static void _emit_sample(const SensorSample &sample);
/** @endcond */
/*----------------------------------------------------------------------------*/
/** @ingroup PRIVATE_Data                                                      */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** HX711 scale object */
HX711 _scale;

/** Sensor sample FIFO buffer */
FIFObuf<SensorSample>  _sensor_fifo(MAX_FIFO_SIZE);
volatile uint32_t _seq = 0;
volatile uint16_t _sticky_status = HANDGRIP_STATUS_OK;

/** @} */
/*----------------------------------------------------------------------------*/
/** @ingroup PUBLIC_API                                                        */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/**
 * @brief Setup the application.
 */
void setup()
{
    /* Serial port */
    Serial.begin(SERIAL_BAUD_RATE);

    /* HX711 scale object */
    _scale.begin(GPIO_DATA_PIN, GPIO_CLOCK_PIN);

    /* Keep HX711 offset/scale configured for operator sanity, but never rely on
     * get_units() for calibration. D2 always carries raw_count explicitly. */
    _scale.set_scale(SCALE_FACTOR);
    _scale.set_offset(SCALE_OFFSET);

    /* Emit metadata (M2) at boot so the LSL_Bridge/Handgrip_Calibration can
     * capture firmware schema, constants, and expected HX711 rate. */
    _emit_metadata();

    /* Set Timer based Interrupt for sampling */
    Timer1.initialize(SAMPLING_PERIOD_US);
    Timer1.attachInterrupt(sample_scale);

}


/**
 * @brief Main loop.
 * @note This function runs magnitudes faster than the sampling interrupt.
 */
void loop()
{
    SensorSample sample = _sensor_fifo.pop();
    if (sample.timestamp_us == 0U)
    {
        /* Arduino equivalent of "continue" for the main loop(). */
        return;  
    }
    _emit_sample(sample);
}

/** @} */
/*----------------------------------------------------------------------------*/
/* ====================== Interrupt Service Routine ======================== */

/**
 * @brief Timer ISR: non-blocking HX711 sample capture.
 * @note The ISR never waits for the ADC. 
 * It records a status bit when the HX711 is not ready and returns immediately. 
 * This keeps loop latency predictable and makes timing irregularity visible 
 * instead of hidden by blocking reads.
 */
void sample_scale(void)
{
    if (!_scale.is_ready())
    {
        _sticky_status |= HANDGRIP_STATUS_HX711_NOTREADY;
        return;
    }

    SensorSample sample;
    sample.timestamp_us = micros();
    sample.raw_count = _scale.read();
    sample.current_units = _raw_to_units(sample.raw_count);
    sample.seq = _seq++;
    sample.status = _sticky_status;

    if (isnan(sample.current_units))
    {
        sample.status |= HANDGRIP_STATUS_SCALE_INVALID;
    }

    uint8_t ok = _sensor_fifo.push(sample);
    if (!ok)
    {
        _sticky_status |= HANDGRIP_STATUS_FIFO_OVERFLOW;
    }
    else
    {
        _sticky_status = HANDGRIP_STATUS_OK;
    }
}

/* ====================== Utility Functions ================================ */

/* Emit boot/build metadata consumed by LSL_Bridge. */
static void _emit_metadata(void)
{
    Serial.print("M2,");
    Serial.print(HANDGRIP_PAYLOAD_SCHEMA);
    Serial.print(",");
    Serial.print(HANDGRIP_FIRMWARE_VERSION);
    Serial.print(",");
    Serial.print(HANDGRIP_FIRMWARE_GIT_SHA);
    Serial.print(",");
    Serial.print(HX711_EXPECTED_OUTPUT_RATE_HZ, 3);
    Serial.print(",");
    Serial.print(SCALE_FACTOR, 9);
    Serial.print(",");
    Serial.print(SCALE_OFFSET, 3);
    Serial.print(",");
    Serial.print(HANDGRIP_FORCE_UNIT);
    Serial.print("\n");
}

/* Emit one strict D2 data record. */
static void _emit_sample(const SensorSample &sample)
{
    Serial.print("D2,");
    Serial.print(sample.seq);
    Serial.print(",");
    Serial.print(sample.timestamp_us);
    Serial.print(",");
    Serial.print(sample.raw_count);
    Serial.print(",");
    if (isnan(sample.current_units))
    {
        Serial.print("nan");
    }
    else
    {
        Serial.print(sample.current_units, 6);
    }
    Serial.print(",");
    Serial.print(sample.status);
    Serial.print("\n");
}

/* Convert raw HX711 counts to current engineering units for sanity display. */
static float _raw_to_units(int32_t raw_count)
{
    if (SCALE_FACTOR == 0.0F)
    {
        return NAN;
    }
    return ((float)raw_count - SCALE_OFFSET) / SCALE_FACTOR;
}
/** @ingroup PRIVATE_Weak                                                      */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/*----------------------------------------------------------------------------*/
/** @} */
/*--->> END: Private Functions <<---------------------------------------------*/

/** @} */
/** @} */
/** @} */
