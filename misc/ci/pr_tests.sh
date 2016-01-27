#!/bin/bash

sudo apt-get install libssl-dev m2crypto
sudo pip install -r requirements-dev.pip


echo "Running Pylint"
pylint --rcfile=./misc/spacewalk-pylint.rc distributors || exit 1
