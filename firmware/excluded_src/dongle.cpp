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
uint8_t bandAddress[] = {0x24, 0x6F, 0x28, 0x1A, 0x2B, 0x3C}; // replace with actual MAC address of laptop dongle
uint16_t successful_sends = 0;
uint16_t failed_sends = 0;


///////////////
// FUNCTION DECLARATIONS
///////////////
int initESPNOW(uint8_t channel);
void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len);
void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status);
void send_imu_serial(imu_data_t imu_data);
void displayMACAddress();


///////////////
// MAIN 
///////////////
void setup() {
  Serial.begin(115200);
  displayMACAddress();
  //initESPNOW();
  //initIMU();
  //initMotors({0,1,2,3}, 4);
}

void loop(){
    //TODO: check for serial input and put it into motor_update struct
    esp_now_send(bandAddress, (uint8_t *) &motor_update, sizeof(motor_update_t));
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

  esp_now_register_recv_cb(onDataRecv);
  esp_now_register_send_cb(onDataSent);

  memcpy(peerInfo.peer_addr, bandAddress, 6);
  peerInfo.channel = channel;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    return -1;
  }
  return 1;
}

//reciving imu
void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  imu_data_t imu_data;
  memcpy(&imu_data, incomingData, sizeof(imu_data_t));
  send_imu_serial(imu_data);
}

void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  if (status == ESP_NOW_SEND_FAIL)
  {
    failed_sends++;
    return;
  }
  successful_sends++;
}

void send_imu_serial(imu_data_t imu_data){};

//assumes serial.begin() has already been called
//assumes wifi.mode is set to WIFI_STA
void displayMACAddress(){
  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());
}


