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
"""Generic script objects.

TODO: The various mixins assume that they're used by BaseScript.
Either every child object will need self.config, or these need some
work.

TODO: The mixin names kind of need work too?
"""

import codecs
import os
import platform
import pprint
import re
import shutil
import subprocess
import sys
import urllib2

try:
    import simplejson as json
except ImportError:
    import json

from mozharness.base.config import BaseConfig
from mozharness.base.log import SimpleFileLogger, MultiFileLogger, \
                                LogMixin, DEBUG, INFO, WARNING, ERROR, \
                                CRITICAL, FATAL, IGNORE
from mozharness.base.errors import HgErrorList

# OSMixin {{{1
class OSMixin(object):
    """Filesystem commands and the like.

    Currently dependent on LogMixin, and a self.config of some sort.
    """
    def mkdir_p(self, path):
        if not os.path.exists(path):
            self.info("mkdir: %s" % path)
            if not self.config.get('noop'):
                os.makedirs(path)
        else:
            self.debug("mkdir_p: %s Already exists." % path)

    def rmtree(self, path, log_level=INFO, error_level=ERROR,
               exit_code=-1):
        self.log("rmtree: %s" % path, level=log_level)
        if os.path.exists(path):
            if not self.config.get('noop'):
                if os.path.isdir(path):
                    if self._is_windows():
                        self._rmdir_recursive(path)
                    else:
                        shutil.rmtree(path)
                else:
                    os.remove(path)
                if os.path.exists(path):
                    self.log('Unable to remove %s!' % path, level=error_level,
                             exit_code=exit_code)
                    return -1
        else:
            self.debug("%s doesn't exist." % path)
        return 0

    def _is_windows(self):
        if platform.system() in ("Windows",):
            return True
        if platform.system().startswith("CYGWIN"):
            return True

    def _rmdir_recursive(self, path):
        """This is a replacement for shutil.rmtree that works better under
        windows. Thanks to Bear at the OSAF for the code."""
        if not os.path.exists(path):
            return

        # Verify the directory is read/write/execute for the current user
        os.chmod(path, 0700)

        for name in os.listdir(path):
            full_name = os.path.join(path, name)
            # on Windows, if we don't have write permission we can't remove
            # the file/directory either, so turn that on
            if self._is_windows():
                if not os.access(full_name, os.W_OK):
                    # I think this is now redundant, but I don't have an NT
                    # machine to test on, so I'm going to leave it in place
                    # -warner
                    os.chmod(full_name, 0600)
            if os.path.islink(full_name):
                os.remove(full_name) # as suggested in bug #792
            elif os.path.isdir(full_name):
                self._rmdir_recursive(full_name)
            else:
                if os.path.isfile(full_name):
                    os.chmod(full_name, 0700)
                os.remove(full_name)
        os.rmdir(path)

    # http://www.techniqal.com/blog/2008/07/31/python-file-read-write-with-urllib2/
    # TODO thinking about creating a transfer object.
    def download_file(self, url, file_name=None,
                     error_level=ERROR, exit_code=-1):
        """Python wget.
        TODO: option to mkdir_p dirname(file_name) if it doesn't exist.
        TODO: should noop touch the filename? seems counter-noop.
        """
        if not file_name:
            file_name = os.path.basename(url)
        if self.config.get('noop'):
            self.info("Downloading %s" % url)
            return file_name
        req = urllib2.Request(url)
        try:
            self.info("Downloading %s" % url)
            f = urllib2.urlopen(req)
            local_file = open(file_name, 'w')
            local_file.write(f.read())
            local_file.close()
        except urllib2.HTTPError, e:
            self.log("HTTP Error: %s %s" % (e.code, url), level=error_level,
                     exit_code=exit_code)
            return
        except urllib2.URLError, e:
            self.log("URL Error: %s" % (url), level=error_level,
                     exit_code=exit_code)
            return
        return file_name

    def move(self, src, dest, log_level="info", error_level="error",
             exit_code=-1):
        self.log("Moving %s to %s" % (src, dest), level=log_level)
        if not self.config.get('noop'):
            try:
                shutil.move(src, dest)
            # http://docs.python.org/tutorial/errors.html
            except IOError as (errno, strerror):
                self.log("IO error({0}): {1}".format(errno, strerror),
                         level=error_level, exit_code=exit_code)
                return -1
        return 0

    def chmod(self, path, mode):
        self.info("Chmoding %s to %s" % (path, str(oct(mode))))
        if not self.config.get('noop'):
            os.chmod(path, mode)

    def copyfile(self, src, dest, log_level=INFO, error_level=ERROR):
        self.log("Copying %s to %s" % (src, dest), level=log_level)
        if not self.config.get('noop'):
            try:
                shutil.copyfile(src, dest)
            except (IOError, shutil.Error):
                self.dump_exception("Can't copy %s to %s!" % (src, dest),
                                    level=error_level)

    def chdir(self, dir_name, ignore_if_noop=False):
        self.log("Changing directory to %s." % dir_name)
        if self.config.get('noop') and ignore_if_noop:
            self.info("noop: not changing dir")
        else:
            os.chdir(dir_name)

