# -*- coding: utf-8 -*-
from twisted.internet.defer import inlineCallbacks
from globaleaks.handlers import admin, public, rtip, user
from globaleaks.jobs.delivery import Delivery
from globaleaks.orm import tw
from globaleaks.tests import helpers
from globaleaks.utils.templating import Templating, supported_template_types


class notifTemplateTest(helpers.TestGLWithPopulatedDB):
    @inlineCallbacks
    def test_keywords_conversion(self):
        tip_id = ''

        yield self.perform_full_submission_actions()
        yield Delivery().run()

        data = {}
        data['type'] = 'tip'
        data['user'] = yield user.get_user(1, self.dummyReceiver_1['id'], 'en')
        data['context'] = yield admin.context.get_context(1, self.dummyContext['id'], 'en')
        data['notification'] = yield tw(admin.notification.db_get_notification, 1, 'en')
        data['node'] = yield tw(admin.node.db_admin_serialize_node, 1, 'en')
        data['submission_statuses'] = yield tw(public.db_get_submission_statuses, 1, 'en')

        for tip in self.dummyRTips:
            if tip['receiver_id'] == self.dummyReceiver_1['id']:
                tip_id = tip['id']
                break

        data['tip'], _ = yield rtip.get_rtip(1, self.dummyReceiver_1['id'], tip_id, 'en')

        data['comments'] = data['tip']['comments']
        data['comment'] = data['comments'][0]

        data['messages'] = data['tip']['messages']
        data['message'] = data['messages'][0]

        files = yield rtip.receiver_get_rfile_list(data['tip']['id'])
        data['file'] = files[0]

        for key in ['tip', 'comment', 'message', 'file']:
            data['type'] = key
            template = ''.join(supported_template_types[key].keyword_list)
            Templating().format_template(template, data)
