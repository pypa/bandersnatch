#!/usr/bin/env bash

# Script to work out if we're going to run tox unit tests or Integration Tests
# Integration Tests will go off and hit PyPI + pull whiteliested packages
# then check for outputs to exist

CI_CONFIG="src/bandersnatch/tests/ci.conf"
MIRROR_BASE="/tmp/pypi/web"
TGZ_SHA256="bc9430dae93f8bc53728773545cbb646a6b5327f98de31bdd6e1a2b2c6e805a9"


do_ci_verify() {
  peerme_index="$MIRROR_BASE/simple/p/peerme/index.html"
  peerme_json="$MIRROR_BASE/json/peerme"
  peerme_tgz="$MIRROR_BASE/packages/8f/1a/1aa000db9c5a799b676227e845d2b64fe725328e05e3d3b30036f50eb316/peerme-1.0.0-py36-none-any.whl"

  # Test JSON API file exists
  if [ ! -s $peerme_json ]
  then
    echo "No peerme JSON API file exists"
    exit 69
  fi

  # Test Simple HTML was written out
  if [ ! -s $peerme_index ]
  then
    echo "No $peerme_index exists"
    exit 70
  fi

  # Test we got a valid peerme sdist
  if [ ! -s $peerme_tgz ]
  then
    echo "No $peerme_tgz exists!"
    exit 71
  else
    TEST_TGZ_SHA261=$(shasum -a 256 $peerme_tgz | awk '{print $1}')
    if [ "$TEST_TGZ_SHA261" != "$TGZ_SHA256" ]
    then
      echo "Bad peerme 1.0.0 sha256: $TEST_TGZ_SHA261 != $TGZ_SHA256"
      exit 72
    fi
  fi

  echo "Bandersnatch PyPI CI finished successfully!"
}


errorCheck() {
  returnCode=$?
  if [ $returnCode -ne 0 ]
  then
    echo "ERROR $returnCode: $@" >&2
    exit $returnCode
  fi
}


do_ci() {
  echo "Starting CI bandersnatch mirror ..."
  # Run a mirror sync with ci.conf
  bandersnatch --debug --config $CI_CONFIG mirror
  errorCheck "Mirroring failed"

  echo "Starting banersnatch verify ..."
  # Run a verify over CI synced repo
  bandersnatch --debug --config $CI_CONFIG verify --delete --json-update
  errorCheck "Verify failed"

  # Check bandersnatch runs worked
  do_ci_verify
}


# Run tox OR Integration Tests
if [ "$TOXENV" != "INTEGRATION" ]
then
  tox
else
  echo "Running Ingtegration tests due to TOXENV set to INTEGRATION"
  do_ci
fi