# ShellMixin {{{1
class ShellMixin(object):
    """These are very special but very complex methods that, together with
    logging and config, provide the base for all scripts in this harness.

    This is currently dependent on LogMixin and OSMixin, and assumes that
    there is a self.config of some sort.
    """
    def __init__(self):
        self.env = None

    def query_env(self, partial_env=None, replace_dict=None):
        """Environment query/generation method.

        The default, self.query_env(), will look for self.config['env']
        and replace any special strings in there ( %(PATH)s ).
        It will then store it as self.env for speeding things up later.

        If you specify partial_env, partial_env will be used instead of
        self.config['env'], and we don't save self.env as it's a one-off.

        """
        set_self_env = False
        if partial_env is None:
            if self.env is not None:
                return self.env
            partial_env = self.config.get('env', None)
            if partial_env is None:
                partial_env = {}
            set_self_env = True
        env = os.environ.copy()
        if replace_dict is None:
            replace_dict = {}
        replace_dict['PATH'] = os.environ['PATH']
        for key in partial_env.keys():
            env[key] = partial_env[key] % replace_dict
            self.debug("ENV: %s is now %s" % (key, env[key]))
        if set_self_env:
            self.env = env
        return env

    def run_command(self, command, cwd=None, error_list=[], parse_at_end=False,
                    halt_on_failure=False, success_codes=[0],
                    env=None, return_type='status', throw_exception=False):
        """Run a command, with logging and error parsing.

        TODO: parse_at_end, contextLines
        TODO: retry_interval?
        TODO: error_level_override?
        TODO: Add a copy-pastable version of |command| if it's a list.

        error_list example:
        [{'regex': '^Error: LOL J/K', level=IGNORE},
         {'regex': '^Error:', level=ERROR, contextLines='5:5'},
         {'substr': 'THE WORLD IS ENDING', level=FATAL, contextLines='20:'}
        ]
        """
        # Get rid of this when we get rid of the scratchbox stuff
        if return_type == 'output':
            return self.get_output_from_command(command=command, cwd=cwd,
                                                halt_on_failure=halt_on_failure,
                                                env=env)
        num_errors = 0
        if cwd:
            if not os.path.isdir(cwd):
                level = ERROR
                if halt_on_failure:
                    level = FATAL
                self.log("Can't run command %s in non-existent directory %s!" % \
                         (command, cwd), level=level)
                return -1
            self.info("Running command: %s in %s" % (command, cwd))
        else:
            self.info("Running command: %s" % command)
        if self.config.get('noop'):
            self.info("(Dry run; skipping)")
            return
        shell = True
        if isinstance(command, list):
            shell = False
        p = subprocess.Popen(command, shell=shell, stdout=subprocess.PIPE,
                             cwd=cwd, stderr=subprocess.STDOUT, env=env)
        loop = True
        while loop:
            if p.poll() is not None:
                """Avoid losing the final lines of the log?"""
                loop = False
            for line in p.stdout:
                if not line or line.isspace():
                    continue
                line = line.decode("utf-8").rstrip()
                for error_check in error_list:
                    match = False
                    if 'substr' in error_check:
                        if error_check['substr'] in line:
                            match = True
                    elif 'regex' in error_check:
                        if re.search(error_check['regex'], line):
                            match = True
                    else:
                        self.warn("error_list: 'substr' and 'regex' not in %s" % \
                                  error_check)
                    if match:
                        level=error_check.get('level', INFO)
                        self.log(' %s' % line, level=level)
                        if level in (ERROR, CRITICAL, FATAL):
                            num_errors = num_errors + 1
                        break
                else:
                    self.info(' %s' % line)
        return_level = INFO
        if p.returncode not in success_codes:
            return_level = ERROR
            if throw_exception:
                raise subprocess.CalledProcessError(p.returncode, command)
        self.log("Return code: %d" % p.returncode, level=return_level)
        if return_type == 'num_errors':
            if halt_on_failure and num_errors:
                self.fatal("Halting on failure while running %s" % command,
                           exit_code=num_errors)
            return num_errors
        if halt_on_failure and p.returncode not in success_codes:
            self.fatal("Halting on failure while running %s" % command,
                       exit_code=p.returncode)
        return p.returncode

    def get_output_from_command(self, command, cwd=None,
                                halt_on_failure=False, env=None,
                                silent=False, tmpfile_base_path='tmpfile',
                                return_type='output', save_tmpfiles=False,
                                throw_exception=False):
        """Similar to run_command, but where run_command is an
        os.system(command) analog, get_output_from_command is a `command`
        analog.

        Less error checking by design, though if we figure out how to
        do it without borking the output, great.

        TODO: binary mode? silent is kinda like that.
        TODO: since p.wait() can take a long time, optionally log something
        every N seconds?
        TODO: optionally only keep the first or last (N) line(s) of output?
        TODO: optionally only return the tmp_stdout_filename?
        """
        if cwd:
            if not os.path.isdir(cwd):
                level = ERROR
                if halt_on_failure:
                    level = FATAL
                self.log("Can't run command %s in non-existent directory %s!" % \
                         (command, cwd), level=level)
                return -1
            self.info("Getting output from command: %s in %s" % (command, cwd))
        else:
            self.info("Getting output from command: %s" % command)
        # This could potentially return something?
        if self.config.get('noop'):
            self.info("(Dry run; skipping)")
            return
        pv = platform.python_version_tuple()
        python_26 = False
        tmp_stdout = None
        tmp_stderr = None
        tmp_stdout_filename = '%s_stdout' % tmpfile_base_path
        tmp_stderr_filename = '%s_stderr' % tmpfile_base_path

        # TODO probably some more elegant solution than 2 similar passes
        try:
            tmp_stdout = open(tmp_stdout_filename, 'w')
        except IOError:
            level = ERROR
            if halt_on_failure:
                level = FATAL
            self.log("Can't open %s for writing!" % tmp_stdout_filename + \
                     self.dump_exception(), level=level)
            return -1
        try:
            tmp_stderr = open(tmp_stderr_filename, 'w')
        except IOError:
            level = ERROR
            if halt_on_failure:
                level = FATAL
            self.log("Can't open %s for writing!" % tmp_stderr_filename + \
                     self.dump_exception(), level=level)
            return -1
        shell = True
        if isinstance(command, list):
            shell = False
        p = subprocess.Popen(command, shell=shell, stdout=tmp_stdout,
                             cwd=cwd, stderr=tmp_stderr, env=env)
        self.debug("Temporary files: %s and %s" % (tmp_stdout_filename, tmp_stderr_filename))
        p.wait()
        tmp_stdout.close()
        tmp_stderr.close()
        return_level = DEBUG
        output = None
        if os.path.exists(tmp_stdout_filename) and os.path.getsize(tmp_stdout_filename):
            fh = open(tmp_stdout_filename)
            output = fh.read()
            if not silent:
                self.info("Output received:")
                output_lines = output.rstrip().splitlines()
                for line in output_lines:
                    if not line or line.isspace():
                        continue
                    line = line.decode("utf-8")
                    self.info(' %s' % line)
                output = '\n'.join(output_lines)
            fh.close()
        if os.path.exists(tmp_stderr_filename) and os.path.getsize(tmp_stderr_filename):
            return_level = ERROR
            self.error("Errors received:")
            fh = open(tmp_stderr_filename)
            errors = fh.read()
            for line in errors.rstrip().splitlines():
                if not line or line.isspace():
                    continue
                line = line.decode("utf-8")
                self.error(' %s' % line)
            fh.close()
        elif p.returncode:
            return_level = ERROR
        # Clean up.
        if not save_tmpfiles:
            self.rmtree(tmp_stderr_filename)
            self.rmtree(tmp_stdout_filename)
        if p.returncode and throw_exception:
            raise subprocess.CalledProcessError(p.returncode, command)
        self.log("Return code: %d" % p.returncode, level=return_level)
        if halt_on_failure and return_level == ERROR:
            self.fatal("Halting on failure while running %s" % command,
                       exit_code=p.returncode)
        # Hm, options on how to return this? I bet often we'll want
        # output_lines[0] with no newline.
        if return_type != 'output':
            return (tmp_stdout_filename, tmp_stderr_filename)
        else:
            return output



