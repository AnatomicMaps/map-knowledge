import pytest
from mapknowledge import KnowledgeStore

def pytest_addoption(parser):
    parser.addoption(
        "--sckan-version",
        action="store",
        default="sckan-2024-09-21",
        help="SCKAN release to test against",
    )

@pytest.fixture(scope="session")
def store(request):
    sckan_version = request.config.getoption("--sckan-version")
    ks = KnowledgeStore(sckan_version=sckan_version)
    yield ks
    ks.close()
