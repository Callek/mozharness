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
#   Chris Atlee <catlee@mozilla.com>
#   Syed Albiz <salbiz@mozilla.com>
#   Ben Hearsum <bhearsum@mozilla.com>
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
"""sourcetool.py

Port of tools/buildfarm/utils/hgtool.py.

TODO: sourcetool.py currently ignores work_dir completely.
Maybe we should use it instead of dest ?
Maybe I need to rethink work_dir?
"""

import os
import pprint
import sys
try:
    import simplejson as json
except ImportError:
    import json

sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.config import parse_config_file
from mozharness.base.script import BaseScript
from mozharness.base.vcs.mercurial import MercurialVCS

# These variables allow us to create a sourcetool.py that will [hopefully]
# work with a selection of VCSs.
#
# To avoid needing to specify --vcs VCS, softlink sourcetool.py to
# VCStool.py (where VCS is the VCS you want to use, and is a member of
# VCS_CHOICES).
VCS_CHOICES = ['hg',]
VCS_DEFAULT = None
VCS_REQUIRED_OPTION = "--vcs VCS "
VCS_NAME = os.path.basename(sys.argv[0]).replace('tool.py', '')
if VCS_NAME in VCS_CHOICES:
    VCS_DEFAULT = VCS_NAME
    VCS_REQUIRED_OPTION = ""
SOURCE_TOOL_USAGE = """Usage:
    %%prog [options] %srepo [dest]

    %%prog %s--repo REPOSITORY [options]

    %%prog [-h|--help]""" % (VCS_REQUIRED_OPTION, VCS_REQUIRED_OPTION)

