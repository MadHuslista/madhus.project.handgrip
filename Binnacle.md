Obtener: 
    -> Trigger de Inicio
    -> Trigger de Punto máximo 
    -> Trigger de Fin 

    -> Fin de Dato 

Avance Inicial 
    -> Al abrir el equipo - Son galgas extensiométricas. 
    -> Se controlan por un IC, el HX710B

Objetivo Actual: 
    -> Leer la salida del HX710B


Se prueba la carga por USB
    Carga por USB sí funciona, pero necesita la batería conectada. USB sólo sirve para cargar Batería. 
    Pareciera no tener software asociado para la descarga/ transmisión de datos. 


Análisis de las Conexiones de las Galgas. 


=== TEORÍA ==================

Diagrama de Galga (Full Bridge): 
    
    RED     -> Vcc
    WHITE   -> Signal-
    BLACK   -> GND
    GREEN   -> Signal+

El diagrama eléctrico es: 
    
             Vcc
           /     \
(<->)    R1      R3  (-><-)
       /           \
     S+----  dV ----S-
       \            / 
(-><-)   R2      R4  (<->)       
           \     /
             GND

Su comportamiento: 
    -> Compresión   : La galga se engruesa y acorta -> Disminuye su resistencia (-dR)
    -> Tensión      : La galga se adelgaza y estira -> Aumenta su resistencia   (+dR)

