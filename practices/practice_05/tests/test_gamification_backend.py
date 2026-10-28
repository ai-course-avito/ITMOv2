import json
import os
import unittest
from pathlib import Path

from practices.practice_05.project.app import app, USERS_FILE, DATA_FILE


class GamificationBackendTests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        # Reset storage files to a clean state
        for fp in (USERS_FILE, DATA_FILE):
            try:
                os.remove(fp)
            except FileNotFoundError:
                pass

    def login(self, name="alex", utc_offset="+00:00"):
        res = self.client.post('/api/auth/login', json={"name": name, "utc_offset": utc_offset})
        self.assertEqual(res.status_code, 200)
        return res.get_json()

    def profile(self, name="alex"):
        res = self.client.get('/api/user/profile', headers={'X-User-Name': name})
        return res

    def test_login_invalid_name(self):
        res = self.client.post('/api/auth/login', json={"name": "ab"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get('error'), 'invalid_name')

    def test_login_and_profile(self):
        profile = self.login("alex")
        self.assertEqual(profile['name'], 'alex')
        self.assertIn('spins_remaining', profile)
        res = self.profile('alex')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['name'], 'alex')

    def test_catalog_contract(self):
        res = self.client.get('/api/emojis/catalog')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        item = data[0]
        self.assertIn('code', item)
        self.assertIn('version', item)
        self.assertIn('rarity', item)

    def test_spin_pool_has_min_segments_and_emoji(self):
        self.login('alex')
        res = self.client.get('/api/spin/pool')
        self.assertEqual(res.status_code, 200)
        pool = res.get_json()
        segments = pool.get('segments', [])
        self.assertEqual(len(segments), 8)
        self.assertTrue(any(seg.get('type') == 'emoji' for seg in segments))

    def test_spin_and_limit(self):
        self.login('alex')
        # 5 spins allowed
        spins = []
        for i in range(5):
            res = self.client.post('/api/spin', headers={'X-User-Name': 'alex'})
            self.assertEqual(res.status_code, 200)
            spins.append(res.get_json())
        # 6th should be blocked
        res = self.client.post('/api/spin', headers={'X-User-Name': 'alex'})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get('error'), 'no_spins_left')

    def test_task_emoji_assign_flow(self):
        # Login user first (login resets DB in testing mode)
        self.login('alex')
        # Create a task
        self.client.get('/api/tasks')
        res = self.client.post('/api/tasks', json={'title': 'Task 1'})
        self.assertEqual(res.status_code, 201)
        task = res.get_json()
        task_id = task['id']

        # Attempt to assign emoji without owning -> should fail
        res = self.client.post(f'/api/tasks/{task_id}/emojis', headers={'X-User-Name': 'alex'}, json={
            'emoji': {'code': 'fire', 'version': 'v1'}
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get('error'), 'emoji_locked')

        # Grant emoji to user directly in DB (testing path)
        from practices.practice_05.project.app import _db_add_user_emoji
        _db_add_user_emoji('alex', 'fire', 'v1')

        # Assign now should succeed
        res = self.client.post(f'/api/tasks/{task_id}/emojis', headers={'X-User-Name': 'alex'}, json={
            'emoji': {'code': 'fire', 'version': 'v1'}
        })
        self.assertEqual(res.status_code, 200)
        task = res.get_json()
        self.assertTrue(any(e.get('code') == 'fire' for e in task.get('emojis', [])))

        # Re-assign same emoji should error
        res = self.client.post(f'/api/tasks/{task_id}/emojis', headers={'X-User-Name': 'alex'}, json={
            'emoji': {'code': 'fire', 'version': 'v1'}
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get('error'), 'already_assigned')

        # Remove emoji
        res = self.client.delete(f'/api/tasks/{task_id}/emojis/fire:v1', headers={'X-User-Name': 'alex'})
        self.assertEqual(res.status_code, 200)
        task = res.get_json()
        self.assertFalse(any(e.get('code') == 'fire' for e in task.get('emojis', [])))


if __name__ == '__main__':
    unittest.main()
