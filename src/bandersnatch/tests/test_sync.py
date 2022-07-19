from os import sep
from unittest.mock import AsyncMock

import pytest

from bandersnatch import utils
from bandersnatch.mirror import BandersnatchMirror


@pytest.mark.asyncio
async def test_sync_specific_packages(mirror: BandersnatchMirror) -> None:
    FAKE_SERIAL = b"112233"
    with open("status", "wb") as f:
        f.write(FAKE_SERIAL)
    # Package names should be normalized by synchronize()
    specific_packages = ["Foo"]
    mirror.master.all_packages = AsyncMock(return_value={"foo": 1})  # type: ignore
    mirror.json_save = True
    # Recall bootstrap so we have the json dirs
    mirror._bootstrap()
    await mirror.synchronize(specific_packages)

    assert """\
json{0}foo
packages{0}2.7{0}f{0}foo{0}foo.whl
packages{0}any{0}f{0}foo{0}foo.zip
pypi{0}foo{0}json
simple{0}foo{0}index.html
simple{0}foo{0}index.v1_html
simple{0}foo{0}index.v1_json
simple{0}index.html
simple{0}index.v1_html
simple{0}index.v1_json""".format(
        sep
    ) == utils.find(
        mirror.webdir, dirs=False
    )

    assert (
        open("web{0}simple{0}index.html".format(sep)).read()
        == """\
<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>Simple Index</title>
  </head>
  <body>
    <a href="foo/">foo</a><br/>
  </body>
</html>"""
    )
    # The "sync" method shouldn't update the serial
    assert open("status", "rb").read() == FAKE_SERIAL
