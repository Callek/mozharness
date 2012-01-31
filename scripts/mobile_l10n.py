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
"""sign_android.py

"""
# TODO partner repacks downloading/signing
# TODO split out signing and transfers to helper objects so we can do
#      the downloads/signing/uploads in parallel, speeding that up

import hashlib
import os
import sys

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from copy import deepcopy
import re
import subprocess

from mozharness.base.config import parse_config_file
from mozharness.base.errors import BaseErrorList, SSHErrorList
from mozharness.base.log import OutputParser, DEBUG, INFO, WARNING, ERROR, \
     CRITICAL, FATAL, IGNORE
from mozharness.base.signing import SigningMixin
from mozharness.base.vcs.vcsbase import MercurialScript
from mozharness.l10n.locales import LocalesMixin

# So far this only references the ftp platform name.
SUPPORTED_PLATFORMS = ["android", "android-xul"]
JARSIGNER_ERROR_LIST = [{
    "substr": "command not found",
    "level": FATAL,
},{
    "substr": "jarsigner error: java.lang.RuntimeException: keystore load: Keystore was tampered with, or password was incorrect",
    "level": FATAL,
    "explanation": "The store passphrase is probably incorrect!",
},{
    "regex": re.compile("jarsigner: key associated with .* not a private key"),
    "level": FATAL,
    "explanation": "The key passphrase is probably incorrect!",
},{
    "regex": re.compile("jarsigner error: java.lang.RuntimeException: keystore load: .* .No such file or directory"),
    "level": FATAL,
    "explanation": "The keystore doesn't exist!",
},{
    "substr": "jarsigner: unable to open jar file:",
    "level": FATAL,
    "explanation": "The apk is missing!",
}]
TEST_JARSIGNER_ERROR_LIST = [{
    "substr": "jarsigner: unable to open jar file:",
    "level": IGNORE,
}] + JARSIGNER_ERROR_LIST



