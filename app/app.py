import random
import time

from flask import Flask, Response, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Metrics
#
# Three classic instrumentation patterns:
#   Counter   - a number that only goes up (total requests, total errors)
#   Histogram - distribution of a value (request latency, in buckets)
#   Gauge     - a number that goes up and down (in-flight requests)
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)

IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Requests currently being processed",
)

ORDERS_CREATED = Counter("orders_created_total", "Total orders successfully created")
ORDERS_FAILED = Counter("orders_failed_total", "Total orders that failed to process")


@app.before_request
def _start_timer():
    request._start_time = time.time()
    IN_PROGRESS.inc()


@app.after_request
def _record_metrics(response):
    latency = time.time() - getattr(request, "_start_time", time.time())
    endpoint = request.path
    REQUEST_LATENCY.labels(request.method, endpoint).observe(latency)
    REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
    IN_PROGRESS.dec()
    return response


@app.route("/healthz")
def healthz():
    return jsonify(status="ok"), 200


@app.route("/order", methods=["POST"])
def create_order():
    # Simulate variable processing time so the latency histogram has
    # something interesting to show.
    time.sleep(random.uniform(0.01, 0.25))

    # Simulate an occasional downstream failure (~10% of requests) so the
    # error-rate metric isn't always zero.
    if random.random() < 0.1:
        ORDERS_FAILED.inc()
        return jsonify(error="downstream payment service timeout"), 500

    ORDERS_CREATED.inc()
    return jsonify(order_id=random.randint(1000, 9999), status="created"), 201


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
