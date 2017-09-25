======================
GioLand upload service
======================

The GioLand upload service is a platform where service providers can
deliver large files containing GIS data. Deliveries are tagged with:
country, theme, projection, spatial resolution, extent. Each delivery
goes through a workflow of checks, resubmissions and enhancement. See
`this issue`_ for the initial requirements.

Website: https://gaur.eea.europa.eu/gioland/

Issue tracker: http://taskman.eionet.europa.eu/projects/gioland

Code repository: https://github.com/eea/gioland

.. _`this issue`: http://taskman.eionet.europa.eu/issues/2

.. image:: https://travis-ci.org/eea/gioland.svg?branch=master
    :target: https://travis-ci.org/eea/gioland

.. image:: https://coveralls.io/repos/github/eea/gioland/badge.svg?branch=master
    :target: https://coveralls.io/github/eea/gioland?branch=master

.. image:: https://dockerbuildbadges.quelltext.eu/status.svg?organization=eeacms&repository=gioland
   :target: https://hub.docker.com/r/eeacms/gioland/builds


Installation (using docker)
===========================

1. Clone the source repository::

   $ git clone https://github.com/eea/gioland.git

2. Change directory to project directory::

   $ cd gioland/

3. Create a configuration file (copy and modify the example)::

   $ cp .env.example .env

4. Create an Apache configuration file (copy and modify the example)::

   $ cp conf.d/virtual-host.conf.example conf.d/virtual-host.conf

5. Create an instance directory to store user data::

   $ mkdir instance

6. Run docker containers (as daemon)::

   $ docker-compose up -d


Installation (old style)
========================

Prerequisites
~~~~~~~~~~~~~
For RHEL systems::

    $ yum install python-virtualenv python-devel git openldap-devel

For debian systems::

    $ apt-get install python-dev python-virtualenv git libldap2-dev libsasl2-dev


Setup
~~~~~
1. Create a project directory and database directory::

    $ mkdir /var/local/gioland-production
    $ mkdir /var/local/gioland-production/instance
    $ cd /var/local/gioland-production

2. Clone the source repository::

    $ git clone https://github.com/eea/gioland.git

3. Create a virtualenv and install dependencies::

    $ cd /var/local/gioland-production
    $ virtualenv-2.7 ./venv
    $ ./venv/bin/pip install -r gioland/requirements.txt

4. Create a configuration file at ``/var/local/gioland-production/gioland/.env``::

    WAREHOUSE_PATH=/var/local/gioland-production/instance/warehouse
    LOCK_FILE_PATH=/var/local/gioland-production/instance/db.lock
    SECRET_KEY=some random string here

5. Start the application::

    $ cd /var/local/gioland-production/gioland
    $ source ../venv/bin/activate
    $ honcho start


Configuration variables
~~~~~~~~~~~~~~~~~~~~~~~
The application expects configuration via environment variables:

``DEBUG``
    Turns on debugging behaviour if set to ``on``. Not secure for use in
    production.

``WAREHOUSE_PATH``
    Path to folder containing the database and uploaded files.

``LOCK_FILE_PATH``
    Path to lockfile used to synchronize access to chunked file uploads.

``SENTRY_DSN``
    URL of Sentry server to report errors.

``SECRET_KEY``
    Random secret used for Flask browser sessions.

``ROLE_SP``, ``ROLE_ETC``, ``ROLE_NRC``, ``ROLE_ADMIN``, ``ROLE_VIEWER``
    Space-separated lists of principals for that role. Principals can be
    in the format ``user_id:NAME`` or ``ldap_group:NAME``.

``BASE_URL``
    Base URL of the application. Necessary to generate correct URLs.

``UNS_CHANNEL_ID``, ``UNS_LOGIN_USERNAME``, ``UNS_LOGIN_PASSWORD``
    Credentials for sending notifications via UNS.

``UNS_SUPPRESS_NOTIFICATIONS``
    If ``on``, don't send any UNS notifications.

``LDAP_SERVER``, ``LDAP_USER_DN_PATTERN``
    Server and DN pattern for connecting to LDAP. For example
    ``ldap://ldap3.eionet.europa.eu`` and
    ``uid={user_id},ou=Users,o=EIONET,l=Europe``.


Development notes
=================

Data model
~~~~~~~~~~
Each service provider delivery goes through the following stages:

* ``int`` (Service provider upload)
* ``sch`` (Semantic check)
* ``ver`` (Verification)
* ``vch`` (Verification check)
* ``enh`` (Enhancement)
* ``ech`` (Enhancement check)
* ``fin`` (Final integrated)
* ``fva`` (Final validated)

The initial upload is made in a "parcel" (think of it as a folder).
Subsequent steps in the workflow each have their own parcel, where more
files can be uploaded. Parcels have back-forward links so each delivery
is a chain of parcels. If a workflow step (e.g. Verification check)
results in a rejection, a new parcel of the previous step is created, so
the chain can loop back if needed.

Each delivery is tagged with the following metadata fields, which are
copied over from parcel to parcel:

* country
* theme
* projection
* resolution
* extent
* coverage


Database
~~~~~~~~
The application stores data in a ZODB database in
``$WAREHOUSE_PATH/filestorage``. The ``warehouse.py`` module is
responsible for connecting to the database and contains the models.
Uploaded files are stored in the filesystem, under
``$WAREHOUSE_PATH/parcels``, where each parcel has its own folder. Since
the files are accessed from a remote machine via CIFS, for automated GIS
processing, a tree of symlinks is maintained in
``$WAREHOUSE_PATH/tree``, where the path is generated using the metadata
fields of each parcel.


Notifications
~~~~~~~~~~~~~
Uploads and other workflow steps trigger notifications to relevant
people. They are sent via UNS_.

.. _UNS: http://uns.eionet.europa.eu/


Large files
~~~~~~~~~~~
Service providers upload very large files (in the order of 20GB). This
is done via HTTP, with the file split in 1MB chunks, and reassembled on
the server. The chunks are saved in a temporary folder in the parcel.


Contacts
========
The project owner is Alan Steel (alan.steel at eaa.europa.eu)

Other people involved in this project are:

* Alex Morega (alex.morega at eaudeweb.ro)
* Dragoș Catarahia (dragos.catarahia at eaudeweb.ro)


Resources
=========
Minimum requirements: 256MB RAM; 1 CPU

The production server needs a lot of hard disk space because raster map
images are uploaded there.


Copyright and license
=====================
Copyright 2007 European Environment Agency (EEA)

Licensed under the EUPL, Version 1.1 or – as soon they will be approved
by the European Commission - subsequent versions of the EUPL (the
"Licence");

You may not use this work except in compliance with the Licence.

You may obtain a copy of the Licence at:
https://joinup.ec.europa.eu/software/page/eupl/licence-eupl

Unless required by applicable law or agreed to in writing, software
distributed under the Licence is distributed on an "AS IS" basis,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the Licence for the specific language governing permissions and
limitations under the Licence.