# SourceTool {{{1
class SourceTool(BaseScript):
    # These options were chosen with an eye towards backwards
    # compatibility with the existing hgtool.
    #
    # TODO: get rid of env options, or at least remove HG from the names.
    config_options = [[
     ["--rev", "-r"],
     {"action": "store",
      "dest": "vcs_revision",
      "default": os.environ.get('HG_REV'),
      "help": "Specify which revision to update to."
     }
    ],[
     ["--branch", "-b"],
     {"action": "store",
      "dest": "vcs_branch",
      "default": os.environ.get('HG_BRANCH', 'default'),
      "help": "Specify which branch to update to."
     }
    ],[
     # Comment this out til we have more options.
     ["--vcs",],
     {"action": "store",
      "type": "choice",
      "dest": "vcs",
      "default": VCS_DEFAULT,
      "choices": VCS_CHOICES,
      "help": "Specify which VCS to use."
     }
    ],[
     ["--props-file", "-p"],
     {"action": "store",
      "dest": "vcs_propsfile",
      "default": os.environ.get('PROPERTIES_FILE'),
      "help": "build json file containing revision information"
     }
    ],[
     # TODO --tbox and --no-tbox should DIAF once we fix bug 630538.
     ["--tbox",],
     {"action": "store_true",
      "dest": "tbox_output",
      "default": bool(os.environ.get('PROPERTIES_FILE')),
      "help": "Output TinderboxPrint messages."
     }
    ],[
     ["--no-tbox",],
     {"action": "store_false",
      "dest": "tbox_output",
      "help": "Don't output TinderboxPrint messages."
     }
    ],[
     ["--repo",],
     {"action": "store",
      "dest": "vcs_repo",
      "help": "Specify the VCS repo."
     }
    ],[
     ["--dest",],
     {"action": "store",
      "dest": "vcs_dest",
      "help": "Specify the destination directory (optional)"
     }
    ],[
     # TODO Are the shared options HG-specific?
     # I think there are, or we can create, similar behavior in other
     # VCSs.
     ["--shared-dir", '-s'],
     {"action": "store",
      "dest": "vcs_shared_dir",
      "default": os.environ.get('HG_SHARE_BASE_DIR'),
      "help": "clone to a shared directory"
     }
    ],[
     ["--allow-unshared-local-clones",],
     {"action": "store_true",
      "dest": "vcs_allow_unshared_local_clones",
      "default": False,
      "help": "Allow unshared checkouts if --shared-dir is specified"
     }
    ],[
     ["--check-outgoing",],
     {"action": "store_true",
      "dest": "vcs_strip_outgoing",
      "default": False,
      "help": "check for and clobber outgoing changesets"
     }
    ]]

    def __init__(self, require_config_file=False):
        BaseScript.__init__(self, config_options=self.config_options,
                            all_actions=['source',],
                            usage=SOURCE_TOOL_USAGE,
                            require_config_file=require_config_file)

    def _pre_config_lock(self, rw_config):
        # This is a workaround for legacy compatibility with the original
        # hgtool.py.
        #
        # Since we need to read the buildbot json props, as well as parse
        # additional commandline arguments that aren't specified via
        # options, we call this function before locking the config.
        #
        # rw_config is the BaseConfig object that parsed the options;
        # self.config is the soon-to-be-locked runtime configuration.
        #
        # This is a powerful way to hack the config before locking;
        # we need to be careful not to abuse it.
        args = rw_config.args
        c = self.config
        if c.get('vcs') is None:
            self.fatal("Must specify --vcs!\n\n%s" % \
                       rw_config.config_parser.format_help())
        if c.get('vcs_repo') is None:
            if len(args) not in (1, 2):
                self.fatal("""Invalid number of arguments!
You need to either specify --repo or specify it after the options:
%s""" % rw_config.config_parser.get_usage())

            self.config['vcs_repo'] = args[0]
        if len(args) == 2:
            self.config['vcs_dest'] = args[1]
        elif not self.config.get('vcs_dest'):
            self.config['vcs_dest'] = os.path.basename(self.config['vcs_repo'])

        # This is a buildbot-specific props file.
        if self.config.get('vcs_propsfile'):
            js = parse_config_file(self.config['vcs_propsfile'])
            if self.config.get('vcs_revision') is None:
                self.config['vcs_revision'] = js['sourcestamp']['revision']
            if self.config.get('vcs_branch') is None:
                self.config['vcs_branch'] = js['sourcestamp']['branch']

    def source(self):
        c = self.config
        vcs_obj = None
        if self.config['vcs'] == 'hg':
            vcs_obj = MercurialVCS(
             log_obj=self.log_obj,
             #
             # Torn between creating a smaller, more flexible config per
             # helper object, or passing the read-only master config as
             # vcs_obj.config and creating a smaller vcs_obj.vcs_config.
             #
             # Deciding on the latter for now, while reserving the right
             # to change my mind later.
             config=self.config,
             vcs_config={
              'repo': self.config['vcs_repo'],
              'dest': self.config['vcs_dest'],
              'branch': self.config.get('vcs_branch'),
              'revision': self.config.get('vcs_revision'),
              'share_base': self.config.get('vcs_shared_dir'),
              'allow_unshared_local_clones': self.config.get('vcs_allow_unshared_local_clones'),
              'halt_on_failure': self.config.get('halt_on_failure', True),
              'noop': self.config.get('noop'),
             }
            )
        else:
            self.fatal("I don't know how to handle vcs '%s'!" % self.config['vcs'])
        got_revision = vcs_obj.ensure_repo_and_revision()

        self.add_summary("Got revision %s\n" % got_revision)
        if c.get('tbox_output'):
            if c['vcs_repo'].startswith("http"):
                url = "%s/rev/%s" % (c['vcs_repo'], got_revision)
                msg = "<a href=\"%(url)s\">revision: %(got_revision)s</a>" % locals()
                self.add_summary(msg)
            else:
                msg = "revision: %s" % got_revision

            # Print as well as info() to make sure we get the TinderboxPrint
            # sans any log prefixes.
            print "TinderboxPrint: %s" % msg

# __main__ {{{1
if __name__ == '__main__':
    source_tool = SourceTool()
    source_tool.run()
