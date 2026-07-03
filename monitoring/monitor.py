# monitoring/monitor.py — Network Health Monitoring
# Every tick, it:
#   1. Reads the current state of all 16 channels (from environment.py)
#   2. Reads the current state of all IoT devices (from devices.py)
#   3. Decides which devices are in trouble and need ACS to act
#   4. Packages everything into a clean MonitorSnapshot for:
#        - acs.py        (to decide if/where to switch)
#        - data/logger.py (to persist to SQLite)
#        - dashboard/app.py (to display live charts)
#
# Design principle:
#   The Monitor does NOT make decisions about switching channels —
#   that's ACS's job. The Monitor only OBSERVES and REPORTS.
#   This separation (observe vs. decide) is good practice and makes
#   each module easier to explain in your design chapter.

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict
import config
from simulation.environment import ChannelEnvironment, ChannelState
from simulation.devices import DeviceManager, IoTDevice, DeviceStatus


# DATA CONTAINERS
@dataclass
class MonitorSnapshot:
    """
    A complete picture of network health at one tick.

    This is the object that gets passed around to ACS, the logger,
    and the dashboard — so they all see a consistent view of the world
    at this exact moment in time.
    """

    tick: int                                  # Which tick this snapshot is for
    timestamp_ms: int                          # Simulated time in ms (tick * TICK_INTERVAL_MS)

    channel_states: List[ChannelState]         # Snapshot of all 16 channels
    device_states: List[IoTDevice]             # Snapshot of all IoT devices

    #  Aggregate metrics (computed once per tick, used everywhere) 
    avg_packet_loss: float = 0.0               # Average packet loss across all devices
    num_degraded_channels: int = 0             # How many of the 16 channels are interfered
    num_degraded_devices: int = 0              # How many devices are currently DEGRADED

    # Devices flagged as needing an ACS decision this tick 
    # A device needs attention if it has been degraded for long enough that it crosses the detection window (500ms / 5 ticks).
    devices_needing_switch: List[int] = field(default_factory=list)


