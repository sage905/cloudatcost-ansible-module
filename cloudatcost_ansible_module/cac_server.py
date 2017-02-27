#!/usr/bin/python
# Custom Module to manage server instances in a CloudAtCost
# (https://cloudatcost.com) Cloud
# This module was originally based on the Ansible Linode module
from collections import namedtuple, defaultdict
import string
from ansible.module_utils.basic import *

DOCUMENTATION = '''
---
module: cloudatcost
author: "Patrick Toal (@ptoal)"
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
    choices: [1024, 2048, 3072, 4096, 6144, 7168, 8192, 12288, 16384, 20480, 24576, 28672, 32768]
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
     - wait for the instance to be in state 'running' before returning
    default: "yes"
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
     module: cloudatcost
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
     module: cloudatcost
     api_user: bob@smith.com
     api_key: 'longStringFromLinodeApi'
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
     module: cloudatcost
     api_user: bob@smith.com
     api_key: 'longStringFromLinodeApi'
     sid: 12345678
     label: cloudatcost-test1
     state: absent

# Stop a server
- local_action:
     module: cloudatcost
     api_user: bob@smith.com
     api_key: 'longStringFromLinodeApi'
     label: cloudatcost-test1
     state: stopped

# Reboot a server
- local_action:
     module: cloudatcost
     api_user: bob@smith.com
     api_key: 'longStringFromLinodeApi'
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


class CacApiError(StandardError):
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

    server['api'] = api
    return CACServer(api, server)


def check_ok(response):
    if response['status'] != 'ok':
        raise CacApiError('CloudAtCost API call failed. Status: ' + response['status'])


class CACTemplate(namedtuple('CACTemplate', ['desc', 'template_id'])):
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
        templates = api.get_template_info()['data']
        try:
            template = next(t for t in templates
                            if t.get('ce_id') == lookup or t.get('name') == lookup)
        except StopIteration:
            raise LookupError("Template with ID or description: " + lookup + " was not found")
        return cls(template.get('name'), template.get('ce_id'))


class CACServer(object):
    """Represent a server instance at cloudatost.  Perform checking and validation
    on attribute modification, to ensure valid state transitions before committing
    to CloudAtCost API.
    """

    @staticmethod
    def build_server(api, cpu, ram, disk, template):
        """
        Build a server with the provided parameters

        :param api: CACPy instance
        :param cpu: # of vCPU's to allocate
        :param ram: RAM to allocate (MB)
        :param disk: Disk to allocate (GB)
        :param template: OS Template to use (id, or string)
        :return:
        """

        _required_build_params = ('cpu', 'ram', 'disk', 'template')

        assert isinstance(api, CACPy)

        missing = [param for param in _required_build_params if not locals()[param]]

        if missing: raise AttributeError("Server Build missing arguments: " + " ".join(missing))

        os_template = CACTemplate.get_template(api, template)
        response = api.server_build(cpu, ram, disk, os_template)

        if response.get('result') == 'successful':
            return response
        else:
            raise CacApiError(string.Formatter().vformat("Server Build Failed. Status: {status} "
                                                      "#{error}, \"{error_description}\" ",
                                                         (), defaultdict(str, **response)))

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

    _modify_functions = {'label': _set_label, 'rdns': _set_rdns, 'status': _set_status, 'mode': _set_mode}

    def __getattr__(self, item):
        """
        Get the modified value of the server attribute, or the existing value if not modified.

        :raises AttributeError if attribute not found
        """
        val = self._updated_state.get(item, self._current_state.get(item, None))
        if val is not None:
            return val
        else:
            raise AttributeError(self.__class__.__name__ + ' has no attribute: ' + item)

    def __setattr__(self, key, value):
        if key in self.__class__._modify_functions:
            self._updated_state[key] = value
        else:
            raise AttributeError(self.__class__.__name__ + " does not have a modifiable attribute: " + key)

    def __init__(self, api, server):
        object.__setattr__(self, 'api', api)
        object.__setattr__(self, '_current_state', dict(server))  # Copy dictionary
        object.__setattr__(self, '_updated_state', dict())

        if server['template'] is not None:
            self._current_state['template'] = CACTemplate(api, server['template'])

    def __repr__(self):
        return ('{cls.__name__}(api_account={self.api.email}, sid={self.sid}, '
                'label={label})').format(
            cls=type(self), self=self, label=getattr(self, 'label', None))

    def delete(self):
        check_ok(self.api.server_delete(server_id=self.sid))

    def commit(self):
        # Only commit existing records.
        if self.sid is None:
            raise AttributeError("Server commit failed. sid property not set on CACServer object.")

        if get_server(self.api, server_id=self.sid) is None:
            raise LookupError("Unable to find server with sid: " + str(self.sid))

        for (item, value) in self._updated_state.items():
            self._modify_functions[item](self, value)

        return get_server(self.api, server_id=self.sid)


# def cac_servers(module, api, state, label, cpus, ram, storage, template_id,
#                 server_id, runmode, fqdn,
#                 wait, wait_timeout):
#
#
#         # Any create step triggers a job that need to be waited for.
#             # Create server entity
#             try:
#                 # Check os template
#                 for template in api.get_template_info()['data']:
#                     if template['ce_id'] == str(template_id):
#                         template_detail = template['name']
#                         break
#
#                 if not template_detail:
#                     module.fail_json(
#                         msg='OS with id #%d is not an available template' %
#                             template_id)
#
#                 res = api.server_build(cpus, ram, storage, template_id)
#
#                 if res['status'] != 'ok' or res['result'] != 'successful':
#                     module.fail_json(msg="Server Creation Failed: " +
#                                          res['error_description'])
#                 new_server = {}
#                 for i in range(1, wait_timeout / 5):
#                     servers = api.get_server_info()
#                     for server in servers['data']:
#                         if server['servername'] == res['servername']:
#                             new_server = server
#                     if new_server != {}:
#                         break
#                     time.sleep(5)
#                 if new_server == {}:
#                     module.fail_json(msg="Server Build Timed out: " +
#                                          res['error_description'])
#
#                 server_id = new_server['id']
#                 jobs.append(res['taskid'])
#
#                 # Update Label to match label
#                 api.rename_server(server_id, label)
#
#                 action = "create"
#                 changed = True
#
#             except Exception, e:
#                 module.fail_json(msg='Exception during create: ' + e.message)
#
#         # Start / Ensure server is running
#         # Refresh server state
#         server = api.get_server(server_id=server_id)
#
#         # Ensure existing servers are up and running, boot if necessary
#         if server.status != 'Powered On':
#             res = api.power_on_server(server['id'])
#             jobs.append(res['taskid'])
#             changed = True
#
#         # wait here until the instances are up
#         wait_timeout = time.time() + wait_timeout
#         while wait and wait_timeout > time.time():
#             # refresh the server details
#             server = api.get_server(server_id=server['id'])
#             # status:
#             #  "Installing": OS being installed
#             #  "Powered On": System Running
#             #  "Powered Off": System Shut Down
#             #  "Pending On": System Powering Up/Down
#             if server['status'] in ("Powered On", "Failed"):
#                 break
#             time.sleep(5)
#         if wait and wait_timeout <= time.time():
#             # waiting took too long
#             module.fail_json(msg='Timeout waiting on %s (id: %s)' %
#                                  (server['label'], server['id']))
#         # Get a fresh copy of the server details
#         server = api.get_server(server_id=server['id'])
#         if server['status'] != "Powered On":
#             module.fail_json(msg='%s (id: %s) failed to boot' %
#                                  (server['label'], server['is']))
#         # From now on we know the task is a success
#         result = server
#
#     elif state in ('stopped'):
#         for arg in ('label', 'server_id'):
#             if not eval(arg):
#                 module.fail_json(msg='%s is required for active state' % arg)
#
#         if not server:
#             module.fail_json(msg='Server %s (id: %s) not found' %
#                                  (label, server_id))
#
#         if server['status'] == "Powered On":
#             try:
#                 api.power_off_server(server_id)
#             except Exception, e:
#                 module.fail_json(msg='%s' % e)
#             changed = True
#
#     elif state in ('restarted'):
#         for arg in ('label', 'server_id'):
#             if not eval(arg):
#                 module.fail_json(msg='%s is required for active state' % arg)
#
#         if not server:
#             module.fail_json(
#                 msg='Server %s (id: %s) not found' % (label, server_id))
#
#         try:
#             res = api.reset_server(server_id)
#         except Exception, e:
#             module.fail_json(msg='%s' % e)
#         changed = True
#
#     elif server and state in ('absent', 'deleted'):
#         try:
#             res = api.server_delete(server_id)
#             if res['status'] == 'ok':
#                 action = "destroy"
#                 server = None
#         except Exception, e:
#             module.fail_json(msg='%s' % e)
#         changed = True
#
#     if state not in ('absent', 'deleted'):
#         # Ensure Server Runmode is correct
#         if server['mode'].lower() != runmode:
#             res = api.set_run_mode(server_id, runmode)
#             if res['status'] == 'ok':
#                 changed = True
#             else:
#                 module.fail_json(msg='Unable to change runmode to: %s' %
#                                      runmode)
#         # Ensure Server Reverse DNS is correct
#         if fqdn and server['rdns'].lower() != fqdn:
#             res = api.change_hostname(server_id, fqdn)
#             if res['status'] == 'ok':
#                 changed = True
#             else:
#                 module.fail_json(msg='Unable to change Reverse DNS to: %s' %
#                                      runmode)
#
#     module.exit_json(changed=changed, jobs=jobs, server=result, action=action)

def get_api(api_user, api_key):
    try:
        if not api_key:
            api_key = os.environ['CAC_API_KEY']
        if not api_user:
            api_user = os.environ['CAC_API_USER']
    except KeyError:
        raise CacApiError("Unable to get {} for CloudAtCost connection".format(
            'api key from parameter or CAC_API_KEY environment variable' if not api_key else
            'api user from paramater or CAC_API_USER environment variable'))

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
            api_key=dict(),
            api_user=dict(),
            label=dict(type='str', aliases=['name']),
            fqdn=dict(type='str'),
            cpus=dict(type='int'),
            ram=dict(type='int'),
            storage=dict(type='int'),
            template=dict(type='int'),
            runmode=dict(type='str', default="safe"),
            server_id=dict(type='int', aliases=['sid']),
            wait=dict(type='bool', default=True),
            wait_timeout=dict(default=300),
        ),
        supports_check_mode=True
    )

    if not HAS_PYCURL:
        module.fail_json(msg='pycurl required for this module')
    if not HAS_CAC:
        module.fail_json(msg='CACPy required for this module')

    changed = False
    jobs = []
    action = None
    result = {}
    template_detail = None

    # Steps:
    # 2. Create if not existing (Build)
    # 3. Fail if any immutable values are specificed and different (cpus, ram, storage, template_id)
    # 4. Complete available commit operations:
    #  . Update label (Rename)
    #  . Update RDNS
    #  . Update Run Mode
    #  . Update Power State (Power Off, Power On, Reset)

    state = module.params.get('state')

    api_key = module.params.get('api_key')
    api_user = module.params.get('api_user')
    label = module.params.get('label')
    fqdn = module.params.get('fqdn')
    cpus = module.params.get('cpus')
    ram = module.params.get('ram')
    storage = module.params.get('storage')
    template = module.params.get('template')
    server_id = module.params.get('server_id')
    runmode = module.params.get('runmode')
    wait = module.params.get('wait')
    wait_timeout = int(module.params.get('wait_timeout'))

    # Setup the api_key and api_user
    try:
        api = get_api(module.params.get('api_key'), module.params.get('api_user'))
        server = get_server(api, server_id=server_id, label=label)

        # Act on the state
        if state in ('active', 'present', 'started'):
            if not server:
                action = 'build'
                result = CACServer.build_server(api, cpus, ram, storage, template)
                module.exit_json(changed=True, result=result, action=action, build_complete=False)

    except CacApiError, e:
        module.fail_json(msg='%s' % e.message)




    # TODO IMPLEMENT
    # if module.check_mode:
    #     # Check if any changes would be made but don't actually make those changes
    #     module.exit_json(changed=check_if_system_state_would_be_changed())
    #
    #     # TODO ? Implement ansible_facts to provide things like root password?

if __name__ == '__main__':
    main()
