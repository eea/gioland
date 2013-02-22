from collections import OrderedDict


EDITABLE_METADATA = [
    'country',
    'theme',
    'projection',
    'resolution',
    'extent',
    'coverage',
]


METADATA = EDITABLE_METADATA + ['stage']


STAGES = OrderedDict([
    ('int', {
        'label': "Service provider upload",
        'roles': ['ROLE_SP', 'ROLE_ADMIN'],
    }),

    ('sch', {
        'label': "Semantic check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'reject': True,
    }),

    ('ver', {
        'label': "Verification",
        'roles': ['ROLE_SP', 'ROLE_NRC', 'ROLE_ADMIN'],
    }),

    ('vch', {
        'label': "Verification check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'reject': True,
    }),

    ('enh', {
        'label': "Enhancement",
        'roles': ['ROLE_SP', 'ROLE_NRC', 'ROLE_ADMIN'],
    }),

    ('ech', {
        'label': "Enhancement check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'reject': True,
    }),

    ('fin', {
        'label': "Final integrated",
        'roles': ['ROLE_ADMIN'],
    }),

    ('fva', {
        'label': "Final validated",
        'roles': ['ROLE_ADMIN'],
        'last': True,
    }),
])


STAGE_ORDER = list(STAGES)
INITIAL_STAGE = STAGE_ORDER[0]


COUNTRIES_MC = [
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


COUNTRIES_CC = [
    ('al', "Albania"),
    ('ba', "Bosnia and Herzegovina"),
    ('hr', "Croatia"),
    ('me', "Montenegro"),
    ('mk', "Macedonia, FYR of"),
    ('rs', "Serbia"),
    ('xk', "Kosovo"),
    ('xt', "test"),
]


COUNTRIES = COUNTRIES_MC + COUNTRIES_CC


THEMES = [
    ('imp-deg', "Imperviousness Degree"),
    ('imp-chg', "Imperviousness Change"),
    ('tcd',     "Tree Cover Density"),
    ('fty',     "Forest Type"),
    ('tnt',     "Tree / Non-tree"),
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
    'actor_name': GIOLAND_SCHEMA + '#actor_name',
    'stage': GIOLAND_SCHEMA + '#stage',
    'theme': GIOLAND_SCHEMA + '#theme',
    'projection': GIOLAND_SCHEMA + '#projection',
    'resolution': GIOLAND_SCHEMA + '#resolution',
    'extent': GIOLAND_SCHEMA + '#extent',
    'event_type': GIOLAND_SCHEMA + '#event_type',
    'decision': GIOLAND_SCHEMA + '#decision',
}


UNS_FIELD_DEFS = [

    {'name': 'country',
     'label': "Country",
     'rdf_uri': RDF_URI['locality'],
     'range': COUNTRIES},

    {'name': 'theme',
     'label': "Theme",
     'rdf_uri': RDF_URI['theme'],
     'range': THEMES},

    {'name': 'extent',
     'label': "Extent",
     'rdf_uri': RDF_URI['extent'],
     'range': EXTENTS},

    {'name': 'projection',
     'label': "Projection",
     'rdf_uri': RDF_URI['projection'],
     'range': PROJECTIONS},

    {'name': 'resolution',
     'label': "Spatial resolution",
     'rdf_uri': RDF_URI['resolution'],
     'range': RESOLUTIONS},

    {'name': 'stage',
     'label': "Stage",
     'rdf_uri': RDF_URI['stage'],
     'range': [(k, STAGES[k]['label']) for k in STAGES]},

    {'name': 'event_type',
     'label': "Event type",
     'rdf_uri': RDF_URI['event_type'],
     'range': [('comment', "Comment"), ('stage_finished', "Stage finished")]},

]


ALL_ROLES = [
    'ROLE_SP',
    'ROLE_ETC',
    'ROLE_NRC',
    'ROLE_VIEWER',
    'ROLE_ADMIN',
]


DATE_FORMAT = {
    'long': '%d/%m/%Y %H:%M',
    'uns': '%Y-%b-%d %H:%M:%S',
}
