# -*- coding: utf-8
from twisted.internet.defer import inlineCallbacks, returnValue

from globaleaks import models, utils, LANGUAGES_SUPPORTED_CODES, LANGUAGES_SUPPORTED
from globaleaks.db import db_refresh_memory_variables
from globaleaks.db.appdata import load_appdata
from globaleaks.handlers.base import BaseHandler
from globaleaks.handlers.user import can_edit_general_settings_or_raise
from globaleaks.models.config import ConfigFactory, ConfigL10NFactory
from globaleaks.orm import tw
from globaleaks.rest import errors, requests
from globaleaks.state import State
from globaleaks.utils.crypto import Base64Encoder, GCE
from globaleaks.utils.ip import parse_csv_ip_ranges_to_ip_networks
from globaleaks.utils.log import log


def db_update_enabled_languages(session, tid, languages_enabled, default_language):
    """
    Transaction for updating the enabled languages for a tenant

    :param session: An ORM session
    :param tid: A tenant id
    :param languages_enabled: The list of enabled languages
    :param default_language: The language to be set as default
    """
    cur_enabled_langs = models.EnabledLanguage.list(session, tid)
    new_enabled_langs = [y for y in languages_enabled]

    if len(new_enabled_langs) < 1:
        raise errors.InputValidationError("No languages enabled!")

    if default_language not in new_enabled_langs:
        raise errors.InputValidationError("Invalid lang code for chosen default_language")

    appdata = None
    for lang_code in new_enabled_langs:
        if lang_code not in LANGUAGES_SUPPORTED_CODES:
            raise errors.InputValidationError("Invalid lang code: %s" % lang_code)

        if lang_code not in cur_enabled_langs:
            if appdata is None:
                appdata = load_appdata()
            log.debug("Adding a new lang %s" % lang_code)
            models.config.add_new_lang(session, tid, lang_code, appdata)

    to_remove = list(set(cur_enabled_langs) - set(new_enabled_langs))
    if to_remove:
        session.query(models.User).filter(models.User.tid == tid, models.User.language.in_(to_remove)).update({'language': default_language}, synchronize_session=False)
        session.query(models.EnabledLanguage).filter(models.EnabledLanguage.tid == tid, models.EnabledLanguage.name.in_(to_remove)).delete(synchronize_session=False)


def db_admin_serialize_node(session, tid, language, config_node='admin_node'):
    """
    Transaction for fetching the node configuration as admin

    :param session: An ORM session
    :param tid: A tenant ID
    :param language: The language to be used on serialization
    :param config_node: The set of variables to be serialized
    :return: Return the serialized configuration for the specified tenant
    """
    config = ConfigFactory(session, tid).serialize(config_node)

    misc_dict = {
        'languages_supported': LANGUAGES_SUPPORTED,
        'languages_enabled': models.EnabledLanguage.list(session, tid),
        'root_tenant': tid == 1,
        'https_possible': tid == 1 or State.tenant_cache[1].reachable_via_web,
        'encryption_possible': tid == 1 or State.tenant_cache[1].encryption
    }

    if tid != 1:
        root_tenant_node = ConfigFactory(session, 1)
        misc_dict['version'] = root_tenant_node.get_val('version')
        misc_dict['latest_version'] = root_tenant_node.get_val('latest_version')

    l10n_dict = ConfigL10NFactory(session, tid).serialize('node', language)

    return utils.sets.merge_dicts(config, misc_dict, l10n_dict)


def db_update_node(session, tid, user_session, request, language):
    """
    Transaction to update the node configuration

    :param session: An ORM session
    :param tid: A tenant ID
    :param user_session: The current user session
    :param request: The request data
    :param language: the language in which to localize data
    :return: Return the serialized configuration for the specified tenant
    """
    config = ConfigFactory(session, tid)

    enable_escrow = not config.get_val('escrow') and request.get('escrow', False)
    disable_escrow = user_session.ek and config.get_val('escrow') and not request.get('escrow', False)

    config.update('node', request)

    if request['enable_ricochet_panel'] and not request['ricochet_address']:
        request['enable_ricochet_panel'] = False

    # Validate that IP addresses/ranges we're getting are goo
    if 'ip_filter_admin' in request and request['ip_filter_admin_enable'] and request['ip_filter_admin']:
        parse_csv_ip_ranges_to_ip_networks(request['ip_filter_admin'])

    if 'ip_filter_whistleblower_enable' in request and request['ip_filter_whistleblower_enable'] and request['ip_filter_whistleblower']:
        parse_csv_ip_ranges_to_ip_networks(request['ip_filter_whistleblower'])

    if 'languages_enabled' in request and 'default_language' in request:
        db_update_enabled_languages(session,
                                    tid,
                                    request['languages_enabled'],
                                    request['default_language'])

    if language in models.EnabledLanguage.list(session, tid):
        ConfigL10NFactory(session, tid).update('node', request, language)

    if enable_escrow:
        crypto_escrow_prv_key, State.tenant_cache[tid].crypto_escrow_pub_key = GCE.generate_keypair()
        user = models.db_get(session, models.User, models.User.id == user_session.user_id)
        user.crypto_escrow_prv_key = Base64Encoder.encode(GCE.asymmetric_encrypt(user.crypto_pub_key, crypto_escrow_prv_key))

    if disable_escrow:
        if tid == 1:
            session.query(models.User).update({'crypto_escrow_bkp1_key': ''}, synchronize_session=False)

        session.query(models.User).filter(models.User.tid == tid).update({'crypto_escrow_prv_key': '', 'crypto_escrow_bkp2_key': ''}, synchronize_session=False)

    config.set_val('crypto_escrow_pub_key', State.tenant_cache[tid].crypto_escrow_pub_key)

    db_refresh_memory_variables(session, [tid])

    if tid == 1:
        log.setloglevel(config.get_val('log_level'))

    return db_admin_serialize_node(session, tid, language)


class NodeInstance(BaseHandler):
    check_roles = 'user'
    cache_resource = True
    invalidate_cache = True

    @inlineCallbacks
    def determine_allow_config_filter(self):
        """Determines what filters are allowed, else throws invalid authentication"""
        if self.current_user.user_role == 'admin':
            node = ('admin_node', requests.AdminNodeDesc)
        else:
            yield can_edit_general_settings_or_raise(self)
            node = ('general_settings', requests.SiteSettingsDesc)

        returnValue(node)

    @inlineCallbacks
    def get(self):
        """
        Get the node infos.
        """
        config_node = yield self.determine_allow_config_filter()
        serialized_node = yield tw(db_admin_serialize_node,
                                   self.request.tid,
                                   self.request.language,
                                   config_node=config_node[0])
        returnValue(serialized_node)

    @inlineCallbacks
    def put(self):
        """
        Update the node infos.
        """
        config_node = yield self.determine_allow_config_filter()

        request = yield self.validate_message(self.request.content.read(),
                                              config_node[1])

        serialized_node = yield tw(db_update_node,
                                   self.request.tid,
                                   self.current_user,
                                   request,
                                   self.request.language)
        returnValue(serialized_node)
