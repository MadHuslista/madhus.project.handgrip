
#include <SPI.h>

/*
Referencias: 
https://circuitdigest.com/microcontroller-projects/arduino-spi-communication-tutorial
https://forum.arduino.cc/t/arduino-as-spi-slave/52206/15

https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf
(punto 18.5 SPI Register Description);
*/

/*
 * Equipo       Pin Config: 
 * 
 * DOUT (Y)     11  MOSI    Master Outputs, Slave Inputs    
 *              12  MISO    Master Inputs, Slave Outputs
 * PD_SCK (G)   13  SCK     SPI Clock 
 * Ard Pin 9    10  ~SS     Slave Set (negative logic => LOW = Slave Selected)
 */



/******************************************************************************************
 ****************************************************************************************** 
 ******************************************************************************************/


//Pin Config 
int SSpin = 9; 

//Acquisition Utils
unsigned char buf[3];  //Por documentación son 24 bits por tanto 3 bytes
uint32_t f = 0;
volatile byte pos;  
volatile boolean process_it; 
int calib = 10; //10 first values plus  1 interception check 


//State Detection
unsigned long st_time = millis(); 
unsigned long dur_time;
int data_acq = 0; 
int state = -2;

int32_t present_value = 0; 
int32_t calib_prob = 0;

//Scalation
float gradient = 3.575;
float intercept = 0;
float clamp_val = 0.1;


// Start Values
int32_t prev_d0; //Definidos en la calibración 
int32_t prev_d1;

//Derivatives
int32_t dd1;
int32_t dd2; 
int point = 0; 

//Event Flags
bool start_press = false;
bool end_press = true; 
int record_sig = 0; 

//Thresholds
int32_t dd1_th = 10000;
int32_t deci_th = 150000;

//Mask Values
int st_mask  = 1;
int mid_mask = 0;
int end_mask = -1; 
int max_mask = 2;
int data_mask = 3;
int signal_mask = 4;
int mask;

//Storage
float info [3][5];  
int rec_point = 0 ; 

    /*          Data_Mask | Mask   |  Point |  Deci  |  Scal
     * Start
     * Max 
     * End
     */

//




void Visualization(int caso, int32_t deci, int32_t deriv_1, int32_t deriv_2, int rec_sig, int point = 0)
{
    if (caso == 1){
        Serial.println(deci);         
    }
    else if(caso == 2)
    {
        //Envío de Dato escalado
        Serial.println(scalation(deci));         
    }
    else if (caso == 3) 
    {
        // Código para calibración con Excel
        Serial.print(point++); Serial.print("\t");
        Serial.println(deci);
        while(point > 250);
    }

    else if (caso == 4) 
    {
        Serial.print(deci/100); Serial.print("\t"); Serial.println(deriv_1);

    }

    else if (caso == 5) 
    {
        Serial.print(point); Serial.print("\t");
        Serial.print(deci); Serial.print("\t"); 
        Serial.println(deriv_1);

    }
    else if (caso == 6)
    {
        Serial.print(deci/100); Serial.print("\t"); 
        Serial.print(deriv_1); Serial.print("\t");
        Serial.println(deriv_2);
        
    }
    else if (caso == 7)
    {
        Serial.print(deci/100); Serial.print("\t"); 
        Serial.print(deriv_1); Serial.print("\t");
        Serial.print(deriv_2); Serial.print("\t");
        Serial.println(rec_sig*10000);

        
    }

}

void Sender(int mask_type, int mask, int p, int32_t deci, float kg){
    //OverLoaded Func
        Serial.print(mask_type); Serial.print("\t"); 
        Serial.print(mask); Serial.print("\t"); 
        Serial.print(p); Serial.print("\t"); 
        Serial.print(deci); Serial.print("\t"); 
        Serial.println(scalation(deci));

}

void Sender(float data [3][5]  ){
    //OverLoaded Func
    for(int i = 0; i < 3; i ++){
        Serial.print(data[i][0]); Serial.print("\t"); 
        Serial.print(data[i][1]); Serial.print("\t"); 
        Serial.print(data[i][2]); Serial.print("\t"); 
        Serial.print(data[i][3]); Serial.print("\t"); 
        Serial.println(data[i][4]) ;

    }
}

void setup(){

    Serial.begin(115200);
    SPI_config(); 
//    Initial_check();

    pos = 0; 
    process_it = false; 
    digitalWrite(SSpin, LOW);

}

