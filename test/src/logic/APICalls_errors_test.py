from datetime import datetime
from unittest.mock import patch

import pytest
import requests
from requests import HTTPError

from src.logic import APICalls
from src.logic.APICalls import get_multiple_pages, get_pages_until

URL = "https://api.github.com/repos/o/r/issues?per_page=1"
NEXT_PAGE = '<https://api.github.com/repos/o/r/issues?page=2>; rel="next"'


def response(status, body=None, link=None):
    res = requests.Response()
    res.status_code = status
    res._content = (b"[]" if body is None else str(body).replace("'", '"').encode())
    if link:
        res.headers["Link"] = link
    return res


# la prima pagina è corretta, la seconda fallisce con lo stato indicato
def pages_then(status):
    return [response(200, [{"created_at": "2023-11-01T00:00:00Z"}], NEXT_PAGE), response(status)]


@pytest.mark.parametrize("function", [lambda: get_multiple_pages(URL, {}),
                                      lambda: get_pages_until(URL, {}, datetime(2024, 1, 1))])
@pytest.mark.parametrize("status", [403, 429, 500, 502, 503])
def test_pages_raise_on_quota_and_server_errors(function, status):
    with patch.object(APICalls, "get_with_ratelimit", side_effect=pages_then(status)):
        with pytest.raises(HTTPError) as error:
            function()
    assert error.value.response.status_code == status


@pytest.mark.parametrize("function", [lambda: get_multiple_pages(URL, {}),
                                      lambda: get_pages_until(URL, {}, datetime(2024, 1, 1))])
@pytest.mark.parametrize("status", [401, 404])
def test_pages_return_empty_on_missing_repo_or_token(function, status):
    with patch.object(APICalls, "get_with_ratelimit", side_effect=pages_then(status)):
        assert function() == []


def test_pages_ok_collects_all_pages():
    pages = [response(200, [{"id": 1}], NEXT_PAGE), response(200, [{"id": 2}])]
    with patch.object(APICalls, "get_with_ratelimit", side_effect=pages):
        assert get_multiple_pages(URL, {}) == [{"id": 1}, {"id": 2}]
