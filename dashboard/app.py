# dashboard/app.py

import dash
from dash import dcc, html

import config
from .styles import COLORS, LAYOUT
from .callbacks import register_callbacks


class SimulationDashboard:
    """
    Main Dash application wrapper.

    This file only creates the Dash app, defines the global shell,
    and registers callbacks. Page layouts are in layouts.py and
    callback logic is in callbacks.py.
    """

    def __init__(self, logger):
        self.logger = logger
        self.app = dash.Dash(
            __name__,
            title="IoT Interference Simulation Tool",
            suppress_callback_exceptions=True,
        )

        self._build_layout()
        register_callbacks(self.app, self.logger)

    def _build_layout(self):
        self.app.layout = html.Div(
            [
                dcc.Location(id="url", refresh=False),

                html.Div(id="page-content"),

                dcc.Interval(
                    id="tick",
                    interval=config.DASHBOARD_REFRESH_MS,
                    n_intervals=0,
                ),

                dcc.Store(id="store-algo"),
            ],
            style={
                "fontFamily": LAYOUT["font"],
                "background": COLORS["background"],
                "minHeight": "100vh",
            },
        )

    def run(self):
        self.app.run(
            host=config.DASHBOARD_HOST,
            port=config.DASHBOARD_PORT,
            debug=False,
        )