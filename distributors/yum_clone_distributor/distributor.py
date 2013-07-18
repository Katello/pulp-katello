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

from pulp.server.managers.repo.distributor import RepoDistributorManager
from pulp_rpm.yum_plugin import util
from pulp.plugins.distributor import Distributor

import pulp.server.managers.repo._common as common_utils

from pulp_rpm.common.ids import TYPE_ID_DISTRIBUTOR_EXPORT, TYPE_ID_DISTRO, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_PKG_GROUP,\
        TYPE_ID_PKG_CATEGORY, TYPE_ID_RPM, TYPE_ID_SRPM

_LOG = util.getLogger(__name__)
_ = gettext.gettext

REQUIRED_CONFIG_KEYS = []
OPTIONAL_CONFIG_KEYS = ["source_distributor_id", "source_repo_id", "destination_distributor_id"]

YUM_CLONE_DISTRIBUTOR_TYPE = "yum_clone_distributor"

HTTP_PUBLISH_DIR="/var/lib/pulp/published/http/repos"
HTTPS_PUBLISH_DIR="/var/lib/pulp/published/https/repos"

###
# Config Options Explained
###
# source_repo_id        - String: Id of the yum repo containing the 
# source_distributor_id - String: Id of the yum distributor in pulp to copy the export from
# destination_distributor_id - String: ID of th eyum distributor in pulp to copy the export to
# -- plugins ------------------------------------------------------------------

class YumCloneDistributor(Distributor):

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
            'types'        : [TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA, TYPE_ID_DISTRO, TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP]
        }

    def add_error(self, message):
        self.summary["errors"].append(message)

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

    def working_directory(self, repo_id):
        return common_utils.distributor_working_dir('yum_distributor', repo_id)

    def publish_repo(self, repo, publish_conduit, config):
        publish_start_time = time.time()
        _LOG.info("Start publish time %s" % publish_start_time)

        #lookup the source and destination distributors
        dist_manager = RepoDistributorManager()
        destination_dist_config = dist_manager.get_distributor(repo.id, config.get('destination_distributor_id'))['config']
        source_dist_config = dist_manager.get_distributor(config.get('source_repo_id'), config.get('source_distributor_id'))['config']

        #copy contents from source's working directory to destinations       
        source_working_dir = self.working_directory(config.get('source_repo_id'))
        working_dir = self.working_directory(repo.id)
        if not self.copy_directory(source_working_dir, working_dir):
            publish_conduit.set_progress(self.summary)
            raise Exception("Failed to copy metadata.  See errors for more details.")

        #symlink the destination's publish directories 
        if destination_dist_config['http']:
            http_publish_dir = os.path.join(HTTP_PUBLISH_DIR, destination_dist_config["relative_url"]).rstrip('/')
            self.link_directory(working_dir, http_publish_dir)

        if destination_dist_config['https']:
            https_publish_dir  = os.path.join(HTTPS_PUBLISH_DIR, destination_dist_config["relative_url"]).rstrip('/')
            self.link_directory(working_dir, https_publish_dir)

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
                os.makedirs(base_path)
            os.symlink(source, destination)
            return True
        except OSError as error:
            self.add_error(error.message)
            return False

    def copy_directory(self, source_dir, destination_dir):
        try:
            if not os.path.exists(source_dir):
                raise OSError("Source Directory (%s), does not exist, cannot publish.") 
            if os.path.exists(destination_dir):
                shutil.rmtree(destination_dir)
            shutil.copytree(source_dir, destination_dir, True)
            return True
        except OSError as error:
            self.add_error(error.message) 
            return False
