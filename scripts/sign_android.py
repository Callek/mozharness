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

import os
import sys

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from copy import deepcopy
import getpass
import subprocess

from mozharness.base.errors import BaseErrorList, SSHErrorList
from mozharness.base.log import OutputParser, DEBUG, INFO, WARNING, ERROR, \
     CRITICAL, FATAL, IGNORE
from mozharness.base.vcs.vcsbase import MercurialScript
from mozharness.l10n.locales import LocalesMixin

# So far this only references the ftp platform name.
SUPPORTED_PLATFORMS = ["android", "android-xul"]
BASE_JARSIGNER_ERROR_LIST = [{
    "substr": "command not found",
    "level": FATAL,
},{
    "substr": "jarsigner error: java.lang.RuntimeException: keystore load: Keystore was tampered with, or password was incorrect",
    "level": FATAL,
    "explanation": "The store passphrase is probably incorrect!",
},{
    "regex": "jarsigner: key associated with .* not a private key",
    "level": FATAL,
    "explanation": "The key passphrase is probably incorrect!",
},{
    "regex": "jarsigner error: java.lang.RuntimeException: keystore load: .* .No such file or directory",
    "level": FATAL,
    "explanation": "The keystore doesn't exist!",
}]
JARSIGNER_ERROR_LIST = BASE_JARSIGNER_ERROR_LIST + [{
    "substr": "jarsigner: unable to open jar file:",
    "level": FATAL,
    "explanation": "The apk is missing!",
}]
TEST_JARSIGNER_ERROR_LIST = BASE_JARSIGNER_ERROR_LIST + [{
    "substr": "jarsigner: unable to open jar file:",
    "level": IGNORE,
}]

