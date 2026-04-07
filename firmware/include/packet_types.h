#include <stdint.h>

typedef struct t_motor_update {
  uint8_t motor_states[4]; // 0 for off, 1 for on, max 12 motors being controlled
  uint8_t top = motor_states[0];
  uint8_t left = motor_states[1];
  uint8_t bottom = motor_states[2];
  uint8_t right = motor_states[3];
} motor_update_t;

typedef struct t_imu_data {
    int16_t ax; int16_t ay; int16_t az;
    int16_t gx; int16_t gy; int16_t gz;
} imu_data_t;
