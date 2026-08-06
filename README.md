# order-service: GitHub Actions + Prometheus on minikube

A small, deliberately simple project for learning how GitHub Actions and
Prometheus fit together in a real deploy pipeline:

- **App**: a Flask "order service" instrumented with `prometheus_client`
  (a Counter, a Histogram, a Gauge — the three you'll use 90% of the time).
- **CI/CD**: GitHub Actions runs tests, builds the image, and deploys to
  minikube, all in the `github-actions` namespace.
- **Observability**: a plain Prometheus (no Operator/CRDs, so you can see
  exactly what's happening) auto-discovers and scrapes the app via pod
  annotations.

## The one thing to understand before you start

**GitHub's hosted runners live in the cloud. They cannot see your laptop's
minikube cluster.** So this pipeline uses a **self-hosted runner** — a small
agent you install on your own machine — for the `build` and `deploy` jobs.
The `test` job stays on a normal hosted runner since it needs nothing but
Python. This split (hosted for stateless work, self-hosted for
cluster-access work) is exactly how most teams run CI/CD against
on-prem/local/VPC-internal clusters, so it's a good pattern to internalize.

## One-time setup

1. **Install & start minikube**
   ```bash
   minikube start
   ```

2. **Register a self-hosted runner** on the *same machine*:
   - GitHub repo → Settings → Actions → Runners → "New self-hosted runner"
   - Follow the download/config steps GitHub shows you, but when you get to
     `./config.sh`, add a label so the workflow can target it:
     ```bash
     ./config.sh --url https://github.com/<you>/<repo> --token <token> --labels minikube
     ./run.sh          # or: sudo ./svc.sh install && sudo ./svc.sh start
     ```
   - Confirm `kubectl` on that machine is pointed at minikube:
     `kubectl config current-context` should say `minikube`.

3. **Push this repo to GitHub.** The workflow triggers on push to `main`
   (and on PRs, but the build/deploy jobs only make sense on `main` unless
   you adjust the trigger).

That's it — every push now runs test → build → deploy automatically.

## What happens on each push

```
push to main
   │
   ▼
[test]  ubuntu-latest, hosted        pytest against the Flask app
   │
   ▼
[build] self-hosted, on minikube box `minikube image build` — builds the
   │                                  image straight into minikube's internal
   │                                  image store (no registry needed locally)
   ▼
[deploy] self-hosted, on minikube box kubectl apply namespace + Prometheus +
                                       RBAC + the app deployment (with the
                                       new image tag) + service, then waits
                                       for the rollout to succeed
```

## Checking it worked

```bash
kubectl get pods -n github-actions
```

You should see 2 `order-service` pods and 1 `prometheus` pod, all `Running`.

Port-forward the app and hit it a few times to generate metrics:
```bash
kubectl -n github-actions port-forward svc/order-service 8080:8080 &
for i in $(seq 1 30); do curl -s -X POST localhost:8080/order; done
curl -s localhost:8080/metrics | head -30
```

Port-forward Prometheus and open its UI:
```bash
kubectl -n github-actions port-forward svc/prometheus 9090:9090
# open http://localhost:9090
```

Check the **Status → Targets** page first — you should see `order-service`
pods listed as `UP`. That confirms the annotation-based discovery worked.

## PromQL to try

- Request rate by endpoint:
  `sum(rate(http_requests_total[1m])) by (endpoint)`
- Error rate (5xx) as a percentage:
  `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100`
- p95 latency:
  `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`
- Orders created vs failed:
  `sum(rate(orders_created_total[5m]))` and `sum(rate(orders_failed_total[5m]))`
- In-flight requests right now:
  `http_requests_in_progress`

## Where to go next

- Swap the plain Prometheus for `kube-prometheus-stack` (Helm) once you're
  comfortable — it gives you the `ServiceMonitor` CRD instead of hand-written
  scrape configs, plus Grafana and Alertmanager for free.
- Add a `notify` job to the workflow that posts to Slack on rollout failure.
- Push the image to GHCR instead of building into minikube directly, and add
  a `staging` vs `prod` environment with GitHub Environments + required
  reviewers — that's the more "production" version of this same pipeline.
- Add resource-based alerting rules to Prometheus (e.g. alert if error rate
  > 5% for 5 minutes) to practice the alerting side of observability.

## Local dev (no k8s, no Actions) — just the app

```bash
cd app
pip install -r requirements-dev.txt
python app.py
# in another shell
curl -X POST localhost:8080/order
curl localhost:8080/metrics
pytest -v
```
