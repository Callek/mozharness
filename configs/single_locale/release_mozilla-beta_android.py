BRANCH = "mozilla-beta"
MOZILLA_DIR = BRANCH
JAVA_HOME = "/tools/jdk6"
JARSIGNER = "tools/release/signing/mozpass.py"
OBJDIR = "obj-l10n"
# TODO this needs to be built.
EN_US_BINARY_URL = "http://ftp.mozilla.org/pub/mozilla.org/mobile/candidates/%(version)s-candidates/build%(buildnum)d/unsigned/android/en-US"
STAGE_SERVER = "dev-stage01.build.sjc1.mozilla.com"
STAGE_USER = "ffxbld"
STAGE_SSH_KEY = "~/.ssh/ffxbld_dsa"
HG_SHARE_BASE_DIR = "/builds/hg-shared"

config = {
    "log_name": "single_locale",
    "objdir": OBJDIR,
    "locales_file": "buildbot-configs/mozilla/l10n-changesets_mobile-beta.json",
    "locales_dir": "mobile/android/locales",
    "locales_platform": "android",
    "ignore_locales": ["en-US"],
    "repos": [{
        "repo": "http://hg.mozilla.org/releases/mozilla-beta",
        "revision": "default",
        "dest": MOZILLA_DIR,
    },{
        "repo": "http://hg.mozilla.org/build/buildbot-configs",
        "revision": "default",
        "dest": "buildbot-configs"
    },{
        "repo": "http://hg.mozilla.org/build/tools",
        "revision": "default",
        "dest": "tools"
    },{
        "repo": "http://hg.mozilla.org/l10n/compare-locales",
        "revision": "RELEASE_0_9_4"
    }],
    "hg_l10n_base": "http://hg.mozilla.org/releases/l10n/%s" % BRANCH,
    "hg_l10n_tag": "default",
    'vcs_share_base': HG_SHARE_BASE_DIR,
    "l10n_dir": MOZILLA_DIR,

    "release_config_file": "buildbot-configs/mozilla/release-fennec-mozilla-beta.py",
    "repack_env": {
        "JAVA_HOME": JAVA_HOME,
        "PATH": JAVA_HOME + "/bin:%(PATH)s",
        "MOZ_PKG_VERSION": "%(version)s",
        "MOZ_OBJDIR": OBJDIR,
        "JARSIGNER": "%(abs_work_dir)s/" + JARSIGNER,
        "LOCALE_MERGEDIR": "%(abs_merge_dir)s/",
    },
    "base_en_us_binary_url": EN_US_BINARY_URL,
    # TODO ideally we could get this info from a central location.
    # However, the agility of these individual config files might trump that.
    "upload_env": {
        "UPLOAD_USER": STAGE_USER,
        "UPLOAD_SSH_KEY": STAGE_SSH_KEY,
        "UPLOAD_HOST": STAGE_SERVER,
        "UPLOAD_TO_TEMP": "1",
        "MOZ_PKG_VERSION": "%(version)s",
    },
    "base_post_upload_cmd": "post_upload.py -p mobile -n 1 -v %(version)s --builddir android/%(locale)s --release-to-mobile-candidates-dir --nightly-dir=candidates",
    "merge_locales": True,
    "make_dirs": ['config'],
    "mozilla_dir": MOZILLA_DIR,
    # TODO change to MOZILLA_DIR/mobile/android/config/mozconfigs/android/l10n-mozconfig when in-tree l10n-mozconfigs land.
    "mozconfig": "buildbot-configs/mozilla2/android/%s/release/l10n-mozconfig" % BRANCH,
    "jarsigner": JARSIGNER,
    "signature_verification_script": "tools/release/signing/verify-android-signature.sh",
    "default_actions": [
        "clobber",
        "pull",
        "list-locales",
        "setup",
        "repack",
        "upload-repacks",
    ],
}
