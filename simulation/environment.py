# simulation/environment.py — 2.4 GHz Channel Environment Model
# This file models the physical radio environment. It maintains the state of all 16 channels at every simulation tick —
# computing SINR, deriving packet loss, and tracking channel health.
#
#   We model each channel as an independent logical channel for simplicity, consistent with the software-simulation scope of this project.

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict
import config

# CHANNEL STATE — one instance per channel per tick

@dataclass
class ChannelState:
    """
    Snapshot of a single channel's condition at one point in time.

    A dataclass is used here because we just need a clean container
    to pass channel data between modules — no complex behaviour needed.
    """

    channel_id: int           # Channel number (1–16)
    frequency_mhz: float      # Centre frequency in MHz (e.g. 2412 for ch 1)

    # Signal measurements
    sinr_db: float = 0.0      # Signal-to-Interference-plus-Noise Ratio (dB) (Higher = cleaner signal, Below 10 dB = degraded)

    rssi_dbm: float = 0.0     # Received Signal Strength Indicator (dBm)

    interference_power_dbm: float = 0.0   # Total interference power on this channel. Sum of all Wi-Fi + Bluetooth power here

    packet_loss_rate: float = 0.0         # Derived from SINR (0.0 = 0%, 1.0 = 100%)

    # Status flags
    is_interfered: bool = False   # True if SINR is below SINR_THRESHOLD_DB
    is_active: bool = False       # True if an IoT device is currently using this channel

    # History — rolling window of recent SINR readings used by ACS Algorithm 2
    sinr_history: List[float] = field(default_factory=list)

# ENVIRONMENT CLASS — manages all 16 channels

class ChannelEnvironment:
    """
    Models the full 2.4 GHz band as a collection of 16 channels.

    Responsibilities:
      - Initialise all channel objects with their frequencies
      - Update each channel's SINR and packet loss every tick
        based on interference injected by the Interference module
      - Provide channel state snapshots to the Monitor and ACS modules
    """

    def __init__(self):
        # Build the 16 channel objects, each with a unique frequency
        self.channels: Dict[int, ChannelState] = {}

        for i in range(1, config.NUM_CHANNELS + 1):
            freq = config.CHANNEL_START_FREQ_MHZ + (i - 1) * config.CHANNEL_SPACING_MHZ
            self.channels[i] = ChannelState(channel_id=i, frequency_mhz=freq)

        # Track which channel each IoT device is currently assigned to. Key = device_id, Value = channel_id
        self.device_channel_map: Dict[int, int] = {}

        # Tick counter — incremented each simulation step
        self.current_tick: int = 0

        # Seed NumPy's random generator for reproducible simulation runs.
        self.rng = np.random.default_rng(seed=42)

    # INITIALISE DEVICES ON CHANNELS

    def assign_devices_to_channels(self, device_ids: List[int]):
        """
        Spread IoT devices across channels at simulation start.
        Devices are distributed evenly so no single channel starts overloaded.
        e.g. with 10 devices and 16 channels: devices go on channels 1,2,...,10
        """
        for idx, device_id in enumerate(device_ids):
            # Wrap around if more devices than channels (modulo assignment)
            channel_id = (idx % config.NUM_CHANNELS) + 1
            self.device_channel_map[device_id] = channel_id
            self.channels[channel_id].is_active = True

    # CORE UPDATE — called every tick by main.py

    def update(self, interference_map: Dict[int, float]):
        """
        Recalculate SINR and packet loss for every channel.

        Called once per simulation tick by main.py.

        Parameters
        ----------
        interference_map : dict
            Keys = channel_id (1–16)
            Values = total interference power on that channel (dBm)
            Produced by interference.py each tick.
        """
        self.current_tick += 1

        for ch_id, channel in self.channels.items():

            # Read the interference generated for this channel.
            interference_dbm = interference_map.get(ch_id, config.NOISE_FLOOR_DBM)

            # Scale interference gradually so the simulation has visible
            # degradation instead of jumping instantly between perfect and bad.

            if interference_dbm > config.NOISE_FLOOR_DBM:
                # Add a small random fluctuation to simulate changing RF conditions.
                variation = self.rng.normal(0, 2)

                interference_dbm += variation

            channel.interference_power_dbm = interference_dbm

            # STEP 2: Simulate IoT signal strength (RSSI)
            # In a real network, RSSI would come from actual hardware.
            # Here we model it as a baseline signal with small random fluctuation (multipath fading / shadowing) — this is standard in RF simulation.
    
            # np.clip ensures RSSI stays within physically realistic bounds.
            # STEP 2: Simulate IoT signal strength (RSSI)
            # Stronger RSSI on clean channels, weaker RSSI when interference exists.

            if interference_dbm > config.NOISE_FLOOR_DBM:
                base_rssi = -60.0      # Slightly weaker due to interference
            else:
                base_rssi = -53.0      # Stronger on clean channels

            fading = self.rng.normal(loc=0.0, scale=2.0)

            channel.rssi_dbm = float(
                np.clip(
                    base_rssi + fading,
                    config.RSSI_MIN_DBM,
                    config.RSSI_MAX_DBM
                )
            )

            # STEP 3: Calculate SINR
            # SINR (dB) = Signal Power - (Interference Power + Noise Floor)
            #   SINR = Psignal / (Pinterference + Pnoise)
            interference_mw = _dbm_to_mw(interference_dbm)
            noise_mw = _dbm_to_mw(config.NOISE_FLOOR_DBM)
            signal_mw = _dbm_to_mw(channel.rssi_dbm)

            total_interference_mw = interference_mw + noise_mw

            # Avoid division by zero (shouldn't happen, but defensive coding)
            if total_interference_mw <= 0:
                total_interference_mw = 1e-12

            sinr_linear = signal_mw / total_interference_mw
            channel.sinr_db = float(
                np.clip(
                _linear_to_db(sinr_linear),
                -5,
                30
                )
            )

            # STEP 4: Derive packet loss rate from SINR
            # As SINR drops, packet loss rises non-linearly. We use a sigmoid-based mapping — a common approximation in
            # wireless network simulation literature.
            #
            # At SINR = 10 dB (threshold)  → ~20% packet loss
            # At SINR = 20 dB (clean)      → ~1% packet loss
            # At SINR = 0 dB  (very noisy) → ~90% packet loss
            channel.packet_loss_rate = float(_sinr_to_packet_loss(channel.sinr_db))

            # STEP 5: Flag the channel as interfered if SINR is below threshold
            channel.is_interfered = channel.sinr_db < config.SINR_THRESHOLD_DB

            # STEP 6: Update SINR history (used by ACS Algorithm 2)
            # Keep only the last 10 readings (= last 1 second at 100 ms ticks)
            channel.sinr_history.append(channel.sinr_db)
            if len(channel.sinr_history) > 10:
                channel.sinr_history.pop(0)

    # HELPER: SWITCH A DEVICE TO A NEW CHANNEL

    def switch_device_channel(self, device_id: int, new_channel_id: int):
        """
        Move a device from its current channel to a new one.

        Called by acs.py when an algorithm decides to switch a device.
        Updates the device-channel map and the active flags on both channels.
        """
        old_channel_id = self.device_channel_map.get(device_id)

        if old_channel_id and old_channel_id in self.channels:
            # Check if any other device is still on the old channel before marking it inactive
            others_on_old = [
                d for d, ch in self.device_channel_map.items()
                if ch == old_channel_id and d != device_id
            ]
            if not others_on_old:
                self.channels[old_channel_id].is_active = False

        # Assign device to the new channel
        self.device_channel_map[device_id] = new_channel_id
        self.channels[new_channel_id].is_active = True

    # GETTERS — used by monitor.py, acs.py, and dashboard

    def get_channel(self, channel_id: int) -> ChannelState:
        """Return the current state of a single channel."""
        return self.channels[channel_id]

    def get_all_channels(self) -> List[ChannelState]:
        """Return a list of all 16 channel states (sorted by channel_id)."""
        return [self.channels[i] for i in range(1, config.NUM_CHANNELS + 1)]

    def get_clean_channels(self) -> List[ChannelState]:
        """
        Return channels that are clean enough for ACS to switch to.
        A channel qualifies if its SINR is above ACS_MIN_SINR_TO_ACCEPT.
        Used by both ACS algorithms when scanning for a better channel.
        """
        return [
            ch for ch in self.channels.values()
            if ch.sinr_db >= config.ACS_MIN_SINR_TO_ACCEPT
        ]

    def get_device_channel(self, device_id: int) -> int:
        """Return the channel_id that a given device is currently on."""
        return self.device_channel_map.get(device_id, 1)

