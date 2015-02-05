from datetime import datetime
from wtforms import Form, SelectField
from flask import g

from warehouse import get_warehouse
from definitions import COUNTRIES, LOTS, THEMES, PROJECTIONS, RESOLUTIONS
from definitions import EXTENTS, INITIAL_STAGE


class _DeliveryForm(Form):

    theme = SelectField('Theme', choices=THEMES)
    projection = SelectField('Projection', choices=PROJECTIONS)
    resolution = SelectField('Spatial resolution', choices=RESOLUTIONS)
    extent = SelectField('Extent', choices=EXTENTS)

    def save(self):
        data = dict(self.data)
        data['stage'] = INITIAL_STAGE
        if data['extent'] == 'full':
            data['coverage'] = ''
        wh = get_warehouse()
        parcel = wh.new_parcel()
        parcel.save_metadata(data)
        parcel.add_history_item('New upload',
                                datetime.utcnow(),
                                g.username,
                                '')
        return parcel


class CountryDeliveryForm(_DeliveryForm):

    country = SelectField('Country', choices=COUNTRIES)


class LotDeliveryForm(_DeliveryForm):

    lot = SelectField('Lot', choices=LOTS)
