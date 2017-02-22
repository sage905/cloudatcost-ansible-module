from cacpy.CACPy import *
import pytest

V1_SERVER_DEFAULT = {'sdate': '07/14/2015', 'uid': '4482712345', 'ip': '10.1.1.2',
                     'servername': 'c123456789-cloudpro-123456789', 'ram': '2048', 'portgroup': 'Cloud-ip-123',
                     'id': '123456789', 'label': 'serverlabel', 'vmname': 'c90000-CloudPRO-123456789-123456789',
                     'gateway': '10.1.1.1', 'hdusage': '5.123456789', 'rdns': 'server.test.example',
                     'rootpass': 'password',
                     'vncport': '12345', 'hostname': 'server.test.example', 'storage': '10', 'cpuusage': '26',
                     'template': 'CentOS-7-64bit', 'sid': '123456789', 'vncpass': 'secret',
                     'status': 'Powered On',
                     'lable': 'serverlabel', 'servertype': 'cloudpro',
                     'rdnsdefault': 'notassigned.cloudatcost.com',
                     'netmask': '255.255.255.0', 'ramusage': '763.086', 'mode': 'Normal', 'packageid': '15',
                     'panel_note': 'testnote', 'cpu': '4'}

V1_LISTSERVERS_RESPONSE = {'status': 'ok', 'action': 'listservers', 'api': 'v1', 'time': 1487000464}

V1_LIST_TEMPLATES_RESPONSE = {'status': 'ok', 'action': 'listtemplates', 'api': 'v1',
                              'data': [{'ce_id': '1', 'name': 'CentOS 6.7 64bit'},
                                       {'ce_id': '3', 'name': 'Debian-8-64bit'},
                                       {'ce_id': '9', 'name': 'Windows 7 64bit'},
                                       {'ce_id': '24', 'name': 'Windows 2008 R2 64bit'},
                                       {'ce_id': '25', 'name': 'Windows 2012 R2 64bit'},
                                       {'ce_id': '26', 'name': 'CentOS-7-64bit'},
                                       {'ce_id': '27', 'name': 'Ubuntu-14.04.1-LTS-64bit'},
                                       {'ce_id': '74', 'name': 'FreeBSD-10-1-64bit'}], 'time': 1487027299}

V1_STANDARD_RESPONSE_OK = {
    "status": "ok",
    "time": 1425064819,
    "id": "90000",
    "data": []
}

ROOT_URL = BASE_URL + API_VERSION

V1_STANDARD_RESPONSE_ERROR = {
    "status": "error",
    "time": 1425064819,
    "error": 104,
    "error_description": "Error Test Response"
}


class MockServer(object):
    def __init__(self):
        self.server = V1_SERVER_DEFAULT.copy()

    def get_server(self):
        return self.server

    def set_server_attribute(self, attribute, value):
        self.server[attribute] = value

    def get_server_as_list(self):
        return [self.server, ]


def merge_dicts(*dicts):
    return reduce(lambda x, y: x.update(y) or x, dicts, {})


def mocked_requests_get(*args, **kwargs):
    class MockResponse(object):
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    return {
        ROOT_URL + LIST_SERVERS_URL:
            MockResponse(merge_dicts(V1_LISTSERVERS_RESPONSE, {'data': MockServer().get_server_as_list()}), 200),
        ROOT_URL + LIST_TEMPLATES_URL:
            MockResponse(V1_LIST_TEMPLATES_RESPONSE, 200),
    }.get(args[0], MockResponse(V1_STANDARD_RESPONSE_ERROR, 404))


def mocked_requests_post(*args, **kwargs):
    class MockResponse(object):
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    return {
        ROOT_URL + RENAME_SERVER_URL:
            MockResponse(V1_STANDARD_RESPONSE_OK, 200),
        ROOT_URL + SERVER_DELETE_URL:
            MockResponse(V1_STANDARD_RESPONSE_OK, 200),

    }.get(args[0], MockResponse(V1_STANDARD_RESPONSE_ERROR, 404))


# This method will be used by the mock to replace requests.get_template in all tests
@pytest.fixture(autouse=True)
def simulate_get(monkeypatch):
    monkeypatch.setattr("requests.get", mocked_requests_get)


@pytest.fixture(autouse=True)
def simulate_post(monkeypatch):
    monkeypatch.setattr("requests.post", mocked_requests_post)


@pytest.fixture()
def cac_api():
    return CACPy('test@user.com', 'testkey')
