#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla.
#
# The Initial Developer of the Original Code is
# the Mozilla Foundation <http://www.mozilla.org/>.
# Portions created by the Initial Developer are Copyright (C) 2011
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Aki Sasaki <aki@mozilla.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
"""Generic logging, the way I remember it from scripts gone by.

TODO:
- network logging support.
- log rotation config
"""

from datetime import datetime
import logging
import os
import sys
import traceback

# Define our own FATAL_LEVEL
FATAL_LEVEL = logging.CRITICAL + 10
logging.addLevelName(FATAL_LEVEL, 'FATAL')

# mozharness log levels.
DEBUG, INFO, WARNING, ERROR, CRITICAL, FATAL, IGNORE = (
    'debug', 'info', 'warning', 'error', 'critical', 'fatal', 'ignore')



# LogMixin {{{1
class LogMixin(object):
    """This is a mixin for any object to access similar logging
    functionality -- more so, of course, for those objects with
    self.config and self.log_obj, of course.
    """

    def _log_level_at_least(self, level):
        log_level = INFO
        levels = [DEBUG, INFO, WARNING, ERROR, CRITICAL, FATAL]
        if hasattr(self, 'config'):
            log_level = self.config.get('log_level', INFO)
        return levels.index(level) >= levels.index(log_level)

    def _print(self, message, stderr=False):
        if not hasattr(self, 'config') or self.config.get('log_to_console', True):
            if stderr:
                print >> sys.stderr, message
            else:
                print message

    def log(self, message, level=INFO, exit_code=-1):
        if self.log_obj:
            return self.log_obj.log_message(message, level=level,
                                            exit_code=exit_code)
        if level == INFO:
            if self._log_level_at_least(level):
                self._print(message)
        elif level == DEBUG:
            if self._log_level_at_least(level):
                self._print('DEBUG: %s' % message)
        elif level in (WARNING, ERROR, CRITICAL):
            if self._log_level_at_least(level):
                self._print("%s: %s" % (level.upper(), message), stderr=True)
        elif level == FATAL:
            if self._log_level_at_least(level):
                self._print("FATAL: %s" % message, stderr=True)
                raise SystemExit(exit_code)

    # Copying Bear's dumpException():
    # http://hg.mozilla.org/build/tools/annotate/1485f23c38e0/sut_tools/sut_lib.py#l23
    def dump_exception(self, message=None, level=ERROR):
        tb_type, tb_value, tb_traceback = sys.exc_info()
        if message is None:
            message = ""
        else:
            message = "%s\n" % message
        for s in traceback.format_exception(tb_type, tb_value, tb_traceback):
            message += "%s\n" % s
        # Log at the end, as a fatal will attempt to exit after the 1st line.
        self.log(message, level=level)

    def debug(self, message):
        self.log(message, level=DEBUG)

    def info(self, message):
        self.log(message, level=INFO)

    def warning(self, message):
        self.log(message, level=WARNING)

    def error(self, message):
        self.log(message, level=ERROR)

    def critical(self, message):
        self.log(message, level=CRITICAL)

    def fatal(self, message, exit_code=-1):
        self.log(message, level=FATAL, exit_code=exit_code)


