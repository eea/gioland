from datetime import datetime
from wtforms import Form, SelectField, StringField
from wtforms.validators import DataRequired, ValidationError
from flask import g
from warehouse import get_warehouse
from definitions import COUNTRIES, LOTS, STREAM_LOTS,\
    THEMES, COUNTRY_THEMES, RESOLUTIONS, LOT_THEMES, \
    COUNTRY_LOT_THEMES
from definitions import EXTENTS, PARTIAL, INITIAL_STAGE, REFERENCES
from definitions import COUNTRY, LOT, STREAM


def get_lot_theme(id_lot, delivery_type):
    themes = [LOTS.index(x) for x in LOTS if x[0] == id_lot]

    theme_idx = themes[0]

    if delivery_type == COUNTRY:
        return COUNTRY_LOT_THEMES[theme_idx]
    else:
        return LOT_THEMES[theme_idx]


class _BaseDeliveryForm(Form):

    lot = SelectField('Lot', [DataRequired()], choices=LOTS)
    theme = SelectField('Product', [DataRequired()], choices=THEMES)

    def validate_theme(self, field):
        id_lot = self.data['lot']
        theme = get_lot_theme(id_lot, self.DELIVERY_TYPE)
        if theme is not None:
            if field.data in [x[0] for x in theme]:
                return field.validate(self)
        else:
            raise ValidationError('This lot does not have the product provided.')

    def save(self):
        data = dict(self.data)
        data['stage'] = INITIAL_STAGE
        data['delivery_type'] = self.DELIVERY_TYPE
        if data['delivery_type'] == LOT:
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


class _DeliveryForm(_BaseDeliveryForm):

    resolution = SelectField('Spatial resolution', [DataRequired()],
                             choices=RESOLUTIONS)
    reference = SelectField('Reference year', [DataRequired()], choices=REFERENCES)


class CountryDeliveryForm(_DeliveryForm):

    DELIVERY_TYPE = COUNTRY

    theme = SelectField('Product', [DataRequired()], choices=COUNTRY_THEMES)
    country = SelectField('Country', choices=COUNTRIES)


class LotDeliveryForm(_DeliveryForm):

    DELIVERY_TYPE = LOT

    extent = SelectField('Extent', [DataRequired()], choices=EXTENTS)
    coverage = StringField('Coverage')

    def validate_coverage(self, field):
        if self.extent.data == PARTIAL:
            return field.validate(self, [DataRequired()])


class StreamDeliveryForm(_BaseDeliveryForm):

    lot = SelectField('Lot', choices=STREAM_LOTS)
    DELIVERY_TYPE = STREAM
