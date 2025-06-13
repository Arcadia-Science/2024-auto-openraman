//=========================================================
// Neon Light Source Controller
// Controls a calibration neon light source via a relay
// Communication with PC via Serial for command handling
//=========================================================

bool lightOn = false; // Tracks the ON/OFF state of the neon light

//========================= Constants =========================
const int RELAY_CONTROL_PIN = 13;  // Pin on Teensy that controls the relay
const byte BUFFER_SIZE = 40;       // Max size of incoming serial buffer

const char START_MARKER = '<';     // Indicates start of command
const char END_MARKER = '>';       // Indicates end of command

//====================== Serial Buffers =======================
char inputBuffer[BUFFER_SIZE];     // Temporary buffer for incoming characters
char messageFromPC[BUFFER_SIZE] = {0};  // Parsed message from PC

//=================== Serial Parsing State ====================
byte bytesReceived = 0;
bool readInProgress = false;
bool newDataFromPC = false;

//===================== Timing Variables ======================
unsigned long curMillis;
unsigned long prevReplyToPCMillis = 0;
unsigned long replyToPCInterval = 1000; // Not currently used

//=========================================================
void setup() {
  Serial.begin(9600);

  pinMode(RELAY_CONTROL_PIN, OUTPUT);

  // The light is connected to a Normally Closed (NC) terminal on the relay
  // The relay is active HIGH: HIGH = light ON, LOW = light OFF
  // Start with the light OFF
  digitalWrite(RELAY_CONTROL_PIN, LOW);
  lightOn = false;

  // Notify PC that device is initialized
  Serial.println("<INI>");
}

//=========================================================
void loop() {
  curMillis = millis();
  getDataFromPC();  // Read command from PC if available
  updateLight();    // Take action based on received command
}

//=========================================================
// Reads incoming data between START_MARKER and END_MARKER
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
      inputBuffer[bytesReceived] = '\0'; // Null-terminate the string
      parseData();
    }
    else if (readInProgress) {
      if (bytesReceived < BUFFER_SIZE - 1) {
        inputBuffer[bytesReceived++] = x;
      }
    }
  }
}

//=========================================================
// Copies validated input into the message buffer
void parseData() {
  strcpy(messageFromPC, inputBuffer);
}

//=========================================================
// Sends a generic ACK reply to PC
void replyAck() {
  if (newDataFromPC) {
    newDataFromPC = false;
    Serial.println("<ACK>");
  }
}

// Sends current light status to PC
void replyLightStatus() {
  if (newDataFromPC) {
    newDataFromPC = false;
    Serial.println(lightOn ? "<LON>" : "<LOF>");
  }
}

// Resets light to OFF and notifies PC
void replyReset() {
  if (newDataFromPC) {
    newDataFromPC = false;
    Serial.println("Resetting neon light to OFF");
    digitalWrite(RELAY_CONTROL_PIN, LOW);
    lightOn = false;
    Serial.println("<INI>");
  }
}

//=========================================================
// Interprets and responds to commands received from PC
void updateLight() {
  if (newDataFromPC) {
    if (strcmp(messageFromPC, "OPE") == 0) {  // Turn light ON
      if (!lightOn) {
        digitalWrite(RELAY_CONTROL_PIN, HIGH);
        lightOn = true;
      }
      replyAck();
    }
    else if (strcmp(messageFromPC, "CLS") == 0) {  // Turn light OFF
      if (lightOn) {
        digitalWrite(RELAY_CONTROL_PIN, LOW);
        lightOn = false;
      }
      replyAck();
    }
    else if (strcmp(messageFromPC, "STA") == 0) {  // Report Status
      replyLightStatus();
    }
    else if (strcmp(messageFromPC, "RES") == 0) {  // Reset
      replyReset();
    }
  }
}
