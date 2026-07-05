# simulation/devices.py — IoT Devices & Interference Sources
#
# Neither category represents physical hardware — they are software objects
# whose properties (power, channel, type) feed into environment.py's SINR calculations each tick.
#
# Design note:
#   Devices do NOT calculate SINR themselves. They just describe WHO is
#   transmitting and WHERE (which channel). The Environment is responsible for calculating the resulting signal quality.

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import config

# ENUMERATIONS — named constants for device types

class InterfererType(Enum):
    """
    The two categories of interference modelled in this simulation.

    WIFI:      Broadband interferer — occupies ~22 MHz, so it spills across
               multiple adjacent channels simultaneously. Strong signal (-20 dBm).
               Models a nearby Wi-Fi access point.

    BLUETOOTH: Narrowband interferer — occupies ~1 MHz per hop. Bluetooth uses
               frequency hopping (changes channel rapidly), so its interference
               moves around the band. Moderate signal (-40 dBm).
               Models a Bluetooth headset, speaker, or phone.

    These match the interference types described in Literature Review
    (Vatankhah & Liscano 2024; Mseddi et al. 2024).
    """
    WIFI = "wifi"
    BLUETOOTH = "bluetooth"


class DeviceStatus(Enum):
    """
    Lifecycle states for an IoT device.

    IDLE:         Device exists but is not transmitting (not using any channel).
    TRANSMITTING: Device is actively sending data on its assigned channel.
    SWITCHING:    ACS has triggered a channel switch — device is mid-transition.
                  During this state, the device cannot send data (brief outage).
    DEGRADED:     Device is transmitting but on an interfered channel —
                  packet loss is above the acceptable threshold.
    """
    IDLE        = "idle"
    TRANSMITTING = "transmitting"
    SWITCHING   = "switching"
    DEGRADED    = "degraded"

# REALISTIC IOT DEVICE PROFILES
# These profiles help the simulation treat each device differently.
# This is important for Phase 2 because an IP camera should not behave
# the same way as a temperature sensor or smart bulb.

DEVICE_PROFILES = [
    {
        "name": "IP Camera",
        "traffic_type": "Video stream",
        "traffic_load": "High traffic",
        "priority": "High priority",
        "packets_per_tick": 18,
        "sensitivity": 0.90,
    },
    {
        "name": "Temperature Sensor",
        "traffic_type": "Periodic sensing",
        "traffic_load": "Low traffic",
        "priority": "Low priority",
        "packets_per_tick": 4,
        "sensitivity": 0.35,
    },
    {
        "name": "Smart Bulb",
        "traffic_type": "Control message",
        "traffic_load": "Low traffic",
        "priority": "Medium priority",
        "packets_per_tick": 5,
        "sensitivity": 0.45,
    },
    {
        "name": "Door Sensor",
        "traffic_type": "Event alert",
        "traffic_load": "Burst traffic",
        "priority": "High priority",
        "packets_per_tick": 8,
        "sensitivity": 0.75,
    },
    {
        "name": "Smart Lock",
        "traffic_type": "Security command",
        "traffic_load": "Low traffic",
        "priority": "High priority",
        "packets_per_tick": 6,
        "sensitivity": 0.80,
    },
    {
        "name": "IoT Hub",
        "traffic_type": "Coordinator",
        "traffic_load": "Medium traffic",
        "priority": "Critical node",
        "packets_per_tick": 12,
        "sensitivity": 0.85,
    },
    {
        "name": "Smart Plug",
        "traffic_type": "Control message",
        "traffic_load": "Low traffic",
        "priority": "Medium priority",
        "packets_per_tick": 5,
        "sensitivity": 0.45,
    },
    {
        "name": "Motion Sensor",
        "traffic_type": "Motion burst",
        "traffic_load": "Burst traffic",
        "priority": "High priority",
        "packets_per_tick": 9,
        "sensitivity": 0.80,
    },
]
# IOT DEVICE

