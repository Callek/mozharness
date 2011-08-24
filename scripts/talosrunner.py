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
"""talosrunner.py

Set up and run talos.
"""

import os
import sys

sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.errors import PythonErrorList
from mozharness.base.python import virtualenv_config_options, VirtualenvMixin
from mozharness.base.vcs.vcsbase import MercurialScript

# TalosRunner {{{1
class TalosRunner(VirtualenvMixin, MercurialScript):
    config_options = [[
     ["--talos-repo"],
     {"action": "store",
      "dest": "talos_repo",
      "default": "http://hg.mozilla.org/build/talos",
      "help": "Specify the talos repo"
     }
    ],[
     ["--talos-tag", "--talos-tag"],
     {"action": "store",
      "dest": "talos_tag",
      "default": "default",
      "help": "Specify the talos tag"
     }
    ],[
     ["--yaml-url"],
     {"action": "store",
      "dest": "mercurial_url",
      "default": "http://pypi.python.org/packages/source/P/PyYAML/PyYAML-3.10.tar.gz#md5=74c94a383886519e9e7b3dd1ee540247",
      "help": "Specify the mercurial pip url"
     }
    ]] + virtualenv_config_options

    def __init__(self, require_config_file=False):
        self.python = None
        super(TalosRunner, self).__init__(
         config_options=self.config_options,
         all_actions=['preclean',
                      'pull',
                      'create-virtualenv',
                      'download',
                      'run-talos',
# TODO
#                      'upload',
#                      'notify',
                      ],
         default_actions=['preclean',
                          'pull',
                          'download',
                          'run-talos',
                          ],
         require_config_file=require_config_file,
         config={"virtualenv_modules": ["PyYAML"]},
        )

    def _clobber(self):
        dirs = self.query_abs_dirs()
        self.rmtree(dirs['abs_work_dir'])

    def preclean(self):
        self._clobber()

    def pull(self):
        c = self.config
        self.vcs_checkout_repos([{
         "repo": c['talos_repo'],
         "tag": c['talos_tag'],
         "dest": "talos"
        }])

    def download(self):
        pass

    def run_talos(self):
        dirs = self.query_abs_dirs()
        python = self.query_python_path()
        version_dict = self.query_versions()
        TalosList = PythonErrorList[:]

# __main__ {{{1
if __name__ == '__main__':
    talos_runner = TalosRunner()
    talos_runner.run()
