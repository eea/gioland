from contextlib import contextmanager
import flask


def create_mock_app(warehouse_path):
    from manage import create_app
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': 'asdf',
        'WAREHOUSE_PATH': str(warehouse_path),
    })

    @app.route('/test_login', methods=['POST'])
    def test_login():
        flask.session['username'] = flask.request.form['username']
        return "ok"

    return app


@contextmanager
def get_warehouse(app):
    import parcel
    with app.test_request_context():
        with parcel.warehouse() as wh:
            yield wh
