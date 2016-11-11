from collections import OrderedDict


SIMILAR_METADATA = (
    'country',
    'theme',
    'projection',
    'resolution',
    'extent',
)


EDITABLE_METADATA = SIMILAR_METADATA + ('delivery_type', 'coverage',)
METADATA = EDITABLE_METADATA + ('stage',)


REPORT_METADATA = ('country', 'category',)


STAGE_INT = 'int'
STAGE_SCH = 'sch'
STAGE_VER = 'ver'
STAGE_VCH = 'vch'
STAGE_ENH = 'enh'
STAGE_ERH = 'erh'
STAGE_ECH = 'ech'
STAGE_FIN = 'fin'
STAGE_FVA = 'fva'
STAGE_FIH = 'fih'


STAGES = OrderedDict((
    (STAGE_INT, {
        'label': "Service provider upload",
        'roles': ['ROLE_SP', 'ROLE_ADMIN'],
        'file_uploading': True,
    }),

    (STAGE_SCH, {
        'label': "Semantic check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'reject': True,
        'file_uploading': True,
    }),

    (STAGE_VER, {
        'label': "Verification",
        'roles': ['ROLE_SP', 'ROLE_NRC', 'ROLE_ADMIN'],
        'file_uploading': True,
    }),

    (STAGE_VCH, {
        'label': "Verification check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN', 'ROLE_VEP'],
        'reject': True,
        'file_uploading': False,
    }),

    (STAGE_ENH, {
        'label': "Enhancement",
        'roles': ['ROLE_SP', 'ROLE_NRC', 'ROLE_ADMIN'],
        'file_uploading': True,
    }),

    (STAGE_ERH, {
        'label': "Enhancement Report Check",
        'roles': ['ROLE_VEP', 'ROLE_ADMIN'],
        'reject': True,
        'file_uploading': False,
    }),

    (STAGE_ECH, {
        'label': "Enhancement Semantic Check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'reject': True,
        'file_uploading': True,
        'reject_stage': STAGE_ENH,
    }),

    (STAGE_FIN, {
        'label': "Final integrated",
        'roles': ['ROLE_ADMIN', 'ROLE_SP'],
        'file_uploading': True,

    }),

    (STAGE_FVA, {
        'label': "Final Semantic Check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'file_uploading': True,
        'reject': True,
        'reject_stage': STAGE_FIN,
    }),

    (STAGE_FIH, {
        'label': "Final HRL",
        'roles': ['ROLE_ADMIN'],
        'last': True,
    }),
))


LOT_STAGES = OrderedDict((
    (STAGE_INT, {
        'label': "Service provider upload",
        'roles': ['ROLE_SP', 'ROLE_ADMIN'],
        'file_uploading': True,
    }),

    (STAGE_FVA, {
        'label': "Final Semantic Check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'file_uploading': True,
        'reject': True,
        'reject_stage': STAGE_INT,
    }),

    (STAGE_FIH, {
        'label': "Final HRL Lot Mosaic",
        'roles': ['ROLE_ADMIN'],
        'last': True,
    }),

))


STAGES_FOR_MERGING = [STAGE_ENH]
STAGE_ORDER = list(STAGES)
LOT_STAGE_ORDER = list(LOT_STAGES)
INITIAL_STAGE = STAGE_ORDER[0]

COUNTRIES_MC = (
    ('at', "Austria"),
    ('be', "Belgium"),
    ('bg', "Bulgaria"),
    ('hr', "Croatia"),
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
)

COUNTRIES_CC = (
    ('al', "Albania"),
    ('ba', "Bosnia and Herzegovina"),
    ('me', "Montenegro"),
    ('mk', "Macedonia, FYR of"),
    ('rs', "Serbia"),
    ('xk', "Kosovo"),
    ('xt', "test"),
)


COUNTRIES = COUNTRIES_MC + COUNTRIES_CC


LOTS = (
    ('lot 1', 'Lot 1'),
    ('lot 2', 'Lot 2'),
    ('lot 3', 'Lot 3'),
    ('lot 4', 'Lot 4'),
    ('lot 5', 'Lot 5'),
    ('lot 6', 'Lot 6'),
)


COUNTRY = 'country'
LOT = 'lot'
STREAM = 'stream'

THEMES = (
    ('imp-deg', 'Imperviousness Degree'),
    ('imp-chg', 'Imperviousness Change'),
    ('tcd', 'Tree Cover Density'),
    ('fty', 'Forest Type'),
    ('tnt', 'Tree / Non-tree'),
    ('grc', 'Grassland Cover'),
    ('grd', 'Grassland Density'),
    ('wet', 'Wetlands'),
    ('pwb', 'Permanent Water Bodies'),
    ('ngr', 'New grassland - NGR'),
)


THEMES_FILTER = [
    ('imp-deg', 'Imperviousness Degree'),
    ('tcd', 'Tree Cover Density'),
    ('fty', 'Forest Type'),
    ('grc', 'Grassland Cover'),
    ('wet', 'Wetlands'),
    ('pwb', 'Permanent Water Bodies'),
    ('ngr', 'New grassland - NGR'),
]


THEMES_IDS = map(lambda x: x[0], THEMES)


PROJECTIONS = [
    ('ntl', "National"),
    ('eur', "European"),
]

RESOLUTIONS = [
    ('20m', "20m"),
    ('100m', "100m"),
]

FULL = 'full'
PARTIAL = 'partial'
EXTENTS = [
    (FULL, "Full"),
    (PARTIAL, "Partial"),
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
     'label': "Country / Lots",
     'rdf_uri': RDF_URI['locality'],
     'range': COUNTRIES + LOTS},

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
    'ROLE_VEP',
    'ROLE_VIEWER',
    'ROLE_ADMIN',
]


DATE_FORMAT = {
    'long': '%d/%m/%Y %H:%M',
    'uns': '%Y-%b-%d %H:%M:%S',
}


CATEGORIES = [
    ('for', 'Tree Cover density and Forest Type'),
    ('imp', 'Imperviousness'),
    ('gra', 'Grassland'),
    ('waw', 'Wetlands and Permanent Water Body'),
]


DOCUMENTS = ('rtf', 'odf', 'ods', 'gnumeric', 'abw', 'doc', 'docx', 'xls',
             'xlsx', 'pdf')