@dataclass
class IoTDevice:
    """
    Represents one simulated IoT sensor node.

    In a real deployment this would be a ZigBee, BLE, or IEEE 802.15.4 device.
    Here it is a software object with properties that affect the simulation.

    Key properties used by the simulation:
      - channel_id       : which of the 16 channels this device is on
      - tx_power_dbm     : how strongly it transmits (affects SINR calculation)
      - status           : current lifecycle state
      - packets_sent/lost: running counters used to measure performance
    """

    device_id: int                        # Unique identifier (1 to NUM_IOT_DEVICES)
    channel_id: int                       # Current channel assignment (1–16)
    tx_power_dbm: float                   # Transmit power in dBm (typically -50 dBm for a low-power IoT sensor)
    name: str = "Generic IoT Device"
    traffic_type: str = "Sensor data"
    traffic_load: str = "Low traffic"
    priority: str = "Medium priority"
    packets_per_tick: int = 5
    sensitivity: float = 0.5

    status: DeviceStatus = DeviceStatus.IDLE

    # --- Performance counters (accumulate over the entire simulation run) ---
    packets_sent: int = 0                 # Total packets this device attempted to send
    packets_lost: int = 0                 # Total packets lost due to interference

    # --- Channel switch tracking ---
    switch_count: int = 0                 # How many times ACS has moved this device
    last_switch_tick: int = -999          # Tick number of the most recent switch.
                                          # Initialised to -999 so the cooldown check
                                          # passes immediately on the first tick.

    # --- Per-device SINR history (mirrors ChannelState but device-scoped) ---
    # Stores the last 10 SINR readings on the device's current channel.
    # ACS Algorithm 2 uses this to detect sustained degradation vs. a brief dip.
    sinr_readings: List[float] = field(default_factory=list)

    def record_sinr(self, sinr_db: float):
        """
        Append the latest SINR reading and keep only the last 10.
        Called by monitor.py each tick for transmitting devices.
        """
        self.sinr_readings.append(sinr_db)
        if len(self.sinr_readings) > 10:
            self.sinr_readings.pop(0)

    def average_sinr(self) -> float:
        """
        Return the average SINR over the recent history window.
        Returns 0.0 if no readings have been recorded yet.
        Used by ACS Algorithm 2 for weighted scoring.
        """
        if not self.sinr_readings:
            return 0.0
        return float(np.mean(self.sinr_readings))

    def packet_loss_rate(self) -> float:
        """
        Calculate this device's actual observed packet loss rate.

        This is distinct from the channel's theoretical packet_loss_rate in
        environment.py — this measures what actually happened to THIS device's
        packets, accumulated over the whole run.

        Returns 0.0 if no packets have been sent yet (avoids division by zero).
        """
        if self.packets_sent == 0:
            return 0.0
        return self.packets_lost / self.packets_sent

    def can_switch(self, current_tick: int) -> bool:
        """
        Check whether enough time has passed since the last channel switch.

        ACS_SWITCH_COOLDOWN_MS prevents a device from switching repeatedly
        in quick succession (called 'thrashing'). Without this guard, a device
        on a fluctuating channel could switch every tick, which would make
        packet loss WORSE, not better.

        Converts tick difference to milliseconds using TICK_INTERVAL_MS.
        """
        ticks_since_switch = current_tick - self.last_switch_tick
        ms_since_switch = ticks_since_switch * config.TICK_INTERVAL_MS
        return ms_since_switch >= config.ACS_SWITCH_COOLDOWN_MS

    def perform_switch(self, new_channel_id: int, current_tick: int):
        """
        Execute a channel switch for this device.

        Updates the channel assignment, increments the switch counter,
        records the tick, and sets status to SWITCHING (brief outage).
        The caller (acs.py) is responsible for notifying environment.py.
        """
        self.channel_id = new_channel_id
        self.switch_count += 1
        self.last_switch_tick = current_tick
        self.status = DeviceStatus.SWITCHING
        # Clear SINR history — readings from the old channel are no longer relevant
        self.sinr_readings.clear()

    def update_status(self, channel_sinr_db: float, adjusted_loss_rate: float = 0.0):
        """
        Update this device's status based on channel quality and device sensitivity.

        Phase 2:
        Devices do not all degrade equally. A low-duty-cycle sensor should not
        be affected as quickly as a high-traffic camera or motion sensor.
        """

        if self.status == DeviceStatus.SWITCHING:
            self.status = DeviceStatus.TRANSMITTING
            return


        if self.status in (DeviceStatus.TRANSMITTING, DeviceStatus.DEGRADED):
            if channel_sinr_db < config.SINR_THRESHOLD_DB and adjusted_loss_rate >= 0.08:
                self.status = DeviceStatus.DEGRADED
            else:
                self.status = DeviceStatus.TRANSMITTING

# INTERFERER

