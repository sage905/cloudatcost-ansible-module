#!/usr/bin/python
# Custom Module to manage server instances in a CloudAtCost
# (https://cloudatcost.com) Cloud
from collections import namedtuple, defaultdict, MutableMapping
import string

from ansible.module_utils.basic import *

DOCUMENTATION = '''
---
module: cac_server
author: "Patrick Toal (@sage905)"
short_description: Create, Delete, Start, Stop, Restart or Update an instance at CloudAtCost
description: >
    Manage servers at CloudAtCost via the API:
    U(https://github.com/cloudatcost/api)
    An API user and key must be acquired per the Instructions in the API docs.

options:
  state:
    description:
     - Indicate desired state of the resource
    choices: ['present', 'active', 'started', 'absent', 'deleted', 'stopped', 'restarted']
    default: present
  api_key:
    description:
     - CloudAtCost API key
    default: null
  api_user:
    description:
     - CloudAtCost API Username
    default: null
  label:
    aliases: name
    description:
     - Label to give the instance (alphanumeric only.  No spaces, dashes, underscored)
    default: null
    type: string
  fqdn:
    description:
     - Fully Qualified Domain-Name for Reverse DNS setup
    default: null
    type: string
  server_id:
    description:
     - Unique ID of a CloudAtCost server (optional)
    aliases: sid
    default: null
    type: integer
  cpus:
    description:
     - Number of vCPUs (1-16) to allocate to this instance
    default: 1
    type: integer
    choices: [1-16]
  ram:
    description:
     - Amount of RAM to allocate to this instance (MB)
    default: 1024
    type: integer
    choices: [512, 1024, 2048, 3072, 4096, 6144, 7168, 8192, 12288, 16384, 20480, 24576, 28672, 32768]
  storage:
    description:
     - Amount of Disk Storage to allocate to this instance (GB)
    default: 10
    choices: [10 - 1000]
  template_id:
    description:
     - Operating System to use for the instance (must be a #id or text description from /v1/listtemplates.php)
    # Default of 26 is for CentOS 7 x64
    default: 26
    type: integer
  runmode:
    description:
    - The `safe` runmode will automatically shutdown the server after 7 days.  `Normal` will not auto-shutdown the server
    default: safe
    type: string
    choices: ["safe", "normal"]
  wait:
    description:
     - wait for the instance to be powered on before returning
    default: "no"
    choices: [ "yes", "no" ]
  wait_timeout:
    description:
     - how long before wait gives up, in seconds
    # 15min default.  When CloudAtCost is having problems, server provisioning can take DAYS.
    default: 900
requirements:
    - "python >= 2.6"
    - "cacpy >= 0.5.3"
    - "pycurl"
notes:
  - If I(server_id) is specified, it must match an existing server id.

  - If I(server_id) is not specified, the first server in the account that
    exactly matches I(label) is used.

  - If C(state=present), the server will either be created or updated.

  - Only the following attributes can be updated after creation:
      - I(label) (Must provide server_id to change)
      - I(fqdn)
      - I(run_mode)
      - I(state)

  - If C(state in ('absent', 'deleted')), the server will be destroyed!  Use
    with caution.

  - CAC_API_KEY and CAC_API_USER environment variables can be used instead
    of I(api_key) and I(api_user)
'''

