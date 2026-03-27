//
//    FILE: HX_plotter.ino
//  AUTHOR: Rob Tillaart
// PURPOSE: HX711 demo
//     URL: https://github.com/RobTillaart/HX711


#include "HX711.h"
#include "TimerOne.h"
#include <stdint.h>


HX711 scale;

//  adjust pins if needed
uint8_t dataPin = 2;
uint8_t clockPin = 3;

float f;

#define TIMER_BASED 0

void setup()
{
  Serial.begin(115200);
  //  Serial.println();
  //  Serial.println(__FILE__);
  //  Serial.print("HX711_LIB_VERSION: ");
  //  Serial.println(HX711_LIB_VERSION);
  //  Serial.println();

  scale.begin(dataPin, clockPin);

  scale.set_raw_mode();

  //  TODO find a nice solution for this calibration..
  //  load cell factor 20 KG
  //  scale.set_scale(127.15);
  //  load cell factor 5 KG
  scale.set_scale(1);       // TODO you need to calibrate this yourself.
  //  reset the scale to zero = 0
  scale.tare(1);
  Serial.print("rate: "); Serial.println(scale.get_rate());
  Serial.print("mode: "); Serial.println(scale.get_mode());

#if TIMER_BASED
  //Timer1.initialize(12500);
  //Timer1.attachInterrupt(read_data); // blinkLED to run every 0.15 seconds
#endif 
}

uint64_t s_time = 0;
uint64_t e_time = 0;
uint32_t e_count = 0; 
uint32_t _samples = 1000;

void loop()
{
  //  continuous scale 4x per second
  if (e_count == 0){s_time = micros(); Serial.print("s_time  : "); Serial.println((uint32_t)s_time); }

#if TIMER_BASED == 0
  f = scale.get_units(1);
  //Serial.println(f);
  e_count++;
  //if (e_count % 10 == 0){Serial.print("e_count: ");Serial.println(e_count);}
#endif  
  //delay(250);
  if (e_count >= _samples)
  {
    e_time = micros(); 
    Serial.print("e_time  : "); Serial.println((uint32_t)e_time);
    uint64_t sample_time = e_time - s_time; 
    Serial.print("sample_time  : "); Serial.println((uint32_t)sample_time);
    float period_us = (float)sample_time/(float)e_count; 
    float period_ms = period_us / 1000.0;
    float period_s  = period_ms / 1000.0;
    float freq_hz   = 1.0 / period_s;
    Serial.print("e_count  : "); Serial.println(e_count);
    Serial.print("period_us: "); Serial.println(period_us);
    Serial.print("period_ms: "); Serial.println(period_ms);
    Serial.print("freq_hz  : "); Serial.println(freq_hz);
    e_count = 0; 
    int update_samples = Serial.read();
    if (update_samples == 1)
    {
      _samples = Serial.read(); 
    }
  }
}

void read_data(void)
{
  f = scale.get_units(1);
  e_count++;
}

//  -- END OF FILE --

