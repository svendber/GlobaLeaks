# -*- coding: utf-8 -*-
# Implement the notification of new submissions
import copy

from twisted.internet import defer

from globaleaks import models
from globaleaks.handlers.admin.context import admin_serialize_context
from globaleaks.handlers.admin.node import db_admin_serialize_node
from globaleaks.handlers.admin.notification import db_get_notification
from globaleaks.handlers.admin.submission_statuses import db_get_submission_statuses
from globaleaks.handlers.rtip import serialize_rtip, serialize_message, serialize_comment
from globaleaks.handlers.user import user_serialize_user
from globaleaks.jobs.job import LoopingJob
from globaleaks.orm import db_del, transact, tw
from globaleaks.utils.log import log
from globaleaks.utils.pgp import PGPContext
from globaleaks.utils.templating import Templating
from globaleaks.utils.utility import deferred_sleep


trigger_template_map = {
    'ReceiverTip': 'tip',
    'Message': 'message',
    'Comment': 'comment',
    'ReceiverFile': 'file'
}


trigger_model_map = {
    'ReceiverTip': models.ReceiverTip,
    'Message': models.Message,
    'Comment': models.Comment,
    'ReceiverFile': models.ReceiverFile
}


def gen_cache_key(*args):
    return '-'.join(['{}'.format(arg) for arg in args])