EXAMPLES = '''
---
# Create a server
- local_action:
     module: cac_server
     api_user: bob@smith.com
     api_key: 'longStringFromCACApi'
     label: cloudatcost-test1
     cpus: 1
     ram: 1024
     storage: 10
     template_id: 26
     runmode: safe
     wait: yes
     wait_timeout: 3600
     state: present

# Ensure a running server (create if missing)
- local_action:
     module: cac_server
     api_user: bob@smith.com
     api_key: 'longStringFromCaCAPI'
     label: cloudatcost-test1
     cpus: 1
     ram: 1024
     storage: 10
     template_id: 26
     runmode: safe
     wait: yes
     wait_timeout: 3600
     state: present

# Delete a server
- local_action:
     module: cac_server
     api_user: bob@smith.com
     api_key: 'longStringFromCaCAPI'
     sid: 12345678
     label: cloudatcost-test1
     state: absent

# Stop a server
- local_action:
     module: cac_server
     api_user: bob@smith.com
     api_key: 'longStringFromCaCAPI'
     label: cloudatcost-test1
     state: stopped

# Reboot a server
- local_action:
     module: cac_server
     api_user: bob@smith.com
     api_key: 'longStringFromCaCAPI'
     label: cloudatcost-test1
     state: restarted

'''

ANSIBLE_METADATA = {'status': ['preview'],
                    'supported_by': 'community',
                    'version': '1.0'}
try:
    import pycurl

    HAS_PYCURL = True
except ImportError:
    HAS_PYCURL = False

try:
    from cacpy import CACPy

    HAS_CAC = True
except ImportError:
    HAS_CAC = False


class CacApiError(Exception):
    """
    Raised when something went wrong during a call to CloudAtCost's API
    """


def get_server(api, server_id=None, label=None, server_name=None):
    """
    Use the CAC API to search for the provided server_id, servername, or label
    and return the first match found as a CACServer instance.

    Returns None if no server found.
    """
    assert server_id is not None or label is not None or server_name is not None

    try:
        server = next(
            server for server in api.get_server_info().get('data') if
            server['sid'] == str(server_id) or server['servername'] == server_name or server['label'] == label)
    except StopIteration:
        return None

    return CACServer(api, server)


def check_ok(response):
    """ Verify that the API Call has an 'ok' status. """
    if response['status'] != 'ok':
        raise CacApiError('CloudAtCost API call failed. Status: %s' % response)
    return True


class CACTemplate(namedtuple('CACTemplate', ['desc', 'template_id'])):
    """ Represent a CloudAtCost OS Template """

    # Cache templates as they aren't likely to change during execution.
    templates = {}

    @classmethod
    def get_template(cls, api, lookup=None):
        """Return a CACTemplate after querying the Cloudatcost API for a list of templates for a match.

        Required Arguments:
        lookup - Description or id to be matched

        Raises:
        LookupError if desc or template_id can't be found
        ValueError if no lookup parameters are provided
        """

        assert lookup is not None, "Must provide an id or description to lookup."

        if isinstance(lookup, cls):
            lookup = lookup.template_id
        if isinstance(lookup, int):
            lookup = str(lookup)
        if not cls.templates:
            cls.templates = api.get_template_info()['data']
        try:
            template = next(t for t in cls.templates
                            if t.get('ce_id') == lookup or t.get('name') == lookup)
        except StopIteration:
            raise LookupError("Template with ID or description: " + lookup + " was not found")
        return cls(template.get('name'), template.get('ce_id'))


def _poller(poll_func, waittime=300, interval=1):
    for t in range(1, waittime, interval):
        time.sleep(interval)
        result = poll_func()
        if result:
            return result