# BaseScript {{{1
class BaseScript(ShellMixin, OSMixin, LogMixin, object):
    def __init__(self, config_options=None, default_log_level="info", **kwargs):
        super(BaseScript, self).__init__()
        self.return_code = 0
        self.log_obj = None
        self.abs_dirs = None
        if config_options is None:
            config_options = []
        self.summary_list = []
        rw_config = BaseConfig(config_options=config_options,
                               **kwargs)
        self.config = rw_config.get_read_only_config()
        self.actions = tuple(rw_config.actions)
        self.all_actions = tuple(rw_config.all_actions)
        self.env = None
        self.new_log_obj(default_log_level=default_log_level)

        # Set self.config to read-only.
        #
        # We can create intermediate config info programmatically from
        # this in a repeatable way, with logs; this is how we straddle the
        # ideal-but-not-user-friendly static config and the
        # easy-to-write-hard-to-debug writable config.
        #
        # To allow for other, script-specific configurations
        # (e.g., hgtool's buildbot props json parsing), before locking,
        # call self._pre_config_lock().  If needed, this method can
        # alter self.config.
        self._pre_config_lock(rw_config)
        self._config_lock()

        self.info("Run as %s" % rw_config.command_line)

    def _pre_config_lock(self, rw_config):
        pass

    def _config_lock(self):
        self.config.lock()

    def _possibly_run_method(self, method_name, error_if_missing=False):
        if hasattr(self, method_name) and callable(getattr(self, method_name)):
            return getattr(self, method_name)()
        elif error_if_missing:
            self.error("No such method %s!" % method_name)

    def run(self):
        """Default run method.
        This is the "do everything" method, based on actions and all_actions.

        First run self.dump_config() if it exists.
        Second, go through the list of all_actions.
        If they're in the list of self.actions, try to run
        self.preflight_ACTION(), self.ACTION(), and self.postflight_ACTION().

        Preflight is sanity checking before doing anything time consuming or
        destructive.

        Postflight is quick testing for success after an action.

        Run self.summary() at the end.

        """
        self.dump_config()
        for action in self.all_actions:
            if action not in self.actions:
                self.action_message("Skipping %s step." % action)
            else:
                method_name = action.replace("-", "_")
                self.action_message("Running %s step." % action)
                self._possibly_run_method("preflight_%s" % method_name)
                self._possibly_run_method(method_name, error_if_missing=True)
                self._possibly_run_method("postflight_%s" % method_name)
        self.summary()
        dirs = self.query_abs_dirs()
        self.info("Copying logs to upload dir...")
        for log_name in self.log_obj.log_files.keys():
            log_file = self.log_obj.log_files[log_name]
            self.copy_to_upload_dir(os.path.join(dirs['abs_log_dir'], log_file),
                                    dest=os.path.join('logs', log_file),
                                    short_desc='%s log' % log_name,
                                    long_desc='%s log' % log_name,
                                    rotate=True)
        self.copy_to_upload_dir(os.path.join(self.config['base_work_dir'],
                                             'localconfig.json'),
                                rotate=True)
        sys.exit(self.return_code)

    def query_abs_dirs(self):
        if self.abs_dirs:
            return self.abs_dirs
        c = self.config
        dirs = {}
        dirs['abs_work_dir'] = os.path.join(c['base_work_dir'], c['work_dir'])
        dirs['abs_upload_dir'] = os.path.join(dirs['abs_work_dir'], 'upload')
        dirs['abs_log_dir'] = os.path.join(c['base_work_dir'], c.get('log_dir', 'logs'))
        self.abs_dirs = dirs
        return self.abs_dirs

    def dump_config(self, file_path=None):
        c = self.config
        if not file_path:
            file_path = os.path.join(c['base_work_dir'], "localconfig.json")
        self.info("Dumping config to %s." % file_path)
        json_config = json.dumps(self.config, sort_keys=True, indent=4)
        fh = codecs.open(file_path, encoding='utf-8', mode='w+')
        fh.write(json_config)
        fh.close()
        self.info(pprint.pformat(self.config))

    # logging {{{2
    def new_log_obj(self, default_log_level="info"):
        dirs = self.query_abs_dirs()
        log_config = {"logger_name": 'Simple',
                      "log_name": 'log',
                      "log_dir": dirs['abs_log_dir'],
                      "log_level": default_log_level,
                      "log_format": '%(asctime)s %(levelname)8s - %(message)s',
                      "log_to_console": True,
                      "append_to_log": False,
                     }
        log_type = self.config.get("log_type", "multi")
        if log_type == "multi":
            log_config['logger_name'] = 'Multi'
        for key in log_config.keys():
            value = self.config.get(key, None)
            if value is not None:
                log_config[key] = value
        if log_type == "multi":
            self.log_obj = MultiFileLogger(**log_config)
        else:
            self.log_obj = SimpleFileLogger(**log_config)

    def action_message(self, message):
        self.info("#####")
        self.info("##### %s" % message)
        self.info("#####")

    def summary(self):
        self.action_message("%s summary:" % self.__class__.__name__)
        if self.summary_list:
            for item in self.summary_list:
                try:
                    self.log(item['message'], level=item['level'])
                except ValueError:
                    """log is closed; print as a default. Ran into this
                    when calling from __del__()"""
                    print "### Log is closed! (%s)" % item['message']

    def add_summary(self, message, level=INFO):
        self.summary_list.append({'message': message, 'level': level})
        # TODO write to a summary-only log?
        # Summaries need a lot more love.
        self.log(message, level=level)

    def copy_to_upload_dir(self, target, dest=None, short_desc="unknown",
                           long_desc="unknown",
                           log_level=DEBUG, error_level=ERROR,
                           rotate=False, max_backups=10):
        """Copy target file to upload_dir/dest.

        Potentially update a manifest in the future if we go that route.

        Currently only copies a single file; would be nice to allow for
        recursive copying; that would probably done by creating a helper
        _copy_file_to_upload_dir().

        short_desc and long_desc are placeholders for if/when we add
        upload_dir manifests.
        """
        dirs = self.query_abs_dirs()
        if dest is None:
            dest = os.path.basename(target)
        if dest.endswith('/'):
            dest_file = os.path.basename(target)
            dest_dir = os.path.join(dirs['abs_upload_dir'], dest)
        else:
            dest_file = os.path.basename(dest)
            dest_dir = os.path.join(dirs['abs_upload_dir'], os.path.dirname(dest))
        dest = os.path.join(dest_dir, dest_file)
        if not os.path.exists(target):
            self.log("%s doesn't exist!" % target, level=error_level)
            return None
        self.mkdir_p(dest_dir)
        if os.path.exists(dest):
            if os.path.isdir(dest):
                self.log("%s exists and is a directory!" % dest, level=error_level)
                return -1
            if rotate:
                # Probably a better way to do this
                oldest_backup = 0
                backup_regex = re.compile("^%s\.(\d+)$" % dest_file)
                for filename in os.listdir(dest_dir):
                    r = re.match(backup_regex, filename)
                    if r and r.groups()[0] > oldest_backup:
                        oldest_backup = r.groups()[0]
                if oldest_backup > 0:
                    for backup_num in range(int(oldest_backup), 0, -1):
                        # TODO more error checking?
                        if backup_num >= max_backups:
                            self.rmtree(os.path.join(dest_dir, dest_file,
                                                     str(backup_num)),
                                        log_level=DEBUG)
                        else:
                            self.move(os.path.join(dest_dir, '%s.%s' % (dest_file, str(backup_num))),
                                      os.path.join(dest_dir, '%s.%s' % (dest_file, str(backup_num + 1))),
                                      log_level=DEBUG)
                if self.move(dest, "%s.1" % dest, log_level=DEBUG):
                    self.log("Unable to move %s!" % dest, level=error_level)
                    return -1
            else:
                if self.rmtree(dest, log_level=DEBUG):
                    self.log("Unable to remove %s!" % dest, level=error_level)
                    return -1
        self.copyfile(target, dest, log_level=DEBUG)
        if os.path.exists(dest):
            return dest
        else:
            self.log("%s doesn't exist after copy!" % dest, level=error_level)
            return None



# __main__ {{{1
if __name__ == '__main__':
    pass
