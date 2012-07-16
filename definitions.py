from collections import OrderedDict


METADATA_FIELDS = [
    'country',
    'theme',
    'projection',
    'resolution',
    'extent',
]


STAGES = OrderedDict([
    ('int', dict(label="Intermediate", roles=['ROLE_SERVICE_PROVIDER'])),
    ('sch', dict(label="Semantic check", roles=['ROLE_ETC'], reject=True)),
    ('ver', dict(label="Verification", roles=['ROLE_NRC'])),
    ('vch', dict(label="Verification check", roles=['ROLE_ETC'], reject=True)),
    ('enh', dict(label="Enhancement", roles=['ROLE_NRC'])),
    ('ech', dict(label="Enhancement check", roles=['ROLE_ETC'], reject=True)),
    ('fin', dict(label="Final integrated", roles=[])),
    ('fva', dict(label="Final validated", roles=[])),
])


STAGE_ORDER = list(STAGES)
INITIAL_STAGE = STAGE_ORDER[0]


COUNTRIES = [
    ('at', "Austria"),
    ('be', "Belgium"),
    ('bg', "Bulgaria"),
    ('cy', "Cyprus"),
    ('cz', "Czech Republic"),
    ('dk', "Denmark"),
    ('ee', "Estonia"),
    ('fi', "Finland"),
    ('fr', "France"),
    ('de', "Germany"),
    ('gr', "Greece"),
    ('hu', "Hungary"),
    ('is', "Iceland"),
    ('ie', "Ireland"),
    ('it', "Italy"),
    ('lv', "Latvia"),
    ('li', "Liechtenstein"),
    ('lt', "Lithuania"),
    ('lu', "Luxembourg"),
    ('mt', "Malta"),
    ('nl', "Netherlands"),
    ('no', "Norway"),
    ('pl', "Poland"),
    ('pt', "Portugal"),
    ('ro', "Romania"),
    ('sk', "Slovakia"),
    ('si', "Slovenia"),
    ('es', "Spain"),
    ('se', "Sweden"),
    ('ch', "Switzerland"),
    ('tr', "Turkey"),
    ('gb', "United Kingdom"),
]


THEMES = [
    ('imp-deg', "Imperviousness Degree"),
    ('imp-chg', "Imperviousness Change"),
    ('tcd',     "Tree Cover Density"),
    ('fty',     "Forest Type"),
    ('tnt',     "Tree / Non-tree"),
    ('tty',     "Tree Type"),
    ('grc',     "Grassland Cover"),
    ('grd',     "Grassland Density"),
    ('wet',     "Wetlands"),
    ('pwb',     "Permanent Water Bodies"),
]

PROJECTIONS = [
    ('ntl', "National"),
    ('eur', "European"),
]

RESOLUTIONS = [
    ('20m', "20m"),
    ('25m', "25m"),
    ('100m', "100m"),
]


EXTENTS = [
    ('full', "Full"),
    ('partial', "Partial"),
]


GIOLAND_SCHEMA = 'http://gaur.eea.europa.eu/gioland/static/schema.rdf'
RDF_URI = {
    'rdf_type': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
    'title': 'http://purl.org/dc/elements/1.1/title',
    'identifier': 'http://purl.org/dc/elements/1.1/identifier',
    'date': 'http://purl.org/dc/elements/1.1/date',
    'parcel_event': GIOLAND_SCHEMA + '#parcelevent',
    'locality': GIOLAND_SCHEMA + '#locality',
    'actor': GIOLAND_SCHEMA + '#actor',
    'stage': GIOLAND_SCHEMA + '#stage',
    'theme': GIOLAND_SCHEMA + '#theme',
    'projection': GIOLAND_SCHEMA + '#projection',
    'resolution': GIOLAND_SCHEMA + '#resolution',
    'extent': GIOLAND_SCHEMA + '#extent',
}
