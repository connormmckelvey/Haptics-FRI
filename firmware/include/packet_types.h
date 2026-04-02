#include <stdint.h>

typedef struct t_motor_update {
  uint8_t motor_states[12]; // 0 for off, 1 for on, max 12 motors being controlled
  uint8_t amount_of_motors; // number of motors being controlled
} motor_update_t;

typedef struct t_imu_data {
  float roll;
  float pitch;
  float yaw;
  uint32_t timestamp;
} imu_data_t;
