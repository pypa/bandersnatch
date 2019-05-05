# Maintaining Bandersnatch

This document sets out the roles, processes and responsibilities `bandersnatch`
maintainers hold and can conduct.

## Summary of being a Maintainer of `bandersnatch`

- **Issue Triage**
  - Asses if the Issue is accurate + reproducible
  - If feature, asses if this fits the *bandersnatch mission*
- **PR Merging**
  - Access Pull Requests for suitability and adherence to the *bandersnatch mission*
- If is preferred that big changes be pulling in from *branches* via *Pull Requests*
  - Peer reviewed by another maintainer
- **Releases**
- You will have **"the commit bit"** access

### Links to key mentioned files

- Change Log: [CHANGES.md](https://github.com/pypa/bandersnatch/blob/master/CHANGES.md)
- Mission Statement: Can be found in bandersnatch's [README.md](https://github.com/pypa/bandersnatch/blob/master/README.md)
- Readme File: [README.md](https://github.com/pypa/bandersnatch/blob/master/README.md)
- Semantic Versioning: [PEP 440 Semantic](https://www.python.org/dev/peps/pep-0440/#semantic-versioning)

## Processes

### Evaluating Issues and Pull Requests

Please always think of the mission of bandersnatch. We should just mirror in a
compatible way a PEP381 mirror. Simple is always better than complex and all *bug*
issues need to be reproducable for our developers.

#### pyup.io
- Remember it's not perfect
  - It does not take into account modules pinned dependencies
  - e.g. If requests wants *urllib3<1.25* *pyup.io* can still try and update it
- Until we have **CI** that effectively runs `pip freeze` from time to time we
  should recheck our minimal deps that we pin in `requirements.txt`

### Releasing to PyPI
Every maintainer can release to PyPI. A maintainer should have agreement of
two or more Maintainers that it is a suitable time for a release.

#### Release Process

- Update `src/bandersnatch/__init__.py` version
- Update the Change Log with difference from the last release
- Push / Merge to Master
- Create a GitHub Release
  - Tag with the semantic version number
- Build a `sdist` + `wheel`
- Use `twine` to upload to PyPI