class CACServer(MutableMapping):
    """Represent a server instance at cloudatost.  Perform checking and validation
    on attribute modification, to ensure valid state transitions before committing
    to CloudAtCost API.
    """

    def _set_label(self, value):
        check_ok(self.api.rename_server(new_name=value, server_id=self._current_state['sid']))

    def _set_rdns(self, value):
        check_ok(self.api.change_hostname(new_hostname=value, server_id=self._current_state['sid']))

    def _set_mode(self, value):
        check_ok(self.api.set_run_mode(run_mode=value, server_id=self._current_state['sid']))

    def _set_status(self, value):
        if value in ('Powered On', 'on'):
            check_ok(self.api.power_on_server(server_id=self._current_state['sid']))
        elif value in ('Powered Off', 'off'):
            check_ok(self.api.power_off_server(server_id=self._current_state['sid']))
        elif value in ('Restarted', 'restart'):
            check_ok(self.api.reset_server(server_id=self._current_state['sid']))
        elif value in ('Deleted', 'delete'):
            check_ok(self.api.server_delete(server_id=self['sid']))

    _modify_functions = {'label': _set_label, 'rdns': _set_rdns, 'status': _set_status, 'mode': _set_mode}

    def __init__(self, api, server):
        self.api = api
        self._current_state = dict(server)
        self._changed_attrs = dict()

        if server['template'] is not None:
            self._current_state['template'] = CACTemplate.get_template(api, server['template'])

    def __delitem__(self, key):
        self._changed_attrs.__delitem__(key)

    def __len__(self):
        return len(self.__getstate__())

    def __iter__(self):
        return self.__getstate__().__iter__()

    def __getitem__(self, item):
        """
        Get the modified value of the server attribute, or the existing value if not modified.

        :raises AttributeError if attribute not found
        """
        return self._changed_attrs[item] if item in self._changed_attrs else self._current_state[item]

    def __setitem__(self, key, value):
        if key in self.__class__._modify_functions:
            if self._current_state[key] != value:
                self._changed_attrs[key] = value
        else:
            raise KeyError(self.__class__.__name__ + " does not have a modifiable item: " + key)

    def __repr__(self):
        return ('{cls.__name__}(api_account={self.api.email}, sid={self[sid]}, '
                'label={label})').format(
            cls=type(self), self=self, label=self.get('label'))

    def __getstate__(self):
        return self._current_state.copy()

    def check(self):
        return bool(self._changed_attrs)

    def commit(self):
        # Only commit existing records.
        if self['sid'] is None:
            raise AttributeError("Server commit failed. sid property not set on CACServer object.")

        if get_server(self.api, server_id=self['sid']) is None:
            raise LookupError("Unable to find server with sid: " + str(self['sid']))

        if len(self._changed_attrs) > 0:
            for (item, value) in list(self._changed_attrs.items()):
                self._modify_functions[item](self, value)

            return get_server(self.api, server_id=self['sid'])
        else:
            return self

    @staticmethod
    def check_server_status(api, servername, status):
        def f():
            server = get_server(api, server_name=servername)
            if server and server['status'] == status:
                return server

        return f

    @staticmethod
    def build_server(api, cpu, ram, disk, template, label, wait=False, wait_timeout=300):
        """
        Build a server with the provided parameters

        :param label: Name to give the server for the Panel
        :param api: CACPy instance
        :param cpu: # of vCPU's to allocate
        :param ram: RAM to allocate (MB)
        :param disk: Disk to allocate (GB)
        :param template: OS Template to use (id, or string)
        :param wait: Wait for server build to complete
        :param wait_timeout: Seconds to wait for build to complete
        :return: ( request.Response, CACServer ) response from CAC server, CACServer object if build completed
        :raises CacApiError on any error
        """

        _required_build_params = ('cpu', 'ram', 'disk', 'template', 'label')

        assert isinstance(api, CACPy)

        missing = [param for param in _required_build_params if not locals()[param]]

        if missing:
            raise AttributeError("Server Build missing arguments: " + " ".join(missing))

        assert ram in [512, 1024, 2048, 3072, 4096, 6144, 7168, 8192, 12288, 16384, 20480, 24576, 28672, 32768]
        assert cpu in range(1, 16)

        os_template = CACTemplate.get_template(api, template)

        # The CloudAtCost Build timing can be unpredictable, but optimally works like:
        # 1. call API to build.
        # 2. JSON response includes result: successful, a taskid (which is useless since the listtasks API
        # doesn't work), and a servername.
        # 3. Once the task is queued, a new server will show up in the listservers call with the servername and a
        # status of "Installing".  This could take minutes, hours, or days.
        # 4. The server will be built, and at that time, the status will change to "Powered On".  The server then takes
        # some time to boot.

        # Queue the build
        server = None

        response = api.server_build(cpu, ram, disk, os_template.template_id)
        if response.get('result') == 'successful':
            # Optionally wait for the server to be Powered On.  Poll every 10s.
            if wait:
                server = _poller(CACServer.check_server_status(api, response.get('servername'), 'Powered On'),
                                 wait_timeout, 10)
                # Set the label, so we can find it again in the future
                if server:
                    server['label'] = label
                    server.commit()
            return server, response
        else:
            raise CacApiError(string.Formatter().vformat("Server Build Failed. Status: {status} "
                                                         "#{error}, \"{error_description}\" ",
                                                         (), defaultdict(str, **response)))


