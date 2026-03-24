"""
Ansible vars plugin that reads config/network.json and auto-sets
ansible_host for any inventory host whose name matches a key in
local_hosts or remote_hosts.

This eliminates IP duplication between network.json and hosts.yml.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
    name: network_json
    version_added: "1.0"
    short_description: Sets ansible_host from config/network.json
    description:
        - Reads config/network.json (relative to the repo root).
        - For each host in the inventory whose name appears in
          local_hosts or remote_hosts, sets ansible_host to the
          corresponding IP address.
        - Hosts that already define ansible_host explicitly in
          inventory are NOT overridden.
    options: {}
"""

import json
import os

from ansible.inventory.host import Host
from ansible.plugins.vars import BaseVarsPlugin


class VarsModule(BaseVarsPlugin):

    REQUIRES_ENABLED = True

    def get_vars(self, loader, path, entities, cache=True):
        super().get_vars(loader, path, entities)

        network = self._load_network()
        if network is None:
            return {}

        ip_map = {}
        ip_map.update(network.get("local_hosts", {}))
        ip_map.update(network.get("remote_hosts", {}))

        data = {}
        for entity in entities:
            if isinstance(entity, Host):
                hostname = entity.get_name()
                if hostname in ip_map:
                    data["ansible_host"] = ip_map[hostname]
        return data

    # ------------------------------------------------------------------
    def _load_network(self):
        """Locate and parse config/network.json from the repo root."""
        # Walk up from the inventory path to find the repo root.
        # The repo root contains the config/ directory.
        candidates = [
            os.path.join(os.getcwd(), "config", "network.json"),
            os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "config", "network.json"
            ),
        ]
        for candidate in candidates:
            real = os.path.realpath(candidate)
            if os.path.isfile(real):
                with open(real, "r") as fh:
                    return json.load(fh)
        return None