void loop(){

    if(process_it)
    {
        int32_t deci = concat_convert(buf);
        present_value = deci;

        if(calib){
            calibration(deci);
        }
        else{

            data_acq = 1;
            st_time = millis();

            //Derivatives compute. 
            point++;
            dd1 = deci - prev_d0;
            dd2 = dd1 - prev_d1; 

            //Update Values
            prev_d0 = deci; 
            prev_d1 = dd1;
            mask = mid_mask; 


            //Start Detection
            if (end_press && (dd1 > dd1_th) && (deci > -deci_th)){
                
                start_press = true;
                end_press = false;                
                record_sig = 1; 
                rec_point = 0;

                mask = st_mask;
                
                info[0][0] = data_mask;
                info[0][1] = st_mask;
                info[0][2] = rec_point;
                info[0][3] = deci;
                info[0][4] = scalation(deci);

            }

            //True Peak Detection 
            if (start_press and (deci > info[1][3])){
                info[1][2] = rec_point;
                info[1][3] = deci;
                info[1][4] = scalation(deci); 
            }


            //End Detection
            if(start_press and (dd1 < 0) and (dd2 > 0) and(dd1 > -dd1_th) and (deci < -deci_th)){
                start_press = false; 
                end_press = true; 
                record_sig = 0;

                mask = end_mask;
                Sender(signal_mask, mask, rec_point, deci, scalation(deci)); //Como inhabilita el record_sig, igual es necesario enviar el dato de fin

                info[2][0] = data_mask;
                info[2][1] = end_mask;
                info[2][2] = rec_point;
                info[2][3] = deci;
                info[2][4] = scalation(deci);

                Sender(info);

                //Reset del True Max
                info[1][0] = data_mask;
                info[1][1] = max_mask;
                info[1][2] = -1;
                info[1][3] = -10000000;
                info[1][4] = 0;


            }

            //Send Signal 
            if (record_sig){
                Sender(signal_mask, mask,rec_point, deci, scalation(deci));
                rec_point += 1; 
            }

            //Visualization(7, deci, dd1, dd2, record_sig,point);
//            while(point > 2000);



        }
        pos = 0;
        process_it = false;
        digitalWrite(SSpin, LOW);
    } else {


        if ( !data_acq && calib  ){
            state = -2; // Está en estado apagado. 
        } 
        else if (!data_acq && !calib ){
            state = -1; // Se acaba de terminar de calibrar, espera a que inicia la toma de datos. 
            
        }
        else if(data_acq && !calib && (millis()- st_time) < 100){
            state = 1; // Modo ON, está tomando datos. 

            if(calib_prob){
                
                /*  Si se inicio en Modo calibración, sin haber detectado el apagado (Es decir, sin resetear el estado del equipo)
                    Se efectúa el reseteo aquí, pero actualizando el estado al valor que debería llevar al momento:
                    Es decir: 
                        calib = 8 (esta detección ocurre al 2' punto generado desde encendido el equipo)
                        intercept  = 10%( primer punto) + 10%( segundo punto)

                    Además: 
                    state = -2;  
                    data_acq = 0; 
                    
                    Para mantener consistencia con el apagado correcto
                */

                state = -2; 
                data_acq = 0; 
                calib = 8; 
                intercept = calib_prob/10.0 + present_value/10.0;

                calib_prob = 0;
            }
        }
        else if(data_acq && !calib && (millis()- st_time) >= 200){
            state = 0; // Ocurrió el Apagado. (El instante de cambio de estado)
            calib_prob = 0;
            Serial.print(state); Serial.print("\t");
            Serial.println(404);
            data_acq = 0; 
            calib = 10; 
            intercept = 0;


        }
        else if(data_acq && !calib && (millis()- st_time) > 150){
            calib_prob = present_value; 
            /*  Si llegó hasta acá, probablemente Inició en Modo Calibración. 
                Y luego se apagó sin haber tomado datos. 
                El tema es que la espera de fin calib e inicio de datos es indiferenciable de la espera de un apagado. 
            */
        }

        // Serial.print(data_acq); Serial.print("\t");
        // Serial.print(calib);
        // Serial.print("\t");
        // Serial.print(state); Serial.print("\t");
        // Serial.println(millis()- st_time);


    }

}




float scalation(int32_t x)
{
    float y = (gradient/100000.0)*(x - intercept);
    //Estos joputas sólo entregan valores desde y > 0.5 | y < -0.5!!!
    y = y*((y > clamp_val) + (y < -clamp_val)); 
    return y;
}

void calibration(int32_t init_read){

    intercept += init_read/10.0; //Average of the first 10 values at device startup
    calib -- ;
    // if(!calib && !(-225800.0 < intercept && intercept < -169600.0)){      //If resultant Intercept not (-1Kg < intercept < 1Kg) assign -195680; 
    //     intercept = -195680;
    // }    
    prev_d0 = intercept; 
    prev_d1 = intercept;
    info[1][0] = data_mask;
    info[1][1] = max_mask;
    info[1][2] = -1;
    info[1][3] = -10000000;
    info[1][4] = 0;

    Serial.println(intercept);

}



