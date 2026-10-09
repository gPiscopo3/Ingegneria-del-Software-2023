import os
from unittest.mock import patch

import pytest

from src.logic import APICalls

# i test marcati "integration" chiamano GitHub (rete e GH_TOKEN): senza token vengono saltati, gli altri girano sempre


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: richiede la rete e la variabile d'ambiente GH_TOKEN")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("GH_TOKEN"):
        return
    skip = pytest.mark.skip(reason="GH_TOKEN non impostato")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(name="token")
def fixture_token():
    return os.environ["GH_TOKEN"]


@pytest.fixture(name="http_statuses")
def fixture_http_statuses():
    # codici HTTP delle risposte ricevute: dicono perché un risultato è vuoto (404, 401...) e non solo che lo è
    statuses = []
    original = APICalls.get_with_ratelimit

    def recording(url, header):
        response = original(url, header)
        statuses.append(response.status_code)
        return response

    with patch.object(APICalls, "get_with_ratelimit", side_effect=recording):
        yield statuses