# BaseLogger {{{1
class BaseLogger(object):
    """Create a base logging class.
    TODO: status? There may be a status object or status capability in
    either logging or config that allows you to count the number of
    error,critical,fatal messages for us to count up at the end (aiming
    for 0).
    """
    LEVELS = {DEBUG: logging.DEBUG,
              INFO: logging.INFO,
              WARNING: logging.WARNING,
              ERROR: logging.ERROR,
              CRITICAL: logging.CRITICAL,
              FATAL: FATAL_LEVEL
             }

    def __init__(self, log_level=INFO,
                 log_format='%(message)s',
                 log_date_format='%H:%M:%S',
                 log_name='test',
                 log_to_console=True,
                 log_dir='.',
                 log_to_raw=False,
                 logger_name='',
                 halt_on_failure=True,
                 append_to_log=False,
                ):
        self.halt_on_failure = halt_on_failure,
        self.log_format = log_format
        self.log_date_format = log_date_format
        self.log_to_console = log_to_console
        self.log_to_raw = log_to_raw
        self.log_level = log_level
        self.log_name = log_name
        self.log_dir = log_dir
        self.append_to_log = append_to_log

        # Not sure what I'm going to use this for; useless unless we
        # can have multiple logging objects that don't trample each other
        self.logger_name = logger_name

        self.all_handlers = []
        self.log_files = {}

        self.create_log_dir()

    def create_log_dir(self):
        if os.path.exists(self.log_dir):
            if not os.path.isdir(self.log_dir):
                os.remove(self.log_dir)
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        self.abs_log_dir = os.path.abspath(self.log_dir)

    def init_message(self, name=None):
        if not name:
            name = self.__class__.__name__
        self.log_message("%s online at %s in %s" % \
                         (name, datetime.now().strftime("%Y%m%d %H:%M:%S"),
                         os.getcwd()))

    def get_logger_level(self, level=None):
        if not level:
            level = self.log_level
        return self.LEVELS.get(level, logging.NOTSET)

    def get_log_formatter(self, log_format=None, date_format=None):
        if not log_format:
            log_format = self.log_format
        if not date_format:
            date_format = self.log_date_format
        return logging.Formatter(log_format, date_format)

    def new_logger(self, logger_name):
        """Create a new logger.
        By default there are no handlers.
        """
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(self.get_logger_level())
        self._clear_handlers()
        if self.log_to_console:
            self.add_console_handler()
        if self.log_to_raw:
            self.log_files['raw'] = '%s_raw.log' % self.log_name
            self.add_file_handler(os.path.join(self.abs_log_dir,
                                               self.log_files['raw']),
                                 log_format='%(message)s')

    def _clear_handlers(self):
        """To prevent dups -- logging will preserve Handlers across
        objects :(
        """
        attrs = dir(self)
        if 'all_handlers' in attrs and 'logger' in attrs:
            for handler in self.all_handlers:
                self.logger.removeHandler(handler)
            self.all_handlers = []

    def __del__(self):
        logging.shutdown()
        self._clear_handlers()

    def add_console_handler(self, log_level=None, log_format=None,
                          date_format=None):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.get_logger_level(log_level))
        console_handler.setFormatter(self.get_log_formatter(log_format=log_format,
                                                            date_format=date_format))
        self.logger.addHandler(console_handler)
        self.all_handlers.append(console_handler)

    def add_file_handler(self, log_path, log_level=None, log_format=None,
                       date_format=None):
        if not self.append_to_log and os.path.exists(log_path):
            os.remove(log_path)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(self.get_logger_level(log_level))
        file_handler.setFormatter(self.get_log_formatter(log_format=log_format,
                                                         date_format=date_format))
        self.logger.addHandler(file_handler)
        self.all_handlers.append(file_handler)

    def log_message(self, message, level=INFO, exit_code=-1):
        """Generic log method.
        There should be more options here -- do or don't split by line,
        use os.linesep instead of assuming \n, be able to pass in log level
        by name or number.

        Adding the IGNORE special level for runCommand.
        """
        if level == IGNORE:
            return
        for line in message.splitlines():
            self.logger.log(self.get_logger_level(level), line)
        if level == FATAL and self.halt_on_failure:
            self.logger.log(FATAL_LEVEL, 'Exiting %d' % exit_code)
            raise SystemExit(exit_code)



# SimpleFileLogger {{{1
class SimpleFileLogger(BaseLogger):
    """Create one logFile.  Possibly also output to
    the terminal and a raw log (no prepending of level or date)
    """
    def __init__(self,
                 log_format='%(asctime)s %(levelname)8s - %(message)s',
                 logger_name='Simple', log_dir='logs', **kwargs):
        BaseLogger.__init__(self, logger_name=logger_name, log_format=log_format,
                            log_dir=log_dir, **kwargs)
        self.new_logger(self.logger_name)
        self.init_message()

    def new_logger(self, logger_name):
        BaseLogger.new_logger(self, logger_name)
        self.log_path = os.path.join(self.abs_log_dir, '%s.log' % self.log_name)
        self.log_files['default'] = self.log_path
        self.add_file_handler(self.log_path)




# MultiFileLogger {{{1
class MultiFileLogger(BaseLogger):
    """Create a log per log level in log_dir.  Possibly also output to
    the terminal and a raw log (no prepending of level or date)
    """
    def __init__(self, logger_name='Multi',
                 log_format='%(asctime)s %(levelname)8s - %(message)s',
                 log_dir='logs', log_to_raw=True, **kwargs):
        BaseLogger.__init__(self, logger_name=logger_name,
                            log_format=log_format,
                            log_to_raw=log_to_raw, log_dir=log_dir,
                            **kwargs)

        self.new_logger(self.logger_name)
        self.init_message()

    def new_logger(self, logger_name):
        BaseLogger.new_logger(self, logger_name)
        min_logger_level = self.get_logger_level(self.log_level)
        for level in self.LEVELS.keys():
            if self.get_logger_level(level) >= min_logger_level:
                self.log_files[level] = '%s_%s.log' % (self.log_name,
                                                       level)
                self.add_file_handler(os.path.join(self.abs_log_dir,
                                                   self.log_files[level]),
                                      log_level=level)



# __main__ {{{1

if __name__ == '__main__':
    pass