La Func de Transferencia es: 

    dV = Vcc * [  (R2/(R1+R2) - (R4/(R3+R4)  ]

Para su correcto funcionamiento se asume que todas las Rn son de igual valor nominal

    R1 = R2 = R3 = R4 = R

Y luego, que varían de igual manera en dR, según indica el diagrama (-><- / <->)
Por tanto, reemplazando respectivamente R-dR / R+dR
La func de transferencia queda en: 

    dV = Vcc * dR/R = dR * Vcc/R

O lo que es lo mismo: 


    dV(dR) = dR * K ; con K = Vcc/R


====== PLACA ==========

Estas llgan directamente a la Placa a un conector: 

GND AN_N AN_P +3.3V 
Bck Wht  Grn  Red      

    BLACK   -> GND
    WHITE   -> Signal-
    GREEN   -> Signal+        
    RED     -> Vcc

Además, son dos galgas que están conectadas en paralelo (R-R; W-W; B-B; G-G) lo que así _promedia_ la salida 

----

Luego la salida pasa por dos R, y un capacitor de desacople para llegar al IC? Preguntar. 

S- -> R ----,---IN-|    |
            C      |IC  |
S+ -> R ----'---IN+|    |


Placa tiene un puerto de Debugueo: 

    GND     Green     - En continuidad con el GND de las galgas y con el pin2 (AGND) del IC (Input Ground)     
    SCLK    Yellw     (Aunque parece que estos sclk y DIO son del procesador, no de la data) 
    DIO     Nrnja
    3.3V    Red
  (ESTOS PINES NO COINCIDEN CON LA SALIDA DEL HX710B -> CORRESPONDEN A LA CPU AUNQUE AÚN NO SE HA PROBADO) 

Se utilizará este Ground como referencia para poder analizar las mediciones. 


Del IC HX710B se va al CPU

CPU: ARM STM32F103RC - Package LQFP64 (https://www.tme.com/Document/fb7c415b4c99be3d814655275d039285/stm32f103xd_xe.pdf)

|       |       
|       |
|   IC  |DOUT       - CPU(6 hacia arriba desde cost inf der direc lectura code cpu) pc7
|       |PD_SCK     - CPU(7)                                                        pc8


======= MEDICIONES SALIDA DIGITAL IC ==============

|       |       
|       |
|   IC  |DOUT    
|       |PD_SCK  

PD_SCK
    
    - Al osciloscopear el PD_SCK, en escala 1V/5.00uS -> SE ENCUENTRAN LOS 27  PULSOS QUE INDICA LA DOCUMENTACIÓN! Y DE MANERA CONSISTENTE! 
   
    Características del Pulso:  
    - 27 pulsos, de ~1uS en High y ~1uS en Low (consistente con valor típico en doc) 
    
    Interpretación: 
    - La CPU efectivamente le está enviando el tren de pulsos al HX710B
    - Este tren de pulsos provoca que se devuelva: El Differential Input a 40HZ 

DOUT

    - 24bits 
    - Configurado en 2's complement
        > Esto significa -> el complemento del número binario más 1
        > Ej: bin: 110010 -> complemento: 001101 -> 2's complm: complm + 1: 001101 + 1 = 01110


    - min:  800000h     max:    7FFFFFh     (hex y bin, cada dígito del hex coincide con su rep en 4bin cuando el hex completo se pasa a bin) 
            8   1000            7   0111    
            0   0000            F   1111
            0   0000            F   1111
            0   0000            F   1111
            0   0000            F   1111
            0   0000            F   1111

        > 800000h = 1000 0000 0000 0000 0000 0000
        > 7FFFFFh = 0111 1111 1111 1111 1111 1111


PROTOCOLO DE COMUNICACIÓN: 

- El DOUT genera un falling edge.
- De ahí, se esperan 0.1uS = 100nS y luego se comienzan los 27 pulsos del PD_SCK
- A la vez, desde que -empiezan- los 27 pulsos del PD_SCK (que en la práctica configuran el dato siguiente, el actual viene configurado por el PD_SCK anterior) 
    hasta que inicia el primer BIT (MSB) pasan 0.1uS = 100nS

- El resto de los Bits, pasan a 40Hz Data rate. 
    - No sé si eso significa 40Hz cada bit, o 40 datos de 24bits por segundos. 

    Caso 1: 40bits/seg => 1 bit = 0.025s = 25ms
    Caso 2: 40datos/seg = (40*24)/seg = 1000bits/seg = 1ms! (puedo compararlo con la señal de test del oscilo!)  




    Aún no resuelto pero: 

SE EL CPU SOLICITA DATOS CADA ~40ms! (Lo que tiene lógica por la baja freq' de la señal) 

    > Y es cada esos 40ms que el PD_SCK envía los 27 pulsos
    > CADA PULSO (High+Low) ES UN BIT RECUPERADO
    >

    EJ

    kkkkkkllkkkkklklklklllkl
    111111001111101010100010 = -197982

==================== Siguiente paso de acción -> Soldar los cables. 

Planificación del cableado: 

    1. Tienen que salir 3 cables
        GND,    -> Azul
        DOUT,   -> Amarillo
        PD_SCK  -> Verde

    2. La salida será por lateral, para facilitar montaje y mantención 
        -> Y en específico abajo del botón lateral izquierdo superior (flecha arriba); 
            Esto porque así evita curvas peligrosas, avanza por debajo de la pantalla y la eleva un poco pero de manera uniforme. 

SUCCESS PERO PULENTO
TODO FUNCIONA Y SE MANTIENE ESTABLE CTMRE <3


Características de la Señal: 

-> PD_SCK: 

    - 27 pulsos- 46.6us (Cada pulso es un High+Low)
    - Periodo Señal: 39ms / 25.64Hz
    - Ocurre cada 39ms. Y al inicio de esos 39ms dispara 27 pulsos en 46.6us. Luego silencio, hasta el siguiente segmento de 39ms.  

    AMP: 
        (Obser & under shoots, not always) 
        - Ovsershoot: ~ +4.68V  
        - Undershoot: ~ -1.12V
        - High V:       3.36V
        - Low  V:       0V. 
    
    Time: 
        - Pulso completo: 
            Periodo:    1.76us 
            Freq:       568.18 KHz

        - High Time:    0.72us (1.39MHz) 
        - Low  Time:    1.06us (952.38KHz) 

        - Rise Time: 86ns
        - Fall Time: 94ns

-> DOUT: 
    
    - 24 pulsos - 42.30us (Aquí no son 'pulsos' sino que son 'estados' pudiendo ser HIGH or LOW)
    - Periodo Señal: 39ms / 25.64Hz
    - Ocurre cada 39ms. Y al inicio de esos 39ms dispara 24 pulsos en 42.3us. Luego silencio, hasta el siguiente segmento de 39ms.  
    - Aquí cada 'estado' H or L, dura un pulso 'high+low' de PD_SCK

    AMP: 
        - High V:       3.36V
        - Low  V:       0V. 

    Time: 
        - Estado: 
            Periodo:    1.8us
            Freq:       555.56KHz    

            Rise Time: 0.55us 1.82MHz
            Fall Time: 0.4us  2.56MHz

    Delay from PD_SCK: 
        - Rise: 38ns
        - Fall: 28ns

=== Siguiente paso: 

--- Código: 

Partir sampleando y ploteando el PD_SCK para ver la velocidad del arduino, sino pasar a un Mega (?) 
https://www.proyectoelectronico.com/arduino/bascula-con-arduino-hx710.html

Luego hacer calibración:    
    - Tomar una serie de datos entre el dato binario y lo presentado en pantalla 
    - Luego hacer regresión lineal en Excel para pillar la ecuación lineal (?) -> Debería 

    [UPDATE: DONE & DONE MUTHAFUCA lml]


== Side tracked to DUE. 

-> Maybe using external interrupts will be more reliable: 

-> Intenté de todas las maneras posibles con los interruptores del DUE y la función de lectura rápida. Y nada. 
        (UPDATE: pero no confuiguré el DUe como Slave SPI. esto era)  

=> OJO! Cuando hice la conversión a Binario, y obtuve valores erráticos, no consideré que la codificación estaba en 2 bin complement! 
    Por tanto si bien está el riesgo que de los valores no capturen todos los bits, 
    Aún está en calidad de riesgo y podría ser una solución viable. 


=== Hasta ahora no he logrado la frecuencia de muestreo suficiente para lograr lo anterior. 

Intento con: Rasberry Pi 3 Model B+
(Later for Raspberry PICO: (https://www.tomshardware.com/how-to/raspberry-pi-pico-setup)


Instalation Types:

    Headless, vs Headwith   :   Headless: Not peripherals attached (i.e. No monitor, no keyboard, no mouse needed. Contoled by SSH) 
    GUI vs CLI              :   As mentioned. GUI tiene montón de software extra, que vuelve las actualizaciones mucho más lentas. 


First Try: 
    -> Headless && CLI instalation: https://www.tomshardware.com/reviews/raspberry-pi-headless-setup-how-to,6028.html

    About the choosen OS: 
    -> The chip is 64-bit, but the official OS releases are 32-bit; because the 64bit chip are only a new thing; and as everything (app, OS, enviroment) is 32-bit the major compatibility is in 32, and the 64 version are still a few, not fully maintained and the performance boost is still not relevant. 

    Installation: 

    -> Install Raspberry Pi Imager: https://www.raspberrypi.com/software/
    -> Open it and choose Operating System: 
            Production : Raspberry Pi OS LITE (32-bit); Choose SD
            Development: Raspberry Pi OS (32-bit); Choose SD 
    -> Write Configs: 
        - Hostname: SensorPi
        - Enable SSH: 
            -> Use Pass authentication
                User: pi
                Pass: sensorpi

        - Enable wireless LAN: 
            -> Configure Wireless LAN. 

                SSID (nombre de la red):    Claro-db60-5G
                PAss:                       118856000816

    -> Write
        -> Ojo, pide contraseña de admin y muestra un contador de avance. 


    Connección mediante SSH: 

    -> Insertar la SD en el Pi, y conectar con conector USB
    -> Buscar la IP 
        - ifconfig (para saber IP de la red) (192.168.0.5)
        - sudo nmap -sn 192.168.0.5/24 (ej: sudo nmap -sn 192.168.1.91/24

        -> Rasp IP: 192.168.0.7
    
    -> ssh pi@192.168.0.7 // pass: sensorpi
        -> Success. 


    -> sudo apt update && sudo apt upgrade. 


    Connección mediante VNC

    Instalar VNC Viewer 
        User: nicolaschiappacasse@gmail.com
        Pass: nicolas526

    -> Pi SSH connected, run in terminal: 
        sudo raspi-config
            Interfacing Options -> VNC -> yes -> Enter -> Finish
    
    -> VNC Viewer: 
        New connection 
        VNC Server: 192.168.0.7 (Ip of Pi) 
            user & pass. 

    -> If "Cannot currently show desktop" 
        sudo raspi-config > Display Optiones > Some resolution > Reboot. 

        
        



NEXT: How to use GPIO
!! Is a Linux OS!! SO the way to program an use that programs are the same way that is used in Linux Mint!! 

-> So, open a Python file, write the program and then just show it. // Same with C. 

https://schollz.com/raspberrypi/gpio/
https://forums.raspberrypi.com/viewtopic.php?t=327097

http://abyz.me.uk/rpi/pigpio/piscope.html


INTERESTING WITH GO: https://periph.io/news/2017/gpio_perf/

INTERESTING WITH C: 
    - https://bob.cs.sonoma.edu/IntroCompOrg-RPi/sec-cgpio.html
    - https://www.ics.com/blog/how-control-gpio-hardware-c-or-c
    - https://www.ics.com/blog/gpio-programming-using-sysfs-interface  -> SYS INTERFACE
    - https://s-matyukevich.github.io/raspberry-pi-os/ COURSE

    - https://www.bigmessowires.com/2018/05/26/raspberry-pi-gpio-programming-in-c/ Alternatives to control GPIO
    - https://elinux.org/RPi_GPIO_Code_Samples#bcm2835_library                     Alternatives to control GPIO         

    - https://www.instructables.com/Microcontroller-Register-Manipulation/          General Register Manipulation


First Test with C: 

-> Install WiringPi: 

https://forums.raspberrypi.com/viewtopic.php?f=33&t=207884&p=1285283#p1285283

    cd /tmp
    wget https://unicorn.drogon.net/wiringpi-2.46-1.deb
    sudo dpkg -i wiringpi-2.46-1.deb

-> Setup Wiring Pi (How to Build) && Blink LED:
https://www.electronicwings.com/raspberry-pi/how-to-use-wiringpi-library-on-raspberry-pi

To compile & execute: 

gcc -o led_blink led_blink.c -l wiringPi
sudo ./led_blink


-> Example Interrupts: 

https://github.com/WiringPi/WiringPi/blob/master/examples/isr.c
http://wiringpi.com/reference/priority-interrupts-and-threads/

next: https://www.bigmessowires.com/2018/05/26/raspberry-pi-gpio-programming-in-c/
!!!
    -> fINALLY THE c CONTROL WITH REGISTERS! 



-> NEXT: 
Create interrupt that COUNTS the downs and then timeout

=> NOT GOOD FUCK

NEXT: How to send the data out from de Raspberry. 

https://stackoverflow.com/questions/67792258/how-to-send-real-time-output-from-raspberry-pi-to-my-external-computer
https://stackoverflow.com/questions/64642122/how-to-send-real-time-sensor-data-to-pc-from-raspberry-pi-zero
http://www.steves-internet-guide.com/into-mqtt-python-client/


============== SPI 

Pareciera ser ue se podría adaptar la señal a ser leída bajo protocolo SPI


"Shifts in a byte of data one bit at a time. Starts from either the most (i.e. the leftmost) or least (rightmost) significant bit. For each bit, the clock pin is pulled high, the next bit is read from the data line, and then the clock pin is taken low.
If you’re interfacing with a device that’s clocked by rising edges, you’ll need to make sure that the clock pin is low before the first call to shiftIn(), e.g. with a call to digitalWrite(clockPin, LOW).
Note: this is a software implementation; Arduino also provides an SPI library that uses the hardware implementation, which is faster but only works on specific pins."

https://www.arduino.cc/reference/en/language/functions/advanced-io/shiftin/



=> El Arduino acepta hasta 16MHz SPI (o min 8MHz)

- En SPI Hz = bps => 16MHz = 16Mbps => 1bit = 0.0625us! Más que suficiente. 

=> Por tanto se está configurando como Esclavo SPI segú manipulación de Registros y librería SPI
        Referencias: 
        https://forum.arduino.cc/t/arduino-as-spi-slave/52206/9 THIS IS THE BIG ONE
        https://circuitdigest.com/microcontroller-projects/arduino-spi-communication-tutorial

        https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf
        (punto 18.5 SPI Register Description);


=> El protocolo SPI tiene 2 configuracines principales:

    -> Clock Polarity   : 

                        Define el estado 'inactivo' del reloj.  
                        Es decir, toda la computación se hace durante el estado 'activo' del reloj
                        Luego el 'leading edge' (canto de inicio del ciclo) y el 'trailing edge' (canto de término del ciclo) quedan definidos en función de este estado activo. 

                        Por tanto: 
                        CPOL = 0    =>  idle = 0    => Activo = 1   => Leading = Rising Edge; Trailing = Falling Edge
                        CPOL = 1    =>  idle = 1    => Activo = 0   => Leading = Falling Edge; Trailing = Leading Edge

    -> Clock Phase      : 

                        Define la 'fase' de la data respecto al reloj 
                        Es decir, en qué canto (Leading or Trailing) se samplea el dato, y en cuál canto se _cambia_ el dato. 

                        Por tanto: 
                        CPHA = 0    :   Data Sampling   => Leading Edge     ; Data Shifting => Trailing Edge
                        CPHA = 1    :   Data Shifting   => Leading Edge     ; Data Sampling => Trailing Edge 


                        Aquí cabe destacar que dado que el Leading Edge -por definición- viene antes que el Trailing Edge, 
                        Sí CPHA = 0 (i.e. Primero Sampling y luego Shifting) entonces antes del primer ciclo, el DATO YA DEBE ESTAR ESPERANDO para ser leído


=> Dada esta configuración la Señal del HX710B es: 


                        Según documentación: 

        
        PD_SCK: 

            -> 'idle    state' = 0; porque si PD_SCK se mantiene en '1' por más de 60us; proboca que el HX710B entre en 'power down mode' 
            -> 'active  state' = 1; porque data is shifted out from the DOUT by 'POSITIVE CLOCK PULSES' of the PD_SCK

            Luego:             
                    CPOL = 0; idle at 0 => ACTIVO at "1"  

        DOUT: 

            -> El dato es 'shifted out' from the IC by de positive pulse of PD_SCK:
            -> Por tanto, 

                -> El bit aparece/cambia en DOUT                            en el Leading Edge  => Que dado que CPOL = 0 => Aparece en el Rising Edge
                -> Por tanto el bit está estable y por tanto debe ser leído en el Trailing Edge => Que dado que CPOL = 0 => Aparece en el Falling Edge
                
                
            Luego: 
                    CPHA = 1    : Data Shifting   => Leading Edge     ; Data Sampling => Trailing Edge 
        

        



=> Avances: 

    -> Reacciona sólo cuando está enviando data. 
    -> El timing del 'process_it' es app 40ms, lo que corresponde 

    -> pero los datos son los que no calzan!!

    => LO LOGREÉEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE CONSHATUMARE LO LOGRÉ OH SÍ LO LOGREEEEE WEOOON AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAH

        ME 
    

        FALTAN 


        MAYÚSCULAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAS



                                                    LO 

                                                        LOGRÉ   


                                                               CONSHA
                                                                                TUMAREeEEEEEEEEEEEEEEEEEEEE!!!!






    -> Efectivamente, el codigo funcionaba relativamente bien. 

    -> Improvements necesarios: 

       -> Primero simular el SS!
        https://arduino.stackexchange.com/questions/5097/how-do-i-transfer-more-than-1-byte-at-once-via-spi-bus
        Setup:            
            int SSpin = 4;
            digitalWrite(SSpin,LOW) 
        ISR: 
            when done, digitalWrite(SSpin, HIGH);

        loop: 
            when process done, digitalWrite(SSpin, LOW);

        Esto sincroniza la data -en particular el high- tal como dice el Datasheet del ATMEl


    -> Segundo!!

        El Serial.print tiene una pifia. ASUME que es signed char al imprimir char, BIN => Por tanto falla por overflow (?) y lanza 32 BITS CTMRE

        Al corregir según: 
            Serial.prinln((unsigned char) buf[0], BIN); QUEDA IMPECABLE CTMRE



    *YEEEEEEEEEEEEESSSSSSSSS*



=> En el proceso de conversión de los Bytes recibidos (3) a decimal. 

    => El ADC del Arduino tiene 26bit degault buffer size. De ahí que sólo pueda manejar shifts hasta el espacio 16. 
        https://forum.arduino.cc/t/concatenate-bytes-into-single-value/594562/5


        Solución es castear (long)A<<16

    => Además, como no existe un uint24_t, estamos trabajando con un uint32_t

        -> Por tanto, antes de hacer la conversión two complemet, se debe enmascarar con |= 0xFF000000 (|= 0b111111111 00000000 00000000 00000000)
            Para que al hacer la inversión de bits, se consideren sólo 3 byts de info real. 



=> Conversión de Decimal a Valor en Kg correspondiente: Calibración: 


    250 puntos consecutivos, con medida estable en Kg
    0 - 22 Kg

    => VARÍA!!!

    -> Para mantener una calibración 'correcta', el equipo mide el cero en cada encendido. 
    Para ello, genera 10 LLAMADAS AL CONVERSOR PARA CONOCER SU ESTADO! 

        -> Y respecto a ello, hace la calibración. 

        -> Además de que si la calibración está demasiado por fuera de los valores estimados (-1 < val < 1)[Kg] los trimea al un valor previo 
        (probablemente el tarado anterior
                => EEPROM? Ojo EEPROM se comunica por SPI) 

    == ESTOS WEONES PA OCULTAR EL JITTER DE SU MEDICIÓN EN CERO, SÓLO INDICAN EL VALOR POR SOBRE (-0.5 > VAL > 0.5)!!!!!
        -> Se incorpora por compliance. 


NEXT STEPS: 

    -> Deuda: Hacer la calibración con el excel. 

    Como la calibración la estoy haciendo en base a los DECI, la calibración del Arduino no me afecta. Al contrario, me ayuda a omitir el jitter del reseteo. 

    -> Implementar la detección de los Cantos. 

        => Estrategia de Detección: 

            - Todo calculado en base a los DECI
            - el Start y End => Calculado en base a la 1' derivada discreta. 

            - el max => Peak detection utilizado en el LaceClips


        => Protocolo de envío: 
            - Todo por Serial. 
            - Cuando inicia la medición, envía: "Tag Inicio medición - millis()" => Se considera time de inicio para el conteo del resto 

        => Tag Start: 
            - "Tag Start - millis() - vak Kg"

        => Tag Max: 
            - "Tag Max - millis() - vak Kg"

        => Tag End: 
            - "Tag End - millis() - vak Kg"




LAST STEPS: 

        => Encase: 

        -> En Arduino Nano (ATmega328P, 16MHz; igual que el UNO) 
        -> Carcasa en 3D
        -> Alimentado por Batería independiente (?) => Intentar medir consumo 

        => Características del Encase: 

            -> Cambio de Batería o CONECTOR para la batería del Disp 
            -> Botón de encendido con luz LED para Patrones LED


            -> Patrones LED: 
                
                -> Patrón de Encendido una vez que ya hayan ocurrido las 10 llamadas de calibración ) 
                -> Presionar el Botón: 
                        -> Sólo una Vez: RESETEA Al Aruidno: https://www.instructables.com/two-ways-to-reset-arduino-in-software/
                        -> Mantenido: Apaga al Dispositivo (Algún capacitor + Relé? ) 
                                Esto se llama "Latching Relay Circuit" 
                                        => Módulo '1 Channel Latching Relay"
                                        => Ideal ocupar el Latching in low level (ground is ltached) 

                                Otra idea es agregar un circuito con Capacitores
                                        -> Hold => Apaga
                                            -> Se me ocurre que la cosa sea mediante el Volaje que va subiendo en el Cap ?
                                            -> O puede ser la corriente (aunque el comportamiento es al revés |I| siempre va de máx a 0, aunque varía la dirección de flujo si es carga o descarga (http://physics.bu.edu/py106/notes/Meters.html) 
                                                  
                                        -> Un toque => Resetea
                
                -> Patrón de DESCONECTADO -> Requiere Presión Manual para reseteo. 



========================== CONTINUACIÓN: 


&&&&&&&&&&&&&&&&&& TO DO &&&&&&&&&&&&&&&&&&&&&&&&: 

    -> A. Deuda: Hacer la calibración con el excel. 
            Como la calibración la estoy haciendo en base a los DECI, la calibración del Arduino no me afecta. Al contrario, me ayuda a omitir el jitter del reseteo. 

    +> B. Implementar la detección de los Cantos. 

        => Estrategia de Detección: 
            - Todo calculado en base a los DECI
            - el Start y End => Calculado en base a la 1' derivada discreta. 
    
    +> C. (2) Implementar la detección del máximo en tiempo real
            - el max => Peak detection utilizado en el LaceClips
                -> Requiere una ventana

            => Nope se hace luego de tener el end

    +> D. (3) Clampar la detección a 100gr

    +> E. (4) Implementar Comunicación del Vector de Dato 
        => Protocolo de envío: 
            - Todo por Serial. 

        => Tag Start: 
            - "Tag Start Code;val Kg"

        => Tag Max: 
            - "Tag Max Code;val Kg"

    +> F. (5) Implementar Buffer de datos. 
            - Captura completa desde start a fin 
            - Metadata: 
                - Cantidad de datos 
                - True Maxim. 

    +> G. (6) Señal de apagado del equipo. 
            - 
    +> H. Detección del Máximo pero post Buffer. 

LAST STEPS: 

        => Encase: 

        +> En Arduino Nano (ATmega328P, 16MHz; igual que el UNO) 
        -> Carcasa en 3D
        +> Alimentado por Batería independiente (?) => Intentar medir consumo EDIT: No necesario, porque siempre estará conectado con el PC 

        => Características del Encase: 

            -> Cambio de Batería o CONECTOR para la batería del Disp 
            -> Botón de encendido con luz LED para Patrones LED


            +> Patrones LED:  (EDIT: Al final no es necesario, porque la persona no necesita ver el led, lo necesita ver el experimentador) 
                
                +> Patrón de Encendido una vez que ya hayan ocurrido las 10 llamadas de calibración ) 
                +> Presionar el Botón: 
                        -> Sólo una Vez: RESETEA Al Aruidno: https://www.instructables.com/two-ways-to-reset-arduino-in-software/
                        -> Mantenido: Apaga al Dispositivo (Algún capacitor + Relé? ) 
                                Esto se llama "Latching Relay Circuit" 
                                        => Módulo '1 Channel Latching Relay"
                                        => Ideal ocupar el Latching in low level (ground is ltached) 

                                Otra idea es agregar un circuito con Capacitores
                                        -> Hold => Apaga
                                            -> Se me ocurre que la cosa sea mediante el Volaje que va subiendo en el Cap ?
                                            -> O puede ser la corriente (aunque el comportamiento es al revés |I| siempre va de máx a 0, aunque varía la dirección de flujo si es carga o descarga (http://physics.bu.edu/py106/notes/Meters.html) 
                                                  
                                        -> Un toque => Resetea
                
                +> Patrón de DESCONECTADO -> Requiere Presión Manual para reseteo. 


===========================================================

    +> B. Implementar la detección de los Cantos. 


    => Implementación exitosa, basta reemplazar las seañles deriv y deriv2 por los valores dd1 y dd2 
    -> Listo. Canto de entrada y canto de salida correctamente implementado. 

    
    +> C. (2) Implementar la detección del máximo en tiempo real

        -> Se probó trabajar con filtrado para mejorar el comportamiento de las derivadas, y en consecuencias los análisis, 
            pero en detrimento, retrasaba la señal. El tema es que el Ts = 40ms, y la resolución temporal crítica es 10ms!
       
        => Se intentará trabajar con una predicción en tiempo real. 
            => Efectuando extrapolaciones lineales en dd1 y dd2, intentar predecir el siguiente dd0

        => Hasta ahora el método actual funciona relativamente bien. Detecta el punto, pero con un sample de desfase generalmente.  (lo que implica 40ms! ) 


=======

    - I1: Filtrar dd1 (retrasa mucho) 

    - I2: Utilizar dd2 de dd1 filtrado 
        -> Quizás llega al cero en el peak 

    - I3: Incluir dd2 normal ¿Tendrá un comportamiento cercano al zero thresholdeable? 

    - I4: Si dd2 <0 Y la predicción está dentro del th

        => https://dsp.stackexchange.com/questions/33893/what-is-the-need-for-prediction-filter-in-pcm-and-dpcm
        => Al usar: 

            t=-1 => (xp, yp)  ;t=0 => (x0, y0)  ;t=1 => (xf, yf) 

            (yf - y0) = (y0 - yp) * (xf - x0) 
                        ---------
                        (x0 - xp) 
            
         #Aprovechando que es una señal discreta y no interesa demasiado el tiempo real) 
        
            (xf - x0) = (x0 - xp) = 1
        => 
            (yf - y0) = (y0 - yp)  
            (yf       = (y0 - yp) + y0
             yf       = 2y0 - yp  
            

    => La interpolación funciona bien, pero la detección falla. Aumenta el error de detección porque oscila demasiado y la oscilación cruza los thresholds 

    => TAMPOCO!! 
    Ya agoté la info de dd1, necesito más info. 


    - I5: Crear un modelo que mfodele la curva completa, y luego avanzar a través de la curva 
        
    - I6: Modelo semi periódico de la cosa yl o mismo que I5 


==============

Revisar el intercepto, mirarlo no más 

Recoectar el USB reinicia el Arduino! (Como pierde energía, lo apaga y lo enciende) 



========== Last Steps. 


+> Preparar el Encase
+> Efectuar una Calibración correcta. 



=============================================

https://naylampmechatronics.com/blog/25_tutorial-trasmisor-de-celda-de-carga-hx711-balanza-digital.html
https://www.e-gizmo.net/oc/kits%20documents/HX-711%20Weighing%20sensor/HX-711.pdf

============================================

Conexión Galgas: 
- 
ADC - Galga
Azul - Negro
amarillo - Blanco
verde - verde
rojo - rojo



===================================================


New topology:
- Arduino Nano - Old Bootloader
- Lib HX711 https://github.com/RobTillaart/HX711

Load Cell Amp:

| Pin HX711 Module | Cable | Pin Arduino Nano |
| ---------------- | ----- | ---------------- |
| VCC              | Rojo  | 5V (output)      |
| DAT              | Café  | D2               |
| CLK              | Azul  | D3               |
| GND              | Negro | GND              |


| Cable Galgas    | Semantic           | Pin HX711 Module |
| --------------- | ------------------ | ---------------- |
| Red Pair        | VCC                | RED              |
| Black Pair      | GND                | BLA              |
| White Pair      | Signal +           | WHT              |
| Green Pair      | Signal -           | GRN              |
| -not connected- | Shield against EMI | YEL              |


Acquisition Board Setup: 

## Power 
| Pin Acquisition Board | Cable Power | Semantic |
| --------------------- | ----------- | -------- |
| 19 - L                | Live        | Live     |
| 20 - N                | Neutral     | Neutral  |


## Celda de carga PM58
| Pin Acquisition Board | Cable Celda PM58 | Semantic     |
| --------------------- | ---------------- | ------------ |
| 5 - E+                | Red              | Excitation + |
| 6 - E-                | Black            | Excitation - |
| 7 - S-                | White            | Signal -     |
| 8 - S+                | Green            | Signal +     |


## Protocolo USB-RS485 (modbus - salida digital)

| Pin Acquisition Board | Cable Galgas | Semantic |
| --------------------- | ------------ | -------- |
| 1 - A+                | Red          | A+       |
| 2 - B-                | Black        | B-       |


### Config: 

1. Power the instrument and wait until it reaches normal display. 
2. Press Fn once to enter the menu system. 
3. Scroll main menus until you reach C5.CoM. 
4. Press ENT to enter that menu. 
5. Scroll to the parameter you want (check table below) 
6. When the parameter is shown, use the up/T key to change its value. 
7. Press ENT to confirm/save that item. 
8. Press Fn to go back out.

**Table of parameters**
| Menu Ítem ID | Parameter / Semantic         | **Set Value**  | Value Range    | Default   |
| ------------ | ---------------------------- | -------------- | -------------- | --------- |
| 500.Ar       | Device address               | 001            | 001–253        | 001       |
| 501.br       | Baud rate (in HectaBaud)     | 1152[hBaud]    | 24-6000[hBaud] | 96[hBaud] |
| 502.Vb       | Parity bit                   | 0  (no parity) | 0–2            | 0         |
| 503.so       | Stop bit                     | 1              | 1/2            | 1         |
| 504.AS       | ModBus Active sending mode   |                | 0(off)–1(on)   | 0         |
| 505.AF       | ModBus Active-send frequency | 100 Hz         | 0–9            | 2         |

