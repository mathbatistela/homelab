# Traefik Role

This role manages Traefik reverse proxy configuration.

## Service Templates

Three templates are available for common service patterns:

### 1. simple-http
Basic HTTP service with HTTPS and TLS certificate.

```yaml
traefik_conf:
  template: simple-http
  service_name: myapp
  service_host: myapp.local.batistela.tech
  service_backend_url: http://192.168.1.107:8080
```

### 2. with-middleware
HTTP service with custom middlewares (auth, redirects, headers).

```yaml
traefik_conf:
  template: with-middleware
  service_name: myapp
  service_host: myapp.local.batistela.tech
  service_backend_url: http://192.168.1.107:8080
  service_middlewares:
    - name: auth
      type: basicAuth
      users: "admin:$apr1$..."
```

### 3. tcp-service
For TCP/UDP services (databases, game servers).

```yaml
traefik_conf:
  template: tcp-service
  service_name: minecraft
  service_entrypoint: minecraft
  service_backend_address: 192.168.1.105:25565
```

## Inline Content Method

For complex custom configurations:

```yaml
traefik_conf:
  filename: custom-service.yml
  content: |
    http:
      routers:
        custom:
          rule: "Host(`custom.local.batistela.tech`)"
          # ... full custom config
```

## Authelia Integration

Authelia middleware is configured in `infra.yml` and available globally as `authelia@file`.

### Protecting a Service with Authelia

To protect any service with Authelia authentication, add the middleware to your service configuration:

**Method 1: Using inline content**
```yaml
traefik_conf:
  filename: protected-app.yml
  content: |
    http:
      routers:
        protected-app:
          rule: "Host(`app.{{ traefik_local_domain }}`)"
          entryPoints:
            - https
          service: protected-app-service
          middlewares:
            - authelia@file  # Add this line
          tls:
            certResolver: {{ traefik_cert_resolver_name }}

      services:
        protected-app-service:
          loadBalancer:
            servers:
              - url: "http://192.168.1.107:8080"
```

**Method 2: Using with-middleware template**
```yaml
traefik_conf:
  template: with-middleware
  service_name: protected-app
  service_host: app.local.batistela.tech
  service_backend_url: http://192.168.1.107:8080
  service_middlewares:
    - name: authelia
      type: forwardAuth  # Reference to global authelia middleware
```

### Authelia Access
- **Portal**: https://auth.local.batistela.tech
- **Backend IP**: 192.168.1.109:9091
- **ForwardAuth Endpoint**: http://192.168.1.109:9091/api/authz/forward-auth

### How It Works

1. User accesses protected service (e.g., `https://app.local.batistela.tech`)
2. Traefik forwards auth request to Authelia via ForwardAuth middleware
3. If not authenticated, user is redirected to `https://auth.local.batistela.tech`
4. After successful authentication, user is redirected back to original service
5. Authelia passes user info via headers: `Remote-User`, `Remote-Groups`, `Remote-Email`, `Remote-Name`

### Example: Protect Portainer

```yaml
- name: Protect Portainer with Authelia
  include_role:
    name: traefik
    tasks_from: configure_service
  vars:
    traefik_conf:
      filename: portainer.yml
      content: |
        http:
          routers:
            portainer:
              rule: "Host(`portainer.{{ traefik_local_domain }}`)"
              entryPoints:
                - https
              service: portainer-service
              middlewares:
                - authelia@file
              tls:
                certResolver: {{ traefik_cert_resolver_name }}

          services:
            portainer-service:
              loadBalancer:
                servers:
                  - url: "http://192.168.1.107:9443"
```
