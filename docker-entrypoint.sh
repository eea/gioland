#!/bin/bash

set -e

cd /gioland && python manage.py runcherrypy -p 5000 -H 0.0.0.0
