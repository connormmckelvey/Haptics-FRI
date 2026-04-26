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
#define IMU_CALIBRATION_INTERVAL 1000000 // in milliseconds
#define SCL_PIN 7
#define SDA_PIN 6
// Set to 1 to locally drive motors from IMU test code in loop().
// Default 0 keeps production behavior: ESP-NOW commands -> remap -> motors.
#define BAND_IMU_TEST_MODE 0

MPU6050 imu;
esp_now_peer_info_t peerInfo;
//uint8_t laptopDongleAddress[] = {0xE8, 0xF6, 0x0A, 0x16, 0xFF, 0x94}; // laptop dongle MAC address
uint8_t numMotors;
uint8_t motorpins[4];
uint16_t successful_sends = 0;
uint16_t failed_sends = 0;
unsigned long last_imu_get_time = 0;
unsigned long last_imu_calibration_time = 0;
int initResult;


///////////////
// FUNCTION DECLARATIONS
///////////////
int initMotors(uint8_t motorpins[]);
int updateMotorStates(motor_update_t motor_update);
float getWristPitchDegrees();
uint8_t getWristMotorOffset();
motor_update_t remapMotors(motor_update_t received);
int initIMU();
void calibrateIMU();
imu_data_t get_imu_data();
int initESPNOW(uint8_t channel);
void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len);
void displayMACAddress();
void displayChannel();


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
  uint8_t mtrPins[] = {2,3,4,5};
  initMotors(mtrPins);
}

void loop() {
#if BAND_IMU_TEST_MODE
  // IMU test mode: keep requesting the top motor, then remap it using the
  // current wrist quadrant so we can verify orientation tracking.
  if (millis() - last_imu_get_time >= IMU_SAMPLE_INTERVAL) {
    last_imu_get_time = millis();

    motor_update_t topMotorCommand{};
    topMotorCommand.motor_states[0] = HIGH;

    motor_update_t remapped = remapMotors(topMotorCommand);
    updateMotorStates(remapped);

    Serial.print("IMU pitch: ");
    Serial.println(getWristPitchDegrees());
    Serial.print("Motor offset: ");
    Serial.println(getWristMotorOffset());
    Serial.print("Remapped motor states: ");
    for (int i = 0; i < 4; i++) {
      Serial.print(remapped.motor_states[i]);
      Serial.print(" ");
    }
    Serial.println();
  }
#endif
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

// Returns the wrist pitch angle in degrees, normalized to 0-360.
float getWristPitchDegrees() {
  imu_data_t data = get_imu_data();
  
  // Convert accelerometer to pitch angle (-180 to 180 degrees).
  // This uses rotation around the IMU Y axis.
  float pitch = atan2(-data.ax, data.az) * 180.0 / M_PI;
  
  // Shift to 0-360
  if (pitch < 0) pitch += 360.0;

  return pitch;
}

// Map the measured pitch bands to a single motor offset.
// These thresholds are tuned to the angles observed on the bench and avoid
// splitting the output across two motors.
uint8_t getWristMotorOffset() {
  float pitch = getWristPitchDegrees();

  if (pitch >= 337.5 || pitch < 20.0) {
    return 0; // top
  }
  if (pitch < 155.0) {
    return 1; // right
  }
  if (pitch < 292.5) {
    return 2; // bottom
  }
  return 3; // left
}

// Remap motor update based on wrist rotation.
// The band only has four motor outputs, so this uses measured pitch bands to
// select a single physical motor per orientation.
motor_update_t remapMotors(motor_update_t received) {
  motor_update_t remapped{};

  uint8_t offset = getWristMotorOffset();

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