def get_api(api_user, api_key):
    try:
        if not api_key:
            api_key = os.environ['CAC_API_KEY']
        if not api_user:
            api_user = os.environ['CAC_API_USER']
    except KeyError:
        raise CacApiError("Unable to get %s for CloudAtCost connection" % (
            "api key from parameter or CAC_API_KEY environment variable" if not api_key else
            "api user from paramater or CAC_API_USER environment variable"))

    api = CACPy(api_user, api_key)

    check_ok(api.get_resources())
    return api


def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(default='present',
                       choices=['active', 'present', 'started',
                                'deleted', 'absent', 'stopped',
                                'restarted']),
            api_key=dict(type='str'),
            api_user=dict(type='str'),
            label=dict(type='str', aliases=['name']),
            fqdn=dict(type='str'),
            cpus=dict(type='int'),
            ram=dict(type='int'),
            storage=dict(type='int'),
            template=dict(type='int'),
            runmode=dict(type='str'),
            server_id=dict(type='int', aliases=['sid']),
            wait=dict(type='bool', default=False),
            wait_timeout=dict(default=300),
        ),
        supports_check_mode=True
    )

    if not HAS_PYCURL:
        module.fail_json(msg='pycurl required for this module')
    if not HAS_CAC:
        module.fail_json(msg='CACPy required for this module')

    changed = False
    response = None

    state = module.params.get('state')
    label = module.params.get('label')
    rdns = module.params.get('fqdn')
    cpus = module.params.get('cpus')
    runmode = module.params.get('runmode')
    ram = module.params.get('ram')
    storage = module.params.get('storage')
    template = module.params.get('template')
    server_id = module.params.get('server_id')
    wait = module.params.get('wait')
    wait_timeout = int(module.params.get('wait_timeout'))

    try:
        api = get_api(module.params.get('api_user'), module.params.get('api_key'))
        server = get_server(api, server_id=server_id, label=label)

        if state in ('absent', 'deleted'):
            if server:
                server['status'] = "Deleted"
        else:
            # For any other state, we need a server object.
            if not server:
                server, response = CACServer.build_server(api, cpus, ram, storage, template, label, wait, wait_timeout)
                if response['result'] == "successful":
                    changed = True
                else:
                    module.fail_json(msg="Build initiated but no server was returned.  Check CloudAtCost Panel.  You "
                                         "will need to manually set the server label in the panel before trying again."
                                         "Response: %s" % response)
            if not server:
                # We didn't wait for it to build, or it timed out
                module.exit_json(changed=True, server=None, response = response)

            if state in ('present', 'active', 'started'):
                server['status'] = 'Powered On'
            elif state == 'stopped':
                server['status'] = 'Powered Off'
            elif state == 'restarted':
                server['status'] = 'Restarted'

            if label:
                server['label'] = label
            if rdns:
                server['rdns'] = rdns
            if runmode:
                server['mode'] = runmode

        if module.check_mode:
            changed = server.check()
            server = None
        else:
            updated = server.commit()
            if updated != server:
                changed = True
                server = updated

        module.exit_json(changed=changed, server=server, response=response)

    except Exception as e:
        module.fail_json(msg='%s' % e.message)


if __name__ == '__main__':
    main()
