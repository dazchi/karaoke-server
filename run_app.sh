#!/bin/bash

source .venv/bin/activate
nohup python app.py > /dev/null 2>&1 &
