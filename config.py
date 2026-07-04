# config.py — Central Configuration
# All tunable parameters live here.
# main.py mutates these at runtime when the user clicks Start,
# so the simulation always uses whatever the dashboard collected.

# CHANNEL SETTINGS
NUM_CHANNELS            = 16
CHANNEL_START_FREQ_MHZ  = 2412
CHANNEL_SPACING_MHZ     = 5

# SIGNAL & INTERFERENCE THRESHOLDS
SINR_THRESHOLD_DB       = 10.0
RSSI_MIN_DBM            = -90.0
RSSI_MAX_DBM            = -30.0
NOISE_FLOOR_DBM         = -95.0

# PACKET LOSS
PACKET_LOSS_HIGH        = 0.20
PACKET_LOSS_TARGET      = 0.05

# ACS
ACS_DETECTION_WINDOW_MS = 500
ACS_SWITCH_COOLDOWN_MS  = 1000
ACS_MIN_SINR_TO_ACCEPT  = 15.0
RECOVERY_SUCCESS_THRESHOLD = 0.80

# SIMULATION TIMING
TICK_INTERVAL_MS        = 500
SIMULATION_DURATION_S   = 60
TOTAL_TICKS             = (SIMULATION_DURATION_S * 1000) // TICK_INTERVAL_MS

# DEVICE & INTERFERER COUNTS  ← mutated at runtime by main.py
NUM_IOT_DEVICES         = 10
IOT_TX_POWER_DBM        = -50.0
NUM_WIFI_INTERFERERS    = 3
NUM_BT_INTERFERERS      = 4
WIFI_TX_POWER_DBM       = -20.0
BT_TX_POWER_DBM         = -40.0

# DATA LOGGING
DB_PATH                 = "data/simulation.db"
CSV_EXPORT_PATH         = "data/results.csv"
LOG_EVERY_N_TICKS       = 1

# DASHBOARD
DASHBOARD_PORT          = 8050
DASHBOARD_HOST          = "127.0.0.1"
DASHBOARD_REFRESH_MS    = 1000

# RESOURCE LIMITS
MAX_CPU_PERCENT         = 15
MAX_RAM_MB              = 512