# This is a template config file for peptest user

# The peptest mozharness script is set up so that specifying None
# is the same as not specifying the option at all
import os

config = {
    # mozharness script options
    "base_work_dir": os.getcwd(),
    "work_dir": "build",
    "log_name": "pep",
    "log_level": "info",
    "test_url": "url_to_packaged_tests",
    # path or url to a zip or folder containing the mozbase packages
    "mozbase_url": "url_to_mozbase_zip",
    # path or url to a zip or folder containing peptest
    "peptest_url": "url_to_peptest_zip",

    # peptest options

    "appname": "path_to_application_binary",
    # defaults to firefox, can also be thunderbird, fennec, etc.
    "app": "firefox",
    "test_manifest": "path_to_test_manifest",
    # optional, use an existing profile (temp profile created by default)
    "profile_path": None,
    # global timeout in seconds (without output)
    "timeout": 60,
    # if specified, creates a webserver for hosting test
    # related files at this document root
    "server_path": None,
    "server_port": None,
    # EventTracer setting, the threshold to count a failure (ms)
    "tracer_threshold": 50,
    # EventTracer setting, interval at which to send tracer events (ms)
    "tracer_interval": 10,
    # URL or path to the symbols directory for debugging crashes
    "symbols_path": None,

    # get latest tinderbox options
    # (these are only used by the get-latest-tinderbox action)
    "get_latest_tinderbox_product": "mozilla-central",
    "get_latest_tinderbox_platform": None, # defaults to current platform
    "get_latest_tinderbox_debug_build": False,
}

# these config options depend on the abs_work_dir option
abs_work_dir = os.path.abspath(os.path.join(config['base_work_dir'],
                                            config['work_dir']))

config['virtualenv_path'] = os.path.join(abs_work_dir, "venv")
# directory to extract tests to
config['test_install_dir'] = os.path.join(abs_work_dir, "tests")
# directory to install application to
config['application_install_dir'] = os.path.join(abs_work_dir,
                                                 "application")
