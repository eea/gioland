from StringIO import StringIO
from mock import patch, call
import flask
from common import AppTestCase, record_events


def setUpModule(self):
    import parcel; self.parcel = parcel
    import warehouse; self.warehouse = warehouse


class PermisionsTest(AppTestCase):

    CREATE_WAREHOUSE = True

    def setUp(self):
        self.client = self.app.test_client()
        self.client.post('/test_login', data={'username': 'somebody'})

    def add_to_role(self, username, role_name):
        self.app.config.setdefault(role_name, []).append('user_id:' + username)

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

    def try_upload(self, parcel_name):
        url = '/parcel/' + parcel_name + '/file'
        post_data = {'file': (StringIO("xx"), 'y.txt')}
        with record_events(parcel.file_uploaded) as uploaded_files:
            post_resp = self.client.post(url, data=post_data)
        if post_resp.status_code == 403:
            self.assertEqual(len(uploaded_files), 0)
            return False
        elif post_resp.status_code == 302:
            self.assertEqual(len(uploaded_files), 1)
            return True
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

    def try_delete_file(self, parcel_name, filename):
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

    def test_random_user_not_allowed_to_begin_upload(self):
        self.assertFalse(self.try_new_parcel())

    def test_service_provider_allowed_to_begin_upload(self):
        self.add_to_role('somebody', 'ROLE_SERVICE_PROVIDER')
        self.assertTrue(self.try_new_parcel())


    def test_random_user_not_allowed_to_upload_at_intermediate_state(self):
        name = self.create_parcel()
        self.assertFalse(self.try_upload(name))

    def test_service_provider_allowed_to_upload_at_intermediate_state(self):
        self.add_to_role('somebody', 'ROLE_SERVICE_PROVIDER')
        name = self.create_parcel()
        self.assertTrue(self.try_upload(name))


    def test_random_user_not_allowed_to_finalize_at_intermediate_state(self):
        name = self.create_parcel()
        self.assertFalse(self.try_finalize(name))

    def test_service_provider_allowed_to_finalize_at_intermediate_state(self):
        self.add_to_role('somebody', 'ROLE_SERVICE_PROVIDER')
        name = self.create_parcel()
        self.assertTrue(self.try_finalize(name))

    def test_admin_allowed_to_finalize_at_intermediate_state(self):
        self.add_to_role('somebody', 'ROLE_ADMIN')
        name = self.create_parcel()
        self.assertTrue(self.try_finalize(name))


    def test_random_user_not_allowed_to_upload_at_semantic_check_stage(self):
        name = self.create_parcel(stage='sch')
        self.assertFalse(self.try_upload(name))

    def test_etc_user_allowed_to_upload_at_semantic_check_stage(self):
        self.add_to_role('somebody', 'ROLE_ETC')
        name = self.create_parcel(stage='sch')
        self.assertTrue(self.try_upload(name))

    def test_admin_user_allowed_to_upload_at_semantic_check_stage(self):
        self.add_to_role('somebody', 'ROLE_ADMIN')
        name = self.create_parcel(stage='sch')
        self.assertTrue(self.try_upload(name))


    def test_random_user_not_allowed_to_finalize_at_semantic_check_stage(self):
        name = self.create_parcel(stage='sch')
        self.assertFalse(self.try_finalize(name))

    def test_service_provider_not_allowed_to_finalize_at_semantic_check(self):
        self.add_to_role('somebody', 'ROLE_SERVICE_PROVIDER')
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

    def test_nrc_user_allowed_to_upload_at_enhancement_stage(self):
        self.add_to_role('somebody', 'ROLE_NRC')
        name = self.create_parcel(stage='enh')
        self.assertTrue(self.try_upload(name))

    def test_admin_user_allowed_to_upload_at_enhancement_stage(self):
        self.add_to_role('somebody', 'ROLE_ADMIN')
        name = self.create_parcel(stage='enh')
        self.assertTrue(self.try_upload(name))


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
        self.add_to_role('somebody', 'ROLE_SERVICE_PROVIDER')
        name = self.create_parcel()
        self.try_upload(name)
        self.app.config["ROLE_SERVICE_PROVIDER"] = []
        self.assertFalse(self.try_delete_file(name, 'y.txt'))

    def test_admin_user_allowed_to_delete_file_from_parcel(self):
        self.add_to_role('somebody', 'ROLE_SERVICE_PROVIDER')
        name = self.create_parcel()
        self.try_upload(name)
        self.assertTrue(self.try_delete_file(name, 'y.txt'))


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
