# =============================================================================
# main.py — Simulation Entry Point
# =============================================================================
# Run with:   python main.py
#
# The dashboard starts first in a background thread.
# The user configures the simulation on the Setup page and clicks Start.
# The dashboard calls run_simulation() in a daemon thread, passing the
# user's settings.  run_simulation() mutates config BEFORE initialising
# any simulation modules — so every module picks up the user's values.
#
# Tick order each tick:
#   1. InterferenceEngine  → update Bluetooth hopping, build interference_map
#   2. ChannelEnvironment  → recalculate SINR/packet loss on all 16 channels
#   3. DeviceManager       → simulate packet transmission, update device status
#   4. NetworkMonitor      → observe state, flag devices needing ACS decision
#   5. ACS Algorithm       → decide whether to switch each flagged device
#   6. Apply decisions     → execute any approved switches
#   7. SimulationLogger    → persist metrics and switch events to SQLite
# =============================================================================

import time
import threading
import config

from simulation.environment import ChannelEnvironment
from simulation.devices     import DeviceManager
from simulation.interference import InterferenceEngine
from monitoring.monitor     import NetworkMonitor
from algorithms.acs         import create_algorithm
from data.logger            import SimulationLogger
from dashboard.app import SimulationDashboard
from dashboard.callbacks import register_runner, set_simulation_state, get_simulation_state


# =============================================================================
# HELPERS
# =============================================================================

