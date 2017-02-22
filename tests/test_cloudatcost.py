import pytest
from cloudatcost_ansible_module.cac_server import get_template, get_server


class TestServerClass(object):

    def test_template_lookup(self, cac_api):
        template = get_template(cac_api, '27')
        assert template.desc == "Ubuntu-14.04.1-LTS-64bit"

        template = get_template(cac_api, "Ubuntu-14.04.1-LTS-64bit")
        assert template.template_id == "27"

    def test_get_nonexistent_server_returns_none(self, cac_api):
        server = get_server(cac_api, 000000000)
        assert server is None

    def test_get_server_by_sid(self, cac_api):
        server = get_server(cac_api, server_id='123456789')
        assert (server.sid == '123456789')

    def test_get_server_by_label(self, cac_api):
        server = get_server(cac_api, label='serverlabel')
        assert (server.sid == '123456789')

    def test_edit_existing_server_label(self, cac_api):
        server = get_server(cac_api, 123456789)
        server.label = 'test'
        assert server.label == 'test'

    def test_update_uneditable_raises_error(self, cac_api):
        server = get_server(cac_api, 123456789)
        pytest.raises(AttributeError, setattr, server, 'cpu', '16')

    def test_update_edit_calls_api(self, cac_api):
        server = get_server(cac_api, 123456789)
        server.label = "testing"
        server.commit()

    def test_delete(self, cac_api):
        server = get_server(cac_api, 123456789)
        server.delete()


            # def test_create_new_server(self, cac_api):
    #     server = CACServer(cac_api,
    #                        template=26,
    #                        cpu=4, ram=2048, storage=40)
    #     assert (server.template == cac_api.get_template(26))
    #     assert (server.cpu == 4 and server.ram == 2048 and server.storage == 40)
    #     server.build()
    #
