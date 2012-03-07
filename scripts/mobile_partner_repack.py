#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****
"""mobile_partner_repack.py

"""

from copy import deepcopy
import os
import sys

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.errors import BaseErrorList, SSHErrorList
from mozharness.base.log import OutputParser, ERROR, FATAL, IGNORE
from mozharness.mozilla.release import ReleaseMixin
from mozharness.base.vcs.vcsbase import MercurialScript
from mozharness.mozilla.l10n.locales import LocalesMixin

# So far this only references the ftp platform name.
SUPPORTED_PLATFORMS = ["android"]



# MobilePartnerRepack {{{1
class MobilePartnerRepack(LocalesMixin, ReleaseMixin, MercurialScript):
    config_options = [[
     ['--locale',],
     {"action": "extend",
      "dest": "locales",
      "type": "string",
      "help": "Specify the locale(s) to repack"
     }
    ],[
     ['--partner',],
     {"action": "extend",
      "dest": "partners",
      "type": "string",
      "help": "Specify the partner(s) to repack"
     }
    ],[
     ['--locales-file',],
     {"action": "store",
      "dest": "locales_file",
      "type": "string",
      "help": "Specify a json file to determine which locales to repack"
     }
    ],[
     ['--tag-override',],
     {"action": "store",
      "dest": "tag_override",
      "type": "string",
      "help": "Override the tags set for all repos"
     }
    ],[
     ['--platform',],
     {"action": "extend",
      "dest": "platforms",
      "type": "choice",
      "choices": SUPPORTED_PLATFORMS,
      "help": "Specify the platform(s) to repack"
     }
    ],[
     ['--user-repo-override',],
     {"action": "store",
      "dest": "user_repo_override",
      "type": "string",
      "help": "Override the user repo path for all repos"
     }
    ],[
     ['--release-config-file',],
     {"action": "store",
      "dest": "release_config_file",
      "type": "string",
      "help": "Specify the release config file to use"
     }
    ],[
     ['--version',],
     {"action": "store",
      "dest": "version",
      "type": "string",
      "help": "Specify the current version"
     }
    ],[
     ['--old-version',],
     {"action": "store",
      "dest": "old_version",
      "type": "string",
      "help": "Specify the version to update from"
     }
    ],[
     ['--buildnum',],
     {"action": "store",
      "dest": "buildnum",
      "type": "int",
      "default": 1,
      "metavar": "INT",
      "help": "Specify the current release build num (e.g. build1, build2)"
     }
    ]]

    def __init__(self, require_config_file=True):
        self.release_config = {}
        LocalesMixin.__init__(self)
        MercurialScript.__init__(self,
            config_options=self.config_options,
            all_actions=[
                "clobber",
                "pull",
                "download",
#                "repack",
#                "upload",
            ],
            require_config_file=require_config_file
        )

    # Helper methods {{{2
    def add_failure(self, platform, locale, **kwargs):
        s = "%s:%s" % (platform, locale)
        if 'message' in kwargs:
            kwargs['message'] = kwargs['message'] % {'platform': platform, 'locale': locale}
        super(MobilePartnerRepack, self).add_failure(s, **kwargs)

    def query_failure(self, platform, locale):
        s = "%s:%s" % (platform, locale)
        return super(MobilePartnerRepack, self).query_failure(s)

    # Actions {{{2

    def pull(self):
        c = self.config
        dirs = self.query_abs_dirs()
        repos = []
        replace_dict = {}
        if c.get("user_repo_override"):
            replace_dict['user_repo_override'] = c['user_repo_override']
            # deepcopy() needed because of self.config lock bug :(
            for repo_dict in deepcopy(c['repos']):
                repo_dict['repo'] = repo_dict['repo'] % replace_dict
                repos.append(repo_dict)
        else:
            repos = c['repos']
        self.vcs_checkout_repos(repos, parent_dir=dirs['abs_work_dir'],
                                tag_override=c.get('tag_override'))

    def download(self):
        c = self.config
        rc = self.query_release_config()
        dirs = self.query_abs_dirs()
        locales = self.query_locales()
        base_url = c['download_base_url'] + '/' + \
                   c['download_unsigned_base_subdir'] + '/' + \
                   c.get('unsigned_apk_base_name', 'gecko-unsigned-unaligned.apk')
        replace_dict = {
            'buildnum': rc['buildnum'],
            'version': rc['version'],
        }
        success_count = total_count = 0
        for platform in c['platforms']:
            replace_dict['platform'] = platform
            for locale in locales:
                replace_dict['locale'] = locale
                url = base_url % replace_dict
                parent_dir = '%s/unsigned/%s/%s' % (dirs['abs_work_dir'],
                                           platform, locale)
                file_path = '%s/gecko.ap_' % parent_dir
                self.mkdir_p(parent_dir)
                total_count += 1
                if not self.download_file(url, file_path):
                    self.add_failure(platform, locale,
                                     message="Unable to download %(platform)s:%(locale)s unsigned apk!")
                else:
                    success_count += 1
        self.summarize_success_count(success_count, total_count,
                                     message="Downloaded %d of %d unsigned apks successfully.")

    def upload(self):
        c = self.config
        if not c['platforms']:
            self.info("No platforms to rsync! Skipping...")
            return
        rc = self.query_release_config()
        dirs = self.query_abs_dirs()
        rsync = self.query_exe("rsync")
        ssh = self.query_exe("ssh")
        ftp_upload_dir = c['ftp_upload_base_dir'] % {
            'version': rc['version'],
            'buildnum': rc['buildnum'],
        }
        cmd = [ssh, '-oIdentityFile=%s' % rc['ftp_ssh_key'],
               '%s@%s' % (rc['ftp_user'], rc['ftp_server']),
               'mkdir', '-p', ftp_upload_dir]
        self.run_command(cmd, cwd=dirs['abs_work_dir'],
                         error_list=SSHErrorList)
        cmd = [rsync, '-e']
        cmd += ['%s -oIdentityFile=%s' % (ssh, rc['ftp_ssh_key']), '-azv']
        cmd += c['platforms']
        cmd += ["%s@%s:%s/" % (rc['ftp_user'], rc['ftp_server'], ftp_upload_dir)]
        self.run_command(cmd, cwd=dirs['abs_work_dir'],
                         error_list=SSHErrorList)



# main {{{1
if __name__ == '__main__':
    mobile_partner_repack = MobilePartnerRepack()
    mobile_partner_repack.run()
