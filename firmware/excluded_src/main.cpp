#include <Arduino.h>


void setup() {
  Serial.begin(115200);

  // On ESP32-C3 with USB-CDC, the port may need a moment to enumerate.
  const unsigned long startMs = millis();
  while (!Serial && (millis() - startMs) < 2000) {
    delay(10);
  }

  Serial.println("Booted; starting loop prints...");
}


void loop() {
  Serial.println("Hello, World!");
  delay(1000); // Wait for 1 second before printing again
}