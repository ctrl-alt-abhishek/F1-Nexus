"""
app/services/signalr_client.py - SignalR client for live timing.
"""

import logging
import time
import os

logger = logging.getLogger(__name__)

def check_token_valid() -> bool:
    try:
        import fastf1.livetiming.client as client
        g = client.get_auth_token.__globals__
        _verify_jwt = g.get('_verify_jwt')
        JWKS_URL = g.get('JWKS_URL')
        AUTH_DATA_FILE = g.get('AUTH_DATA_FILE')
        
        if _verify_jwt and JWKS_URL and AUTH_DATA_FILE and os.path.exists(AUTH_DATA_FILE):
            with open(AUTH_DATA_FILE) as f:
                token = f.read().strip()
            if token:
                _verify_jwt(token, JWKS_URL)
                return True
    except Exception as e:
        logger.warning("FastF1 token verification failed: %s", e)
    return False

from fastf1.livetiming.client import SignalRClient

class MemorySignalRClient(SignalRClient):
    """
    Custom SignalRClient that overrides output file writing to process messages
    directly in memory via a callback.
    """
    def __init__(self, callback, no_auth: bool = False, logger=None, timeout: int = 60):
        # Pass dummy filename to satisfy super().__init__
        super().__init__(filename="dummy.txt", no_auth=no_auth, logger=logger, timeout=timeout)
        self.callback = callback

    def _on_connect(self):
        super()._on_connect()
        # Automatically subscribe/re-subscribe to topics upon connection/reconnection
        self._connection.send(
            "Subscribe", [self.topics], on_invocation=self._on_message
        )

    def _run(self):
        # Override to avoid opening files
        import requests
        from signalrcore.hub_connection_builder import HubConnectionBuilder
        from fastf1.livetiming.client import get_auth_token

        # Pre-negotiate to get a valid AWSALBCORS header token
        r = requests.options(self._negotiate_url, headers=self.headers)
        if 'AWSALBCORS' in r.cookies:
            self.headers.update(
                {"Cookie": f"AWSALBCORS={r.cookies['AWSALBCORS']}"}
            )

        # Configure and create connection
        options = {
            "verify_ssl": True,
            "headers": self.headers
        }
        if not self._no_auth:
            options["access_token_factory"] = get_auth_token

        self._connection = HubConnectionBuilder() \
            .with_url(self._connection_url, options=options) \
            .configure_logging(logging.INFO) \
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5
            }) \
            .build()

        self._connection.on_open(self._on_connect)
        self._connection.on_close(self._on_close)
        self._connection.on('feed', self._on_message)

        self._connection.start()

        # wait for connection to be established
        while not self._is_connected:
            time.sleep(0.1)

    def _on_message(self, msg):
        self._t_last_message = time.time()
        from signalrcore.messages.completion_message import CompletionMessage

        if isinstance(msg, CompletionMessage):
            # Process the initial state returned by the subscription call
            if msg.result and isinstance(msg.result, dict):
                for key, val in msg.result.items():
                    try:
                        self.callback(key, val, "")
                    except Exception:
                        self.logger.exception("Callback error during initial message processing")
        elif isinstance(msg, list) and len(msg) >= 3:
            try:
                self.callback(msg[0], msg[1], msg[2])
            except Exception:
                self.logger.exception("Callback error during message processing")

    def _supervise(self):
        # check if data is still being received and exit if not
        self._t_last_message = time.time()
        while True:
            # If the connection drops, we should exit immediately so the worker can retry or handle it
            if not self._is_connected:
                self.logger.warning("Connection closed - exiting supervisor loop")
                self._exit()
                return

            if (self.timeout != 0
                    and time.time() - self._t_last_message > self.timeout):

                self.logger.warning(f"Timeout - received no data for more "
                                    f"than {self.timeout} seconds!")

                self._exit()
                return

            time.sleep(1)

    def _exit(self):
        if self._connection:
            self._connection.stop()

def run_client_blocking(client) -> None:
    """Blocking runner for the SignalR client (executed in thread pool)."""
    try:
        client.start()
    except Exception as exc:
        logger.debug("SignalR client exited: %s", exc)
