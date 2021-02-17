# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR BSD-3-Clause

import json
import logging
import os
import re
import sys

import boto3
import botocore.client


def resource_has_tags(resource, tags={}):
    """Checks if a resource defines all `tags`."""
    return all(
        tag_key in resource.keys() and resource[tag_key] == tag_value
        for (tag_key, tag_value) in tags.items()
    )


class S3ResourceFetcher:
    """A class for fetching vmm-reference test resources from S3."""

    def __init__(
            self,
            resource_bucket,
            resource_manifest_path,
            download_location=None,
    ):
        """Initializes the S3 client, manifest of test resources and S3 bucket name."""
        with open(resource_manifest_path) as json_file:
            self._resource_manifest = json.load(json_file)
        self._resource_bucket = resource_bucket
        self._s3 = boto3.client(
            's3',
            config=botocore.client.Config(signature_version=botocore.UNSIGNED)
        )
        if download_location is None:
            path = os.path.join(
                os.path.dirname(__file__),
                "../../resources")
            self._default_download_location = os.path.abspath(path)
        else:
            self._default_download_location = download_location
        self.log = logging.getLogger(__name__)
        self.log.info(
            "Setting default download location: ",
            self._default_download_location
        )

    def download(self, resource_type, resource_name, tags={}, version=None, download_location=None):
        """Downloads the resource specified by name and type. Optionally, the user can
        specify what tags the resource needs to have, and its version.

        The default version used when downloading is the latest version as defined in the
        resource manifest."""
        # TODO: The resource_name does not need to be required, because we can download
        # resources by type & tags.
        version = version or self.get_latest_version()
        download_location = download_location or self._default_download_location

        if version in self._resource_manifest.keys():
            resource_parent = self._resource_manifest[version]
        else:
            raise Exception("Invalid version: {}".format(version))

        resources = [r for r in resource_parent
                     if r["resource_type"] == resource_type
                     and r["resource_name"] == resource_name
                     and resource_has_tags(r, tags)]
        if len(resources) == 0:
            self.log.error("No resources found")
            exit(1)

        downloaded_file_paths = []
        for resource in resources:
            abs_dir = os.path.join(download_location, resource["relative_path"])
            self.log.info(
                "Creating download location if it does not exist: ",
                abs_dir
            )
            os.makedirs(abs_dir, exist_ok=True)
            abs_path = os.path.join(abs_dir, resource_name)

            object_key = "{}/{}/{}".format(version, resource_type, resource_name)
            self.log.info("Object to download from S3:", object_key)
            self.log.info("Downloading file to: ", abs_path, file=sys.stderr)

            if not os.path.exists(abs_path):
                self._s3.download_file(self._resource_bucket, object_key, abs_path)
            downloaded_file_paths.append(abs_path)

        return downloaded_file_paths

    def get_latest_version(self):
        """Returns the latest version as defined in the resource manifest file."""
        version_re = re.compile("^v[{0-9}]+")
        versions = [key for key in self._resource_manifest.keys() if version_re.match(key)]
        return "v{}".format(max(map(lambda v: int(v[1:]), versions)))
