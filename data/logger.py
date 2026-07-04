# data/logger.py — SQLite Logging & CSV Export
# This file persists simulation data to SQLite and CSV so dashboard results
# remain available after a run finishes.

import csv
import os
import sqlite3
import threading
from typing import List, Optional

import config
from algorithms.acs import SwitchDecision
from monitoring.monitor import MonitorSnapshot


class SimulationLogger:
    def __init__(self, algorithm_name: str = "unknown"):
        self.algorithm_name = algorithm_name
        self.db_path = config.DB_PATH
        self.csv_path = config.CSV_EXPORT_PATH

        # Dash callbacks and the simulation loop run in different threads.
        # SQLite can handle this if access to the shared connection is locked.
        self._db_lock = threading.RLock()

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.connection: Optional[sqlite3.Connection] = None
        self._setup_database()

    def _algorithm(self) -> str:
        """Return a safe canonical algorithm name for database operations."""
        value = self.algorithm_name
        if isinstance(value, dict):
            value = value.get("algorithm") or value.get("name")

        if value == "threshold":
            return "Threshold-Based ACS"
        if value == "weighted":
            return "Weighted Scoring ACS"
        if value in ("Threshold-Based ACS", "Weighted Scoring ACS"):
            return value

        return "Threshold-Based ACS"

    def _setup_database(self):
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        with self._db_lock:
            cursor = self.connection.cursor()
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

    def log_tick(self, snapshot: MonitorSnapshot):
        """Write one row of network-wide metrics and channel data for a tick."""
        if snapshot.tick % config.LOG_EVERY_N_TICKS != 0:
            return

        algorithm = self._algorithm()
        with self._db_lock:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO tick_metrics
                (algorithm_name, tick, timestamp_ms, avg_packet_loss,
                 num_degraded_channels, num_degraded_devices)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                algorithm,
                snapshot.tick,
                snapshot.timestamp_ms,
                snapshot.avg_packet_loss,
                snapshot.num_degraded_channels,
                snapshot.num_degraded_devices,
            ))

            channel_rows = [
                (
                    algorithm,
                    snapshot.tick,
                    ch.channel_id,
                    ch.sinr_db,
                    ch.packet_loss_rate,
                    int(ch.is_interfered),
                    int(ch.is_active),
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
        """Record one ACS decision/event."""
        algorithm = self._algorithm()
        with self._db_lock:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO switch_events
                (algorithm_name, tick, device_id, should_switch, target_channel, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                algorithm,
                tick,
                decision.device_id,
                int(decision.should_switch),
                decision.target_channel,
                decision.reason,
            ))
            self.connection.commit()

    def get_recent_tick_metrics(self, limit: int = 100) -> List[tuple]:
        """Fetch recent tick-level metrics for the current algorithm."""
        algorithm = self._algorithm()
        with self._db_lock:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT tick, timestamp_ms, avg_packet_loss,
                       num_degraded_channels, num_degraded_devices
                FROM tick_metrics
                WHERE algorithm_name = ?
                ORDER BY tick DESC
                LIMIT ?
            """, (algorithm, int(limit)))
            rows = cursor.fetchall()
        rows.reverse()
        return rows

    def get_latest_channel_snapshot(self) -> List[tuple]:
        """Fetch the most recent channel snapshot for the current algorithm."""
        algorithm = self._algorithm()
        with self._db_lock:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT MAX(tick) FROM channel_metrics WHERE algorithm_name = ?
            """, (algorithm,))
            latest_tick_row = cursor.fetchone()
            if latest_tick_row is None or latest_tick_row[0] is None:
                return []
            latest_tick = latest_tick_row[0]

            cursor.execute("""
                SELECT channel_id, sinr_db, packet_loss_rate, is_interfered, is_active
                FROM channel_metrics
                WHERE algorithm_name = ? AND tick = ?
                ORDER BY channel_id ASC
            """, (algorithm, latest_tick))
            return cursor.fetchall()

    def get_switch_events(self, only_approved: bool = True) -> List[tuple]:
        """Fetch ACS switch events for the current algorithm."""
        algorithm = self._algorithm()
        with self._db_lock:
            cursor = self.connection.cursor()
            if only_approved:
                cursor.execute("""
                    SELECT tick, device_id, target_channel, reason
                    FROM switch_events
                    WHERE algorithm_name = ? AND should_switch = 1
                    ORDER BY tick ASC
                """, (algorithm,))
            else:
                cursor.execute("""
                    SELECT tick, device_id, should_switch, target_channel, reason
                    FROM switch_events
                    WHERE algorithm_name = ?
                    ORDER BY tick ASC
                """, (algorithm,))
            return cursor.fetchall()

    def get_available_algorithms(self) -> List[str]:
        with self._db_lock:
            cursor = self.connection.cursor()
            cursor.execute("SELECT DISTINCT algorithm_name FROM tick_metrics")
            return [row[0] for row in cursor.fetchall()]

    def export_to_csv(self):
        """Export the current algorithm's tick metrics to CSV."""
        algorithm = self._algorithm()
        with self._db_lock:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT tick, timestamp_ms, avg_packet_loss,
                       num_degraded_channels, num_degraded_devices
                FROM tick_metrics
                WHERE algorithm_name = ?
                ORDER BY tick ASC
            """, (algorithm,))
            rows = cursor.fetchall()

        safe_name = algorithm.lower().replace(" ", "_").replace("-", "")
        export_path = self.csv_path.replace(".csv", f"_{safe_name}.csv")

        with open(export_path, mode="w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([
                "tick", "timestamp_ms", "avg_packet_loss",
                "num_degraded_channels", "num_degraded_devices",
            ])
            writer.writerows(rows)

        print(f"[Logger] Exported {len(rows)} rows to {export_path}")
        return export_path

    def close(self):
        if self.connection:
            with self._db_lock:
                self.connection.close()

    def clear_algorithm_data(self):
        """Clear logged rows for the currently selected algorithm only."""
        algorithm = self._algorithm()
        with self._db_lock:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM tick_metrics WHERE algorithm_name = ?", (algorithm,))
            cursor.execute("DELETE FROM channel_metrics WHERE algorithm_name = ?", (algorithm,))
            cursor.execute("DELETE FROM switch_events WHERE algorithm_name = ?", (algorithm,))
            self.connection.commit()
        print(f"[Logger] Cleared previous rows for {algorithm}.")

    def clear_all_data(self):
        """Wipe all logged data for a fresh start."""
        with self._db_lock:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM tick_metrics")
            cursor.execute("DELETE FROM channel_metrics")
            cursor.execute("DELETE FROM switch_events")
            self.connection.commit()
        print("[Logger] All logged data cleared.")
