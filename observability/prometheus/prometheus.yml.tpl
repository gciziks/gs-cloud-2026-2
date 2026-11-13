global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: vigia
    scheme: __MVP_SCHEME__
    metrics_path: /metrics
    authorization:
      type: Bearer
      credentials_file: /etc/prometheus/token
    static_configs:
      - targets: [__MVP_HOST__]

  - job_name: vigia-host
    scheme: __MVP_SCHEME__
    metrics_path: /node-metrics
    authorization:
      type: Bearer
      credentials_file: /etc/prometheus/token
    static_configs:
      - targets: [__MVP_HOST__]
