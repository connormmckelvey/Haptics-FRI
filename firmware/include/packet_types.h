#include <stdint.h>

typedef struct t_motor_update {
  uint8_t motor_states[4]; // 0=top, 1=right, 2=bottom, 3=left
} motor_update_t;

typedef struct t_imu_data {
    int16_t ax; int16_t ay; int16_t az;
    int16_t gx; int16_t gy; int16_t gz;
} imu_data_t;
