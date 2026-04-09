#include <Arduino.h>
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include "packet_types.h"
#include "MPU6050.h"

///////////////
// GLOBALS
///////////////
#define IMU_SAMPLE_INTERVAL 200 // in milliseconds
#define SCL_PIN 5
#define SDA_PIN 4

MPU6050 imu;
esp_now_peer_info_t peerInfo;
//uint8_t laptopDongleAddress[] = {0xE8, 0xF6, 0x0A, 0x16, 0xFF, 0x94}; // laptop dongle MAC address
uint8_t numMotors;
uint8_t motorpins[4];
uint16_t successful_sends = 0;
uint16_t failed_sends = 0;
unsigned long last_imu_get_time = 0;
int initResult;


///////////////
// FUNCTION DECLARATIONS
///////////////
int initMotors(uint8_t motorpins[]);
int updateMotorStates(motor_update_t motor_update);
uint8_t getWristQuadrant();
motor_update_t remapMotors(motor_update_t received);
int initIMU();
void calibrateIMU();
imu_data_t get_imu_data();
int initESPNOW(uint8_t channel);
void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len);
void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status);
void displayMACAddress();
void displayChannel();
int check_disconnect();


///////////////
// MAIN 
///////////////
void setup() {
  last_imu_get_time = 0;
  Serial.begin(115200);
  displayMACAddress();
  initResult = initESPNOW(6);
  if (initIMU()) {
    calibrateIMU();
  }  
  uint8_t mtrPins[] = {2,3,4,5}; // example motor pins
  initMotors(mtrPins);
}

void loop() {
  //displayMACAddress();
  //Serial.print("init result: ");
  //Serial.println(initResult);
  // motor_update_t mtest;
  // mtest.motor_states[0] = HIGH;
  // mtest.motor_states[1] = LOW;
  // mtest.motor_states[2] = LOW;
  // mtest.motor_states[3] = LOW;
  // updateMotorStates(mtest);
  // Serial.println("Motor states updated");
  //delay(1000);
}

///////////////
// FUNCTION DEFINITIONS
///////////////

// motor control
// initalize numMotors, motorpins, pinMode, and set all motors to off
int initMotors(uint8_t mtrpins[]) {
  for (int i = 0; i < 4; i++) {
    motorpins[i] = mtrpins[i];
    pinMode(motorpins[i], OUTPUT);
    digitalWrite(motorpins[i], LOW); // start with motors off
  }
  return 1;
}

//update motor states based on motor_update struct received through ESPNOW
int updateMotorStates(motor_update_t motor_update) {
  for (int i = 0; i < 4; i++) {
    digitalWrite(motorpins[i], motor_update.motor_states[i]);
  }
  return 1;
}

// Returns 0-3 representing which 90-degree quadrant the wrist is in
uint8_t getWristQuadrant() {
  imu_data_t data = get_imu_data();
  
  // Convert accelerometer to roll angle (-180 to 180 degrees)
  float roll = atan2(data.ay, data.az) * 180.0 / M_PI;
  
  // Shift to 0-360
  if (roll < 0) roll += 360.0;
  
  // Quantize into 4 quadrants
  return (uint8_t)(roll / 90.0) % 4;
}

// Remap motor update based on wrist rotation
motor_update_t remapMotors(motor_update_t received) {
  motor_update_t remapped{};
  uint8_t offset = getWristQuadrant();
  
  for (int i = 0; i < 4; i++) {
    remapped.motor_states[(i + offset) % 4] = received.motor_states[i];
  }
  return remapped;
}


int initIMU() {
  Wire.begin(SDA_PIN, SCL_PIN);
  imu.initialize();
  
  if (!imu.testConnection()) {
    Serial.println("MPU6050 connection failed");
    return 0;
  }
  Serial.println("MPU6050 connection successful");
  return 1;
}

void calibrateIMU() {    
  Serial.println("Calibrating IMU, hold still...");
  imu.setXAccelOffset(0); imu.setYAccelOffset(0); imu.setZAccelOffset(0);
  imu.setXGyroOffset(0);  imu.setYGyroOffset(0);  imu.setZGyroOffset(0);
  imu.CalibrateAccel(6);
  imu.CalibrateGyro(6);
  Serial.println("Calibration complete");
}

imu_data_t get_imu_data() {
  imu_data_t data;
  imu.getMotion6(&data.ax, &data.ay, &data.az, &data.gx, &data.gy, &data.gz);
  return data;
}


int initESPNOW(uint8_t channel = 1) {
  WiFi.mode(WIFI_STA);

  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false); // was being called twice, also should be false after setting channel

  if (esp_now_init() != ESP_OK) { return 0; }

  esp_now_register_recv_cb(onDataRecv);

  return 1;
}

void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  motor_update_t received;
  memcpy(&received, incomingData, sizeof(motor_update_t));
  motor_update_t remapped = remapMotors(received);
  updateMotorStates(remapped);

  Serial.println("Updated Motor States:");
  for (int i = 0; i < 4; i++) {
    Serial.print(remapped.motor_states[i]);
    Serial.print(" ");
  }
  Serial.println();
}

//assumes serial.begin() has already been called
//assumes wifi.mode is set to WIFI_STA
void displayMACAddress(){
  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());
}

void displayChannel(){
  uint8_t primaryChan;
  wifi_second_chan_t secondChan;
  esp_wifi_get_channel(&primaryChan, &secondChan);
  Serial.print("Actual channel: ");
  Serial.println(primaryChan);
}

// send IMU data through ESPNOW
// receive motor control commands through ESPNOW
// toggle motors correctly

// check if dongle exists, try to reconnect if it doesn't, return 1 disconnected, 0 if connected
int check_disconnect(){return 0;}