# MobileSingleLocale {{{1
class MobileSingleLocale(LocalesMixin, SigningMixin, MercurialScript):
    config_options = [[
     ['--locale',],
     {"action": "extend",
      "dest": "locales",
      "type": "string",
      "help": "Specify the locale(s) to sign and update"
     }
    ],[
     ['--locales-file',],
     {"action": "store",
      "dest": "locales_file",
      "type": "string",
      "help": "Specify a json file to determine which locales to sign and update"
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
      "help": "Specify the platform(s) to sign"
     }
    ],[
     ['--user-repo-override',],
     {"action": "store",
      "dest": "user_repo_override",
      "type": "string",
      "help": "Override the user repo path for all repos"
     }
    ],[
     ['--key-alias',],
     {"action": "store",
      "dest": "key_alias",
      "type": "choice",
      "choices": ['production', 'nightly'],
      "help": "Specify the key alias"
     }
    ],[
     ['--update-platform',],
     {"action": "extend",
      "dest": "update_platforms",
      "type": "choice",
      "choices": SUPPORTED_PLATFORMS,
      "help": "Specify the platform(s) to create update snippets for"
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
    ],[
     ['--old-buildnum',],
     {"action": "store",
      "dest": "old_buildnum",
      "type": "int",
      "default": 1,
      "metavar": "INT",
      "help": "Specify the release build num to update from (e.g. build1, build2)"
     }
    ],[
     ['--keystore',],
     {"action": "store",
      "dest": "keystore",
      "type": "string",
      "help": "Specify the location of the signing keystore"
     }
    ]]

    def __init__(self, require_config_file=True):
        LocalesMixin.__init__(self)
        SigningMixin.__init__(self)
        MercurialScript.__init__(self,
            config_options=self.config_options,
            all_actions=[
                "clobber",
                "pull",
            ],
            require_config_file=require_config_file
        )

    # Helper methods {{{2
    def query_release_config(self):
        if self.release_config:
            return self.release_config
        c = self.config
        dirs = self.query_abs_dirs()
        if c.get("release_config_file"):
            self.info("Getting release config from %s..." % c["release_config_file"])
            rc = None
            try:
                rc = parse_config_file(
                    os.path.join(dirs['abs_work_dir'],
                                 c["release_config_file"]),
                    config_dict_name="releaseConfig"
                )
            except IOError:
                self.fatal("Release config file %s not found!" % c["release_config_file"])
            except RuntimeError:
                self.fatal("Invalid release config file %s!" % c["release_config_file"])
            self.release_config['version'] = rc['version']
            self.release_config['buildnum'] = rc['buildNumber']
            self.release_config['old_version'] = rc['oldVersion']
            self.release_config['old_buildnum'] = rc['oldBuildNumber']
            self.release_config['ftp_server'] = rc['ftpServer']
            self.release_config['ftp_user'] = c.get('ftp_user', rc['hgUsername'])
            self.release_config['ftp_ssh_key'] = c.get('ftp_ssh_key', rc['hgSshKey'])
            self.release_config['aus_server'] = rc['stagingServer']
            self.release_config['aus_user'] = rc['ausUser']
            self.release_config['aus_ssh_key'] = c.get('aus_ssh_key', '~/.ssh/%s' % rc['ausSshKey'])
        else:
            self.info("No release config file; using default config.")
            for key in ('version', 'buildnum', 'old_version', 'old_buildnum',
                        'ftp_server', 'ftp_user', 'ftp_ssh_key',
                        'aus_server', 'aus_user', 'aus_ssh_key',):
                self.release_config[key] = c[key]
        self.info("Release config:\n%s" % self.release_config)
        return self.release_config

    def query_buildid(self, platform, base_url, buildnum=None, version=None):
        # TODO rewrite for nightly.
        pass

    def _sign(self, apk, error_list=None):
        # TODO rewrite to use mozpass.py
        pass

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

    def verify_signatures(self):
        c = self.config
        rc = self.query_release_config()
        dirs = self.query_abs_dirs()
        verification_error_list = BaseErrorList + [{
            "regex": re.compile(r'''^Invalid$'''),
            "level": FATAL,
            "explanation": "Signature is invalid!"
        },{
            "substr": "filename not matched",
            "level": ERROR,
        },{
            "substr": "ERROR: Could not unzip",
            "level": ERROR,
        },{
            "regex": re.compile(r'''Are you sure this is a (nightly|release) package'''),
            "level": FATAL,
            "explanation": "Not signed!"
        }]
        locales = self.query_locales()
        env = self.query_env(partial_env=c.get("env"))
        for platform in c['platforms']:
            for locale in locales:
                signed_path = '%s/%s/%s' % (platform, locale,
                    c['apk_base_name'] % {'version': rc['version'],
                                          'locale': locale})
                self.run_command([c['signature_verification_script'],
                                  '--tools-dir=tools/',
                                  '--%s' % c['key_alias'],
                                  '--apk=%s' % signed_path],
                                 cwd=dirs['abs_work_dir'],
                                 env=env,
                                 error_list=verification_error_list)

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

    def create_snippets(self):
        c = self.config
        rc = self.query_release_config()
        dirs = self.query_abs_dirs()
        locales = self.query_locales()
        replace_dict = {
            'version': rc['version'],
            'buildnum': rc['buildnum'],
        }
        total_count = {'snippets': 0, 'links': 0}
        successful_count = {'snippets': 0, 'links': 0}
        for platform in c['update_platforms']:
            buildid = self.query_buildid(platform, c['buildid_base_url'])
            old_buildid = self.query_buildid(platform, c['old_buildid_base_url'],
                                             buildnum=rc['old_buildnum'],
                                             version=rc['old_version'])
            if not buildid:
                self.add_summary("Can't get buildid for %s! Skipping..." % platform, level=ERROR)
                continue
            replace_dict['platform'] = platform
            replace_dict['buildid'] = buildid
            for locale in locales:
                replace_dict['locale'] = locale
                parent_dir = '%s/%s/%s' % (dirs['abs_work_dir'],
                                           platform, locale)
                replace_dict['apk_name'] = c['apk_base_name'] % replace_dict
                signed_path = '%s/%s' % (parent_dir, replace_dict['apk_name'])
                if not os.path.exists(signed_path):
                    self.add_summary("Unable to create snippet for %s:%s: apk doesn't exist!" % (platform, locale), level=ERROR)
                    continue
                replace_dict['size'] = self.query_filesize(signed_path)
                replace_dict['sha512_hash'] = self.query_sha512sum(signed_path)
                for channel, channel_dict in c['update_channels'].items():
                    total_count['snippets'] += 1
                    total_count['links'] += 1
                    replace_dict['url'] = channel_dict['url'] % replace_dict
                    # Create previous link
                    previous_dir = os.path.join(dirs['abs_work_dir'], 'update',
                                                channel_dict['dir_base_name'] % (replace_dict),
                                                'Fennec', rc['old_version'],
                                                c['update_platform_map'][platform],
                                                old_buildid, locale, channel)
                    self.mkdir_p(previous_dir)
                    self.run_command(["touch", "partial.txt"],
                                     cwd=previous_dir, error_list=BaseErrorList)
                    status = self.run_command(
                        ['ln', '-s',
                         '../../../../../snippets/%s/%s/latest-%s' % (platform, locale, channel),
                         'complete.txt'],
                        cwd=previous_dir, error_list=BaseErrorList
                    )
                    if not status:
                        successful_count['links'] += 1
                    # Create snippet
                    contents = channel_dict['template'] % replace_dict
                    snippet_dir = "%s/update/%s/Fennec/snippets/%s/%s" % (
                      dirs['abs_work_dir'],
                      channel_dict['dir_base_name'] % (replace_dict),
                      platform, locale)
                    snippet_file = "%s/latest-%s" % (snippet_dir, channel)
                    self.info("Creating snippet for %s %s %s" % (platform, locale, channel))
                    self.mkdir_p(snippet_dir)
                    try:
                        fh = open(snippet_file, 'w')
                        fh.write(contents)
                        fh.close()
                    except:
                        self.add_summary("Unable to write to %s!" % snippet_file, level=ERROR)
                        self.info("File contents: \n%s" % contents)
                    else:
                        successful_count['snippets'] += 1
        level = INFO
        for k in successful_count.keys():
            if successful_count[k] < total_count[k]:
                level = ERROR
            self.add_summary("Created %d of %d %s successfully." % \
                             (successful_count[k], total_count[k], k),
                             level=level)

    def upload_snippets(self):
        c = self.config
        rc = self.query_release_config()
        dirs = self.query_abs_dirs()
        update_dir = os.path.join(dirs['abs_work_dir'], 'update',)
        if not os.path.exists(update_dir):
            self.error("No such directory %s! Skipping..." % update_dir)
            return
        rsync = self.query_exe("rsync")
        ssh = self.query_exe("ssh")
        aus_upload_dir = c['aus_upload_base_dir'] % {
            'version': rc['version'],
            'buildnum': rc['buildnum'],
        }
        cmd = [ssh, '-oIdentityFile=%s' % rc['aus_ssh_key'],
               '%s@%s' % (rc['aus_user'], rc['aus_server']),
               'mkdir', '-p', aus_upload_dir]
        self.run_command(cmd, cwd=dirs['abs_work_dir'],
                         error_list=SSHErrorList)
        cmd = [rsync, '-e']
        cmd += ['%s -oIdentityFile=%s' % (ssh, rc['aus_ssh_key']), '-azv', './']
        cmd += ["%s@%s:%s/" % (rc['aus_user'], rc['aus_server'], aus_upload_dir)]
        self.run_command(cmd, cwd=update_dir, error_list=SSHErrorList)



# main {{{1
if __name__ == '__main__':
    single_locale = MobileSingleLocale()
    single_locale.run()
