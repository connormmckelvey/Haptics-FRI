// DONGLE FIRMWARE
// recieves motor updates via serial and relays them to the band via ESPNOW
#include <Arduino.h>
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include "packet_types.h"

///////////////
// GLOBALS
///////////////
esp_now_peer_info_t peerInfo;
uint8_t bandAddress[] = {0x34, 0xCD, 0xB0, 0x53, 0x36, 0x28}; // band MAC address
uint8_t xiaobandAddress[] = {0xE8, 0xF6, 0x0A, 0x17, 0x00, 0xC0}; // seeed band MAC address

uint16_t successful_sends = 0;
uint16_t failed_sends = 0;

// Testing: set to 1 to ignore Serial and send dummy motor updates over ESP-NOW.
#ifndef DONGLE_DUMMY_MODE
#define DONGLE_DUMMY_MODE 1
#endif

#ifndef DONGLE_DUMMY_PERIOD_MS
#define DONGLE_DUMMY_PERIOD_MS 200
#endif

#ifndef DONGLE_DUMMY_MOTOR_COUNT
#define DONGLE_DUMMY_MOTOR_COUNT 4
#endif


///////////////
// FUNCTION DECLARATIONS
///////////////
int initESPNOW(uint8_t channel);
void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status);
void displayMACAddress();


///////////////
// MAIN 
///////////////
void setup() {
  Serial.begin(115200);
  displayMACAddress();

  // Initialize ESP-NOW + peer.
  initESPNOW(1);
}

void loop(){
#if DONGLE_DUMMY_MODE
  static unsigned long lastSendMs = 0;
  static uint8_t step = 0;

  const unsigned long nowMs = millis();
  if (nowMs - lastSendMs < DONGLE_DUMMY_PERIOD_MS) {
    return;
  }
  lastSendMs = nowMs;

  motor_update_t motorUpdate{};
  motorUpdate.amount_of_motors = (DONGLE_DUMMY_MOTOR_COUNT > 12) ? 12 : DONGLE_DUMMY_MOTOR_COUNT;
  if (motorUpdate.amount_of_motors == 0) {
    motorUpdate.amount_of_motors = 1;
  }
  motorUpdate.motor_states[step % motorUpdate.amount_of_motors] = 1;
  step++;

  esp_now_send(bandAddress, reinterpret_cast<const uint8_t*>(&motorUpdate), sizeof(motor_update_t));
  return;
#else
  // Non-blocking serial -> motor_update_t framing.
  // Expects raw bytes for a motor_update_t (sizeof == 13).
  static uint8_t rxBuf[sizeof(motor_update_t)];
  static size_t rxLen = 0;

  while (Serial.available() > 0) {
    const int byteRead = Serial.read();
    if (byteRead < 0) {
      break;
    }

    rxBuf[rxLen++] = static_cast<uint8_t>(byteRead);

    if (rxLen >= sizeof(motor_update_t)) {
      motor_update_t motorUpdate;
      memcpy(&motorUpdate, rxBuf, sizeof(motor_update_t));

      esp_now_send(bandAddress, reinterpret_cast<const uint8_t*>(&motorUpdate), sizeof(motor_update_t));
      rxLen = 0;
    }
  }
#endif
}

///////////////
// FUNCTION DEFINITIONS
///////////////

// init ESPNOW protocol
//returns 1 if successful, 0 if failed to init ESPNOW, -1 if failed to add peer
int initESPNOW(uint8_t channel = 1) {
  WiFi.mode(WIFI_STA);

  // Set the ESP32 Wi-Fi channel
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(true);

  if (esp_now_init() != ESP_OK){return 0;}

  esp_now_register_send_cb(onDataSent);

  memcpy(peerInfo.peer_addr, bandAddress, 6);
  peerInfo.channel = channel;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    return -1;
  }
  return 1;
}

void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  if (status == ESP_NOW_SEND_FAIL)
  {
    failed_sends++;
    return;
  }
  successful_sends++;
}

//assumes serial.begin() has already been called
//assumes wifi.mode is set to WIFI_STA
void displayMACAddress(){
  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());
}


