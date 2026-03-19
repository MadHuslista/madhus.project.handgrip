const byte DOUT = 2;
const byte PD_SCK = 3; 

byte data = 0b000000000000000000000000000;
int pos = 26; 
bool b ; 

inline void digitalWriteDirect(int pin, boolean val){
  if(val) g_APinDescription[pin].pPort -> PIO_SODR = g_APinDescription[pin].ulPin;
  else    g_APinDescription[pin].pPort -> PIO_CODR = g_APinDescription[pin].ulPin;
}

inline int digitalReadDirect(int pin){
  return !!(g_APinDescription[pin].pPort -> PIO_PDSR & g_APinDescription[pin].ulPin);
}

void setup() {
  pinMode(DOUT, INPUT_PULLUP);
  pinMode(PD_SCK,INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PD_SCK), Init, FALLING);
  Serial.begin(115200);

}

unsigned long s, e, t; 
bool a[27] = {};

void loop() {
  Serial.println(data,BIN);
}

void Init() {
  bitWrite(data, pos,digitalReadDirect(DOUT));
  pos--;
  if(pos==0){
    pos = 26;
   }
}
