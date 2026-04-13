# Home Assistant Monitoring Setup

This document describes how to configure Home Assistant to push metrics and logs to the monitoring stack.

## Architecture

```
┌─────────────────┐         ┌──────────────────┐
│  Home Assistant │         │  infra (monitor) │
│  192.168.1.70   │         │  192.168.1.102   │
│                 │         │                  │
│  • Prometheus   │───────▶ │  • Prometheus    │
│    /api/prometheus        │  • Loki          │
│    (port 8123)  │         │  • Grafana       │
│                 │         │                  │
│  • Promtail     │───────▶ │  (Visualization) │
│    (log shipper)│         │                  │
└─────────────────┘         └──────────────────┘
```

## Ansible Setup (Already Applied)

The following has been configured via Ansible:

1. **Prometheus scrape job** - Added to `prometheus.yml.j2` to scrape HA's `/api/prometheus` endpoint
2. **Promtail log shipper** - Deployed on HA to forward logs to Loki
3. **HA Playbook** - Created at `playbooks/vms/ha.yml`

## Manual Steps Required in Home Assistant

You must manually configure Home Assistant to enable Prometheus metrics export. Edit your `configuration.yaml`:

```yaml
# Enable Prometheus metrics export
prometheus:
  namespace: hass

# Optional: Enable InfluxDB for additional metrics
influxdb:
  host: 192.168.1.103
  port: 8181
  database: homeassistant
  username: homeassistant
  password: YOUR_PASSWORD
  max_retries: 3
  default_measurement: state
  include:
    domains:
      - sensor
      - binary_sensor
      - switch
      - light
      - climate
```

### Restart Home Assistant

After editing `configuration.yaml`, restart Home Assistant to apply changes:

1. Go to **Settings** → **System** → **Restart** (or use the UI restart button)
2. Or via command line: `ha core restart`

## Verification

### Check Prometheus is Scraping

1. Open Grafana: https://grafana.local.batistela.tech
2. Go to **Explore** → Select **Prometheus** datasource
3. Run query: `up{job="home-assistant"}`
4. Should return `1` (healthy)

### View Home Assistant Metrics

Example PromQL queries:

```promql
# Entity count
hass_sensor_state{}

# Climate temperature
hass_climate_temperature{}

# Binary sensor states
hass_binary_sensor_state{}
```

### Check Logs in Grafana

1. Go to **Explore** → Select **Loki** datasource
2. Run query: `{job="home-assistant"}`
3. Filter by level: `{job="home-assistant"} |= "ERROR"`

## Troubleshooting

### Prometheus Not Scraping

1. Verify HA is accessible: `curl http://192.168.1.70:8123/api/prometheus`
2. Check Prometheus targets: http://prometheus.local.batistela.tech/targets
3. Look for `home-assistant` job errors

### No Logs in Loki

1. Check promtail container on HA: `docker logs promtail`
2. Verify log file exists: `ls -la /var/log/home-assistant/`
3. Check Loki is receiving: Query `{job="home-assistant"}` in Grafana

### Access Denied

Home Assistant may require authentication for the Prometheus endpoint. If so, you have two options:

1. **Add long-lived access token** to Prometheus scrape config
2. **Whitelist Prometheus IP** in HA's `configuration.yaml`:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 192.168.1.102  # infra VM IP
```

## Deploy Changes

To apply the Ansible configuration:

```bash
cd ansible
. ../.venv/bin/activate
ansible-playbook playbooks/vms/ha.yml
```

To update the monitoring stack with the new HA scrape job:

```bash
ansible-playbook playbooks/vms/monitoring.yml
# Then manually restart the monitoring stack on infra:
# cd /opt/monitoring/docker_compose_files && docker compose restart
```
