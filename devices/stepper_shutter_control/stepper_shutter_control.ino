// Controls the stepper motor-based shutter

#include <Stepper.h>

const int stepsToMove = 200;

// initialize the stepper library on pins 8 through 11:
Stepper myStepper(stepsToMove, 8, 10, 9, 11);

bool shutterOpen;


const byte buffSize = 40;
char inputBuffer[buffSize];
const char startMarker = '<';
const char endMarker = '>';
byte bytesRecvd = 0;
boolean readInProgress = false;
boolean newDataFromPC = false;

char messageFromPC[buffSize] = {0};
int newFlashInterval = 0;
float servoFraction = 0.0; // fraction of servo range to move


unsigned long curMillis;

unsigned long prevReplyToPCmillis = 0;
unsigned long replyToPCinterval = 1000;

//=============

void setup() {
  Serial.begin(9600);

  // set the speed at X rpm:
  myStepper.setSpeed(80);

  shutterOpen=false;
  // tell the PC we are ready
  Serial.println("<INI>");
}

//=============

void loop() {
  curMillis = millis();
  getDataFromPC();
  updateShutter();


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

void replyShutterStatus() {

  if (newDataFromPC) {
    newDataFromPC = false;
    if (shutterOpen) {
      Serial.println("<STO>");
    }
    else {
      Serial.println("<STC>");
    }
  }
}

void replyReset() {

  if (newDataFromPC) {
    newDataFromPC = false;
    Serial.println("<INI>");
    shutterOpen = false;
  }
}
//============

void updateShutter() {

   if (newDataFromPC) {
    if (strcmp(messageFromPC, "OPE") == 0) {
      if (!shutterOpen) {
        myStepper.step(stepsToMove);
        delay(3000);
      }
      shutterOpen=true;
      replyAck();
    }

    if (strcmp(messageFromPC, "CLS") == 0) {
      if (shutterOpen) {
      myStepper.step(-stepsToMove);
      delay(3000);
      }
      shutterOpen=false;
      replyAck();
    }

    if (strcmp(messageFromPC, "STA") == 0) {
      replyShutterStatus();
    }

    if (strcmp(messageFromPC, "RES") == 0) {
      replyReset();
    }

  }


}
