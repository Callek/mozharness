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
"""multi_locale_build.py

This should be a mostly generic multilocale build script.
"""

import os
import sys

sys.path.insert(1, os.path.dirname(os.path.dirname(sys.path[0])))

from mozharness.base.errors import SSHErrorList, PythonErrorList, MakefileErrorList
from mozharness.base.log import DEBUG, INFO, WARNING, ERROR, CRITICAL, FATAL, IGNORE
from mozharness.base.vcs.vcsbase import MercurialScript
from mozharness.l10n.locales import LocalesMixin



# MultiLocaleBuild {{{1
class MultiLocaleBuild(LocalesMixin, MercurialScript):
    config_options = [[
     ["--locale",],
     {"action": "extend",
      "dest": "locales",
      "type": "string",
      "help": "Specify the locale(s) to repack"
     }
    ],[
     ["--merge-locales",],
     {"action": "store_true",
      "dest": "merge_locales",
      "default": False,
      "help": "Use default [en-US] if there are missing strings"
     }
    ],[
     ["--no-merge-locales",],
     {"action": "store_false",
      "dest": "merge_locales",
      "help": "Do not allow missing strings"
     }
    ],[
     ["--objdir",],
     {"action": "store",
      "dest": "objdir",
      "type": "string",
      "default": "objdir",
      "help": "Specify the objdir"
     }
    ],[
     ["--l10n-base",],
     {"action": "store",
      "dest": "hg_l10n_base",
      "type": "string",
      "help": "Specify the L10n repo base directory"
     }
    ],[
     ["--l10n-tag",],
     {"action": "store",
      "dest": "hg_l10n_tag",
      "type": "string",
      "help": "Specify the L10n tag"
     }
    ],[
     ["--tag-override",],
     {"action": "store",
      "dest": "tag_override",
      "type": "string",
      "help": "Override the tags set for all repos"
     }
    ],[
     ["--user-repo-override",],
     {"action": "store",
      "dest": "user_repo_override",
      "type": "string",
      "help": "Override the user repo path for all repos"
     }
    ],[
     ["--l10n-dir",],
     {"action": "store",
      "dest": "l10n_dir",
      "type": "string",
      "default": "l10n",
      "help": "Specify the l10n dir name"
     }
    ]]

    def __init__(self, require_config_file=True):
        LocalesMixin.__init__(self)
        MercurialScript.__init__(self, config_options=self.config_options,
                                 all_actions=['clobber', 'pull-build-source',
                                              'pull-locale-source',
                                              'build', 'package-en-US',
                                              'upload-en-US',
                                              'add-locales', 'package-multi',
                                              'upload-multi'],
                                 require_config_file=require_config_file)

    def clobber(self):
        c = self.config
        if c['work_dir'] != '.':
            path = os.path.join(c['base_work_dir'], c['work_dir'])
            if os.path.exists(path):
                self.rmtree(path, error_level=FATAL)
        else:
            self.info("work_dir is '.'; skipping for now.")

    def pull_build_source(self):
        c = self.config
        dirs = self.query_abs_dirs()
        repos = []
        replace_dict = {}
        # Replace %(user_repo_override)s with c['user_repo_override']
        if c.get("user_repo_override"):
            replace_dict['user_repo_override'] = c['user_repo_override']
            for repo_dict in c['repos']:
                repo_dict['repo'] = repo_dict['repo'] % replace_dict
                repos.append(repo_dict)
        else:
            repos = c['repos']
        self.vcs_checkout_repos(c['repos'], tag_override=c.get('tag_override'))

    def pull_locale_source(self):
        c = self.config
        dirs = self.query_abs_dirs()
        self.mkdir_p(dirs['abs_l10n_dir'])
        locales = self.query_locales()
        locale_repos = []
        hg_l10n_base = c['hg_l10n_base']
        if c.get("user_repo_override"):
            hg_l10n_base = hg_l10n_base % {"user_repo_override": c["user_repo_override"]}
        for locale in locales:
            tag = c.get('hg_l10n_tag', 'default')
            if hasattr(self, 'locale_dict'):
                tag = self.locale_dict[locale]
            locale_repos.append({
                'repo': "%s/%s" % (hg_l10n_base, locale),
                'tag': tag
            })
        self.vcs_checkout_repos(repo_list=locale_repos,
                                parent_dir=dirs['abs_l10n_dir'],
                                tag_override=c.get('tag_override'))

    def build(self):
        c = self.config
        dirs = self.query_abs_dirs()
        self.copyfile(os.path.join(dirs['abs_work_dir'], c['mozconfig']),
                      os.path.join(dirs['abs_mozilla_dir'], 'mozconfig'),
                      error_level=FATAL)
        command = "make -f client.mk build"
        env = self.query_env()
        self._process_command(command=command, cwd=dirs['abs_mozilla_dir'],
                              env=env, error_list=MakefileErrorList,
                              halt_on_failure=True)

    def add_locales(self):
        c = self.config
        dirs = self.query_abs_dirs()
        locales = self.query_locales()

        for locale in locales:
            self.run_compare_locales(locale, halt_on_failure=True)
            command = 'make chrome-%s L10NBASEDIR=%s' % (locale, dirs['abs_l10n_dir'])
            if c['merge_locales']:
                command += " LOCALE_MERGEDIR=%s" % dirs['abs_merge_dir']
            status = self._process_command(command=command,
                                           cwd=dirs['abs_locales_dir'],
                                           error_list=MakefileErrorList)
            if status:
                self.return_code += 1
                self.add_summary("Failed to add locale %s!" % locale,
                                 level="error")
            else:
                self.add_summary("Added locale %s successfully." % locale)

    def package_en_US(self):
        self.package(package_type='en-US')

    def preflight_package_multi(self):
        dirs = self.query_abs_dirs()
        self.run_command("rm -rfv dist/fennec*", cwd=dirs['abs_objdir'])

    def package_multi(self):
        self.package(package_type='multi')

    def additional_packaging(self, package_type='en-US', env=None):
        dirs = self.query_abs_dirs()
        command = "make package-tests"
        if package_type == 'multi':
            command += " AB_CD=multi"
        self.run_command(command, cwd=dirs['abs_objdir'], env=env,
                         error_list=MakefileErrorList,
                         halt_on_failure=True)
        # TODO deal with buildsymbols

    def package(self, package_type='en-US'):
        c = self.config
        dirs = self.query_abs_dirs()

        command = "make package"
        env = self.query_env()
        if env is None:
            # This is for Maemo, where we don't want an env for builds
            # but we do for packaging.  self.query_env() will return None.
            env = os.environ.copy()
        if package_type == 'multi':
            command += " AB_CD=multi"
            env['MOZ_CHROME_MULTILOCALE'] = "en-US " + \
                                            ' '.join(self.query_locales())
            self.info("MOZ_CHROME_MULTILOCALE is %s" % env['MOZ_CHROME_MULTILOCALE'])
        # TODO remove once bug 611648 fixed
        if 'jarsigner' in c:
            env['JARSIGNER'] = os.path.join(dirs['abs_work_dir'],
                                            c['jarsigner'])
        self._process_command(command=command, cwd=dirs['abs_objdir'],
                              env=env, error_list=MakefileErrorList,
                              halt_on_failure=True)
        self.additional_packaging(package_type=package_type, env=env)

    def upload_en_US(self):
        # TODO
        self.info("Not written yet.")

    def upload_multi(self):
        # TODO
        self.info("Not written yet.")

    def _process_command(self, **kwargs):
        """Stub wrapper function that allows us to call scratchbox in
           MaemoMultiLocaleBuild.

        """
        return self.run_command(**kwargs)

# __main__ {{{1
if __name__ == '__main__':
    pass
