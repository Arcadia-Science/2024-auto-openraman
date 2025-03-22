// Controls the neon light source via a relay

bool lightOn; // status of neon light source (True: ON, False: OFF)

const int RELAY_CONTROL_PIN = 13; // pin on Teensy that commands the relay

const byte buffSize = 40;
char inputBuffer[buffSize];
const char startMarker = '<';
const char endMarker = '>';
byte bytesRecvd = 0;
boolean readInProgress = false;
boolean newDataFromPC = false;

char messageFromPC[buffSize] = {0};

unsigned long curMillis;

unsigned long prevReplyToPCmillis = 0;
unsigned long replyToPCinterval = 1000;

//=============

void setup() {
  Serial.begin(9600);

  pinMode(RELAY_CONTROL_PIN, OUTPUT);
  // The light is connected to an NC terminal on the relay, so by default it is on
  // The relay is active HIGH i.e. HIGH -> light ON; LOW -> light OFF
  // we will turn it off in the very beginning

  digitalWrite(RELAY_CONTROL_PIN, LOW);
  lightOn=false;



  // tell the PC we are ready
  Serial.println("<INI>");

}

//=============

void loop() {
  curMillis = millis();
  getDataFromPC();
  updateLight();


}

//=============

void getDataFromPC() {

    // receive data from PC and save it into inputBuffer

  if(Serial.available() > 0) {

    char x = Serial.read();

      // the order of these IF clauses is significant

    if (x == endMarker) {
      readInProgress = false;
      newDataFromPC = true;
      inputBuffer[bytesRecvd] = 0;
      parseData();
    }

    if(readInProgress) {
      inputBuffer[bytesRecvd] = x;
      bytesRecvd ++;
      if (bytesRecvd == buffSize) {
        bytesRecvd = buffSize - 1;
      }
    }

    if (x == startMarker) {
      bytesRecvd = 0;
      readInProgress = true;
    }
  }
}

//=============

void parseData() {

    // split the data into its parts

  //messageFromPC = inputBuffer;
  strcpy(messageFromPC, inputBuffer);
  /*
  char * strtokIndx; // this is used by strtok() as an index

  strtokIndx = strtok(inputBuffer,",");      // get the first part - the string
  strcpy(messageFromPC, strtokIndx); // copy it to messageFromPC

  strtokIndx = strtok(NULL, ","); // this continues where the previous call left off
  newFlashInterval = atoi(strtokIndx);     // convert this part to an integer

  strtokIndx = strtok(NULL, ",");
  servoFraction = atof(strtokIndx);     // convert this part to a float
  */
}

//=============

void replyAck() {

  if (newDataFromPC) {
    newDataFromPC = false;
    Serial.println("<ACK>");
  }
}

void replyLightStatus() {

  if (newDataFromPC) {
    newDataFromPC = false;
    if (lightOn) {
      Serial.println("<LON>");
    }
    else {
      Serial.println("<LOF>");
    }
  }
}

void replyReset() {

  if (newDataFromPC) {
    newDataFromPC = false;
    Serial.println("Resetting neon light to OFF");
    digitalWrite(RELAY_CONTROL_PIN, LOW);
    Serial.println("<INI>");
    lightOn = false;
  }
}
//============

void updateLight() {

   if (newDataFromPC) {
    if (strcmp(messageFromPC, "OPE") == 0) {
      if (!lightOn) {
        digitalWrite(RELAY_CONTROL_PIN, HIGH);
      }
      lightOn=true;
      replyAck();
    }

    if (strcmp(messageFromPC, "CLS") == 0) {
      if (lightOn) {
        digitalWrite(RELAY_CONTROL_PIN, LOW);
      }
      lightOn=false;
      replyAck();
    }

    if (strcmp(messageFromPC, "STA") == 0) {
      replyLightStatus();
    }

    if (strcmp(messageFromPC, "RES") == 0) {
      replyReset();
    }

  }


}
