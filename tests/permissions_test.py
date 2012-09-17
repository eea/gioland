from StringIO import StringIO
from mock import patch, call
import flask
from common import AppTestCase, record_events


def setUpModule(self):
    import parcel
    import warehouse
    self.parcel = parcel
    self.warehouse = warehouse


class PermisionsTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def add_to_role(self, username, role_name):
        self.app.config.setdefault(role_name, []).append('user_id:' + username)

    def remove_from_role(self, username, role_name):
        if role_name in self.app.config:
            users = self.app.config[role_name]
            self.app.config[role_name] = [u for u in users
                                          if u != 'user_id:%s' % username]

    def create_parcel(self, stage=None):
        with patch('auth.authorize'):
            post_resp = self.client.post('/parcel/new',
                                         data=self.PARCEL_METADATA)
            self.assertEqual(post_resp.status_code, 302)
            parcel_name = post_resp.location.rsplit('/', 1)[-1]

        if stage is not None:
            with self.app.test_request_context():
                wh = warehouse.get_warehouse()
                wh.get_parcel(parcel_name).metadata['stage'] = stage

        return parcel_name

    def try_new_parcel(self):
        with record_events(parcel.parcel_created) as new_parcels:
            post_resp = self.client.post('/parcel/new',
                                         data=self.PARCEL_METADATA)
        if post_resp.status_code == 403:
            self.assertEqual(len(new_parcels), 0)
            return False
        elif post_resp.status_code == 302:
            self.assertEqual(len(new_parcels), 1)
            return True
        else:
            self.fail('unexpected http status code')

    def try_upload(self, name):
        data = {
            'resumableFilename': 'data.gml',
            'resumableIdentifier': 'data_gml',
            'resumableTotalSize': '3',
        }
        file_data = dict(data)
        file_data['resumableChunkSize'] = '3'
        file_data['resumableChunkNumber'] = '1'
        file_data['file'] = (StringIO('teh'), 'data.gml')

        with record_events(parcel.file_uploaded) as uploaded_files:
            post_resp = self.client.post('/parcel/%s/chunk' % name,
                                         data=file_data)
            if post_resp.status_code == 403:
                self.assertEqual(len(uploaded_files), 0)
                return False
            elif post_resp.status_code == 200:
                resp = self.client.post('/parcel/%s/finalize_upload' % name,
                                        data=data)
                if resp.status_code != 200:
                    self.fail('finalize upload failed')
                self.assertEqual(len(uploaded_files), 1)
                return True
            else:
                self.fail('unexpected http status code')

    def try_upload_file(self, name, filename='data_single.gml'):
        data = {'file': (StringIO('teh map data'), filename)}
        resp = self.client.post('/parcel/%s/file' % name, data=data)
        if resp.status_code == 302:
            return True
        elif resp.status_code == 403:
            return False
        else:
            self.fail('unexpected http status code')

    def try_finalize(self, parcel_name):
        with record_events(parcel.parcel_finalized) as finalized_parcels:
            post_resp = self.client.post('/parcel/%s/finalize' % parcel_name)
        if post_resp.status_code == 403:
            self.assertEqual(len(finalized_parcels), 0)
            return False
        elif post_resp.status_code == 302:
            self.assertEqual(len(finalized_parcels), 1)
            return True
        else:
            self.fail('unexpected http status code')

    def try_delete(self, parcel_name):
        with record_events(parcel.parcel_deleted) as deleted_parcels:
            post_resp = self.client.post('/parcel/%s/delete' % parcel_name)
        if post_resp.status_code == 403:
            self.assertEqual(len(deleted_parcels), 0)
            return False
        elif post_resp.status_code == 302:
            self.assertEqual(len(deleted_parcels), 1)
            return True
        else:
            self.fail('unexpected http status code')

    def try_delete_file(self, parcel_name, filename='data.gml'):
        with record_events(parcel.parcel_file_deleted) as deleted_parcel_files:
            post_resp = self.client.post('/parcel/%s/file/%s/delete' %
                                        (parcel_name, filename))
            if post_resp.status_code == 403:
                self.assertEqual(len(deleted_parcel_files), 0)
                return False
            elif post_resp.status_code == 302:
                self.assertEqual(len(deleted_parcel_files), 1)
                return True
            else:
                self.fail('unexpected http status code')

    def test_no_user_not_allowed(self):
        self.client.get('/test_logout')
        resp = self.client.get('/')
        self.assertEqual(302, resp.status_code)
        self.assertIn('/login', resp.location)

    def test_random_user_not_allowed(self):
        self.remove_from_role('somebody', 'ROLE_VIEWER')
        resp = self.client.get('/')
        self.assertEqual(200, resp.status_code)
        self.assertIn('You are not authorized to view this page.', resp.data)

    def test_role_viewer_allowed(self):
        resp = self.client.get('/')
        self.assertEqual(200, resp.status_code)

    def test_random_user_not_allowed_to_begin_upload(self):
        self.assertFalse(self.try_new_parcel())

    def test_service_provider_allowed_to_begin_upload(self):
        self.add_to_role('somebody', 'ROLE_SP')
        self.assertTrue(self.try_new_parcel())

    def test_random_user_not_allowed_to_upload_at_intermediate_state(self):
        name = self.create_parcel()
        self.assertFalse(self.try_upload(name))
        self.assertFalse(self.try_upload_file(name))

    def test_service_provider_allowed_to_upload_at_intermediate_state(self):
        self.add_to_role('somebody', 'ROLE_SP')
        name = self.create_parcel()
        self.assertTrue(self.try_upload(name))
        self.assertTrue(self.try_upload_file(name))

    def test_random_user_not_allowed_to_finalize_at_intermediate_state(self):
        name = self.create_parcel()
        self.assertFalse(self.try_finalize(name))

    def test_service_provider_allowed_to_finalize_at_intermediate_state(self):
        self.add_to_role('somebody', 'ROLE_SP')
        name = self.create_parcel()
        self.assertTrue(self.try_finalize(name))

    def test_admin_allowed_to_finalize_at_intermediate_state(self):
        self.add_to_role('somebody', 'ROLE_ADMIN')
        name = self.create_parcel()
        self.assertTrue(self.try_finalize(name))

    def test_random_user_not_allowed_to_upload_at_semantic_check_stage(self):
        name = self.create_parcel(stage='sch')
        self.assertFalse(self.try_upload(name))
        self.assertFalse(self.try_upload_file(name))

    def test_etc_user_allowed_to_upload_at_semantic_check_stage(self):
        self.add_to_role('somebody', 'ROLE_ETC')
        name = self.create_parcel(stage='sch')
        self.assertTrue(self.try_upload(name))
        self.assertTrue(self.try_upload_file(name))

    def test_admin_user_allowed_to_upload_at_semantic_check_stage(self):
        self.add_to_role('somebody', 'ROLE_ADMIN')
        name = self.create_parcel(stage='sch')
        self.assertTrue(self.try_upload(name))
        self.assertTrue(self.try_upload_file(name))

    def test_random_user_not_allowed_to_finalize_at_semantic_check_stage(self):
        name = self.create_parcel(stage='sch')
        self.assertFalse(self.try_finalize(name))

    def test_service_provider_not_allowed_to_finalize_at_semantic_check(self):
        self.add_to_role('somebody', 'ROLE_SP')
        name = self.create_parcel(stage='sch')
        self.assertFalse(self.try_finalize(name))

    def test_etc_user_allowed_to_finalize_at_semantic_check_stage(self):
        self.add_to_role('somebody', 'ROLE_ETC')
        name = self.create_parcel(stage='sch')
        self.assertTrue(self.try_finalize(name))

    def test_admin_user_allowed_to_finalize_at_semantic_check_stage(self):
        self.add_to_role('somebody', 'ROLE_ADMIN')
        name = self.create_parcel(stage='sch')
        self.assertTrue(self.try_finalize(name))

    def test_random_user_not_allowed_to_upload_at_enhancement_stage(self):
        name = self.create_parcel(stage='enh')
        self.assertFalse(self.try_upload(name))
        self.assertFalse(self.try_upload_file(name))

    def test_nrc_user_allowed_to_upload_at_enhancement_stage(self):
        self.add_to_role('somebody', 'ROLE_NRC')
        name = self.create_parcel(stage='enh')
        self.assertTrue(self.try_upload(name))
        self.assertTrue(self.try_upload_file(name))

    def test_admin_user_allowed_to_upload_at_enhancement_stage(self):
        self.add_to_role('somebody', 'ROLE_ADMIN')
        name = self.create_parcel(stage='enh')
        self.assertTrue(self.try_upload(name))
        self.assertTrue(self.try_upload_file(name))

    def test_random_user_not_allowed_to_finalize_at_enhancement_stage(self):
        name = self.create_parcel(stage='enh')
        self.assertFalse(self.try_finalize(name))

    def test_nrc_user_allowed_to_finalize_at_enhancement_stage(self):
        self.add_to_role('somebody', 'ROLE_NRC')
        name = self.create_parcel(stage='enh')
        self.assertTrue(self.try_finalize(name))

    def test_admin_user_allowed_to_finalize_at_enhancement_stage(self):
        self.add_to_role('somebody', 'ROLE_ADMIN')
        name = self.create_parcel(stage='enh')
        self.assertTrue(self.try_finalize(name))

    def test_random_user_not_allowed_to_delete_parcel(self):
        name = self.create_parcel()
        self.assertFalse(self.try_delete(name))

    def test_admin_user_allowed_to_delete_parcel(self):
        self.add_to_role('somebody', 'ROLE_ADMIN')
        name = self.create_parcel()
        self.assertTrue(self.try_delete(name))

    def test_allow_parcel_deletion(self):
        self.app.config['ALLOW_PARCEL_DELETION'] = False
        name = self.create_parcel()
        self.assertFalse(self.try_delete(name))

    def test_random_user_not_allowed_to_delete_file_from_parcel(self):
        self.add_to_role('somebody', 'ROLE_SP')
        name = self.create_parcel()
        self.try_upload(name)
        self.app.config["ROLE_SP"] = []
        self.assertFalse(self.try_delete_file(name, 'y.txt'))

    def test_admin_user_allowed_to_delete_file_from_parcel(self):
        self.add_to_role('somebody', 'ROLE_SP')
        name = self.create_parcel()
        self.try_upload(name)
        self.assertTrue(self.try_delete_file(name))


