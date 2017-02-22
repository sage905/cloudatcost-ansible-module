#!/usr/bin/env python
"""
CloudAtCost external inventory script. Automatically finds hosts and
returns them under the host group 'cloudatcost'

Some code borrowed from linode.py inventory script by Dan Slimmon

"""

import os.path
# import re
import sys
import argparse
# from time import time
from cacpy import CACPy
# import ConfigParser


try:
    import json
except ImportError:
    import simplejson as json

_group = 'cloudatcost'  # a default group
_prepend = 'cloud_'  # Prepend all CloudAtCost data, to avoid conflicts


class CloudAtCostInventory(object):
    def __init__(self):
        """Main execution path."""
        self.api_key = None
        self.api_user = None

        self.args = self.parse_cli_args()
        self.inventory = {}

        # CloudAtCost API Object
        self.setupAPI()

        self.update_inventory()

        # Data to print
        if self.args.host:
            data_to_print = self.get_host_info(self.args.host)
        elif self.args.list:
            # Display list of nodes for inventory
            data_to_print = {
                _group: [server['label'] for server
                         in self.inventory if server['label']],
                '_meta': {
                    'hostvars': dict((server['label'],
                                      self.get_host_info(label=server['label']))
                                     for server in self.inventory)
                }
            }
        else:
            data_to_print = "Error: Invalid options"

        print(json_format_dict(data_to_print, True))

    def update_inventory(self):
        """Makes a CloudAtCost API call to get the list of servers."""
        res = self.api.get_server_info()
        if res['status'] == 'ok':
            self.inventory = res['data']
        else:
            print("Looks like CloudAtCost's API is down:")
            print("")
            print(res)
            sys.exit(1)

    def get_server(self, server_id=None, label=None):
        """Gets details about a specific server."""
        for server in self.inventory:
            if (server_id and server['id'] == server_id) or \
                    (label and server['label'] == label):
                return server
        return None

    def get_host_info(self, label):
        """Get variables about a specific host."""

        server = self.get_server(label=label)
        if not server:
            return json_format_dict({}, True)

        retval = {}
        for (key, value) in server.iteritems():
            retval["{}{}".format(_prepend, key)] = value

        # Set the SSH host information, so these inventory items can be used if
        # their labels aren't FQDNs
        retval['ansible_ssh_host'] = server["ip"]
        retval['ansible_host'] = server["ip"]

        return retval

    def setupAPI(self):

        # Setup the api_key
        if not self.api_key:
            try:
                self.api_key = os.environ['CAC_API_KEY']
            except KeyError, e:
                print "Please provide API Key."
                sys.exit(1)

        # Setup the api_user
        if not self.api_user:
            try:
                self.api_user = os.environ['CAC_API_USER']
            except KeyError, e:
                print "Please provide API User."
                sys.exit(1)

        # setup the auth
        try:
            self.api = CACPy(self.api_user, self.api_key)
            self.api.get_resources()
        except Exception, e:
            print "Failed to contact CloudAtCost API."
            print ""
            print e
            sys.exit(1)

    @staticmethod
    def parse_cli_args():
        """Command line argument processing"""
        parser = argparse.ArgumentParser(
                description='Produce an Ansible Inventory file based on CloudAtCost')
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--list', action='store_true', default=True,
                           help='List servers (default: True)')
        group.add_argument('--host', action='store',
                           help='Get all the variables about a specific server')

        parser.add_argument('--refresh-cache', action='store_true',
                            default=False,
                            help='Force refresh of cache by making API requests to CloudAtCost (default: False - use cache files)')
        return parser.parse_args()


def json_format_dict(data, pretty=False):
    """Converts a dict to a JSON object and dumps it as a formatted string.
    :param data: string
    """
    if pretty:
        return json.dumps(data, sort_keys=True, indent=2)
    else:
        return json.dumps(data)


CloudAtCostInventory()
