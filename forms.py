from datetime import datetime
from wtforms import Form, SelectField, StringField
from wtforms.validators import DataRequired
from flask import g

from warehouse import get_warehouse
from definitions import COUNTRIES, LOTS, THEMES, PROJECTIONS, RESOLUTIONS
from definitions import EXTENTS, PARTIAL, INITIAL_STAGE
from definitions import COUNTRY, LOT


class _DeliveryForm(Form):

    theme = SelectField('Theme', [DataRequired()], choices=THEMES)
    projection = SelectField('Projection', [DataRequired()],
                             choices=PROJECTIONS)
    resolution = SelectField('Spatial resolution', [DataRequired()],
                             choices=RESOLUTIONS)
    extent = SelectField('Extent', [DataRequired()], choices=EXTENTS)
    coverage = StringField('Coverage')

    def validate_coverage(self, field):
        if self.extent.data == PARTIAL:
            return field.validate(self, [DataRequired()])

    def save(self):
        data = dict(self.data)
        data['stage'] = INITIAL_STAGE
        if data['extent'] == 'full':
            data['coverage'] = ''
        data['delivery_type'] = self.DELIVERY_TYPE
        wh = get_warehouse()
        parcel = wh.new_parcel()
        parcel.save_metadata(data)
        parcel.add_history_item('New upload',
                                datetime.utcnow(),
                                g.username,
                                '')
        return parcel


class CountryDeliveryForm(_DeliveryForm):

    DELIVERY_TYPE = COUNTRY

    country = SelectField('Country', choices=COUNTRIES)


class LotDeliveryForm(_DeliveryForm):

    DELIVERY_TYPE = LOT

    country = SelectField('Lot', choices=LOTS)
