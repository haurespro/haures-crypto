#!/bin/bash
apt-get update -y
apt-get install -y libpq-dev libssl-dev libffi-dev build-essential python3-dev
pip install -r requirements.txt
