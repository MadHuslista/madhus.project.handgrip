#include "HX711.h"


// Pin Config
const int DOUT=A1;
const int CLK=A0;

// Calibration 
const int sample_freq = 180;
const int time_estab = 180;
int samples_estab;

// Scalation
float intercept = 0;
float gradient = 3.63128; 
float clamp_val = 0.1;   

//Start_Values
long prev_d0; 
long prev_d1; 

//Signals
long deci;
long dd1; 
long dd2; 

//Event Flags
bool start_press = false;
bool end_press = true; 
int record_sig = 0; 

//Thresholds
long dd1_th = 5000;
long deci_th_st;
long deci_th_end = 150000;


//Storage
int rec_point = 0; 
long max_point; 
long max_deci;
float package [4]; 
//          Init_Flag   | End_Flag  | Pos_Max   | Scal_Max  | Deci_Max





HX711 dinam;
void setup() {

  
    Serial.begin(115200);
    dinam.begin(DOUT, CLK);


    // Inicio de Conexión
    Serial.println("Iniciando conexión...");  
    while(!dinam.is_ready()){  }
    Serial.println("Conexión establecida"); 

    // Espera para estabilización de señal 
    Serial.print("Esperando estabilización de la señal...\n~");
    Serial.print(time_estab); Serial.println("[s]"); 

    Serial.println("\n Presionar un par de veces, para mejorar la estabilización\n"); 

    for (int i = 0; i < time_estab; i++){
        dinam.read_average(sample_freq);     
        if(i %5 == 0){
        Serial.print(":"); 
        Serial.print(i); 
        Serial.println("[s]"); 
        }
    } 
    Serial.println("Señal estabilizada"); 
    

    // Tarado
    Serial.println("Tarando..");
    calibration(sample_freq*2); 
    // Serial.println(intercept); 
    // Serial.println(dd1_th); 
    // Serial.println(deci_th_st);
    Serial.println("Tara completada");

}

int p = 0; 
unsigned long st; 
unsigned long ed; 

void loop(){


    //Read 
    deci = dinam.read();

    //Derivatives compute
    dd1 = deci - prev_d0; 
    dd2 = dd1 - prev_d1; 

    //Update values; 
    prev_d0 = deci; 
    prev_d1 = dd1; 

    //Inside Peak
    if(start_press and !end_press){
        package[0] = 0;
        package[1] = 0;
        package[2] = -1;
        package[3] = -1;
    }

    //Start Detection
    if(end_press &&(dd1 > dd1_th) &&(deci > - deci_th_st)){

        start_press = true; 
        end_press = false; 
        record_sig = 1; 
        rec_point = 0; 

        package[0] = 1;
        package[1] = 0;
        package[2] = -1;
        package[3] = -1;
    
    }


    //True Peak Detect
    if(start_press and (deci > max_deci)){
        max_deci = deci; 
        max_point = rec_point; 
    }

    //End Detection
    if(start_press and (dd1 < 0) and (dd2>0) and (dd1 < dd1_th) and (deci < -deci_th_end)){

        start_press = false; 
        end_press = true; 
        record_sig = 0; 

        package[0] = 0;
        package[1] = 1;
        package[2] = max_point;
        package[3] = scalation(max_deci);

        Sender(package);

        //Reset del True Max
        package[0] = 0;
        package[1] = 0;
        package[2] = -1;
        package[3] = -1;

        max_point = -1; 
        max_deci = -10000000;

    }

    //Send Signal 
    if (record_sig and rec_point == 0){
        Sender(package);
    }

    if (record_sig){
        rec_point += 1; 
    }
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

    package[0] = 0;     //Init Flag
    package[1] = 0;     //End Flag
    package[2] = -1;    //Max Pos
    package[3] = -1;    //Max Value

    max_point = -1; 
    max_deci = -10000000;

    deci_th_st = long(abs(intercept)/10000) *10000 +5000;

}

float scalation(long x)
{
    float y = (gradient/100000.0)*(x - intercept);
    //Estos joputas sólo entregan valores desde y > 0.5 | y < -0.5!!!
    y = y*((y > clamp_val) + (y < -clamp_val)); 
    return y;
}



void Sender(float data[4]){
    
    for (int i = 0; i < 4; i++){
        Serial.print(data[i]);Serial.print("\t"); 
    }
    Serial.println();
}

