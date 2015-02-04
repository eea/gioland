from wtforms import Form, SelectField
from werkzeug.utils import HTMLBuilder

from definitions import COUNTRIES, LOTS, THEMES, PROJECTIONS, RESOLUTIONS
from definitions import EXTENTS


class _DeliveryForm(Form):

    themes = SelectField('Theme', choices=THEMES)
    projection = SelectField('Projection', choices=PROJECTIONS)
    resolution = SelectField('Spatial resolution', choices=RESOLUTIONS)
    extent = SelectField('Extent', choices=EXTENTS)


class CountryDeliveryForm(_DeliveryForm):

    country = SelectField('Country', choices=COUNTRIES)


class LotDeliveryForm(_DeliveryForm):

    lot = SelectField('Lot', choices=LOTS)
