"""
An inventory plugin pulling data from a MongoDB instance. The code is largely based
on the contents of https://www.redhat.com/sysadmin/ansible-plugin-inventory-files
"""

from typing import Any
import pymongo, pathlib

from bson import json_util

# The imports below are the ones required for an Ansible plugin
from ansible.errors import AnsibleParserError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

DOCUMENTATION = r'''
    name: pcolladosoto.grid.lab_db
    plugin_type: inventory
    short_description: Returns a dynamic host inventory from data in a MongoDB instance
    description: >
      Parses purposefully formatted machine information present on a MongoDB instance
      to then generate a dynamic inventory.
    options:
      plugin:
          description:
            - Name of the plugin. This allows us to automatically load this plugin through
            - Ansible's builtin `auto` plugin.
          required: True
          type: string
          choices:
            - lab_db
      uri:
        description: MongoDB instance URI.
        required: True
        type: string
        default: mongodb://some.place:some.port
      domain:
        description: The domain to append to the hostnames enabling DNS lookups.
        required: True
        type: string
        default: .foo.fee.fii
      db:
        description: MongoDB database containing the data to build the inventory with.
        required: True
        type: string
        default: some-db
      machine_collection:
        description: MongoDB collection containing the data describing the physical machines.
        required: True
        type: string
        default: machine-collection
      management_collection:
        description: MongoDB collection containing the different management groups.
        required: True
        type: string
        default: group-collection
'''

class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):

    NAME = 'pcolladosoto.grid.lab_db'

    def __init__(self):
        super(InventoryModule, self).__init__()

        # The plugin name. It should be `lab_db`
        self.plugin = None

        # The MongoDB database URI
        self.db_uri = None

        # The MongoDB collection
        self.collection = None

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

            groupsData, machineData = getMongoData(
                self.get_option("uri"), self.get_option("db"),
                self.get_option("machine_collection"),
                self.get_option("management_collection")
            )

            for machine in machineData:
                if not machine.get("active", True):
                    for i, group in enumerate(groupsData):
                        
                        groupsData[i]["members"] = list(filter(
                            lambda item: item["hostname"] != machine["hostname"], group["members"]
                        ))
                    continue
                hostname = f"{machine['hostname']}{domain}"
                self.inventory.add_host(hostname)
                for k, v in machine.items():
                    if k != "hostname":
                        self.inventory.set_variable(hostname, k, v)

            for group in groupsData:
                groupName = group["name"]
                self.inventory.add_group(groupName)
                for groupMember in group["members"]:
                    self.inventory.add_child(groupName, f"{groupMember['hostname']}{domain}")

        except KeyError as kerr:
            raise AnsibleParserError(f"missing required option on the configuration file: {path}:{kerr}")
        except ConnectionError as cerr:
            raise AnsibleParserError(f"error contacting the MongoDB instance: {cerr}")
        except ValueError as verr:
            raise AnsibleParserError(f"error gathering data: {verr}")
    
def getMongoData(uri: str, db: str, machineCollectionName: str, groupsCollectionName: str, debug: bool = False) -> tuple[list, list]:
    mongoClient = pymongo.MongoClient(uri, serverSelectionTimeoutMS = 2000)
    try:
        mongoClient.server_info()
    except pymongo.errors.ServerSelectionTimeoutError:
        raise ConnectionError("Couldn't connect to the MongoDB instance. Is the URI correct?")
    machineCollection = mongoClient[db][machineCollectionName]
    groupsCollection  = mongoClient[db][groupsCollectionName]

    groups = list(groupsCollection.find({}, {'_id': False}))
    if len(groups) == 0:
        raise ValueError("the group collection is empty")
    
    machines = list(machineCollection.find({}, {'_id': False}))
    if len(machines) == 0:
        raise ValueError("the machine collection is empty")

    if debug:
        pathlib.Path("/tmp/lab-db-inventory.json").write_text(json_util.dumps(
            {"groups": groups, "machines": machines}, indent = 4
        ))

    return groups, machines
