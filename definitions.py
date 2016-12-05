from collections import OrderedDict
from utils import remove_duplicates_preserve_order


SIMILAR_METADATA = (
    'country',
    'lot',
    'product',
    'resolution',
    'extent',
    'reference',
)

LOT_EXCLUDE_METADATA = (
    'country',
)

COUNTRY_EXCLUDE_METADATA = (
    'coverage',
    'extent',
)

STREAM_EXCLUDE_METADATA = (
    'coverage',
    'extent',
    'country',
    'resolution',
    'reference'
)

EDITABLE_METADATA = SIMILAR_METADATA + ('delivery_type', 'coverage',)
METADATA = EDITABLE_METADATA + ('stage',)


REPORT_METADATA = ('lot', 'product')


STAGE_INT = 'int'
STAGE_SCH = 'sch'
STAGE_VER = 'ver'
STAGE_VCH = 'vch'
STAGE_VSC = 'vsc'
STAGE_ENH = 'enh'
STAGE_ERH = 'erh'
STAGE_ECH = 'ech'
STAGE_FIN = 'fin'
STAGE_FVA = 'fva'
STAGE_FIH = 'fih'
STAGE_FMC = 'fmc'
STAGE_FHM = 'fhm'

STAGES = OrderedDict((
    (STAGE_INT, {
        'label': "Service provider upload",
        'roles': ['ROLE_SP', 'ROLE_ADMIN'],
        'file_uploading': True,
    }),

    (STAGE_FVA, {
        'label': "Final Semantic check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'file_uploading': True,
        'reject': True,
        'reject_stage': STAGE_INT,
    }),

    (STAGE_FIH, {
        'label': "Final HRL",
        'roles': ['ROLE_SP',
                  'ROLE_ADMIN'],
        'last': True,
    }),
))


LOT_STAGES = OrderedDict((
    (STAGE_INT, {
        'label': "Service provider upload",
        'roles': ['ROLE_SP', 'ROLE_ADMIN'],
        'file_uploading': True,
    }),

    (STAGE_VSC, {
        'label': "Validation sample check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'file_uploading': True,
        'reject': True,
        'reject_stage': STAGE_INT,
        'partial': True,
    }),

    (STAGE_SCH, {
        'label': "Semantic Check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'file_uploading': True,
        'reject': True,
        'reject_stage': STAGE_INT,
    }),

    (STAGE_FIH, {
        'label': "Final HRL",
        'roles': ['ROLE_SP', 'ROLE_ADMIN'],
        'file_uploading': True,
    }),

    (STAGE_FMC, {
        'label': "Final mosaic check",
        'roles': ['ROLE_ETC', 'ROLE_ADMIN'],
        'reject': True,
        'reject_stage': STAGE_FIH,
    }),

    (STAGE_FHM, {
        'label': "Final HRL mosaic",
        'roles': ['ROLE_SP', 'ROLE_ETC', 'ROLE_ADMIN'],
        'last': True,
    }),
))


PARTIAL_LOT_STAGES = LOT_STAGES
FULL_LOT_STAGES = OrderedDict(
    (k, v) for k, v in LOT_STAGES.items()
    if not v.get('partial', False)
)


STAGES_FOR_MERGING = [STAGE_ENH]
STAGE_ORDER = list(STAGES)
LOT_STAGE_ORDER = list(LOT_STAGES)
PARTIAL_LOT_STAGES_ORDER = list(PARTIAL_LOT_STAGES)
FULL_LOT_STAGES_ORDER = list(FULL_LOT_STAGES)

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
    ('lot1', 'Lot 1 Imperviousness'),
    ('lot2', 'Lot 2 Forest'),
    ('lot3', 'Lot 3 Grassland'),
    ('lot4', 'Lot 4 Wetness and water'),
    ('lot5', 'Lot 5 Small woody features'),
)

STREAM_LOTS = LOTS[2:5]
COUNTRY = 'country'
LOT = 'lot'
STREAM = 'stream'


LOT1_PRODUCTS = (
    ('imp-deg', 'Imperviousness degree'),
    ('imp-chg', 'Imperviousness change'),
    ('imp-chg-cls', 'Imperviousness change classified'),
    ('imp-deg-prd', 'Imperviousness degree reference product (vector)'),
    ('imp-deg-grd', 'Imperviousness degree reference (grid)'),
    ('bvd', 'Biophysical variables delivery'),
)

LOT2_PRODUCTS = (
    ('bvd', 'Biophysical variables delivery'),
    ('tcd', 'Tree Cover Density'),
    ('dlt', 'Dominant Leaf Type'),
    ('fty', 'Forest Type'),
    ('fsl', 'Forest Additional Support Layer'),
    ('dlt-chg', 'Dominant Leaf Type Change'),
    ('tcd-chg', 'Tree Cover Density Change'),
    ('tcd-prd', 'Tree Cover Density Reference Product (Vector data)'),
    ('tcd-grd', 'Tree Cover Density Reference Grid'),
)

LOT3_PRODUCTS = (
    ('grl', 'Grassland'),
    ('gvp', 'Grassland Vegetation Probability'),
    ('pgi', 'Ploughing Indicator'),
)

