# -*- coding: utf-8 -*-
#
#   statistics_sched
#   ****************
#
#  Statistics works collecting every N-th minutes the amount of important
#  operations happened
#
#  This impact directly the statistics collection for OpenData purpose and
#  private information.
#  The anomaly detection based on stress level measurement.

import os
from twisted.internet.defer import inlineCallbacks

from globaleaks.jobs.base import GLJob
from globaleaks.settings import GLSetting, transact
from globaleaks.models import WeekStats, Anomalies
from globaleaks.utils.utility import log, datetime_to_ISO8601, datetime_now



@transact
def save_anomalies(store, when_anomaly, anomaly_desc, alarm_raised):

   newanom = Anomalies()

   newanom.alarm = alarm_raised
   newanom.stored_when = when_anomaly
   newanom.events = anomaly_desc

   store.add(newanom)

@transact
def save_statistics(store, start, end, activity_collection):

    newstat = WeekStats()

    if activity_collection:
        log.debug("since %s to %s I've collected: %s" %
                  (start, end, activity_collection) )

    newstat.start = start
    newstat.summary = dict(activity_collection)
    newstat.freemb = ResourceChecker.get_free_space()

    store.add(newstat)


class AnomaliesSchedule(GLJob):
    """
    This class check for Anomalies, using the Alarm() object
    implemented in anomaly.py
    """

    def operation(self, alarm_enable=True):
        """
        Every X seconds is checked if anomalies are happening
        from anonymous interaction (submission/file/comments/whatever flood)
        If the alarm has been raise, logs in the DB the event.
        """
        from globaleaks.anomaly import Alarm

        delta = Alarm().compute_activity_level(notification=alarm_enable)

        return delta


class StatisticsSchedule(GLJob):
    """
    Statistics just flush two temporary queue and store them
    in the database.
    """

    collection_start_datetime = None

    @inlineCallbacks
    def operation(self):
        """
        executed every 60 minutes
        """

        from globaleaks.handlers.statistics import AnomaliesCollection
        # AnomaliesCollection queue is dumped in the appropriate row
        from globaleaks.handlers.statistics import RecentEventsCollection
        # RecentEventsQueue is synthesized and dumped in the stats classic row

        for when, anomaly_blob in dict(AnomaliesCollection.RecentAnomaliesQ).iteritems():
            # anomaly_blob is composed by [ { "kind" : $number }, alarm_level ]
            yield save_anomalies(when, anomaly_blob[0], anomaly_blob[1])

        AnomaliesCollection.RecentAnomaliesQ = dict()

        # Addres the statistics. the time start and end are in string
        # without the last 8 bytes, to let d3.js parse easily (or investigate),
        # creation_date, default model, is ignored in the visualisation
        current_time = datetime_to_ISO8601(datetime_now())[:-8]
        statistic_summary = {}

        #  {  'id' : expired_event.event_id
        #     'when' : datetime_to_ISO8601(expired_event.creation_date)[:-8],
        #     'event' : expired_event.event_type, 'duration' :   }

        for descblob in RecentEventsCollection.RecentEventQueue:
            if not descblob.has_key('event'):
                continue
            statistic_summary.setdefault(descblob['event'], 0)
            statistic_summary[descblob['event']] += 1

        yield save_statistics(StatisticsSchedule.collection_start_datetime,
                              current_time, statistic_summary)

        RecentEventsCollection.RecentEventQueue = []
        StatisticsSchedule.collection_start_datetime = current_time

        log.debug("Saved stats and time updated, keys saved %d" %
                  len(statistic_summary.keys()))


class ResourceChecker(GLJob):
    """
    ResourceChecker is a scheduled job that verify the available
    resources in the GlobaLeaks box.
    At the moment is implemented only a monitor for the disk space,
    because the files that might be uploaded depend directly from
    this resource.
    """

    @classmethod
    def get_free_space(cls):
        statvfs = os.statvfs(GLSetting.working_path)
        free_mega_bytes = statvfs.f_frsize * statvfs.f_bavail / (1024 * 1024)
        return free_mega_bytes

    def operation(self):

        from globaleaks.anomaly import Alarm
        free_mega_bytes = ResourceChecker.get_free_space()

        alarm = Alarm()
        alarm.report_disk_usage(free_mega_bytes)