int32_t concat_convert(unsigned char buffer[]){

    //Concatenación de los bytes  (ojo que se ocupa uint32_t f, porque no existe uint24_t, por lo que sobra el MSB byte!)
    uint32_t val = ((uint32_t)buffer[0]<<16) |((uint32_t)buffer[1]<<8) | ((uint32_t)buffer[2]<<0);; 

    //Conversión de Two Complement -> Decimal con signo
    uint32_t sign_mask = 0x800000; // 1 in MSB of 3 bytes

    if ((val & sign_mask)==0){
        return val; 
    }
    else{
        return -(~(val | 0xFF000000 ) +1); 
        // val | 0xFF000000 -> Como val es de 4 bytes, pero el valor útil es de sólo 3 bytes, 
        // debo enmascarar el primer byte con 1, para que al invertir se omita. 
        // -() + 1-> complemento + 1 me da el valor absoluto, y luego se agrega el signo
    }

}

ISR(SPI_STC_vect){
    byte c = SPDR; //Lectura de la data que llegó al Registro: Buffer SPI (1 byte)

    if (pos < sizeof(buf)){
        buf[pos++] = c;         //Traspaso de la data leída al buffer en código para continuar con la palabra, 
        
        if(pos==sizeof(buf)){
            digitalWrite(SSpin, HIGH); // Si la palabra se completó, mandar la señal de 'Fin de Data' 
            process_it = true;
        }
    }
}




void SPI_config(){
    
    pinMode(MISO, OUTPUT);
    pinMode(SSpin,OUTPUT);


    /* 
     * Configuración de la comunicación SPI 
     */

    //Habilitación de la detección de dato SPI por interrupción 
    SPCR |= 0x80; // |= 0b 1000 0000 // |= _BV(SPIE) // SPI.attachInterrupt();

    //Habilitación de la Comunicación SPI!
    SPCR |= 0x40; // |= 0b 0100 0000 // |=  _BV(SPE) 

    //Data Order as MSB First (1 = LSB first; 0 = MSB First)
    SPCR &= 0xDF; // &= 0b 1101 1111 // &= ~(_BV(DORD))

    //Habilitación del Arduino como Slave
    SPCR &= 0xEF; // &= 0b 1110 1111 // &= ~(_BV(MSTR))

    //Configuración de CPOL => Señal HX710 es CPOL = 0
    SPCR &= 0xF7; // &= 0b 1111 0111 // &= ~(_BV(CPOL))

    //Configuración de CPHA => Señal HX710 es CPHA = 1 
    SPCR |= 0x04; // |= 0b 0000 0100 // |=  _BV(CPHA) 

    //Los últimos 2 bits son para configuración de freq' del SCK, lo cual no tiene efecto en el slave
    //Serial.print("SPCR: ");
    //Serial.println(SPCR, BIN);
}

void Initial_check(){
    unsigned char A = 0b11111100; 
    unsigned char B = 0b11111010;
    unsigned char C = 0b10100010;
    f = ((uint32_t)A<<16) |((uint32_t)B<<8) | ((uint32_t)C<<0);
    Serial.print(f, BIN); Serial.print("  =>  ");

    buf[0] = A; 
    buf[1] = B; 
    buf[2] = C; 
    int32_t d = concat_convert(buf); //    int32_t d = -(~(f | 0xFF000000 ) +1);
    Serial.println(d);

}

/*
 * LEGACY CODE: 
 * 
    Data debería ser: 
    1111 1100 1111 1010 0111 0010 => -197982


    Rev del Buf
        Serial.print((unsigned char)buf[0], BIN); Serial.print("\t");
        Serial.print((unsigned char)buf[1], BIN); Serial.print("\t");
        Serial.print((unsigned char)buf[2], BIN);  Serial.print("\t");

    Concatenación de los bytes  (ojo que se ocupa uint32_t f, porque no existe uint24_t)
    f = ((uint32_t)buf[0]<<16) |((uint32_t)buf[1]<<8) | ((uint32_t)buf[2]<<0);
    Serial.println(f, BIN);

    Datos: 
    -   Char is an integer type, y corresponde a un byte de 8 bits => Lo que corresponde al tammaño del registo SPDR (la data recibida del SPI)
    -   sizeof entrega el número de bytes del objeto 
    -   array[index++]  => var++ post-increment, ++var pre-increment
                        => primero entrega array[index]; y luego aplica index++;- 

    -   Existe un SPI buffer, que luego de leer SPDR, lo vuelve a rellenar. 


 */