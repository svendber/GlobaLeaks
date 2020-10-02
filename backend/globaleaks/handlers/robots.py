# -*- coding: utf-8 -*-
#
# Implementation of robots.txt resource
from globaleaks.handlers.base import BaseHandler


class RobotstxtHandler(BaseHandler):
    """
    Handler that implements the Robot.txt api
    """
    check_roles = 'any'

    def get(self):
        """
        Get the robots.txt
        """
        self.request.setHeader(b'Content-Type', b'text/plain')

        if (self.request.tid != 1 and self.state.tenant_cache[self.request.tid].mode == 'demo') or \
           (not self.state.tenant_cache[self.request.tid].allow_indexing):
            return "User-agent: *\nDisallow: *"

        data = "User-agent: *\n"
        data += "Allow: /$\n"
        data += "Disallow: *\n"
        data += "Sitemap: https://%s/sitemap.xml" % self.state.tenant_cache[self.request.tid].hostname

        return data
