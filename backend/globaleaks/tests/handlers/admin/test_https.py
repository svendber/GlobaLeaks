# -*- coding: utf-8 -*-
from OpenSSL import crypto, SSL
from twisted.internet.defer import inlineCallbacks, returnValue

from globaleaks.handlers.admin import https
from globaleaks.models import config
from globaleaks.orm import tw
from globaleaks.rest import errors
from globaleaks.state import State
from globaleaks.tests import helpers
from globaleaks.tests.utils import test_tls
from globaleaks.utils.letsencrypt import ChallTok


@inlineCallbacks
def set_init_params(tls_config):
    hostname = 'localhost:9999'
    yield tw(config.db_set_config_variable, 1, 'hostname', hostname)
    State.tenant_cache[1].hostname = hostname


class TestFileHandler(helpers.TestHandler):
    _handler = https.FileHandler

    @inlineCallbacks
    def setUp(self):
        self.valid_setup = test_tls.get_valid_setup()
        yield super(TestFileHandler, self).setUp()
        yield set_init_params(self.valid_setup)

    @inlineCallbacks
    def get_and_check(self, name, is_set):
        handler = self.request(role='admin', handler_cls=https.ConfigHandler)

        response = yield handler.get()

        self.assertEqual(response['files'][name]['set'], is_set)

        returnValue(response)

    @inlineCallbacks
    def test_key_file(self):
        n = 'key'

        yield self.get_and_check(n, False)

        # Try to upload an invalid key
        bad_key = 'donk donk donk donk donk donk'
        handler = self.request({'name': 'key', 'content': bad_key}, role='admin')
        yield self.assertFailure(handler.post(n), errors.InputValidationError)

        # Upload a valid key
        good_key = self.valid_setup['key']
        handler = self.request({'name': 'key', 'content': good_key}, role='admin')

        yield handler.post(n)

        response = yield self.get_and_check(n, True)

        # Test key generation
        yield handler.put(n)

        response = yield self.get_and_check(n, True)
        was_generated = response['files']['key']['set']
        self.assertTrue(was_generated)

        # Try delete actions
        yield handler.delete(n)

        yield self.get_and_check(n, False)

    @inlineCallbacks
    def test_cert_file(self):
        n = 'cert'

        yield self.get_and_check(n, False)
        yield https.PrivKeyFileRes.create_file(1, self.valid_setup['key'])

        # Test bad cert
        body = {'name': 'cert', 'content': 'bonk bonk bonk'}
        handler = self.request(body, role='admin')
        yield self.assertFailure(handler.post(n), errors.InputValidationError)

        # Upload a valid cert
        body = {'name': 'cert', 'content': self.valid_setup[n]}
        handler = self.request(body, role='admin')
        yield handler.post(n)

        yield self.get_and_check(n, True)

        handler = self.request(role='admin')
        response = yield handler.get(n)
        self.assertEqual(response, self.valid_setup[n])

        # Finally delete the cert
        yield handler.delete(n)
        yield self.get_and_check(n, False)

    @inlineCallbacks
    def test_chain_file(self):
        n = 'chain'

        yield self.get_and_check(n, False)
        yield https.PrivKeyFileRes.create_file(1, self.valid_setup['key'])
        yield https.CertFileRes.create_file(1, self.valid_setup['cert'])
        State.tenant_cache[1].hostname = 'localhost'

        body = {'name': 'chain', 'content': self.valid_setup[n]}
        handler = self.request(body, role='admin')

        yield handler.post(n)
        yield self.get_and_check(n, True)

        handler = self.request(role='admin')
        response = yield handler.get(n)
        self.assertEqual(response, self.valid_setup[n])

        yield handler.delete(n)
        yield self.get_and_check(n, False)


class TestConfigHandler(helpers.TestHandler):
    _handler = https.ConfigHandler

    @inlineCallbacks
    def test_all_methods(self):
        valid_setup = test_tls.get_valid_setup()
        yield set_init_params(valid_setup)
        yield https.PrivKeyFileRes.create_file(1, valid_setup['key'])
        yield https.CertFileRes.create_file(1, valid_setup['cert'])
        yield https.ChainFileRes.create_file(1, valid_setup['chain'])

        handler = self.request(role='admin')

        yield handler.post()
        response = yield handler.get()
        self.assertTrue(response['enabled'])

        self.test_reactor.pump([50])

        yield handler.put()
        response = yield handler.get()
        self.assertFalse(response['enabled'])


class TestCSRHandler(helpers.TestHandler):
    _handler = https.CSRFileHandler

    @inlineCallbacks
    def test_post(self):
        n = 'csr'

        valid_setup = test_tls.get_valid_setup()
        yield set_init_params(valid_setup)
        yield https.PrivKeyFileRes.create_file(1, valid_setup['key'])
        State.tenant_cache[1].hostname = 'notreal.ns.com'

        d = {
            'country': 'it',
            'province': 'regione',
            'city': 'citta',
            'company': 'azienda',
            'department': 'reparto',
            'email': 'indrizzio@email',
        }

        body = {'name': 'csr', 'content': d}
        handler = self.request(body, role='admin')
        yield handler.post(n)

        response = yield handler.get(n)

        pem_csr = crypto.load_certificate_request(SSL.FILETYPE_PEM, response)

        comps = pem_csr.get_subject().get_components()
        self.assertIn((b'CN', b'notreal.ns.com'), comps)
        self.assertIn((b'C', b'IT'), comps)
        self.assertIn((b'L', b'citta'), comps)


class TestAcmeChallengeHandler(helpers.TestHandler):
    _handler = https.AcmeChallengeHandler

    @inlineCallbacks
    def test_get(self):
        # tmp_chall_dict pollutes scope
        tok = 'yT-RDI9dU7dJPxaTYOgY_YnYYByT4CVAVCC7W3zUDIw'
        v = '{}.5vh2ZRCJGmNUKEEBn-SN6esbMnSl1w8ZT0LDUwexTAM'.format(tok)
        ct = ChallTok(v)

        State.tenant_state[1].acme_tmp_chall_dict.set(tok, ct)

        handler = self.request()
        resp = yield handler.get(tok)

        self.assertEqual(resp, v)
