# -*- coding: utf-8
# Implement reset of variables related to sessions
from globaleaks.jobs.job import LoopingJob

__all__ = ['SessionManagement']


class SessionManagement(LoopingJob):
    interval = 60
    monitor_interval = 10

    def operation(self):
        """
        This scheduler is responsible for:
            - Reset of failed login attempts counters
        """
        self.state.settings.failed_login_attempts.clear()
