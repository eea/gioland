from datetime import datetime
from wtforms import Form, SelectField, StringField
from wtforms.validators import DataRequired, ValidationError
from flask import g
from warehouse import get_warehouse
from definitions import COUNTRIES, LOTS, STREAM_LOTS,\
    PRODUCTS, COUNTRY_PRODUCTS, RESOLUTIONS, LOT_PRODUCTS, \
    COUNTRY_LOT_PRODUCTS
from definitions import EXTENTS, PARTIAL, INITIAL_STAGE, REFERENCES
from definitions import COUNTRY, LOT, STREAM


def get_lot_product(lot_id, delivery_type):
    if delivery_type == COUNTRY:
        return COUNTRY_LOT_PRODUCTS.get(lot_id, None)
    else:
        return LOT_PRODUCTS.get(lot_id, None)


class _BaseDeliveryForm(Form):

    lot = SelectField('Lot', [DataRequired()], choices=LOTS)
    product = SelectField('Product', [DataRequired()], choices=PRODUCTS)

    def validate_product(self, field):
        id_lot = self.data['lot']
        product = get_lot_product(id_lot, self.DELIVERY_TYPE)
        if product is not None:
            if field.data in [x[0] for x in product]:
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

    product = SelectField('Product', [DataRequired()], choices=COUNTRY_PRODUCTS)
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
