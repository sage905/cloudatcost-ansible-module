from cacpy.CACPy import *
import pytest
import mock

from cloudatcost_ansible_module import cac_server

ROOT_URL = BASE_URL + API_VERSION

V1_LISTSERVERS_RESPONSE = {'status': 'ok', 'action': 'listservers', 'api': 'v1',
                           'data': [{'sdate': '07/14/2015', 'uid': '4482712345', 'ip': '10.1.1.2',
                                     'servername': 'c123456789-cloudpro-123456789', 'ram': '2048',
                                     'portgroup': 'Cloud-ip-123',
                                     'id': '123456789', 'label': 'serverlabel',
                                     'vmname': 'c90000-CloudPRO-123456789-123456789',
                                     'gateway': '10.1.1.1', 'hdusage': '5.123456789', 'rdns': 'server.test.example',
                                     'rootpass': 'password',
                                     'vncport': '12345', 'hostname': 'server.test.example', 'storage': '10',
                                     'cpuusage': '26',
                                     'template': 'CentOS-7-64bit', 'sid': '123456789', 'vncpass': 'secret',
                                     'status': 'Powered On',
                                     'lable': 'serverlabel', 'servertype': 'cloudpro',
                                     'rdnsdefault': 'notassigned.cloudatcost.com',
                                     'netmask': '255.255.255.0', 'ramusage': '763.086', 'mode': 'Normal',
                                     'packageid': '15',
                                     'panel_note': 'testnote', 'cpu': '4'}], 'time': 1487000464}

V1_LIST_TEMPLATES_RESPONSE = {'status': 'ok', 'action': 'listtemplates', 'api': 'v1',
                              'data': [{'ce_id': '1', 'name': 'CentOS 6.7 64bit'},
                                       {'ce_id': '3', 'name': 'Debian-8-64bit'},
                                       {'ce_id': '9', 'name': 'Windows 7 64bit'},
                                       {'ce_id': '24', 'name': 'Windows 2008 R2 64bit'},
                                       {'ce_id': '25', 'name': 'Windows 2012 R2 64bit'},
                                       {'ce_id': '26', 'name': 'CentOS-7-64bit'},
                                       {'ce_id': '27', 'name': 'Ubuntu-14.04.1-LTS-64bit'},
                                       {'ce_id': '74', 'name': 'FreeBSD-10-1-64bit'}], 'time': 1487027299}

V1_LISTSERVERS_RESPONSE_POST_BUILD = {'status': 'ok', 'action': 'listservers', 'api': 'v1',
                           'data': [{'sdate': '07/14/2015', 'uid': '4482712345', 'ip': '10.1.1.2',
                                     'servername': 'c123456789-cloudpro-123456789', 'ram': '2048',
                                     'portgroup': 'Cloud-ip-123',
                                     'id': '123456789', 'label': 'serverlabel',
                                     'vmname': 'c90000-CloudPRO-123456789-123456789',
                                     'gateway': '10.1.1.1', 'hdusage': '5.123456789', 'rdns': 'server.test.example',
                                     'rootpass': 'password',
                                     'vncport': '12345', 'hostname': 'server.test.example', 'storage': '10',
                                     'cpuusage': '26',
                                     'template': 'CentOS-7-64bit', 'sid': '123456789', 'vncpass': 'secret',
                                     'status': 'Powered On',
                                     'lable': 'serverlabel', 'servertype': 'cloudpro',
                                     'rdnsdefault': 'notassigned.cloudatcost.com',
                                     'netmask': '255.255.255.0', 'ramusage': '763.086', 'mode': 'Normal',
                                     'packageid': '15',
                                     'panel_note': 'testnote', 'cpu': '4'},
                                    {'sdate': '07/14/2016', 'uid': '4482712345', 'ip': '10.1.1.3',
                                     'servername': 'c012345678-cloudpro-012345678', 'ram': '1024',
                                     'portgroup': 'Cloud-ip-123',
                                     'id': '012345678', 'label': 'serverlabel',
                                     'vmname': 'c90000-CloudPRO-012345678-012345678',
                                     'gateway': '10.1.1.1', 'hdusage': '5.012345678', 'rdns': 'server.test.example',
                                     'rootpass': 'password',
                                     'vncport': '12345', 'hostname': 'server.test.example', 'storage': '10',
                                     'cpuusage': '26',
                                     'template': 'CentOS-7-64bit', 'sid': '012345678', 'vncpass': 'secret',
                                     'status': 'Powered On',
                                     'lable': 'serverlabel', 'servertype': 'cloudpro',
                                     'rdnsdefault': 'notassigned.cloudatcost.com',
                                     'netmask': '255.255.255.0', 'ramusage': '763.086', 'mode': 'Normal',
                                     'packageid': '15',
                                     'panel_note': 'testnote', 'cpu': '4'}
                                    ], 'time': 1487000464}


V1_STANDARD_RESPONSE_OK = {
    "status": "ok",
    "time": 1425064819,
    "id": "90000",
    "data": []
}

V1_STANDARD_RESPONSE_ERROR = {
    "status": "error",
    "time": 1425064819,
    "error": 104,
    "error_description": "Error Test Response"
}

V1_BUILD_SUCCES = {'action': 'build',
                   'api': 'v1',
                   'result': 'successful',
                   'servername': 'c012345678-cloudpro-012345678',
                   'status': 'ok',
                   'taskid': 7858123456789,
                   'time': 1487860096}

V1_BUILD_FAILED = {'error': 105,
                   'error_description': 'invalid CPU value',
                   'status': 'error',
                   'time': 1487860604}


# This method will be used by the mock to replace requests.get_template in all tests
@pytest.fixture()
def mock_cac_api():
    api = mock.Mock(spec=CACPy)
    api.email = 'test@user.com'
    api.key = 'shhverysecret'
    api.get_server_info.return_value = V1_LISTSERVERS_RESPONSE
    api.get_template_info.return_value = V1_LIST_TEMPLATES_RESPONSE
    api.rename_server.return_value = V1_STANDARD_RESPONSE_OK
    api.change_hostname.return_value = V1_STANDARD_RESPONSE_OK
    api.set_run_mode.return_value = V1_STANDARD_RESPONSE_OK
    api.server_delete.return_value = V1_STANDARD_RESPONSE_OK
    api.power_off_server.return_value = V1_STANDARD_RESPONSE_OK
    api.power_on_server.return_value = V1_STANDARD_RESPONSE_OK
    api.reset_server.return_value = V1_STANDARD_RESPONSE_OK
    api.server_build.return_value = V1_BUILD_SUCCES
    return api


@pytest.fixture()
def simulated_build(num):
    for i in range(1, num, 1):
        yield V1_LISTSERVERS_RESPONSE
    while True:
        yield V1_LISTSERVERS_RESPONSE_POST_BUILD


@pytest.fixture()
def patch_get_api(monkeypatch):
    def patch_api(api_user, api_key):
        return mock_cac_api()
    monkeypatch.setattr(cac_server, "get_api", patch_api)


@pytest.fixture()
def patch_get_api_simulated_build(monkeypatch):
    def patch_api(api_user, api_key):
        api = mock_cac_api()
        api.get_server_info.side_effect = simulated_build(1)
        return api
    monkeypatch.setattr(cac_server, "get_api", patch_api)


@pytest.fixture()
def cac_api_fail_build():
    api = mock.Mock(spec=CACPy)
    api.get_server_info.return_value = V1_LISTSERVERS_RESPONSE
    api.get_template_info.return_value = V1_LIST_TEMPLATES_RESPONSE
    api.server_build.return_value = V1_BUILD_FAILED
    return api


