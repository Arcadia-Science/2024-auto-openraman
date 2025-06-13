//=========================================================
// Stepper Motor Shutter Controller
// Controls a stepper-motor-based shutter via serial commands
//=========================================================

#include <Stepper.h>

//========================== Constants ==========================
const int STEPS_TO_MOVE = 200;         // Number of steps to fully open/close the shutter
const int STEPPER_SPEED_RPM = 80;      // Speed of the stepper motor in RPM

const byte BUFFER_SIZE = 40;           // Max size of input buffer
const char START_MARKER = '<';         // Start of command
const char END_MARKER = '>';           // End of command

//======================= State Variables =======================
Stepper myStepper(STEPS_TO_MOVE, 8, 10, 9, 11);  // Motor wired to pins 8, 10, 9, 11
bool shutterOpen = false;                        // Tracks shutter state

char inputBuffer[BUFFER_SIZE];           // Raw input buffer
char messageFromPC[BUFFER_SIZE] = {0};   // Parsed command message

byte bytesReceived = 0;
bool readInProgress = false;
bool newDataFromPC = false;

//===================== Timing (unused, placeholder) =====================
unsigned long curMillis;
unsigned long prevReplyToPCMillis = 0;
unsigned long replyToPCInterval = 1000;

//=========================================================
void setup() {
  Serial.begin(9600);
  myStepper.setSpeed(STEPPER_SPEED_RPM);

  shutterOpen = false;

  // Notify PC that setup is complete
  Serial.println("<INI>");
}

//=========================================================
void loop() {
  curMillis = millis();
  getDataFromPC();    // Check for incoming serial commands
  updateShutter();    // Act on commands if any
}

//=========================================================
// Reads data from the serial buffer enclosed in < and >
void getDataFromPC() {
  while (Serial.available() > 0) {
    char x = Serial.read();

    if (x == START_MARKER) {
      bytesReceived = 0;
      readInProgress = true;
    }
    else if (x == END_MARKER) {
      readInProgress = false;
      newDataFromPC = true;
      inputBuffer[bytesReceived] = '\0'; // Null-terminate string
      parseData();
    }
    else if (readInProgress && bytesReceived < BUFFER_SIZE - 1) {
      inputBuffer[bytesReceived++] = x;
    }
  }
}

//=========================================================
// Parses the inputBuffer into a command message
void parseData() {
  strcpy(messageFromPC, inputBuffer);
}

//=========================================================
// Sends an acknowledgement to the PC
void replyAck() {
  if (newDataFromPC) {
    newDataFromPC = false;
    Serial.println("<ACK>");
  }
}

// Sends current shutter status to PC
void replyShutterStatus() {
  if (newDataFromPC) {
    newDataFromPC = false;
    Serial.println(shutterOpen ? "<STO>" : "<STC>");
  }
}

// Resets the shutter state without moving the motor
void replyReset() {
  if (newDataFromPC) {
    newDataFromPC = false;
    Serial.println("<INI>");
    shutterOpen = false;
  }
}

//=========================================================
// Interprets commands and acts accordingly
void updateShutter() {
  if (newDataFromPC) {
    if (strcmp(messageFromPC, "OPE") == 0) {  // Open shutter
      if (!shutterOpen) {
        myStepper.step(STEPS_TO_MOVE);
        delay(3000); // Allow mechanical settling
      }
      shutterOpen = true;
      replyAck();
    }
    else if (strcmp(messageFromPC, "CLS") == 0) {  // Close shutter
      if (shutterOpen) {
        myStepper.step(-STEPS_TO_MOVE);
        delay(3000); // Allow mechanical settling
      }
      shutterOpen = false;
      replyAck();
    }
    else if (strcmp(messageFromPC, "STA") == 0) {  // Status
      replyShutterStatus();
    }
    else if (strcmp(messageFromPC, "RES") == 0) {  // Reset
      replyReset();
    }
  }
}