class RolesTest(AppTestCase):

    def setUp(self):
        self.app.config['LDAP_SERVER'] = 'ldap://some.ldap.server'
        UsersDB_patch = patch('auth.UsersDB')
        self.mock_UsersDB = UsersDB_patch.start()
        self.addCleanup(UsersDB_patch.stop)

    def test_users_db_connection(self):
        import auth
        mock_udb = self.mock_UsersDB.return_value
        mock_udb.member_roles_info.return_value = []
        with self.app.test_request_context():
            auth.get_ldap_groups('somebody')
        self.assertEqual(self.mock_UsersDB.mock_calls[0],
                         call(ldap_server='some.ldap.server'))

    def test_role_list_fetched_from_ldap(self):
        import auth
        mock_udb = self.mock_UsersDB.return_value
        mock_udb.member_roles_info.return_value = [
            ('eionet', None),
            ('eionet-nfp', None),
            ('eionet-nfp-dk', None),
        ]

        with self.app.test_request_context():
            roles = auth.get_ldap_groups('somebody')

        self.assertEqual(roles, ['eionet', 'eionet-nfp', 'eionet-nfp-dk'])
        self.assertEqual(mock_udb.member_roles_info.mock_calls,
                         [call('user', 'somebody')])

    def test_authorize_looks_into_ldap_groups(self):
        import auth
        mock_udb = self.mock_UsersDB.return_value
        mock_udb.member_roles_info.return_value = [('eionet-nrc', None)]
        self.app.config['ROLE_NRC'] = ['ldap_group:eionet-nrc']

        with self.app.test_request_context():
            flask.g.username = 'somebody'
            self.assertFalse(auth.authorize(['ROLE_ETC']))
            self.assertTrue(auth.authorize(['ROLE_NRC']))

    def test_authorize_for_anonymous_returns_false(self):
        import auth
        self.app.config['ROLE_ETC'] = ['user_id:somebody']
        with self.app.test_request_context():
            self.app.preprocess_request()
            self.assertFalse(auth.authorize(['ROLE_ETC']))


class RequireAdminTest(AppTestCase):

    def setUp(self):
        import auth

        @self.app.route('/some_view')
        @auth.require_admin
        def some_view():
            return "inside"

    def test_admin_required_decorator_redirects_to_login(self):
        resp = self.client.get('/some_view')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.location)

    def test_admin_required_decorator_allows_admin_user(self):
        self.app.config.setdefault('ROLE_ADMIN', []).append('user_id:somebody')
        resp = self.client.get('/some_view')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, "inside")
