#include <Arduino.h>


void setup() {
  Serial.begin(115200);

  // On ESP32-C3 with USB-CDC, the port may need a moment to enumerate.
  const unsigned long startMs = millis();
  while (!Serial && (millis() - startMs) < 2000) {
    delay(10);
  }

  Serial.println("Booted; starting loop prints...");
  pinMode(2, OUTPUT); // Set GPIO2 as an output pin (built-in LED on many ESP32 boards)
}


void loop() {
  Serial.println("Hello, World!");
  digitalWrite(2, HIGH); // Turn the LED on
  delay(1000); // Wait for 1 sec    ond before printing again
}