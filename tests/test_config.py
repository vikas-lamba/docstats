import pytest
import py

from docstats.config import parseconfig, geturls

# Our global variable which is used in our configuration parser
config = None


def setup_module(module):
    if config is not None:
        return

    tmpdir = py.path.local('/tmp/pytest/').mkdir('config')
    tmpfile = tmpdir / "docstats.ini"
    tmpfile.write("""[globals]
branch = develop

[doc-a]
url = git://doc-a.git

[doc-b]
url = git://doc-b.git

[doc-c]
url =
        """)
    # module is our global scope
    module.config = parseconfig(tmpfile.strpath)[1]


def teardown_module(module):
    tmpdir = py.path.local('/tmp/pytest/config')
    tmpdir.remove(ignore_errors=True)


# --------------------------------------------------------
def test_config_global():
    assert config['globals']

def test_config_global_branch():
    assert config['globals']['branch']

def test_config_sections():
    sec = config.sections()
    assert config.sections() == ['doc-a', 'doc-b', 'doc-c']

def test_config_url():
    assert config['doc-a']['url'] == 'git://doc-a.git'


def test_geturls():
    urls = list(geturls(config))
    assert len(urls) == 2
    assert urls == ['git://doc-a.git', 'git://doc-b.git']