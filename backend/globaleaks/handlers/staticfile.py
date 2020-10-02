# -*- coding: utf-8 -*-
#
# Handler exposing application files
import os

from globaleaks.handlers.base import BaseHandler
from globaleaks.rest import errors
from globaleaks.utils.fs import directory_traversal_check


class StaticFileHandler(BaseHandler):
    check_roles = 'none'
    handler_exec_time_threshold = 30

    def __init__(self, state, request):
        BaseHandler.__init__(self, state, request)

        self.root = "%s%s" % (os.path.abspath(state.settings.client_path), "/")

    def get(self, filename):
        if not filename:
            filename = 'index.html'

        abspath = os.path.abspath(os.path.join(self.root, filename))

        directory_traversal_check(self.root, abspath)

        if os.path.exists(abspath + '.gz') and os.path.isfile(abspath + '.gz'):
            return self.write_file(filename + '.gz', abspath + '.gz')
        elif os.path.exists(abspath) and os.path.isfile(abspath):
            return self.write_file(filename, abspath)

        raise errors.ResourceNotFound()
