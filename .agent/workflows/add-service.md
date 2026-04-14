# Workflow: Add a new service

## Decision: Manifest-driven or manual fragment?

Use **manifest-driven** if:
- Simple HTTP/TCP service
- Standard Traefik/Pangolin routing
- No custom middleware or health checks

Use **manual fragment** if:
- Complex routing rules
- Custom middleware chain
- TCP special cases
- Part of an existing concern group (arr-stack, auth, admin)

## Manifest-driven steps
1. Create `config/services/<group>/<service>.yml`
   - Follow `config/services/schema.json`
   - Set `exposure.local.mode: generated` and/or `exposure.public.mode: generated`
2. Run `python scripts/validate_sources.py` to check the manifest
3. Run `make syntax-check`
4. Run `make dry-run-<host>` (Ansible check mode)
5. Apply: `make play-<host>`

## Manual fragment steps
1. Edit the relevant fragment file in `config/fragments/traefik/` or `config/fragments/pangolin/`
2. Ensure the service is referenced from the appropriate playbook or host_vars
3. Run `make syntax-check`
4. Run `make dry-run-<host>`
5. Apply: `make play-<host>`

## Post-change
- Update `AGENTS.md` if this is a new category of service
- Run `make check`
- `make agent-log TARGET=add-service STATUS=done`
