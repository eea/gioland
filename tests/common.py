from contextlib import contextmanager


def create_mock_app(warehouse_path):
    from manage import create_app
    return create_app({
        'TESTING': True,
        'SECRET_KEY': 'asdf',
        'WAREHOUSE_PATH': str(warehouse_path),
    })


@contextmanager
def get_warehouse(app):
    import parcel
    with app.test_request_context():
        with parcel.warehouse() as wh:
            yield wh