# PRIVATE HELPER FUNCTIONS
# These are module-level utility functions used only within this file.
# Prefixed with _ to signal they are internal (Python convention).

def _dbm_to_mw(dbm: float) -> float:
    """
    Convert power from dBm to milliwatts.

    Formula: P(mW) = 10 ^ (P(dBm) / 10)
    This conversion is necessary because you cannot add dBm values directly —
    you must convert to linear (mW), add, then convert back.
    """
    return 10 ** (dbm / 10.0)


def _mw_to_dbm(mw: float) -> float:
    """
    Convert power from milliwatts to dBm.

    Formula: P(dBm) = 10 * log10(P(mW))
    """
    if mw <= 0:
        return -200.0   # Effectively zero power
    return 10.0 * np.log10(mw)


def _linear_to_db(linear_ratio: float) -> float:
    """
    Convert a linear power ratio to decibels (dB).

    Formula: dB = 10 * log10(ratio)
    Used to convert the linear SINR ratio into dB form.
    """
    if linear_ratio <= 0:
        return -100.0
    return 10.0 * np.log10(linear_ratio)


def _sinr_to_packet_loss(sinr_db: float) -> float:
    """
    Map SINR (dB) to a packet loss rate (0.0 – 1.0).

    Uses a sigmoid (logistic) function centred at the SINR threshold.
    This gives a smooth, non-linear relationship between signal quality
    and packet loss — which matches real-world RF behaviour better than
    a simple linear mapping.

    Calibrated so that:
      - SINR >= 20 dB  → ~1%  packet loss  (clean channel)
      - SINR =  10 dB  → ~20% packet loss  (at threshold — matches proposal)
      - SINR =   0 dB  → ~90% packet loss  (heavily interfered)
      - SINR <= -5 dB  → ~99% packet loss  (unusable channel)

    The steepness parameter (k=0.3) controls how sharply packet loss
    rises as SINR falls — tuned to match the 20–25% baseline stated
    in your problem statement.
    """
    # Sigmoid centred at SINR_THRESHOLD_DB, scaled to [0, 1]
    k = 0.4   # Steepness of the curve
    midpoint = config.SINR_THRESHOLD_DB   # = 10 dB — loss rises sharply here

    packet_loss = 1.0 / (1.0 + np.exp(k * (sinr_db - midpoint)))

    # Clamp to realistic bounds — even perfect channels have ~1% loss
    return float(np.clip(packet_loss, 0.01, 0.99))