@dataclass
class Interferer:
    """
    Represents one interference source in the 2.4 GHz band.

    Interferers are NOT intelligent — they don't respond to the simulation.
    They just occupy channels with a certain power level, and their
    presence is read by interference.py to build the interference_map
    that gets passed to environment.py each tick.

    Wi-Fi interferers affect multiple channels simultaneously (broadband).
    Bluetooth interferers hop between channels each tick (frequency hopping).
    """

    interferer_id: int                    # Unique ID
    interferer_type: InterfererType       # WIFI or BLUETOOTH
    primary_channel: int                  # The main channel this interferer sits on
    tx_power_dbm: float                   # Transmit power (Wi-Fi: -20, BT: -40 dBm)

    # --- Wi-Fi specific: how many adjacent channels it bleeds into ---
    # Wi-Fi channels are 22 MHz wide, spaced 5 MHz apart.
    # So a Wi-Fi AP on channel 6 bleeds into channels 4–8 (±2 channels).
    bandwidth_channels: int = 1           # Number of channels affected (set in factory)

    # --- Bluetooth specific: current hopped channel ---
    # Bluetooth frequency hops ~1600 times/second. In our 100ms tick simulation,
    # we move it to a new random channel each tick to approximate this behaviour.
    current_hop_channel: int = 1          # Updated each tick by interference.py

    # --- Active flag: interferers can be toggled on/off during the simulation ---
    # This allows the simulation to model interference appearing and disappearing,
    # which is realistic (e.g. a neighbour turns on their Wi-Fi router).
    is_active: bool = True

    def get_affected_channels(self) -> List[int]:
        """
        Return the list of channel IDs this interferer is currently affecting.

        Wi-Fi:      Returns primary_channel ± (bandwidth_channels // 2)
                    e.g. primary=6, bandwidth=5 → channels [4, 5, 6, 7, 8]

        Bluetooth:  Returns only [current_hop_channel] (one channel at a time,
                    but it moves every tick).

        All returned channel IDs are clamped to the valid range [1, NUM_CHANNELS].
        """
        if not self.is_active:
            return []   # Inactive interferer affects nothing

        if self.interferer_type == InterfererType.WIFI:
            half = self.bandwidth_channels // 2
            affected = range(
                self.primary_channel - half,
                self.primary_channel + half + 1
            )
            # Clamp to valid channel range
            return [ch for ch in affected if 1 <= ch <= config.NUM_CHANNELS]

        elif self.interferer_type == InterfererType.BLUETOOTH:
            # Bluetooth affects only its current hop channel
            return [self.current_hop_channel]

        return []


# DEVICE MANAGER — creates and manages all devices in one place

