# data/logger.py — SQLite Logging & CSV Export
# This file is responsible for PERSISTING simulation data so it survives
# after the simulation ends. Without this, all results would vanish
# the moment the program closes — which is no good for an evaluation chapter
# that needs graphs, tables, and statistical comparisons between algorithms.
#
# Two storage formats are used:
#   1. SQLite (data/simulation.db)
#   2. CSV (data/results.csv)      
#
# Design principle:
#   The Logger does not calculate anything — it just RECORDS what other modules (Monitor, ACS) have already computed. This keeps it simple
#   and means logging never affects simulation behaviour.

import sqlite3
import csv
import os
from typing import List, Optional
from dataclasses import dataclass
import config
from monitoring.monitor import MonitorSnapshot
from algorithms.acs import SwitchDecision


class SimulationLogger:

    def __init__(self, algorithm_name: str = "unknown"):
      
        self.algorithm_name = algorithm_name
        self.db_path = config.DB_PATH
        self.csv_path = config.CSV_EXPORT_PATH

        # Ensure the /data directory exists before SQLite tries to create
        # the database file inside it.
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.connection: Optional[sqlite3.Connection] = None
        self._setup_database()

    # DATABASE SETUP

    def _setup_database(self):
     
        # check_same_thread=False allows the dashboard (which may run in a different thread via Dash's dev server) to read from the same
        # connection safely for read-only queries.
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.connection.cursor()

        #tick_metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tick_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                algorithm_name TEXT,
                tick INTEGER,
                timestamp_ms INTEGER,
                avg_packet_loss REAL,
                num_degraded_channels INTEGER,
                num_degraded_devices INTEGER
            )
        """)

        # --- channel_metrics table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                algorithm_name TEXT,
                tick INTEGER,
                channel_id INTEGER,
                sinr_db REAL,
                packet_loss_rate REAL,
                is_interfered INTEGER,
                is_active INTEGER
            )
        """)

        # --- switch_events table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS switch_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                algorithm_name TEXT,
                tick INTEGER,
                device_id INTEGER,
                should_switch INTEGER,
                target_channel INTEGER,
                reason TEXT
            )
        """)

        self.connection.commit()

    # LOGGING METHODS — called every tick by main.py
    def log_tick(self, snapshot: MonitorSnapshot):
        """
        Write one row of network-wide metrics for this tick.

        Called once per tick from main.py, right after monitor.observe().
        Respects LOG_EVERY_N_TICKS from config.py to control how much
        data is written (set to 1 to log every tick, higher to reduce
        database size for longer runs).
        """
        if snapshot.tick % config.LOG_EVERY_N_TICKS != 0:
            return   # Skip this tick based on the configured logging frequency

        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO tick_metrics
            (algorithm_name, tick, timestamp_ms, avg_packet_loss,
             num_degraded_channels, num_degraded_devices)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            self.algorithm_name,
            snapshot.tick,
            snapshot.timestamp_ms,
            snapshot.avg_packet_loss,
            snapshot.num_degraded_channels,
            snapshot.num_degraded_devices
        ))

        # Also log per-channel detail for the spectrum view.
        # executemany is used here for efficiency — inserting 16 rows individually would be slower than one batched call.
        channel_rows = [
            (
                self.algorithm_name,
                snapshot.tick,
                ch.channel_id,
                ch.sinr_db,
                ch.packet_loss_rate,
                int(ch.is_interfered),   # SQLite has no native boolean type,
                int(ch.is_active)        # so booleans are stored as 0/1
            )
            for ch in snapshot.channel_states
        ]
        cursor.executemany("""
            INSERT INTO channel_metrics
            (algorithm_name, tick, channel_id, sinr_db, packet_loss_rate,
             is_interfered, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, channel_rows)

        self.connection.commit()

    def log_switch_event(self, tick: int, decision: SwitchDecision):
        """
        Record a single ACS decision (whether it resulted in a switch or not).

        Called by main.py every time acs.decide() returns a result —
        logging BOTH approved and rejected decisions is intentional:
        it lets you analyse not just how often the algorithm switches,
        but how often it correctly decides NOT to switch (e.g. because
        no better channel was available).
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO switch_events
            (algorithm_name, tick, device_id, should_switch, target_channel, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            self.algorithm_name,
            tick,
            decision.device_id,
            int(decision.should_switch),
            decision.target_channel,
            decision.reason
        ))
        self.connection.commit()

    # READ METHODS — used by the dashboard to display live/historical data

    def get_recent_tick_metrics(self, limit: int = 100) -> List[tuple]:
        """
        Fetch the most recent N rows of tick_metrics for the current algorithm.

        Used by dashboard/app.py to populate the live packet-loss-over-time
        and degraded-channel-count line charts. Returns raw tuples (rather
        than objects) since Plotly/Dash callbacks work efficiently with
        simple row data that can be sliced directly into chart traces.
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT tick, timestamp_ms, avg_packet_loss,
                   num_degraded_channels, num_degraded_devices
            FROM tick_metrics
            WHERE algorithm_name = ?
            ORDER BY tick DESC
            LIMIT ?
        """, (self.algorithm_name, limit))
        rows = cursor.fetchall()
        rows.reverse()   # Return in chronological order (oldest first) for charts
        return rows

    def get_latest_channel_snapshot(self) -> List[tuple]:
        """
        Fetch the most recent tick's data for all 16 channels.

        Used by the dashboard's live spectrum bar chart, which shows
        the current SINR/interference state of every channel at once.
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT MAX(tick) FROM channel_metrics WHERE algorithm_name = ?
        """, (self.algorithm_name,))
        latest_tick_row = cursor.fetchone()
        latest_tick = latest_tick_row[0]

        if latest_tick is None:
            return []   # No data logged yet

        cursor.execute("""
            SELECT channel_id, sinr_db, packet_loss_rate, is_interfered, is_active
            FROM channel_metrics
            WHERE algorithm_name = ? AND tick = ?
            ORDER BY channel_id ASC
        """, (self.algorithm_name, latest_tick))
        return cursor.fetchall()

    def get_switch_events(self, only_approved: bool = True) -> List[tuple]:
        """
        Fetch all switch events for the current algorithm.

        Parameters
        ----------
        only_approved : bool
            If True, only return events where should_switch was True
            (i.e. actual switches that happened). If False, return
            every decision including rejected ones.
        """
        cursor = self.connection.cursor()
        if only_approved:
            cursor.execute("""
                SELECT tick, device_id, target_channel, reason
                FROM switch_events
                WHERE algorithm_name = ? AND should_switch = 1
                ORDER BY tick ASC
            """, (self.algorithm_name,))
        else:
            cursor.execute("""
                SELECT tick, device_id, should_switch, target_channel, reason
                FROM switch_events
                WHERE algorithm_name = ?
                ORDER BY tick ASC
            """, (self.algorithm_name,))
        return cursor.fetchall()

    def get_available_algorithms(self) -> List[str]:
        """
        Return the distinct algorithm names present in the database.

        Used by the dashboard to populate a dropdown selector, letting
        the user switch between viewing Algorithm 1's results and
        Algorithm 2's results side by side after both runs are complete.
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT DISTINCT algorithm_name FROM tick_metrics")
        return [row[0] for row in cursor.fetchall()]

    # CSV EXPORT — called once at the end of a simulation run

    def export_to_csv(self):
        """
        Export the full tick_metrics table (for this algorithm) to CSV.

        Called once by main.py after the simulation loop finishes.
        This gives you a simple flat file you can open directly in Excel,
        or load with pandas for additional statistical analysis in your
        evaluation chapter (e.g. computing mean/median packet loss,
        recovery success rate, etc.).
        """
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT tick, timestamp_ms, avg_packet_loss,
                   num_degraded_channels, num_degraded_devices
            FROM tick_metrics
            WHERE algorithm_name = ?
            ORDER BY tick ASC
        """, (self.algorithm_name,))
        rows = cursor.fetchall()

        # Build a unique filename per algorithm so running both algorithms
        # doesn't overwrite each other's CSV exports.
        safe_name = self.algorithm_name.lower().replace(" ", "_")
        export_path = self.csv_path.replace(".csv", f"_{safe_name}.csv")

        with open(export_path, mode="w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            # Header row — column names matching the SELECT order above
            writer.writerow([
                "tick", "timestamp_ms", "avg_packet_loss",
                "num_degraded_channels", "num_degraded_devices"
            ])
            writer.writerows(rows)

        print(f"[Logger] Exported {len(rows)} rows to {export_path}")
        return export_path

    # CLEANUP
    def close(self):
        """
        Close the SQLite connection cleanly.

        Called by main.py when the simulation ends, to avoid leaving
        an open database connection (which can cause file-lock issues
        on some systems, especially Windows).
        """
        if self.connection:
            self.connection.close()


    def clear_algorithm_data(self):
        """
        Clear logged rows for the currently selected algorithm only.

        main.py calls this at the start of a new run so the live dashboard
        shows fresh data for that algorithm, without deleting results from
        the other algorithm.
        """
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM tick_metrics WHERE algorithm_name = ?", (self.algorithm_name,))
        cursor.execute("DELETE FROM channel_metrics WHERE algorithm_name = ?", (self.algorithm_name,))
        cursor.execute("DELETE FROM switch_events WHERE algorithm_name = ?", (self.algorithm_name,))
        self.connection.commit()
        print(f"[Logger] Cleared previous rows for {self.algorithm_name}.")

    def clear_all_data(self):
        """
        Wipe all logged data for a fresh start.

        Useful during development when you want to re-run the simulation
        without accumulating duplicate data across multiple test runs.
        NOT called automatically — call manually if needed, e.g. from a
        small reset script.
        """
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM tick_metrics")
        cursor.execute("DELETE FROM channel_metrics")
        cursor.execute("DELETE FROM switch_events")
        self.connection.commit()
        print("[Logger] All logged data cleared.")