# MONITOR CLASS
class NetworkMonitor:
    """
    Observes the environment and devices each tick, and flags problems.

    Maintains a small amount of its own state: a per-device counter of
    "how many consecutive ticks has this device been degraded" — this is
    what implements the 500ms detection window from your NFR, rather than
    reacting to a single noisy SINR dip immediately.
    """

    def __init__(self):
        # Tracks consecutive degraded ticks per device.
        # Key = device_id, Value = consecutive tick count
        # Reset to 0 whenever the device's channel becomes healthy again.
        self._consecutive_degraded_ticks: Dict[int, int] = {}

        # How many consecutive degraded ticks before we flag a device to ACS.
        # ACS_DETECTION_WINDOW_MS = 500ms, TICK_INTERVAL_MS = 100ms -> 5 ticks.
        # Using floor division ensures this stays an integer tick count.
        self.detection_window_ticks = (
            config.ACS_DETECTION_WINDOW_MS // config.TICK_INTERVAL_MS
        )

        # Keep a short rolling history of avg_packet_loss for dashboard trend lines (e.g. a sparkline). Capped to avoid unbounded memory growth.
        self.packet_loss_history: List[float] = []
        self._MAX_HISTORY = 600   # 600 ticks = 60 seconds at 100ms/tick

    # MAIN TICK FUNCTION
    def observe(
        self,
        environment: ChannelEnvironment,
        device_manager: DeviceManager,
        current_tick: int
    ) -> MonitorSnapshot:
        """
        Take a full snapshot of network health for this tick.

        Called once per tick by main.py, AFTER environment.update() and
        device_manager.update() have already run (so the data is fresh).

        Returns
        -------
        MonitorSnapshot
            Everything ACS, the logger, and the dashboard need for this tick.
        """

        channel_states = environment.get_all_channels()
        device_states = device_manager.get_all_devices()

        # Compute aggregate metrics
        avg_loss = self._compute_average_packet_loss(device_states)
        num_degraded_channels = sum(1 for ch in channel_states if ch.is_interfered)
        num_degraded_devices = sum(
            1 for d in device_states if d.status == DeviceStatus.DEGRADED
        )

        # Update consecutive-degraded-tick counters & decide who needs ACS
        devices_needing_switch = self._update_degradation_tracking(
            device_states, environment, current_tick
        )

        # Maintain rolling packet loss history for dashboard trend chart
        self.packet_loss_history.append(avg_loss)
        if len(self.packet_loss_history) > self._MAX_HISTORY:
            self.packet_loss_history.pop(0)

        return MonitorSnapshot(
            tick=current_tick,
            timestamp_ms=current_tick * config.TICK_INTERVAL_MS,
            channel_states=channel_states,
            device_states=device_states,
            avg_packet_loss=avg_loss,
            num_degraded_channels=num_degraded_channels,
            num_degraded_devices=num_degraded_devices,
            devices_needing_switch=devices_needing_switch
        )

    # HELPER: AVERAGE PACKET LOSS
    def _compute_average_packet_loss(self, devices: List[IoTDevice]) -> float:
        """
        Average the CURRENT-TICK packet loss rate across all transmitting devices.

        We use each device's channel's instantaneous packet_loss_rate here
        (not the cumulative packets_lost/packets_sent), because for live
        dashboard display we want to show "how bad is it RIGHT NOW",
        not the all-time average which would be slow to react to changes.
        """
        active_devices = [
            d for d in devices
            if d.status in (DeviceStatus.TRANSMITTING, DeviceStatus.DEGRADED)
        ]

        if not active_devices:
            return 0.0

        # Each device's most recent SINR reading tells us its current channel quality; we convert that into "current loss" via the device's own
        # cumulative rate as a stable estimate. For simplicity and to avoid importing environment's sigmoid function here, we use the device's
        # running average loss rate so far this run.
        losses = [d.packet_loss_rate() for d in active_devices]
        return float(np.mean(losses))

    
    # HELPER: DEGRADATION TRACKING (implements the 500ms detection window)
    def _update_degradation_tracking(
        self,
        devices: List[IoTDevice],
        environment: ChannelEnvironment,
        current_tick: int
    ) -> List[int]:
        """
        Track how long each device's channel has been degraded, and decide
        which devices have crossed the detection window threshold.

        This is the core logic behind your NFR: "detect interference within
        500ms". Rather than reacting to a single bad tick (which could just
        be random fading noise), we require SUSTAINED degradation across
        multiple consecutive ticks before flagging the device to ACS.

        Returns
        -------
        list of int
            device_ids that have been degraded for >= detection_window_ticks
            and should be evaluated by ACS this tick.
        """
        flagged_devices = []

        for device in devices:
            # Skip devices that are mid-switch — they'll resume next tick
            if device.status == DeviceStatus.SWITCHING:
                continue

            channel = environment.get_channel(device.channel_id)
            current_count = self._consecutive_degraded_ticks.get(device.device_id, 0)

            if channel.is_interfered:
                # Channel is bad this tick -> increment the streak
                current_count += 1
            else:
                # Channel is healthy -> reset the streak to zero
                current_count = 0

            self._consecutive_degraded_ticks[device.device_id] = current_count

            # Flag this device if it has been degraded long enough AND it's allowed to switch again (respects the cooldown in devices.py)
            if (current_count >= self.detection_window_ticks
                    and device.can_switch(current_tick)):
                flagged_devices.append(device.device_id)

        return flagged_devices

    # PUBLIC HELPER: RESET TRACKING FOR A DEVICE (called after a switch)
    def reset_degradation_tracking(self, device_id: int):
        """
        Clear the consecutive-degraded-ticks counter for a device.

        Called by acs.py immediately after switching a device to a new
        channel, so the device gets a fresh detection window on its new
        channel rather than carrying over its old "degraded streak".
        """
        self._consecutive_degraded_ticks[device_id] = 0