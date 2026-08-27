"""Constants for the Amperfied Connect Modbus integration."""

from homeassistant.const import Platform

# ##### General #####
DOMAIN = "amperfied_connect_modbus"
DEVICE_MANUFACTURER = "Amperfied"
DEVICE_MODEL = "Connect"

# ##### Configuration #####
# Configuration keys
CONF_DEVICE_ID = "device_id"
CONF_AUTO_THREE_PHASE_AFTER_ECO = "auto_three_phase_after_eco"
CONF_PHASE_SWITCH_VERIFY = "phase_switch_verify"
CONF_REARM_ON_DISCONNECT = "rearm_on_disconnect"
# Update interval for coordinator
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_AUTO_THREE_PHASE_AFTER_ECO = True
DEFAULT_PHASE_SWITCH_DURATION = 90
DEFAULT_PHASE_SWITCH_VERIFY = True
DEFAULT_REARM_ON_DISCONNECT = True
PHASE_SWITCH_VERIFY_MARGIN = 5
PHASE_SWITCH_GRACE_PERIOD = 10

# Platforms
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# ##### Data Keys #####
# Init Data
DATA_REG_LAYOUT_VER = "reg_layout_ver"
DATA_HW_VARIANT = "hw_variant"
DATA_SW_VERSION = "sw_version"
DATA_HW_MIN_CURR = "hw_min_current"
DATA_HW_MAX_CURR = "hw_max_current"
# Sensors
DATA_CHARGING_STATE = "charging_state"
DATA_CHARGING_POWER = "charging_power"
DATA_PHASES_ACTIVE = "phases_active"
DATA_CURRENT = "current"
DATA_CURRENT_L1 = "current_l1"
DATA_CURRENT_L2 = "current_l2"
DATA_CURRENT_L3 = "current_l3"
DATA_PCB_TEMPERATURE = "pcb_temperature"
DATA_VOLTAGE_L1 = "voltage_l1"
DATA_VOLTAGE_L2 = "voltage_l2"
DATA_VOLTAGE_L3 = "voltage_l3"
DATA_EXTERNAL_LOCK_STATE = "external_lock_state"
DATA_ENERGY_SINCE_POWER_ON = "energy_since_power_on"
DATA_TOTAL_ENERGY = "total_energy"
DATA_SESSION_ENERGY = "session_energy"
DATA_PHASE_SWITCH_STATE = "phase_switch_state"
DATA_PHASE_SWITCH_DURATION = "phase_switch_duration"
# MID power meter (v2.0.0+, hardware-optional, probed via reg 3000)
DATA_MID_CURRENT_L1 = "mid_current_l1"
DATA_MID_CURRENT_L2 = "mid_current_l2"
DATA_MID_CURRENT_L3 = "mid_current_l3"
DATA_MID_VOLTAGE_L1 = "mid_voltage_l1"
DATA_MID_VOLTAGE_L2 = "mid_voltage_l2"
DATA_MID_VOLTAGE_L3 = "mid_voltage_l3"
DATA_MID_POWER_FORWARD = "mid_power_forward"
DATA_MID_ENERGY_FORWARD = "mid_energy_forward"
DATA_MID_ENERGY_REVERSE = "mid_energy_reverse"
# Binary Sensors
DATA_IS_PLUGGED = "is_plugged"
DATA_IS_CHARGING = "is_charging"
# Hardware Command
COMMAND_ECO_MODE = "eco_mode_command"
COMMAND_FAILSAFE_CURRENT = "failsafe_current_command"
COMMAND_REMOTE_LOCK = "remote_lock_command"
COMMAND_STANDBY = "standby_function_control"
COMMAND_TARGET_CURRENT = "max_current_command"
COMMAND_WATCHDOG_TIMEOUT = "watchdog_timeout_command"
COMMAND_PHASE_SWITCH = "phase_switch_control"
# Buttons
BUTTON_STOP_CHARGING = "stop_charging"
# Virtual
VIRTUAL_ENABLE = "virtual_enable"
VIRTUAL_TARGET_CURRENT = "virtual_current"

# ##### Map for charging state #####
# Values from the heidelberg modbus docs
CHARGING_STATE_MAP = {
    2: "A",
    3: "A",
    4: "B",
    5: "B",
    6: "C",
    7: "C",
    8: "D",
    9: "E",
    10: "F",
    11: "E",
}
