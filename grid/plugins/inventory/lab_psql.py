"""
An inventory plugin pulling data from a PostgreSQL instance. The code is largely based
on the contents of https://www.redhat.com/sysadmin/ansible-plugin-inventory-files
"""

from typing import Any
import psycopg2, pathlib, json

# The imports below are the ones required for an Ansible plugin
from ansible.errors import AnsibleParserError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

# Documentation on the different fields can be found at:
#   https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_documenting.html#documentation-fields
DOCUMENTATION = r'''
    name: pcolladosoto.grid.lab_psql
    plugin_type: inventory
    short_description: Returns a dynamic host inventory from data in a PostgreSQL instance
    description: >
      Parses purposefully formatted machine information present on a PostgreSQL instance
      to then generate a dynamic inventory.
    options:
      plugin:
          description: >
            Name of the plugin. This allows us to automatically load this plugin
            through Ansible's builtin `auto` plugin.
          required: true
          type: string
          choices:
            - pcolladosoto.grid.lab_psql
      uri:
        description: PostgreSQL instance URI.
        required: true
        type: string
        default: postgresql://some.place:some.port
      domain:
        description: The domain to append to the hostnames enabling DNS lookups.
        required: true
        type: string
        default: .foo.fee.fii
      deny_list:
        description: >
          List of hostnames to avoid acting on. The domain name shouldn't be included.
        required: false
        type: list
        elements: string
        default: []
      debug:
        description: Dump raw inventories to `/tmp/lab-psql-inventory.json`
        required: false
        type: boolean
        default: false
'''

class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = 'pcolladosoto.grid.lab_psql'

    def __init__(self):
        super(InventoryModule, self).__init__()

        # The plugin name. It should be `lab_psql`
        self.plugin = None

        # The PostgreSQL database URI
        self.db_uri = None

    # We'll signal we can work with any YAML file. We could impose a tighter
    # restriction on what filenames we can work with. This, however, doesn't
    # need to be a completely accurate filter: it'll just make Ansible discard
    # unsuitable plugins faster.
    def verify_file(self, path: str):
        if super(InventoryModule, self).verify_file(path):
            return path.endswith('yaml') or path.endswith('yml')
        return False

    # Time to parse and generate our entire inventory! Note you can refer to [0] for
    # more information an the methods exposed by the `inventory` parameter. The `loader`
    # offers the possibility of reading in JSON and YAML files as well as extracting
    # secrets from Ansible Vaults. The `path` parameter is the path of the inventory
    # source (i.e. the input config file). Finally, `cache` determines whether a cache
    # should be leveraged. For general documentation please refer to [1].
    # References:
    #  0: https://github.com/ansible/ansible/blob/devel/lib/ansible/inventory/data.py
    #  1: https://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html
    def parse(self, inventory: Any, loader: Any, path: Any, cache: bool = True) -> Any:
        super(InventoryModule, self).parse(inventory, loader, path, cache)

        # Set configuration options and also load any cached information.
        self._read_config_data(path)
        try:
            self.plugin = self.get_option("plugin")

            domain = self.get_option("domain")

            denyList = self.get_option("deny_list")

            groups = getPostgresData(
                self.get_option("uri"), debug = self.get_option("debug")
            )

            for k, v in groups.items():
                groupName = k
                self.inventory.add_group(groupName)
                for hostname in v:
                    if hostname in denyList:
                        continue
                    fullHostname = f"{hostname}{domain}"
                    self.inventory.add_host(fullHostname)
                    self.inventory.add_child(groupName, fullHostname)

        except KeyError as kerr:
            raise AnsibleParserError(f"key error: {path}:{kerr}")
        except ConnectionError as cerr:
            raise AnsibleParserError(f"error contacting the PostgreSQL instance: {cerr}")
        except ValueError as verr:
            raise AnsibleParserError(f"error gathering data: {verr}")

def getPostgresData(uri: str, debug: bool = False) -> tuple[list, dict]:
    conn = psycopg2.connect(uri)
    cur = conn.cursor()

    groups = {}
    cur.execute("SELECT machines.hostname, groupname FROM machines " +
                "FULL OUTER JOIN machinesgroups ON machines.hostname = machinesgroups.hostname")
    for entry in cur.fetchall():
        if len(entry) != 2:
            continue
        groupName = entry[1] if entry[1] != None else "ungrouped"
        if groupName not in groups:
            groups[groupName] = []
        groups[groupName].append(entry[0])

    if len(groups) == 0:
        raise ValueError("no machines found...")

    if debug:
        pathlib.Path("/tmp/lab-psql-inventory.json").write_text(json.dumps(
            {"groups": groups}, indent = 4
        ))

    cur.close()
    conn.close()

    return groups
