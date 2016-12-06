from datetime import datetime
from wtforms import Form, SelectField
from wtforms.validators import DataRequired, ValidationError
from flask import g
from warehouse import get_warehouse
from definitions import COUNTRIES, COUNTRY, COUNTRY_PRODUCTS
from definitions import COUNTRY_LOT_PRODUCTS, EXTENTS, INITIAL_STAGE
from definitions import LOT, LOT_PRODUCTS, LOTS, PRODUCTS, RESOLUTIONS
from definitions import REFERENCES, STREAM,  STREAM_LOTS, STREAM_LOT_PRODUCTS


def get_lot_products(lot_id, delivery_type):
    if delivery_type == COUNTRY:
        return COUNTRY_LOT_PRODUCTS.get(lot_id)
    elif delivery_type == LOT:
        return LOT_PRODUCTS.get(lot_id)
    elif delivery_type == STREAM:
        return STREAM_LOT_PRODUCTS.get(lot_id)


class _BaseDeliveryForm(Form):

    lot = SelectField('Lot', [DataRequired()], choices=LOTS)
    product = SelectField('Product', [DataRequired()], choices=PRODUCTS)

    def validate(self):
        lot_id = self.data['lot']
        provided_product = self.data['product']
        products = get_lot_products(lot_id, self.DELIVERY_TYPE)
        if provided_product in [slug for slug, name in products]:
            return super(_BaseDeliveryForm, self).validate()
        raise ValidationError('This lot does not have the product provided.')

    def save(self):
        data = dict(self.data)
        data['stage'] = INITIAL_STAGE[self.DELIVERY_TYPE]
        data['delivery_type'] = self.DELIVERY_TYPE
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


class StreamDeliveryForm(_BaseDeliveryForm):

    lot = SelectField('Lot', choices=STREAM_LOTS)
    DELIVERY_TYPE = STREAM
