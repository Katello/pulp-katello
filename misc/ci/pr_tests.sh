#!/bin/bash

sudo apt-get install libssl-dev m2crypto
sudo pip install -r requirements-dev.pip --use-mirrors


echo "Running Pylint"
pylint --rcfile=./misc/spacewalk-pylint.rc distributors || exit 1
