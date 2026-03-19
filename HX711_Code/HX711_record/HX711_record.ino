#include "HX711.h"


// Pin Config
const int DOUT=A1;
const int CLK=A0;

// Calibration 
const int sample_freq = 90;
const int time_estab = 1;
int samples_estab;

// Scalation
float intercept;
float gradient; 
float clamp_val;  


//Start_Values
long prev_d0; 
long prev_d1; 


//Signals
long deci;
long dd1; 
long dd2; 


HX711 dinam;
void setup() {
  
  Serial.begin(115200);
  dinam.begin(DOUT, CLK);


  // Inicio de Conexión
  // Serial.println("Iniciando conexión...");  
  while(!dinam.is_ready()){  }
  // Serial.println("Conexión establecida"); 

  // Espera para estabilización de señal 
  // Serial.println("Esperando estabilización de la señal...\n~");
  // Serial.print(time_estab); Serial.print("[s]"); 

  for (int i = 0; i < time_estab; i++){
    dinam.read_average(sample_freq);     
    if(i %5 == 0){
      // Serial.print(":"); 
      // Serial.print(i); 
      // Serial.println("[s]"); 
    }
  } 
  // Serial.println("Señal estabilizada"); 
  

  // Tarado
  // Serial.println("Tarando..");
  calibration(sample_freq*2); 
  // Serial.println("Tara completada");

}

long p = 0; 

void loop(){

  //Read 
  deci = dinam.read();

  //Derivatives compute
  dd1 = deci - prev_d0; 
  dd2 = dd1 - prev_d1; 

  //Update values; 
  prev_d0 = deci; 
  prev_d1 = dd1; 


//Signal Record
  // Serial.print(p++); Serial.print("\t");
   Serial.println(deci); //Serial.print("\t");
 //  Serial.println(dd1); 

//Signal Calibration
//  Serial.print(p++); Serial.print("\t");
//  Serial.print(intercept); Serial.print("\t");
//  Serial.println(deci); 


}


void calibration(int size){

  // Compute
  intercept = 0; 
  for (int i = 0; i < size; i++){
    long init_read = dinam.read(); 
    intercept += init_read;
  }
  intercept = intercept/float(size); 
 
  //Values set
  prev_d0 = intercept; 
  prev_d1 = intercept; 


}


void Visualization(){

}