class SignAndroid(LocalesMixin, MercurialScript):
    config_options = [[
     ['--locale',],
     {"action": "extend",
      "dest": "locales",
      "type": "string",
      "help": "Specify the locale(s) to sign"
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
# TODO unsigned url, signed url, ssh key/user/server/path,
# --version
# --buildnum
# --previous-version
# --previous-buildnum
# --keystore
# previous build signed url, --ignore-locale, locales_file
# aus key/user/server/path
# verify aus url?
    ]]

    def __init__(self, require_config_file=True):
        self.store_passphrase = os.environ.get('android_storepass')
        self.key_passphrase = os.environ.get('android_keypass')
        LocalesMixin.__init__(self)
        MercurialScript.__init__(self,
            config_options=self.config_options,
            all_actions=[
                "passphrase",
                "clobber",
                "pull",
                "download-unsigned-bits",
                "sign",
                "verify",
#                "upload-signed-bits"
#                "download-previous-bits",
#                "create-snippets",
#                "upload-snippets",
            ],
            require_config_file=require_config_file
        )

    def passphrase(self):
        if not self.store_passphrase:
            print "(store passphrase): ",
            self.store_passphrase = getpass.getpass()
        if not self.key_passphrase:
            print "(key passphrase): ",
            self.key_passphrase = getpass.getpass()

    def verify_passphrases(self):
        c = self.config
        self.info("Verifying passphrases...")
        status = self._sign("NOTAREALAPK", error_list=TEST_JARSIGNER_ERROR_LIST)
        if status == 0:
            self.info("Passphrases are good.")
        else:
            self.fatal("Unable to verify passphrases!")

    def postflight_passphrase(self):
        self.verify_passphrases()

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

    # TODO partner repack download
    def download_unsigned_bits(self):
        c = self.config
        dirs = self.query_abs_dirs()
        locales = self.query_locales()
        base_url = c['download_base_url'] + '/' + \
                   c['download_unsigned_base_subdir'] + '/' + \
                   c.get('unsigned_apk_base_name', 'gecko-unsigned-unaligned.apk')
        replace_dict = {
            'buildnum': c['buildnum'],
            'version': c['version'],
        }
        successful_count = 0
        total_count = 0
        for platform in c['platforms']:
            replace_dict['platform'] = platform
            for locale in locales:
                replace_dict['locale'] = locale
                url = base_url % replace_dict
                parent_dir = '%s/%s/%s' % (dirs['abs_work_dir'],
                                                    platform, locale)
                file_path = '%s/gecko_unsigned_unaligned.apk' % parent_dir
                self.mkdir_p(parent_dir)
                total_count += 1
                if not self.download_file(url, file_path):
                    self.add_summary("Unable to download %s:%s unsigned apk!",
                                     level=ERROR)
                else:
                    successful_count += 1
        level = INFO
        if successful_count < total_count:
            level = ERROR
        self.add_summary("Downloaded %d of %d unsigned apks successfully." % \
                         (successful_count, total_count), level=level)

    def _sign(self, apk, error_list=None):
        c = self.config
        jarsigner = self.query_exe("jarsigner")
        if error_list is None:
            error_list = JARSIGNER_ERROR_LIST
        # This needs to run silently, so no run_command() or
        # get_output_from_command() (though I could add a
        # suppress_command_echo=True or something?)
        p = subprocess.Popen([jarsigner, "-keystore", c['keystore'],
                             "-storepass", self.store_passphrase,
                             "-keypass", self.key_passphrase,
                             apk, c['key_alias']],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        parser = OutputParser(config=self.config, log_obj=self.log_obj,
                              error_list=error_list)
        loop = True
        while loop:
            if p.poll() is not None:
                """Avoid losing the final lines of the log?"""
                loop = False
            for line in p.stdout:
                parser.add_lines(line)
        return parser.num_errors

    def preflight_sign(self):
        if 'passphrase' not in self.actions:
            self.passphrase()
            self.verify_passphrases()

    # TODO partner repack signing
    def sign(self):
        c = self.config
        dirs = self.query_abs_dirs()
        locales = self.query_locales()
        successful_count = 0
        total_count = 0
        zipalign = self.query_exe("zipalign")
        for platform in c['platforms']:
            for locale in locales:
                parent_dir = '%s/%s/%s' % (dirs['abs_work_dir'],
                                                    platform, locale)
                unsigned_unaligned_path = '%s/gecko_unsigned_unaligned.apk' % parent_dir
                unaligned_path = '%s/gecko_unaligned.apk' % parent_dir
                signed_path = '%s/%s' % (parent_dir,
                    c['apk_base_name'] % {'version': c['version'],
                                          'locale': locale})
                self.mkdir_p(parent_dir)
                total_count += 1
                self.info("Signing %s %s." % (platform, locale))
                self.copyfile(unsigned_unaligned_path, unaligned_path)
                if self._sign(unaligned_path) != 0:
                    self.add_summary("Unable to sign %s:%s apk!",
                                     level=FATAL)
                elif self.run_command([zipalign, '-f', '4',
                                       unaligned_path, signed_path],
                                      error_list=BaseErrorList):
                    self.add_summary("Unable to align %s:%s apk!",
                                     level=FATAL)
                else:
                    successful_count += 1
        level = INFO
        if successful_count < total_count:
            level = ERROR
        self.add_summary("Signed %d of %d apks successfully." % \
                         (successful_count, total_count), level=level)

    def verify(self):
        c = self.config
        dirs = self.query_abs_dirs()
        verification_error_list = BaseErrorList + [{
            "regex": r'''^Invalid$''',
            "level": FATAL,
            "explanation": "Signature is invalid!"
        }]
        locales = self.query_locales()
        for platform in c['platforms']:
            for locale in locales:
                signed_path = '%s/%s/%s' % (platform, locale,
                    c['apk_base_name'] % {'version': c['version'],
                                          'locale': locale})
                self.run_command([c['signature_verification_script'],
                                  '--tools-dir=tools/',
                                  '--%s' % c['key_alias'],
                                  '--apk=%s' % signed_path],
                                 cwd=dirs['abs_work_dir'],
                                 error_list=verification_error_list)

if __name__ == '__main__':
    sign_android = SignAndroid()
    sign_android.run()
