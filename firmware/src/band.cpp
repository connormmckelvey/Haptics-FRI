#include <Arduino.h>
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include "packet_types.h"

///////////////
// GLOBALS
///////////////
#define IMU_SAMPLE_INTERVAL 200 // in milliseconds
esp_now_peer_info_t peerInfo;
uint8_t laptopDongleAddress[] = {0x24, 0x6F, 0x28, 0x1A, 0x2B, 0x3C}; // replace with actual MAC address of laptop dongle
uint8_t numMotors;
uint8_t motorpins[12]; //max 12 motors being controlled
uint16_t successful_sends = 0;
uint16_t failed_sends = 0;
unsigned long last_imu_get_time = 0;


///////////////
// FUNCTION DECLARATIONS
///////////////
int initMotors(uint8_t motorpins[], uint8_t numMotors);
int updateMotorStates(motor_update_t motor_update);
int initIMU();
int calibrateIMU();
imu_data_t get_imu_data();
int initESPNOW(uint8_t channel);
void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len);
void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status);
void displayMACAddress();
int check_disconnect();


///////////////
// MAIN 
///////////////
void setup() {
  last_imu_get_time = 0;
  Serial.begin(115200);
  displayMACAddress();
  //initESPNOW();
  //initIMU();
  //initMotors({0,1,2,3}, 4);
}

void loop() {
  if(check_disconnect()) {
    return;
  }
  if(millis() - last_imu_get_time > IMU_SAMPLE_INTERVAL) { // send IMU data every 200ms
    last_imu_get_time = millis();
    imu_data_t imu_data = get_imu_data();
    esp_now_send(laptopDongleAddress, (uint8_t *) &imu_data, sizeof(imu_data_t));  
  }
}

///////////////
// FUNCTION DEFINITIONS
///////////////

// motor control
// initalize numMotors, motorpins, pinMode, and set all motors to off
int initMotors(uint8_t motorpins[], uint8_t numMotors) {
  numMotors = numMotors;
  for (int i = 0; i < numMotors; i++) {
    motorpins[i] = motorpins[i];
    pinMode(motorpins[i], OUTPUT);
    digitalWrite(motorpins[i], LOW); // start with motors off
  }
  return 1;
}

//update motor states based on motor_update struct received through ESPNOW
int updateMotorStates(motor_update_t motor_update) {
  for (int i = 0; i < motor_update.amount_of_motors; i++) {
    digitalWrite(motorpins[i], motor_update.motor_states[i]);
  }
  return 1;
}

// init IMU to calibrate it
int initIMU() {}
int calibrateIMU() {}
imu_data_t get_imu_data() {
  imu_data_t data;
  // populate data with actual IMU readings
  return data;
}

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

  memcpy(peerInfo.peer_addr, laptopDongleAddress, 6);
  peerInfo.channel = channel;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    return -1;
  }
  return 1;
}

void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  motor_update_t motor_update;
  motor_update_t* motor_update_ptr = (motor_update_t*)memcpy(&motor_update, incomingData, sizeof(motor_update_t));
  updateMotorStates(motor_update);
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

// send IMU data through ESPNOW
// receive motor control commands through ESPNOW
// toggle motors correctly

// check if dongle exists, try to reconnect if it doesn't, return 1 disconnected, 0 if connected
int check_disconnect(){
  if(esp_now_is_peer_exist(laptopDongleAddress) == false) {
    if (esp_now_add_peer(&peerInfo) != ESP_OK){
      return 1;
    }
    return 0;
  }
  return 0;
}