class DeviceManager:
    """
    Factory and registry for all IoT devices and interferers.

    Responsibilities:
      - Create all IoT devices and interferers at simulation start
      - Provide access to devices by ID
      - Simulate packet transmission each tick (increment counters)
    """

    def __init__(self):
        self.iot_devices: List[IoTDevice] = []
        self.interferers: List[Interferer] = []

        # Seeded RNG — same seed as environment.py for consistency
        self.rng = np.random.default_rng(seed=42)

    def initialise(self):
        """
        Create all IoT devices and interferers using settings from config.py.
        Called once at the start of the simulation by main.py.
        """
        self._create_iot_devices()
        self._create_interferers()

    # DEVICE CREATION

    def _create_iot_devices(self):
        """
        Spawn IoT devices using realistic profiles.

        Phase 2 change:
        Instead of treating every device as the same generic sensor,
        each device now has its own traffic pattern, priority, and
        interference sensitivity.
        """
        self.iot_devices.clear()

        for i in range(1, config.NUM_IOT_DEVICES + 1):
            profile = DEVICE_PROFILES[(i - 1) % len(DEVICE_PROFILES)]

            device = IoTDevice(
                device_id=i,
                channel_id=1,  # Placeholder — assigned later by environment.py
                tx_power_dbm=config.IOT_TX_POWER_DBM,
                status=DeviceStatus.TRANSMITTING,

                # Phase 2 profile fields
                name=profile["name"],
                traffic_type=profile["traffic_type"],
                traffic_load=profile["traffic_load"],
                priority=profile["priority"],
                packets_per_tick=profile["packets_per_tick"],
                sensitivity=profile["sensitivity"],
            )

            self.iot_devices.append(device)

    def _create_interferers(self):
        """
        Spawn Wi-Fi and Bluetooth interferers.

        Wi-Fi APs are placed on channels 1, 6, and 11 by default —
        these are the standard non-overlapping Wi-Fi channels, which is
        exactly where real-world Wi-Fi deployments concentrate.

        Bluetooth devices are placed randomly across the band, since
        they hop around anyway.
        """
        # --- Wi-Fi interferers ---
        # Standard Wi-Fi channels 1, 6, 11 — placed deliberately to maximise band coverage, as any real Wi-Fi network planner would do.
        wifi_channels = [1, 6, 11]

        for i in range(config.NUM_WIFI_INTERFERERS):
            primary_ch = wifi_channels[i % len(wifi_channels)]
            interferer = Interferer(
                interferer_id=i + 1,
                interferer_type=InterfererType.WIFI,
                primary_channel=primary_ch,
                tx_power_dbm=config.WIFI_TX_POWER_DBM,
                bandwidth_channels=5,   # Wi-Fi bleeds across ±2 adjacent channels
                is_active=True
            )
            self.interferers.append(interferer)

        # Bluetooth interferers 
        # Start on random channels — they will hop every tick anyway
        for j in range(config.NUM_BT_INTERFERERS):
            start_channel = int(self.rng.integers(1, config.NUM_CHANNELS + 1))
            interferer = Interferer(
                interferer_id=config.NUM_WIFI_INTERFERERS + j + 1,
                interferer_type=InterfererType.BLUETOOTH,
                primary_channel=start_channel,
                tx_power_dbm=config.BT_TX_POWER_DBM,
                bandwidth_channels=1,   # BT is narrowband — one channel at a time
                current_hop_channel=start_channel,
                is_active=True
            )
            self.interferers.append(interferer)

    # TICK UPDATE — packet simulation

    def update(self, environment):
        """
        Simulate packet transmission for all IoT devices for one tick.

        Each transmitting device "sends" a fixed number of packets this tick.
        Whether each packet is lost is determined by the channel's packet_loss_rate
        (from environment.py) — modelled as a Bernoulli trial per packet.

        A Bernoulli trial means: flip a biased coin for each packet.
        If the coin lands on "loss" (probability = packet_loss_rate), the packet
        is counted as lost. This is standard in discrete-event network simulation.

        Parameters
        ----------
        environment : ChannelEnvironment
            Passed in so we can read the current packet_loss_rate per channel.
        """

        for device in self.iot_devices:
            if device.status == DeviceStatus.SWITCHING:
                # Device is mid-switch — no packets sent this tick
                continue

            if device.status in (DeviceStatus.TRANSMITTING, DeviceStatus.DEGRADED):
                channel_state = environment.get_channel(device.channel_id)
                loss_rate = channel_state.packet_loss_rate

                # Bernoulli trial: for each of the 10 packets, roll a random number.
                # If it's less than loss_rate, the packet is lost.
                                # Use each device's own traffic profile.
                # Example: IP Camera sends more packets than Temperature Sensor.
                packets_this_tick = device.packets_per_tick

                # More sensitive devices are slightly more affected by the same channel loss.
                # This helps explain why high-priority/burst/video devices degrade first.
                adjusted_loss_rate = min(1.0, loss_rate * device.sensitivity)

                losses = int(
                    self.rng.binomial(
                        n=packets_this_tick,
                        p=adjusted_loss_rate
                    )
                )

                device.packets_sent += packets_this_tick
                device.packets_lost += losses

                # Update device SINR history and status
                device.record_sinr(channel_state.sinr_db)
                device.update_status(channel_state.sinr_db, adjusted_loss_rate)

    # GETTERS
    def get_device(self, device_id: int) -> Optional[IoTDevice]:
        """Return a single IoT device by its ID, or None if not found."""
        for device in self.iot_devices:
            if device.device_id == device_id:
                return device
        return None

    def get_all_devices(self) -> List[IoTDevice]:
        """Return all IoT devices."""
        return self.iot_devices

    def get_all_interferers(self) -> List[Interferer]:
        """Return all interferers (both Wi-Fi and Bluetooth)."""
        return self.interferers

    def get_active_interferers(self) -> List[Interferer]:
        """Return only the interferers that are currently active."""
        return [i for i in self.interferers if i.is_active]

    def get_degraded_devices(self) -> List[IoTDevice]:
        """Return devices currently in DEGRADED status (on a bad channel)."""
        return [d for d in self.iot_devices if d.status == DeviceStatus.DEGRADED]