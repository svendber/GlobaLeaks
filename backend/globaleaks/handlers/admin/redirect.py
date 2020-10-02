# -*- coding: utf-8
from twisted.internet.defer import inlineCallbacks, returnValue

from globaleaks import models
from globaleaks.handlers.base import BaseHandler
from globaleaks.models.serializers import serialize_redirect
from globaleaks.orm import transact, tw
from globaleaks.rest import requests
from globaleaks.state import State


@transact
def get_redirect_list(session, tid):
    """
    Transaction for fetching the full list of redirects configured on a tenant

    :param session: An ORM session
    :param tid: The tenant ID
    :return: The list of redirects configured on a tenant
    """
    return [serialize_redirect(redirect) for redirect in session.query(models.Redirect).filter(models.Redirect.tid == tid)]


@inlineCallbacks
def update_redirects_state(tid):
    """
    Function to fetch and configure the list of redirects configured on a tenant

    :param tid: The tenant for which configure the redirects
    """
    State.tenant_cache[tid]['redirects'] = {}

    redirects = yield get_redirect_list(tid)

    for redirect in redirects:
        State.tenant_cache[tid]['redirects'][redirect['path1']] = redirect['path2']


@transact
def create(session, tid, request):
    """
    Transaction for registering the creation of a redirect for a tenant

    :param session: An ORM session
    :param tid: A tenant ID
    :param request: The request data
    :return: The descriptor of the registered redirect
    """
    request['tid'] = tid
    redirect = models.db_add(session, models.Redirect, request)
    return serialize_redirect(redirect)


class RedirectCollection(BaseHandler):
    check_roles = 'admin'
    cache_resource = True
    invalidate_cache = True

    def get(self):
        """
        Return the list of registered redirects
        """
        return get_redirect_list(self.request.tid)

    @inlineCallbacks
    def post(self):
        """
        Create a new redirect
        """
        request = self.validate_message(self.request.content.read(), requests.AdminRedirectDesc)

        redirect = yield create(self.request.tid, request)

        yield update_redirects_state(self.request.tid)

        returnValue(redirect)


class RedirectInstance(BaseHandler):
    check_roles = 'admin'
    invalidate_cache = True

    @inlineCallbacks
    def delete(self, redirect_id):
        """
        Delete the specified redirect.
        """
        yield tw(models.db_delete,
                 models.Redirect,
                 (models.Redirect.tid == self.request.tid, models.Redirect.id == redirect_id))

        yield update_redirects_state(self.request.tid)