class MailGenerator(object):
    def __init__(self, state):
        self.state = state
        self.cache = {}

    def serialize_config(self, session, key, tid, language):
        cache_key = gen_cache_key(key, tid, language)
        cache_obj = None

        if cache_key not in self.cache:
            if key == 'node':
                cache_obj = db_admin_serialize_node(session, tid, language)
            elif key == 'notification':
                cache_obj = db_get_notification(session, tid, language)

            self.cache[cache_key] = cache_obj

        return self.cache[cache_key]

    def serialize_obj(self, session, key, obj, tid, language):
        obj_id = obj.id

        cache_key = gen_cache_key(key, tid, obj_id, language)
        cache_obj = None

        if cache_key not in self.cache:
            if key == 'user':
                cache_obj = user_serialize_user(session, obj, language)
            elif key == 'context':
                cache_obj = admin_serialize_context(session, obj, language)
            elif key == 'tip':
                itip = session.query(models.InternalTip).filter(models.InternalTip.id == obj.internaltip_id).one()
                cache_obj = serialize_rtip(session, obj, itip, language)
            elif key == 'message':
                cache_obj = serialize_message(session, obj)
            elif key == 'comment':
                cache_obj = serialize_comment(session, obj)
            elif key == 'file':
                cache_obj = models.serializers.serialize_ifile(session, obj)

            self.cache[cache_key] = cache_obj

        return self.cache[cache_key]

    def process_ReceiverTip(self, session, rtip, data):
        user, context = session.query(models.User, models.Context) \
                               .filter(models.User.id == rtip.receiver_id,
                                       models.InternalTip.id == rtip.internaltip_id,
                                       models.Context.id == models.InternalTip.context_id).one()

        tid = context.tid

        data['user'] = self.serialize_obj(session, 'user', user, tid, user.language)
        data['tip'] = self.serialize_obj(session, 'tip', rtip, tid, user.language)
        data['context'] = self.serialize_obj(session, 'context', context, tid, user.language)

        self.process_mail_creation(session, tid, data)

    def process_Message(self, session, message, data):
        # if the message was created by a receiver do not generate mails
        if message.type == "receiver":
            return

        user, context, rtip = session.query(models.User, models.Context, models.ReceiverTip) \
                                     .filter(models.User.id == models.ReceiverTip.receiver_id,
                                             models.ReceiverTip.id == message.receivertip_id,
                                             models.Context.id == models.InternalTip.context_id,
                                             models.InternalTip.id == models.ReceiverTip.internaltip_id).one()

        tid = context.tid

        data['user'] = self.serialize_obj(session, 'user', user, tid, user.language)
        data['tip'] = self.serialize_obj(session, 'tip', rtip, tid, user.language)
        data['context'] = self.serialize_obj(session, 'context', context, tid, user.language)
        data['message'] = self.serialize_obj(session, 'message', message, tid, user.language)

        self.process_mail_creation(session, tid, data)

    def process_Comment(self, session, comment, data):
        for user, context, rtip in session.query(models.User, models.Context, models.ReceiverTip) \
                                          .filter(models.User.id == models.ReceiverTip.receiver_id,
                                                  models.ReceiverTip.internaltip_id == comment.internaltip_id,
                                                  models.Context.id == models.InternalTip.context_id,
                                                  models.InternalTip.id == comment.internaltip_id,
                                                  models.ReceiverTip.internaltip_id == comment.internaltip_id,
                                                  models.ReceiverTip.receiver_id != comment.author_id):
            tid = context.tid

            umsg = copy.deepcopy(data)
            umsg['user'] = self.serialize_obj(session, 'user', user, tid, user.language)
            umsg['tip'] = self.serialize_obj(session, 'tip', rtip, tid, user.language)
            umsg['context'] = self.serialize_obj(session, 'context', context, tid, user.language)
            umsg['comment'] = self.serialize_obj(session, 'comment', comment, tid, user.language)

            self.process_mail_creation(session, tid, umsg)

    def process_ReceiverFile(self, session, rfile, data):
        user, context, rtip, ifile = session.query(models.User, models.Context, models.ReceiverTip, models.InternalFile) \
                                            .filter(models.User.id == models.ReceiverTip.receiver_id,
                                                    models.InternalFile.id == rfile.internalfile_id,
                                                    models.InternalFile.submission.is_(False),
                                                    models.InternalTip.id == models.InternalFile.internaltip_id,
                                                    models.ReceiverTip.id == rfile.receivertip_id,
                                                    models.Context.id == models.InternalTip.context_id).one()

        tid = context.tid

        data['user'] = self.serialize_obj(session, 'user', user, tid, user.language)
        data['tip'] = self.serialize_obj(session, 'tip', rtip, tid, user.language)
        data['user'] = self.serialize_obj(session, 'user', user, tid, user.language)
        data['context'] = self.serialize_obj(session, 'context', context, tid, user.language)
        data['file'] = self.serialize_obj(session, 'file', ifile, tid, user.language)

        self.process_mail_creation(session, tid, data)

    def process_mail_creation(self, session, tid, data):
        user_id = data['user']['id']
        language = data['user']['language']

        # Do not spool emails if the receiver has disabled notifications
        if not data['user']['notification'] or not data['tip']['enable_notifications']:
            log.debug("Discarding emails for %s due to receiver's preference.", user_id)
            return

        data['node'] = self.serialize_config(session, 'node', tid, language)

        data['submission_statuses'] = db_get_submission_statuses(session, tid, language)

        if data['node']['mode'] == 'default':
            data['notification'] = self.serialize_config(session, 'notification', tid, language)
        else:
            data['notification'] = self.serialize_config(session, 'notification', 1, language)

        subject, body = Templating().get_mail_subject_and_body(data)

        # If the receiver has encryption enabled encrypt the mail body
        if data['user']['pgp_key_public']:
            pgpctx = PGPContext(self.state.settings.tmp_path)
            fingerprint = pgpctx.load_key(data['user']['pgp_key_public'])['fingerprint']
            body = pgpctx.encrypt_message(fingerprint, body)

        session.add(models.Mail({
            'address': data['user']['mail_address'],
            'subject': subject,
            'body': body,
            'tid': tid,
        }))

    @transact
    def generate(self, session):
        silent_tids = []
        for tid, cache_item in self.state.tenant_cache.items():
            if cache_item.notification and cache_item.notification.disable_receiver_notification_emails:
                silent_tids.append(tid)

        if silent_tids:
            for x in session.query(models.ReceiverTip).filter(models.ReceiverTip.internaltip_id == models.InternalTip.id,
                                                              models.InternalTip.tid.in_(silent_tids)):
                x.new = False

            for x in session.query(models.Comment).filter(models.Comment.internaltip_id == models.InternalTip.id,
                                                          models.InternalTip.tid.in_(silent_tids)):
                x.new = False

            for x in session.query(models.Message).filter(models.Message.receivertip_id == models.ReceiverTip.id,
                                                          models.ReceiverTip.internaltip_id == models.InternalTip.id,
                                                          models.InternalTip.tid.in_(silent_tids)):
                x.new = False

            for x in session.query(models.ReceiverFile).filter(models.ReceiverFile.receivertip_id == models.ReceiverTip.id,
                                                               models.ReceiverTip.internaltip_id == models.InternalTip.id,
                                                               models.InternalTip.tid.in_(silent_tids)):
                x.new = False

        for trigger in ['ReceiverTip', 'Comment', 'Message', 'ReceiverFile']:
            model = trigger_model_map[trigger]

            for element in session.query(model).filter(model.new.is_(True)):
                data = {
                    'type': trigger_template_map[trigger]
                }

                try:
                    getattr(self, 'process_%s' % trigger)(session, element, data)
                except Exception as e:
                    log.err("Unhandled exception during mail generation: %s", e)
                finally:
                    element.new = False


@transact
def get_mails_from_the_pool(session):
    """
    Fetch the email to be sent.

    Email are spooled every 5 seconds and mailing attepts last 5 days.
    """
    db_del(session, models.Mail, models.Mail.processing_attempts > 86400)

    session.query(models.Mail).update({'processing_attempts': models.Mail.processing_attempts + 1})

    ret = []

    for mail in session.query(models.Mail).order_by(models.Mail.creation_date):
        ret.append({
            'id': mail.id,
            'address': mail.address,
            'subject': mail.subject,
            'body': mail.body,
            'tid': mail.tid
        })

    return ret


class Notification(LoopingJob):
    interval = 5
    monitor_interval = 3 * 60

    @defer.inlineCallbacks
    def spool_emails(self):
        mails = yield get_mails_from_the_pool()
        for mail in mails:
            sent = yield self.state.sendmail(mail['tid'], mail['address'], mail['subject'], mail['body'])
            if sent:
                yield tw(db_del, models.Mail, models.Mail.id == mail['id'])

            yield deferred_sleep(1)

    @defer.inlineCallbacks
    def operation(self):
        yield MailGenerator(self.state).generate()

        yield self.spool_emails()
