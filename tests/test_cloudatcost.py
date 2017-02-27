import pytest
from cacpy import CACPy

from cloudatcost_ansible_module.cac_server import CACTemplate, get_server, CACServer, CacApiError
from cloudatcost_ansible_module import cac_server as cac_server
import json
from ansible.module_utils import basic
from ansible.module_utils._text import to_bytes
import os
from mock import call


def set_module_args(args):
    args = json.dumps({'ANSIBLE_MODULE_ARGS': args})
    basic._ANSIBLE_ARGS = to_bytes(args)


class TestServerClass(object):
    def test_template_lookup(self, mock_cac_api):
        template = CACTemplate.get_template(mock_cac_api, '27')
        assert template.desc == "Ubuntu-14.04.1-LTS-64bit"

        template = CACTemplate.get_template(mock_cac_api, "Ubuntu-14.04.1-LTS-64bit")
        assert template.template_id == "27"

    def test_teamplate_lookup_accepts_instance_as_parameter(self, mock_cac_api):
        template = CACTemplate.get_template(mock_cac_api, '27')
        template2 = CACTemplate.get_template(mock_cac_api, template)
        assert template2 == template

    def test_get_nonexistent_server_returns_none(self, mock_cac_api):
        server = get_server(mock_cac_api, 000000000)
        assert server is None

    def test_server_repr_valid(self, mock_cac_api):
        server = get_server(mock_cac_api, server_id='123456789')
        assert (server.__repr__() == 'CACServer(api_account=test@user.com, sid=123456789, label=serverlabel)')

    def test_get_server_by_sid(self, mock_cac_api):
        server = get_server(mock_cac_api, server_id='123456789')
        assert (server.sid == '123456789')

    def test_get_server_by_label(self, mock_cac_api):
        server = get_server(mock_cac_api, label='serverlabel')
        assert (server.sid == '123456789')

    def test_get_server_by_servername(self, mock_cac_api):
        server = get_server(mock_cac_api, server_name='c123456789-cloudpro-123456789')
        assert (server.sid == '123456789')

    def test_edit_existing_server_label(self, mock_cac_api):
        server = get_server(mock_cac_api, 123456789)
        server.label = 'test'
        assert server.label == 'test'

    def test_update_uneditable_raises_error(self, mock_cac_api):
        server = get_server(mock_cac_api, 123456789)
        pytest.raises(AttributeError, setattr, server, 'cpu', '16')

    def test_update_edit_calls_api(self, mock_cac_api):
        server = get_server(mock_cac_api, 123456789)
        server.label = "testing"
        server.commit()
        assert call.rename_server(new_name='testing', server_id='123456789') in mock_cac_api.method_calls

    def test_update_rdns(self, mock_cac_api):
        server = get_server(mock_cac_api, 123456789)
        server.rdns = "server.test.com"
        server.commit()
        assert call.change_hostname(new_hostname='server.test.com', server_id='123456789') in mock_cac_api.method_calls

    def test_update_mode(self, mock_cac_api):
        server = get_server(mock_cac_api, 123456789)
        server.mode = "normal"
        server.commit()
        assert call.set_run_mode(run_mode='normal', server_id='123456789') in mock_cac_api.method_calls

    def test_power_off_state(self, mock_cac_api):
        server = get_server(mock_cac_api, 123456789)
        server.status = "Powered Off"
        server.commit()
        assert call.power_off_server(server_id='123456789') in mock_cac_api.method_calls

    def test_power_on_state(self, mock_cac_api):
        server = get_server(mock_cac_api, 123456789)
        server.status = "Powered On"
        server.commit()
        assert call.power_on_server(server_id='123456789') in mock_cac_api.method_calls

    def test_restarted_state(self, mock_cac_api):
        server = get_server(mock_cac_api, 123456789)
        server.status = "Restarted"
        server.commit()
        assert call.reset_server(server_id='123456789') in mock_cac_api.method_calls

    def test_delete(self, mock_cac_api):
        server = get_server(mock_cac_api, 123456789)
        server.delete()
        assert call.server_delete(server_id='123456789') in mock_cac_api.method_calls

    def test_change_everything(self, mock_cac_api):
        server = get_server(mock_cac_api, 123456789)
        server.label = "testing"
        server.rdns = "server.test.com"
        server.mode = "normal"
        server.status = "Restarted"
        server.commit()
        assert call.rename_server(new_name='testing', server_id='123456789') in mock_cac_api.method_calls
        assert call.change_hostname(new_hostname='server.test.com', server_id='123456789') in mock_cac_api.method_calls
        assert call.set_run_mode(run_mode='normal', server_id='123456789') in mock_cac_api.method_calls
        assert call.reset_server(server_id='123456789') in mock_cac_api.method_calls

    def test_server_build_success(self, mock_cac_api):
        result = CACServer.build_server(mock_cac_api, cpu=1, ram=1024, disk=10, template=27)
        assert mock_cac_api.method_calls == [call.get_template_info(), call.server_build(1, 1024, 10, CACTemplate(
            desc='Ubuntu-14.04.1-LTS-64bit', template_id='27'))]
        assert result['status'] == 'ok'

    def test_server_build_failure(self, cac_api_fail_build):
        pytest.raises(CacApiError, CACServer.build_server, api=cac_api_fail_build, cpu=1, ram=1024, disk=10,
                      template=27)


class TestAnsibleModule(object):
    def test_get_api_checks_environment(self):
        os.environ.clear()
        pytest.raises(CacApiError, cac_server.get_api, "", "")

    @pytest.mark.usefixtures('patch_get_api')
    def test_module_builds_nonexistent_server(self, capsys):
        set_module_args(dict(api_user="test@guy.com", api_key="secret", label='test', cpus=1, ram=1024, storage=10,
                             template=27, state='present'))
        pytest.raises(SystemExit, cac_server.main)
        out, err = capsys.readouterr()
        output = json.loads(out)
        print(output)
        assert output['changed'] is True
        assert output['result']['action'] == 'build'
        assert output['build_complete'] is False

    @pytest.mark.usefixtures('patch_get_api')
    def test_module_builds_server_and_waits_for_completion(self, capsys):
        set_module_args(dict(api_user="test@guy.com", api_key="secret", label='test', cpus=1, ram=1024, storage=10,
                             template=27, state='present', wait=True, wait_timeout=300))


