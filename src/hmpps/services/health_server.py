from flask import Flask, jsonify
import time
import os
import logging
import threading
import socket


def setup_logging(level: str = 'INFO') -> None:
  """Setup logging configuration."""
  logging.basicConfig(
    level=getattr(logging, level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()],
  )


class HealthServer:
  def __init__(self):
    # Create Flask app for health checks
    self.health_app = Flask(__name__)
    self.host_name = (
      '-'.join(socket.gethostname().split('-')[:-2])
      if len(socket.gethostname().split('-')) > 2
      else socket.gethostname()
    )
    # Get version and productId from environment variables
    self.version = os.getenv('APP_VERSION', 'dev')
    self.environment = os.getenv('ENVIRONMENT', None)
    self.product_id = os.getenv('PRODUCT_ID', None)

    # Initiate the start_time variable
    self.app_start_time = None

    # Environment variable takes precedence over config file
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    setup_logging(log_level)

    self.logger = logging.getLogger(__name__)
    self.add_routes()

  # Routes are linked to below
  def add_routes(self):
    self.health_app.route('/health')(self._health)
    self.health_app.route('/info')(self._info)
    self.health_app.route('/ping')(self._ping)

    @self.health_app.errorhandler(404)
    def page_not_found(e):
      return 'Not found.', 404

  def _health(self):
    health_data = {
      'status': 'UP',
      'service': self.host_name,
    }

    # Return appropriate HTTP status code
    status_code = 200 if health_data['status'] == 'UP' else 503
    return jsonify(health_data), status_code

  def _info(self):
    """Application info endpoint."""
    current_time = time.time()
    uptime_seconds = (
      int(current_time - self.app_start_time) if self.app_start_time else 0
    )

    info_data = {
      'build': {'version': self.version, 'name': self.host_name},
      'uptime': uptime_seconds,
    }
    if self.environment:
      info_data['environment'] = self.environment
    if self.product_id:
      info_data['productId'] = self.product_id

    return jsonify(info_data)

  def _ping(self):
    """Simple ping endpoint for Kubernetes liveness and readiness probes."""
    return 'pong', 200

  def start_health_server(self, port: int = 8080):
    # Store application start time for uptime calculation
    self.logger.info(f'Starting {self.host_name} health app')
    self.app_start_time = time.time()
    """Start the Flask health check server in a separate thread."""
    try:
      # Encourage Flask only to log INFO logging to avoid cluttering our logs
      logging.getLogger('werkzeug').setLevel(logging.INFO)

      self.logger.info('Health check server starting on port %d', port)
      self.health_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except OSError as e:
      self.logger.error('Failed to start health check server: %s', e)

  def start(self):
    # Start health check server in background thread
    health_thread = threading.Thread(
      target=self.start_health_server, args=(8080,), daemon=True
    )
    health_thread.start()
    self.logger.info('Health check endpoint available at http://localhost:8080/health')
