#
# Copyright (c) 2017 SUSE Linux GmbH
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#

from .config import getbranches
from collections import Counter, defaultdict
from .log import log
from git import GitCommandError
import json

import statistics


def iter_commits(repo, dictresult, branchname, start=None, end=None):
    """Iterate through all commits

    :param repo:
    :param dictresult:
    :param str branchname: the name of the branch
    :return:
    """
    start = '' if start is None else start
    end = '' if end is None else end

    rev = "..".join([start, end])
    if rev == '..':
        rev = repo.head

    log.info("Using start=%r", start)
    log.info("Using end=%r", end)

    for idx, commit in enumerate(repo.iter_commits(rev), 1):
        for item in commit.stats.total:
            dictresult[branchname][item] += commit.stats.total[item]
    # Save overall commits:
    dictresult[branchname]['commits'] = idx


def init_stats_dict():
    """Create a dictionary statistics object with defaults to zero for;
       used for counting

    :return: dictionary with all values to zero
    :rtype: dict
    """
    return {item: 0 for item in ('deletions', 'files', 'insertions', 'lines')}


def analyze(repo, config):
    """Analyze the repositories given at queue

    :param queue: a queue
    :type queue: :class:`queue.Queue`
    :param config: the docstats configuration contents
    :type config: :class:`configparser.ConfigParser`
    :return: dictionary with data
        data = { 'branch1': data_of_branch1,
                 'branch2': data_of_branch2,
                }
        data_of_branchX = {'doc-committers': X, # type:set
                           'additions': A,      # type:int
                           'deletions': D,      # type:int
                           '#commits': N,       # type:int
                           'changes':  C,       # type:int
                           'bsc': BSC,          # type:set
                           'gh': GH,            # type:set
                           'fate': FA,          # type:set
                           'trello': TR,        # type:set
                           'doccomments: DC',   # type:set
                           'start-commit': SC   # type:str
                           'end-commit': EC     # type:str
                           }
    :rtype: dict
    """

    result = {}
    wd = repo.working_tree_dir
    section = wd.rsplit("/", 1)[-1]

    for branchname, start, end in getbranches(config.get(section,
                                                         'branches',
                                                         fallback=None)
                                              ):
        result[branchname] = {}
        log.info("start %s", start)
        result[branchname]['start'] = str(start)
        result[branchname]['end'] = str(end)
        try:
            repo.git.checkout(branchname)
        except GitCommandError as error:
            # error contains the following attributes:
            # ._cmd, ._cause, ._cmdline
            # .stderr, .stdout, .status, .command
            log.error(error)
            # We want to have it in the result dict too:
            result[branchname] = {'error': error}
            continue

        log.info("Investigating repo %r on branch %r...", repo.git_dir, branchname)

        result[branchname].update(init_stats_dict())
        iter_commits(repo, result, branchname, start, end)

    if not result:
        branchname = config.get(section, 'branch', fallback=None)
        start =  config.get(section, 'start', fallback='')
        end =  config.get(section, 'end', fallback='')

        if not branchname:
            # Use our default branch...
            branchname = 'develop'
        log.info('No branches key found in config file, using %r branch', branchname)
        result[branchname] = {}
        result[branchname]['start'] = str(start)
        result[branchname]['end'] = str(end)
        result[branchname].update(init_stats_dict())

        iter_commits(repo, result, branchname, start, end)

    log.debug("Result dict is %r", result)

    jsonfile = wd + ".json"
    with open(jsonfile, 'w') as fh:
        json.dump(result, fh, indent=4)
        log.debug("Writing results to %r", jsonfile)

    return result