def _banner(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# =============================================================================
# SIMULATION RUNNER
# =============================================================================

def run_simulation(algorithm_name: str,
                   logger: SimulationLogger,
                   num_devices: int = None,
                   duration_s: int  = None,
                   num_wifi: int    = None,
                   num_bt: int      = None):
    """
    Run the full simulation tick loop for one ACS algorithm.

    User settings (devices, duration, interferers) are applied to
    config BEFORE any simulation module is created, so every module
    reads the correct values.
    """

    # ── Guard against double-start ─────────────────────────────────────
    state = get_simulation_state()
    if state["status"] == "running":
        print("  [main.py] Simulation already running — ignoring duplicate start.")
        return

    # ── Apply user settings to config ──────────────────────────────────
    if num_devices is not None: config.NUM_IOT_DEVICES     = int(num_devices)
    if num_wifi    is not None: config.NUM_WIFI_INTERFERERS = int(num_wifi)
    if num_bt      is not None: config.NUM_BT_INTERFERERS   = int(num_bt)
    if duration_s  is not None:
        config.SIMULATION_DURATION_S = int(duration_s)
        config.TOTAL_TICKS = (config.SIMULATION_DURATION_S * 1000) // config.TICK_INTERVAL_MS

    # ── Create ACS algorithm first so we know the canonical name ───────
    # This must happen before clear_algorithm_data() so the logger clears
    # the correct algorithm's rows (e.g. "Threshold-Based ACS", not "threshold").
    acs = create_algorithm(algorithm_name)
    logger.algorithm_name = acs.name

    # Mark the run as active before any longer setup work, so the
    # dashboard changes from Idle immediately after Start is clicked.
    set_simulation_state(
        status="running",
        algorithm=acs.name,
        tick=0,
        total_ticks=config.TOTAL_TICKS,
        final_loss=None,
        total_switches=0,
        error=None,
    )

    # Clear only this algorithm's previous data, not the whole DB.
    # Re-running RTDS won't wipe PPCS results (and vice versa).
    # The user can wipe everything via the Reset Results button.
    logger.clear_algorithm_data()

    _banner(f"Starting: {acs.name}")
    print(f"  Duration : {config.SIMULATION_DURATION_S}s  ({config.TOTAL_TICKS} ticks)")
    print(f"  Devices  : {config.NUM_IOT_DEVICES}")
    print(f"  WiFi     : {config.NUM_WIFI_INTERFERERS}  |  BT: {config.NUM_BT_INTERFERERS}\n")

    # ── Initialise all simulation modules ─────────────────────────────
    environment         = ChannelEnvironment()
    device_manager      = DeviceManager()
    device_manager.initialise()
    device_ids          = [d.device_id for d in device_manager.get_all_devices()]
    environment.assign_devices_to_channels(device_ids)
    interference_engine = InterferenceEngine()
    monitor             = NetworkMonitor()

    # ── Tick loop ──────────────────────────────────────────────────────
    tick_duration_s = config.TICK_INTERVAL_MS / 1000.0
    total_switches  = 0
    snapshot        = None
    tick = 0

    try:
        for tick in range(1, config.TOTAL_TICKS + 1):

            tick_start = time.time()

            interference_map = interference_engine.update(
                device_manager.get_all_interferers(), current_tick=tick)

            environment.update(interference_map)
            device_manager.update(environment)
            snapshot = monitor.observe(environment, device_manager, tick)
            
            # Log the degraded state before ACS switches devices.
            # This gives the dashboard one visible tick where devices appear as
            # Interference/Degraded before moving into ACS Recovery.
            logger.log_tick(snapshot)
            set_simulation_state(tick=tick)
            for device_id in snapshot.devices_needing_switch:
                device = device_manager.get_device(device_id)
                if device is None:
                    continue
                decision = acs.decide(
                    device=device,
                    environment=environment,
                    all_devices=device_manager.get_all_devices()
                )
                logger.log_switch_event(tick, decision)
                if decision.should_switch and decision.target_channel is not None:
                    device.perform_switch(decision.target_channel, tick)
                    environment.switch_device_channel(device_id, decision.target_channel)
                    monitor.reset_degradation_tracking(device_id)
                    total_switches += 1
                    print(f"  [Tick {tick:>4}] Device {device_id} → Ch {decision.target_channel}"
                          f"  |  {decision.reason[:60]}")

        
            if tick % 50 == 0:
                pct = (tick / config.TOTAL_TICKS) * 100
                print(f"  {tick}/{config.TOTAL_TICKS} ({pct:.0f}%)  |  "
                      f"Loss: {snapshot.avg_packet_loss*100:.1f}%  |  "
                      f"Degraded ch: {snapshot.num_degraded_channels}  |  "
                      f"Switches: {total_switches}")

            elapsed    = time.time() - tick_start
            sleep_time = tick_duration_s - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except Exception as e:
        # If any tick raises an unexpected error, mark the simulation as
        # failed so the dashboard shows "Error" instead of spinning on "Running".
        set_simulation_state(status="error", error=str(e))
        print(f"\n  [ERROR] Simulation failed at tick {tick}: {e}")
        raise

    # ── Complete ───────────────────────────────────────────────────────
    final_loss = snapshot.avg_packet_loss * 100 if snapshot else 0.0
    set_simulation_state(
        status="completed",
        final_loss=final_loss,
        total_switches=total_switches,
        algorithm=acs.name,
    )

    _banner(f"Complete: {acs.name}")
    print(f"  Ticks   : {config.TOTAL_TICKS}  |  Switches: {total_switches}")
    print(f"  Final avg packet loss: {final_loss:.1f}%\n")

    csv_path = logger.export_to_csv()
    print(f"  Exported → {csv_path}\n")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    logger    = SimulationLogger(algorithm_name="initialising")
    dashboard = SimulationDashboard(logger)

    # Give the dashboard a handle so the Start button can trigger the simulation
    def _runner(algorithm, num_devices, duration_s, num_wifi, num_bt):
        run_simulation(
            algorithm_name=algorithm,
            logger=logger,
            num_devices=num_devices,
            duration_s=duration_s,
            num_wifi=num_wifi,
            num_bt=num_bt,
        )

    register_runner(_runner)

    # Start dashboard
    dashboard_thread = threading.Thread(target=dashboard.run, daemon=True)
    dashboard_thread.start()

    print(f"\n  Dashboard → http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")
    print("  Open that URL, go to Simulation Setup, and click Start.\n")

    # Keep alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Exiting.")
        logger.close()


if __name__ == "__main__":
    main()