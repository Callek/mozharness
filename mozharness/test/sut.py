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
'''Interact with SUT Agent and devicemanager.
'''

from mozharness.base.errors import PythonErrorList

# SUT {{{1
sut_config_options = [[
 ["--sut-ip"],
 {"action": "store",
  "dest": "sut_ip",
  # TODO remove the default
  # TODO adb non-ip support?
  "default": "10.0.1.4",
  "help": "Specify the IP address of the device running SUT."
 }
],[
 ["--devicemanager-path"],
 {"action": "store",
  "dest": "devicemanager_path",
  "help": "Specify the path to devicemanager.py."
 }
]]

class SUTMixin(object):
    '''BaseScript mixin, designed to interface with SUT Agent through
    devicemanager.

    Config items:
     * devicemanager_path points to the devicemanager.py location on disk.
     * sut_ip holds the IP of the device.
    '''
    devicemanager_path = None
    devicemanager = None

    def query_devicemanager_path(self):
        """Return the path to devicemanager.py.
        """
        if self.devicemanager_path:
            return self.devicemanager_path
        if self.config['devicemanager_path']:
            self.devicemanager_path = self.config['devicemanager_path']
        else:
            dirs = self.query_abs_dirs()
            self.devicemanager_path = os.path.join(dirs['abs_talos_dir'],
                                                   "devicemanager.py")
        return self.devicemanager_path

    def query_devicemanager(self):
        pass



# __main__ {{{1

if __name__ == '__main__':
    '''TODO: unit tests.
    '''
    pass
