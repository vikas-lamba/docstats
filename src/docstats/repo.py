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
from .log import log
from git import GitCommandError
from .tracker import TRACKERS, findbugid
from .utils import findallmails


def collect_diffstats(commit, dictresult):
    """Collect all the diff statistics like additions, deletions, file changes etc.

    :param commit: the commit
    :type commit: :class:`git.Commit`
    :param dict dictresult: the result of the dictionary
    """
    for item in commit.stats.total:
        dictresult[item] += commit.stats.total[item]


def collect_committers(commit, dictresult, committers):
    """Collect all the committers, be it inside or outside of a team.
       A commiter is identified as a team member is his email address is
       in the list of the committers.

    :param commit:  the commit
    :type commit: :class:`git.Commit`
    :param dict dictresult: the result of the dictionary
    :param committers: ditionary of all team mails; each items are in the
                       syntax of "mail": "primary-mail"
    :type committers: dict
    """
    mail = commit.committer.email.lower()
    if mail in committers:
        key = 'team-committers'
        mail = committers.get(mail)
    else:
        key = 'external-committers'

    dictresult[key].append(mail)
    dictresult[key+'-mails'].append(mail)


def collect_issues(message, dictresult):
    """Collect all tracker issues that can be find in a commit message

    :param message:  the message of a commit
    :type message: str
    :param dict dictresult: the result of the dictionary; the dict will
                            be changed after the function has been called!
    """

    for tracker, issue in findbugid(message):
        # Normalize GitHub issues which starts with
        # "fix(ed|s), clo(SED?), resOLVE(S|D)?
        tracker = "gh" if tracker[:3] in ('fix', 'clo', 'res') else tracker
        if tracker in TRACKERS:
            dictresult[tracker].append(issue)


def if_range_is_empty(repo, rev):
    """Check if there can be a valid commit retrieved from the given range

    :param repo: a repository
    :type repo: :class:`git.Repo`
    :param rev: the range
    :return: True when range has no commits, False otherwise
    """
    try:
        # Just try to grab the first commit
        first = next(repo.iter_commits(rev))
        return True
    except StopIteration:
        return False


def iter_commits(config, repo, dictresult, name, branchname,
                 start=None, end=None):
    """Iterate through all commits

    :param config: the docstats configuration contents
    :type config: :class:`configparser.ConfigParser`
    :param repo: a repository
    :type repo: :class:`git.Repo`
    :param dict dictresult: the result of the dictionary; the
                            dict will be changed after the
                            function has been called
    :param str name: name of the observable branch
    :param str branchname: the name of the branch
    :param start: the start position or None
    :param end: the end position or None
    :return:
    """
    start = '' if start is None else start
    end = '' if end is None else end

    rev = "..".join([start, end])
    if rev == '..':
        rev = repo.head

    try:
        for idx, commit in enumerate(repo.iter_commits(rev), 1):
            # Collect the statistics information
            collect_diffstats(commit, dictresult[name])

            # Collect the committers
            committers = findallmails(config.defaults().get('team-mails', []))
            collect_committers(commit, dictresult[name], committers)

            # Collect the bug issues from different trackers
            collect_issues(commit.message, dictresult[name])

        log.info("Used %s(start=%r, end=%r) #commits=%s",
                 branchname, start, end, idx)
        # Save overall commits:
        dictresult[name]['commits'] = idx

        return dictresult

    except UnboundLocalError:
        # This happens only, when we cannot find any commits on the branch with the specified
        # range.
        log.info("Skipping %s(start=%r, end=%r) as there are no commits in the specified range",
                 branchname, start, end)
        dictresult[name]['commits'] = 0
        # dictresult[name].update(init_stats_dict())
        # dictresult[name].update(init_tracker_dict())
        # dictresult[name].update(init_committer_dict())
        return dictresult


def init_stats_dict():
    """Create a dictionary statistics object with defaults to zero for;
       used for counting

    :return: dictionary with all values to zero
    :rtype: dict
    """
    return {item: 0 for item in ('deletions', 'files', 'insertions', 'lines')}


def init_tracker_dict():
    """Create a dictionary with empty tracker issues

    :return: dictionary with empty list
    :rtype: dict
    """
    return {item: [] for item in TRACKERS}


def init_committer_dict():
    """Create a dictionary with some empty committers keys

    :return: dictionary with empty lists
    :rtype: dict
    """
    return {item: [] for item in ('team-committers', 'external-committers',
                                  'team-committers-mails', 'external-committers-mails')}


def cleanup_dict(dictresult):
    """Cleanup step to turn all sets into list to make sure it is serialized by JSON

    :param dict dictresult: the result of the dictionary; the dict will be changed after the
                            function has been called
    """
    for branch in dictresult:
        #
        for tracker in TRACKERS:
            dictresult[branch][tracker] = list(set(dictresult[branch][tracker]))
        # Make committers unique and count them:
        for item in ('team-committers', 'external-committers',
                     # These are just for debugging purposes:
                     'team-committers-mails', 'external-committers-mails'):
            dictresult[branch][item] = len(set(dictresult[branch][item]))


def analyze(repo, config):
    """Analyze the repositories given at queue

    :param repo: a repository
    :type repo: :class:`git.Repo`
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

    # Check if we have a "branches" section in the config. If not, fallback
    # to develop branch:
    urls = list(getbranches(config.get(section, 'branches', fallback=None)))
    if not urls:
        branchname = config.get(section, 'branch', fallback=None)
        start = config.get(section, 'start', fallback='')
        end = config.get(section, 'end', fallback='')

        if not branchname:
            # Use our default branch...
            branchname = 'develop'
        urls = [(branchname, branchname, start, end)]

    for name, branchname, start, end in urls:
        # Initialize
        result[name] = {}
        result[name]['branch'] = branchname
        result[name]['start'] = str(start)
        result[name]['end'] = str(end)
        result[name].update(init_stats_dict())
        result[name].update(init_tracker_dict())
        result[name].update(init_committer_dict())

        try:
            # head = repo.create_head(branchname)
            # head.checkout(branchname)
            repo.git.checkout(branchname)
        except GitCommandError as error:
            # error contains the following attributes:
            # ._cmd, ._cause, ._cmdline
            # .stderr, .stdout, .status, .command
            log.error(error)
            # We want to have it in the result dict too:
            result[name] = {'error': error}
            continue

        log.info("Investigating %s on repo %r for branch %r...", name, repo.git_dir, branchname)
        iter_commits(config, repo, result, name, branchname, start, end)

    cleanup_dict(result)
    log.debug("Result dict is %r", result)
    return result
