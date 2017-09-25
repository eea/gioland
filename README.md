GioLand upload service
======================

The GioLand upload service is a platform where service providers can
deliver large files containing GIS data. Deliveries are tagged with:
country, theme, projection, spatial resolution, extent. Each delivery
goes through a workflow of checks, resubmissions and enhancement. See
[this issue](http://taskman.eionet.europa.eu/issues/2) for the initial requirements.

[![Travis](https://travis-ci.org/eea/gioland.svg?branch=master)](https://travis-ci.org/eea/gioland)
[![Coverage](https://coveralls.io/repos/github/eea/gioland/badge.svg?branch=master)](https://coveralls.io/github/eea/gioland?branch=master)
[![Docker]( https://dockerbuildbadges.quelltext.eu/status.svg?organization=eeacms&repository=gioland)](https://hub.docker.com/r/eeacms/gioland//builds)

### Prerequisites

* Install [Docker](https://docs.docker.com/engine/installation/)
* Install [Docker Compose](https://docs.docker.com/compose/install/)

### Installing the application

1. Get the source code:

       $ git clone https://github.com/eea/gioland.git
       $ cd gioland/

2. Customize env file:

        $ cp docker/app.env.example docker/app.env
        $ vim docker/app.env

3. Start application stack:

        $ docker-compose up -d
        $ docker-compose logs

### Configuration variables

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

### Development notes

#### Data model

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


#### Database

The application stores data in a ZODB database in
``$WAREHOUSE_PATH/filestorage``. The ``warehouse.py`` module is
responsible for connecting to the database and contains the models.
Uploaded files are stored in the filesystem, under
``$WAREHOUSE_PATH/parcels``, where each parcel has its own folder. Since
the files are accessed from a remote machine via CIFS, for automated GIS
processing, a tree of symlinks is maintained in
``$WAREHOUSE_PATH/tree``, where the path is generated using the metadata
fields of each parcel.


#### Notifications

Uploads and other workflow steps trigger notifications to relevant
people. They are sent via UNS_.

.. _UNS: http://uns.eionet.europa.eu/


#### Large files

Service providers upload very large files (in the order of 20GB). This
is done via HTTP, with the file split in 1MB chunks, and reassembled on
the server. The chunks are saved in a temporary folder in the parcel.


### Contacts

The project owner is Alan Steel (alan.steel at eaa.europa.eu)

Other people involved in this project are:

* Andreea Dima (andreea.dima at eaudeweb.ro)
* Diana Boiangiu (diana.boiangiu at eaudeweb.ro)


### Resources

Minimum requirements: 256MB RAM; 1 CPU

The production server needs a lot of hard disk space because raster map
images are uploaded there.

