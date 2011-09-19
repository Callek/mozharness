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
"""device_talosrunner.py

Set up and run talos against a device running SUT Agent or ADBD.
"""

import os
import re
import sys

sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.errors import PythonErrorList
from mozharness.base.python import virtualenv_config_options, VirtualenvMixin
from mozharness.base.vcs.vcsbase import MercurialScript
from mozharness.test.device import device_config_options, ADBDevice

# DeviceTalosRunner {{{1
class DeviceTalosRunner(VirtualenvMixin, MercurialScript):
    config_options = [[
     ["--talos-zip"],
     {"action": "store",
      "dest": "talos_zip",
      # TODO remove all defaults here
#      "default": "http://people.mozilla.org/~asasaki/talos_ADB.zip",
      "default": "file:///Users/asasaki/Desktop/talos_ADB.zip",
      "help": "Specify a talos zipfile"
     }
    ],[
     ["--talos-repo"],
     {"action": "store",
      "dest": "talos_repo",
      "default": "http://hg.mozilla.org/build/talos",
      "help": "Specify the talos repo"
     }
    ],[
     ["--talos-tag"],
     {"action": "store",
      "dest": "talos_tag",
      "default": "default",
      "help": "Specify the talos tag"
     }
    ],[
     ["--installer-url", "--url"],
     {"action": "store",
      "dest": "installer_url",
      # TODO: wildcard download?
#      "default": "http://ftp.mozilla.org/pub/mozilla.org/mobile/nightly/latest-mozilla-central-android/fennec-9.0a1.multi.android-arm.apk",
      "default": "file:///Users/asasaki/Desktop/fennec-8.0a2.multi.android-arm.apk",
      "help": "Specify the url to the installer"
     }
    ],[
     ["--yaml-url"],
     {"action": "store",
      "dest": "mercurial_url",
      "default": "http://pypi.python.org/packages/source/P/PyYAML/PyYAML-3.10.tar.gz#md5=74c94a383886519e9e7b3dd1ee540247",
      "help": "Specify the mercurial pip url"
     }
    ]] + virtualenv_config_options + device_config_options

    def __init__(self, require_config_file=False):
        self.python = None
        super(DeviceTalosRunner, self).__init__(
         config_options=self.config_options,
         all_actions=['preclean',
                      'pull',
                      'create-virtualenv',
                      'check-device',
# TODO
# cleanup device
                      'download',
# unpack
# tinderbox print revision
# fennecmark for tpan/tzoom
# pageloader
# install app on device
# perfconfigurator
                      'run-talos',
# reboot device
#                      'upload',
#                      'notify',
                      ],
         default_actions=['preclean',
                          'pull',
                          'check-device',
                          'download',
                          'run-talos',
                          ],
         require_config_file=require_config_file,
         config={"virtualenv_modules": ["PyYAML"]},
        )
        self.device_glue = ADBDevice(log_obj=self.log_obj,
                                     config=self.config)

    def query_abs_dirs(self):
        if self.abs_dirs:
            return self.abs_dirs
        abs_dirs = super(DeviceTalosRunner, self).query_abs_dirs()
        c = self.config
        dirs = {}
        dirs['abs_talos_dir'] = os.path.join(abs_dirs['abs_work_dir'],
                                             'talos')
        if c.get('device_flag_dir'):
            # Assumes abs_path ?
            dirs['abs_device_flag_dir'] = c['device_flag_dir']
        else:
            # May need to revisit this default ?
            dirs['abs_device_flag_dir'] = c['base_work_dir']
        for key in dirs.keys():
            if key not in abs_dirs:
                abs_dirs[key] = dirs[key]
        self.abs_dirs = abs_dirs
        return self.abs_dirs

    def _clobber(self):
        dirs = self.query_abs_dirs()
        self.rmtree(dirs['abs_work_dir'])

    def preclean(self):
        self._clobber()

    def pull(self):
        c = self.config
        dirs = self.query_abs_dirs()
        # TODO allow for a talos zip
        if c['talos_zip']:
            self.mkdir_p(dirs['abs_work_dir'])
            status = self.download_file(
                c['talos_zip'],
                file_name=os.path.join(dirs['abs_work_dir'],
                                       "talos.zip")
            )
            # TODO extract
        else:
            self.vcs_checkout_repos([{
             "repo": c['talos_repo'],
             "tag": c['talos_tag'],
             "dest": "talos"
            }])

    def check_device(self):
        # TODO writeme
        pass

    def download(self):
        # TODO: a user friendly way to do this without specifying a url?
        c = self.config
        dirs = self.query_abs_dirs()
        self.mkdir_p(dirs["abs_work_dir"])
        self.chdir(dirs["abs_work_dir"])
        file_name = os.path.basename(c['installer_url'])
        m = re.match(r'([a-zA-Z0-9]*).*\.([^.]*)', file_name)
        if m.group(1) and m.group(2):
            file_name = '%s.%s' % (m.group(1), m.group(2))
        self.download_file(c['installer_url'], file_name=file_name,
                           error_level="fatal")

    def run_talos(self):
        dirs = self.query_abs_dirs()
        python = self.query_python_path()
        TalosList = PythonErrorList[:]

# __main__ {{{1
if __name__ == '__main__':
    device_talos_runner = DeviceTalosRunner()
    device_talos_runner.run()
