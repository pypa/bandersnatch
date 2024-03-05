# flake8: noqa

SIXTYNINE_METADATA = {
    "info": {
        "author": "Cooper Lees",
        "author_email": "me@cooperlees.com",
        "bugtrack_url": None,
        "classifiers": [
            "Development Status :: 3 - Alpha",
            "License :: OSI Approved :: BSD License",
            "Programming Language :: Python :: 3 :: Only",
            "Programming Language :: Python :: 3.6",
        ],
        "description": "# 69",
        "description_content_type": "",
        "docs_url": None,
        "download_url": "",
        "downloads": {"last_day": -1, "last_month": -1, "last_week": -1},
        "home_page": "http://github.com/cooperlees/69",
        "keywords": "",
        "license": "BSD",
        "maintainer": "",
        "maintainer_email": "",
        "name": "69",
        "package_url": "https://pypi.org/project/69/",
        "platform": "",
        "project_url": "https://pypi.org/project/69/",
        "project_urls": {"Homepage": "http://github.com/cooperlees/69"},
        "release_url": "https://pypi.org/project/69/6.9/",
        "requires_dist": None,
        "requires_python": ">=3.6",
        "summary": "Handy module for 2",
        "version": "6.9",
        "yanked": False,
        "yanked_reason": None,
    },
    "last_serial": 10333928,
    "releases": {
        "0.69": [
            {
                "comment_text": "",
                "digests": {
                    "md5": "4328d962656395fbd3e730c9d30bb48c",
                    "sha256": (
                        "5c11f48399f9b1bca802751513f1f97bff6ce97e6facb576b7729e1351453c10"
                    ),
                },
                "downloads": -1,
                "filename": "69-0.69.tar.gz",
                "has_sig": False,
                "md5_digest": "4328d962656395fbd3e730c9d30bb48c",
                "packagetype": "sdist",
                "python_version": "source",
                "requires_python": ">=3.6",
                "size": 1078,
                "upload_time": "2018-05-17T03:37:19",
                "upload_time_iso_8601": "2018-05-17T03:37:19.330556Z",
                "url": "https://files.pythonhosted.org/packages/d3/cc/95dc5434362bd333a1fec275231775d748315b26edf1e7e568e6f8660238/69-0.69.tar.gz",
                "yanked": False,
                "yanked_reason": None,
            }
        ],
        "6.9": [
            {
                "comment_text": "",
                "digests": {
                    "md5": "ff4bf804ef3722a1fd8853a8a32513d4",
                    "sha256": (
                        "0c8deb7c8574787283c3fc08b714ee63fd6752a38d13515a9d8508798d428597"
                    ),
                },
                "downloads": -1,
                "filename": "69-6.9.tar.gz",
                "has_sig": False,
                "md5_digest": "ff4bf804ef3722a1fd8853a8a32513d4",
                "packagetype": "sdist",
                "python_version": "source",
                "requires_python": ">=3.6",
                "size": 1077,
                "upload_time": "2018-05-17T03:47:45",
                "upload_time_iso_8601": "2018-05-17T03:47:45.953704Z",
                "url": "https://files.pythonhosted.org/packages/7b/6e/7c4ce77c6ca092e94e19b78282b459e7f8270362da655cbc6a75eeb9cdd7/69-6.9.tar.gz",
                "yanked": False,
                "yanked_reason": None,
            }
        ],
    },
    "urls": [
        {
            "comment_text": "",
            "digests": {
                "md5": "ff4bf804ef3722a1fd8853a8a32513d4",
                "sha256": (
                    "0c8deb7c8574787283c3fc08b714ee63fd6752a38d13515a9d8508798d428597"
                ),
            },
            "downloads": -1,
            "filename": "69-6.9.tar.gz",
            "has_sig": False,
            "md5_digest": "ff4bf804ef3722a1fd8853a8a32513d4",
            "packagetype": "sdist",
            "python_version": "source",
            "requires_python": ">=3.6",
            "size": 1077,
            "upload_time": "2018-05-17T03:47:45",
            "upload_time_iso_8601": "2018-05-17T03:47:45.953704Z",
            "url": "https://files.pythonhosted.org/packages/7b/6e/7c4ce77c6ca092e94e19b78282b459e7f8270362da655cbc6a75eeb9cdd7/69-6.9.tar.gz",
            "yanked": False,
            "yanked_reason": None,
        }
    ],
    "vulnerabilities": [],
}

EXPECTED_SIMPLE_SIXTYNINE_JSON_1_1 = """\
{"files": [{"filename": "69-0.69.tar.gz", "hashes": {"sha256": "5c11f48399f9b1bca802751513f1f97bff6ce97e6facb576b7729e1351453c10"}, "requires-python": ">=3.6", "size": 1078, "upload-time": "2018-05-17T03:37:19.330556Z", "url": "../../packages/d3/cc/95dc5434362bd333a1fec275231775d748315b26edf1e7e568e6f8660238/69-0.69.tar.gz", "yanked": false}, {"filename": "69-6.9.tar.gz", "hashes": {"sha256": "0c8deb7c8574787283c3fc08b714ee63fd6752a38d13515a9d8508798d428597"}, "requires-python": ">=3.6", "size": 1077, "upload-time": "2018-05-17T03:47:45.953704Z", "url": "../../packages/7b/6e/7c4ce77c6ca092e94e19b78282b459e7f8270362da655cbc6a75eeb9cdd7/69-6.9.tar.gz", "yanked": false}], "meta": {"api-version": "1.1", "_last-serial": "10333928"}, "name": "69", "versions": ["0.69", "6.9"]}\
"""

EXPECTED_SIMPLE_SIXTYNINE_JSON_PRETTY_1_1 = """\
{
    "files": [
        {
            "filename": "69-0.69.tar.gz",
            "hashes": {
                "sha256": "5c11f48399f9b1bca802751513f1f97bff6ce97e6facb576b7729e1351453c10"
            },
            "requires-python": ">=3.6",
            "size": 1078,
            "upload-time": "2018-05-17T03:37:19.330556Z",
            "url": "../../packages/d3/cc/95dc5434362bd333a1fec275231775d748315b26edf1e7e568e6f8660238/69-0.69.tar.gz",
            "yanked": false
        },
        {
            "filename": "69-6.9.tar.gz",
            "hashes": {
                "sha256": "0c8deb7c8574787283c3fc08b714ee63fd6752a38d13515a9d8508798d428597"
            },
            "requires-python": ">=3.6",
            "size": 1077,
            "upload-time": "2018-05-17T03:47:45.953704Z",
            "url": "../../packages/7b/6e/7c4ce77c6ca092e94e19b78282b459e7f8270362da655cbc6a75eeb9cdd7/69-6.9.tar.gz",
            "yanked": false
        }
    ],
    "meta": {
        "api-version": "1.1",
        "_last-serial": "10333928"
    },
    "name": "69",
    "versions": [
        "0.69",
        "6.9"
    ]
}\
"""

EXPECTED_SIMPLE_GLOBAL_JSON_PRETTY = """\
{
    "meta": {
        "_last-serial": 12345,
        "api-version": "1.1"
    },
    "projects": [
        {
            "name": "69"
        },
        {
            "name": "foo"
        }
    ]
}\
"""
