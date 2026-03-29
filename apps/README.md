# Apps

Custom applications built and deployed within the homelab. Each app is self-contained with its own `app.yml` config, Dockerfile(s), and source code.

## Structure

```
apps/
├── README.md           # This file
├── .template/          # Scaffold template for new apps
├── hello-world/        # Example: single-service app
└── adhd-board/         # Example: multi-service app (frontend + API)
```

## App Config (`app.yml`)

Every app has an `app.yml` that defines:

- **Metadata** — name, description, version
- **Services** — one or more Docker services with ports and image names
- **Homelab integration** — which VM hosts the app, Traefik/Pangolin exposure, resource limits

See `.template/app.yml` for a fully commented example.

## Single-Service vs Multi-Service

**Single-service** (`hello-world/`): One Dockerfile at the app root, no `services/` subdirectory.

```
hello-world/
├── app.yml
├── Dockerfile
└── src/
```

**Multi-service** (`adhd-board/`): Multiple services under `services/<name>/`, each with their own Dockerfile.

```
adhd-board/
├── app.yml
├── docker-compose.yml   # Local dev compose
└── services/
    ├── frontend/
    │   ├── Dockerfile
    │   └── src/
    └── api/
        ├── Dockerfile
        └── src/
```

## CLI

Use `scripts/homelab-apps` (or `make apps-<command>`) to manage apps:

```bash
# List all apps
./scripts/homelab-apps list

# Validate all app.yml configs
./scripts/homelab-apps validate

# Create a new app interactively
./scripts/homelab-apps create my-app

# Build an app locally
./scripts/homelab-apps build hello-world

# Build a specific service of a multi-service app
./scripts/homelab-apps build adhd-board --service frontend
```

Or via Make:

```bash
make apps-list
make apps-validate
make apps-build APP=hello-world
```

## CI/CD

Apps are built and pushed to GHCR via `.github/workflows/apps.yml`:

- **Path-based triggering** — only builds apps whose files changed
- **Matrix strategy** — each app builds in parallel
- **`workflow_dispatch`** — manual trigger with optional app filter
- **GHCR** — images pushed to `ghcr.io/<owner>/<app>[-<service>]`

Image tags:
- `latest` on push to `main`
- `sha-<commit>` on every push
- `pr-<number>` on pull requests

## Adding a New App

1. Copy the template:
   ```bash
   ./scripts/homelab-apps create my-app
   ```
   Or manually:
   ```bash
   cp -r apps/.template apps/my-app
   ```

2. Edit `apps/my-app/app.yml` with your app's details.

3. Write your Dockerfile and source code.

4. Validate:
   ```bash
   ./scripts/homelab-apps validate
   ```

5. Commit and push — CI will build the image automatically.

## Homelab Deployment

After CI builds and pushes the image, deploy it via the relevant Ansible playbook:

```bash
# Deploy to the tools VM (most apps land here)
make play-tools
```

The `app.yml` `homelab.host` field indicates which VM runs the app. The exposure config (`homelab.exposure`) drives Traefik/Pangolin routing generation.
