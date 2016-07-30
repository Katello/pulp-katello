# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
import os
import gettext
import shutil
import time
import errno
from lxml import etree

#pylint: disable=F0401
from pulp.plugins.distributor import Distributor
from pulp.server.db import model
from pulp_rpm.yum_plugin import util
from pulp_rpm.common.ids import TYPE_ID_DISTRO, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP, \
                                TYPE_ID_PKG_CATEGORY, TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DISTRIBUTOR_YUM

_LOG = util.getLogger(__name__)
_ = gettext.gettext

XML_NSMAP = {'repomd': 'http://linux.duke.edu/metadata/repo'}

REQUIRED_CONFIG_KEYS = []
OPTIONAL_CONFIG_KEYS = ["source_distributor_id", "source_repo_id", "destination_distributor_id"]

YUM_CLONE_DISTRIBUTOR_TYPE = "yum_clone_distributor"

MASTER_PUBLISH_DIR = "/var/lib/pulp/published/yum/master/yum_distributor"
HTTP_PUBLISH_DIR = "/var/lib/pulp/published/yum/http/repos"
HTTPS_PUBLISH_DIR = "/var/lib/pulp/published/yum/https/repos"

def entry_point():
    return YumCloneDistributor, {}


###
# Config Options Explained
###
# source_repo_id        - String: Id of the yum repo containing the
# source_distributor_id - String: Id of the yum distributor in pulp to copy the export from
# destination_distributor_id - String: ID of th eyum distributor in pulp to copy the export to
# -- plugins ------------------------------------------------------------------

class YumCloneDistributor(Distributor):

    #pylint: disable=E1002
    def __init__(self):
        super(YumCloneDistributor, self).__init__()
        self.cancelled = False
        self.summary = {"errors":[]}
        self.details = {}

    @classmethod
    def metadata(cls):
        return {
            'id'           : YUM_CLONE_DISTRIBUTOR_TYPE,
            'display_name' : 'Yum Clone Distributor',
            'types'        : [TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_DISTRO, \
                              TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP]
        }

    def add_error(self, message):
        self.summary["errors"].append(message)

    #pylint: disable=W0613,R0201
    def validate_config(self, repo, config, related_repos):
        for key in REQUIRED_CONFIG_KEYS:
            value = config.get(key)
            if value is None:
                msg = _("Missing required configuration key: %(key)s" % {"key":key})
                _LOG.error(msg)
                return False, msg
        for key in config.keys():
            if key not in REQUIRED_CONFIG_KEYS and key not in OPTIONAL_CONFIG_KEYS:
                msg = _("Configuration key '%(key)s' is not supported" % {"key":key})
                _LOG.error(msg)
                return False, msg
        return True, None

    def find_yum_distributor(self, repo_id):
        for dist in model.Distributor.objects(repo_id=repo_id):
            if dist.distributor_type_id == TYPE_ID_DISTRIBUTOR_YUM:
                return dist
        raise Exception("Could not find yum distributor for %s" % repo_id)

    def base_working_dir(self, repo_id):
        return os.path.join(MASTER_PUBLISH_DIR, repo_id)

    def full_working_dir(self, repo_id, time_stamp):
        return os.path.join(MASTER_PUBLISH_DIR, repo_id, str(time_stamp))

    def clean_path(self, directory, exclude_subdir):
        for item in os.listdir(directory):
            if os.path.isdir(os.path.join(directory, item)) and item != exclude_subdir:
                shutil.rmtree(os.path.join(directory, item))

    def source_working_dir(self, repo_id):
        relative_path = self.find_yum_distributor(repo_id)['config']['relative_url']
        realpath = self.valid_symlink_dest(os.path.join(HTTPS_PUBLISH_DIR, relative_path))

        if not realpath:
            realpath = self.valid_symlink_dest(os.path.join(HTTP_PUBLISH_DIR, relative_path))
        if not realpath:
            raise Exception("Could not find a published directory for %s." % repo_id)
        return realpath

    def valid_symlink_dest(self, path):
        if not os.path.islink(path):
            raise Exception('%s exists, but should be a symlink.  Cannot find published directory.' % path)
        realpath = os.path.realpath(path)
        if os.path.exists(realpath):
            return realpath
        else:
            return None

    def publish_repo(self, repo, publish_conduit, config):
        publish_start_time = time.time()
        _LOG.info("Start publish time %s" % publish_start_time)

        source_repo_id = config.get('source_repo_id')
        destination_dist_config = self.find_yum_distributor(repo.id)['config']
        source_working_dir = self.source_working_dir(source_repo_id)
        working_dir = self.full_working_dir(repo.id, publish_start_time)

        self.safe_makedirs(working_dir)
        #copy contents from source's working directory to destinations
        if not self.copy_directory(source_working_dir, working_dir):
            publish_conduit.set_progress(self.summary)
            raise Exception("Failed to copy metadata.  See errors for more details.")

        #symlink the destination's publish directories
        if destination_dist_config['http']:
            http_publish_dir = os.path.join(HTTP_PUBLISH_DIR, destination_dist_config["relative_url"]).rstrip('/')
            self.link_directory(working_dir, http_publish_dir)
            util.generate_listing_files(HTTP_PUBLISH_DIR, http_publish_dir)
            self.update_repomd(http_publish_dir)

        if destination_dist_config['https']:
            https_publish_dir = os.path.join(HTTPS_PUBLISH_DIR, destination_dist_config["relative_url"]).rstrip('/')
            self.link_directory(working_dir, https_publish_dir)
            util.generate_listing_files(HTTPS_PUBLISH_DIR, https_publish_dir)
            self.update_repomd(https_publish_dir)

        self.clean_path(self.base_working_dir(repo.id), str(publish_start_time))

        publish_conduit.set_progress(self.summary)
        if len(self.summary["errors"]) > 0:
            raise Exception("Failed to link metadata.  See errors for more details.")
        else:
            return publish_conduit.build_success_report(self.summary, self.details)

    def link_directory(self, source, destination):
        try:
            destination = destination.rstrip('/')
            if os.path.exists(destination):
                os.unlink(destination)
            base_path = os.path.split(destination)[0]
            if not os.path.exists(base_path):
                self.safe_makedirs(base_path)
            os.symlink(source, destination)
            return True
        except OSError as error:
            self.add_error(error.message)
            return False

    def safe_makedirs(self, path):
        try:
            if not os.path.exists(path):
                os.makedirs(path)
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise error

    def copy_directory(self, source_dir, destination_dir):
        try:
            if not os.path.exists(source_dir):
                raise OSError("Source Directory (%s), does not exist, cannot publish." % source_dir)
            if os.path.exists(destination_dir):
                shutil.rmtree(destination_dir)
            shutil.copytree(source_dir, destination_dir, True)
            return True
        except OSError as error:
            self.add_error(error.message or error.strerror)
            return False

    def update_repomd(self, repo_path):
        filename = os.path.join(repo_path, 'repodata/repomd.xml')
        if not os.path.isfile(filename):
            _LOG.error("File %s does not exists, cannot update repomd.xml timestamps." % filename)
            return
        tree = etree.parse(filename)
        timestamps = tree.xpath('//repomd:timestamp', namespaces=XML_NSMAP)
        new_timestamp = str(int(time.time()))

        for timestamp in timestamps:
            timestamp.text = new_timestamp

        revision = tree.xpath('//repomd:revision', namespaces=XML_NSMAP)[0]
        revision.text = new_timestamp

        new_content = etree.tostring(tree, pretty_print=True, encoding="UTF-8", xml_declaration=True)

        f = open(filename, 'w')
        f.write(new_content)
        f.close()
