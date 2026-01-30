"""Package version fetchers initialization."""

from .npm import fetch_npm_version
from .pypi import fetch_pypi_version
from .nuget import fetch_nuget_version
from .maven import fetch_maven_gradle_version
from .docker import fetch_docker_version
from .helm import fetch_helm_chart_version
from .terraform import fetch_terraform_provider_version, fetch_terraform_module_version
from .go import fetch_go_version

__all__ = [
    "fetch_npm_version",
    "fetch_pypi_version",
    "fetch_nuget_version",
    "fetch_maven_gradle_version",
    "fetch_docker_version",
    "fetch_helm_chart_version",
    "fetch_terraform_provider_version",
    "fetch_terraform_module_version",
    "fetch_go_version",
]
