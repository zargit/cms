#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Luca Versari <veluca93@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""This script scans the whole database for file objects references
and removes unreferenced file objects from the file store. If required,
it also replaces all the executable digests in the database with a
tombstone digest, to make executables removable in the clean pass.

"""

import argparse
import logging
import sys

from cms.db import Attachment, Executable, File, Manager, PrintJob, \
    SessionGen, Statement, Testcase, UserTest, UserTestExecutable, \
    UserTestFile, UserTestManager, UserTestResult
from cms.db.filecacher import FileCacher
from cms.server.util import format_size


logger = logging.getLogger()


def make_tombstone(session):
    count = 0
    for exe in session.query(Executable).all():
        if exe.digest != FileCacher.TOMBSTONE_DIGEST:
            count += 1
        exe.digest = FileCacher.TOMBSTONE_DIGEST
    logger.info("Replaced %d executables with the tombstone.", count)


def clean_files(session, dry_run):
    filecacher = FileCacher()
    files = set(file[0] for file in filecacher.list())
    logger.info("A total number of %d files are present in the file store",
                len(files))
    for cls in [Attachment, Executable, File, Manager, PrintJob,
                Statement, Testcase, UserTest, UserTestExecutable,
                UserTestFile, UserTestManager, UserTestResult]:
        for col in ["input", "output", "digest"]:
            if hasattr(cls, col):
                found_digests = set()
                digests = session.query(cls).all()
                digests = [getattr(obj, col) for obj in digests]
                found_digests |= set(digests)
                found_digests.discard(FileCacher.TOMBSTONE_DIGEST)
                logger.info("Found %d digests while scanning %s.%s",
                            len(found_digests), cls.__name__, col)
                files -= found_digests
    logger.info("%d digests are orphan.", len(files))
    total_size = 0
    for orphan in files:
        total_size += filecacher.get_size(orphan)
    logger.info("Orphan files take %s disk space", format_size(total_size))
    if not dry_run:
        for count, orphan in enumerate(files):
            filecacher.delete(orphan)
            if count % 100 == 0:
                logger.info("%d files deleted from the file store", count)
        logger.info("All orphan files have been deleted")


def main():
    parser = argparse.ArgumentParser(
        description="Remove unused file objects from the database. "
        "If -t is specified, also replace all executables with the tombstone")
    parser.add_argument("-t", "--tombstone", action="store_true")
    parser.add_argument("-n", "--dry-run", action="store_true")
    args = parser.parse_args()
    with SessionGen() as session:
        if args.tombstone:
            make_tombstone(session)
        clean_files(session, args.dry_run)
        if not args.dry_run:
            session.commit()
    return True


if __name__ == "__main__":
    sys.exit(0 if main() is True else 1)
