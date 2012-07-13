METADATA_FIELDS = [
    'country',
    'theme',
    'projection',
    'resolution',
    'extent',
]


STAGES = [
    ('int', "Intermediate"),
    ('sch', "Semantic check"),
    ('ver', "Verification"),
    ('vch', "Verification check"),
    ('enh', "Enhancement"),
    ('ech', "Enhancement check"),
    ('fin', "Final integrated"),
    ('fva', "Final validated"),
]
STAGE_ORDER = [s[0] for s in STAGES]
INITIAL_STAGE = STAGE_ORDER[0]


STAGE_ROLES = {
    'int': ['ROLE_SERVICE_PROVIDER'],
    'sch': ['ROLE_ETC'],
    'ver': ['ROLE_NRC'],
    'vch': ['ROLE_ETC'],
    'enh': ['ROLE_NRC'],
    'ech': ['ROLE_ETC'],
    'fin': [],
    'fva': [],
}


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