LOT4_PRODUCTS = (
    ('wwp', 'Wetness and Water product'),
    ('wwp-idx', 'Wetness and Water Probability Index'),
)

LOT5_PRODUCTS = (
    ('swf', 'Small woody features'),
)

COUNTRY_LOT1_PRODUCTS = (
    ('imp-deg', 'Imperviousness degree'),
    ('imp-chg', 'Imperviousness change'),
    ('imp-chg-cls', 'Imperviousness change classified'),
)

COUNTRY_LOT2_PRODUCTS = (
    ('tcd', 'Tree Cover Density'),
    ('dlt', 'Dominant Leaf Type'),
    ('fty', 'Forest Type'),
    ('dlt-chg', 'Dominant Leaf Type Change'),
    ('tcd-chg', 'Tree Cover Density Change'),
)

COUNTRY_LOT3_PRODUCTS = (
    ('grl', 'Grassland'),
)

COUNTRY_LOT4_PRODUCTS = (
    ('wwp', 'Wetness and Water product'),
)

COUNTRY_LOT5_PRODUCTS = (
    ('swf', 'Small woody features'),
)

COUNTRY_LOT_PRODUCTS = {
    'lot1': COUNTRY_LOT1_PRODUCTS,
    'lot2': COUNTRY_LOT2_PRODUCTS,
    'lot3': COUNTRY_LOT3_PRODUCTS,
    'lot4': COUNTRY_LOT4_PRODUCTS,
    'lot5': COUNTRY_LOT5_PRODUCTS,
}

LOT_PRODUCTS = {
    "lot1": LOT1_PRODUCTS,
    "lot2": LOT2_PRODUCTS,
    "lot3": LOT3_PRODUCTS,
    "lot4": LOT4_PRODUCTS,
    "lot5": LOT5_PRODUCTS,
}

DEFAULT_LOT = 'lot1'
DEFAULT_DELIVERY_TYPE = LOT

STREAM_LOT_PRODUCTS = LOT3_PRODUCTS + \
                      LOT4_PRODUCTS + \
                      LOT5_PRODUCTS


PRODUCTS = remove_duplicates_preserve_order(
    LOT1_PRODUCTS +
    LOT2_PRODUCTS +
    LOT3_PRODUCTS +
    LOT4_PRODUCTS +
    LOT5_PRODUCTS
)

COUNTRY_PRODUCTS = remove_duplicates_preserve_order(
    COUNTRY_LOT1_PRODUCTS +
    COUNTRY_LOT2_PRODUCTS +
    COUNTRY_LOT3_PRODUCTS +
    COUNTRY_LOT4_PRODUCTS +
    COUNTRY_LOT5_PRODUCTS
)

STREAM_PRODUCTS = remove_duplicates_preserve_order(STREAM_LOT_PRODUCTS)

PRODUCTS_FILTER = [
    ('imp-deg', 'Imperviousness Degree'),
    ('tcd', 'Tree Cover Density'),
    ('fty', 'Forest Type'),
    ('grc', 'Grassland Cover'),
    ('wet', 'Wetlands'),
    ('pwb', 'Permanent Water Bodies'),
    ('ngr', 'New grassland - NGR'),
]


PRODUCTS_IDS = map(lambda x: x[0], PRODUCTS)
COUNTRY_PRODUCTS_IDS = (map(lambda x: x[0], COUNTRY_PRODUCTS))

RESOLUTIONS = [
    ('20m', "20 m"),
    ('100m', "100 m"),
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
    'lot': GIOLAND_SCHEMA + '#lot',
    'actor': GIOLAND_SCHEMA + '#actor',
    'actor_name': GIOLAND_SCHEMA + '#actor_name',
    'stage': GIOLAND_SCHEMA + '#stage',
    'product': GIOLAND_SCHEMA + '#product',
    'resolution': GIOLAND_SCHEMA + '#resolution',
    'extent': GIOLAND_SCHEMA + '#extent',
    'event_type': GIOLAND_SCHEMA + '#event_type',
    'decision': GIOLAND_SCHEMA + '#decision',
}


UNS_FIELD_DEFS = [  # Need to update this list soon to the new format

    {'name': 'country',
     'label': "Country",
     'rdf_uri': RDF_URI['locality'],
     'range': COUNTRIES},

    {'name': 'lot',
     'label': "Lot",
     'rdf_uri': RDF_URI['lot'],
     'range': LOTS},

    {'name': 'product',
     'label': "Product",
     'rdf_uri': RDF_URI['product'],
     'range': PRODUCTS},

    {'name': 'extent',
     'label': "Extent",
     'rdf_uri': RDF_URI['extent'],
     'range': EXTENTS},

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

REFERENCES = (
    ('2006', '2006'),
    ('2009', '2009'),
    ('2012', '2012'),
    ('2015', '2015'),
    ('20062009', '2006-2009'),
    ('20092012', '2009-2012'),
    ('20122015', '2012-2015'),
    ('20062012', '2006-2012'),
)

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
