from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import inspect, text

from app import migrate


def test_retry_preserves_saved_input_and_terminal_status(client, onboard):
    result, _ = onboard()
    uid = result['user']['id']
    body = {'user_id': uid, 'exercise_id': 'squat', 'start_key': 'retry-test-12345678',
            'pose_summary': {'source': 'camera'}}
    first = client.post('/sessions/start', json=body)
    assert first.status_code == 200
    sid = first.json()['session']['id']
    saved_pose = {'source': 'camera', 'frames': [1, 2]}
    assert client.put(f'/sessions/{sid}/draft?user_id={uid}', json={
        'pose_summary': saved_pose, 'expected_revision': 0}).status_code == 200
    retried = client.post('/sessions/start', json=body).json()['session']
    assert retried['id'] == sid
    assert retried['pose_summary'] == saved_pose
    assert retried['draft_revision'] == 1
    assert client.post('/sessions/start', json={**body, 'exercise_id': 'push_up'}).status_code == 409
    assert client.post(f'/sessions/{sid}/cancel?user_id={uid}').status_code == 200
    assert client.post('/sessions/start', json=body).json()['session']['status'] == 'cancelled'
    # No key retains compatibility with existing clients; keys are scoped to each user.
    legacy = {k: v for k, v in body.items() if k != 'start_key'}
    one = client.post('/sessions/start', json=legacy).json()['session']['id']
    two = client.post('/sessions/start', json=legacy).json()['session']['id']
    assert one != two
    other, _ = onboard('other-user')
    second = client.post('/sessions/start', json={**body, 'user_id': other['user']['id']})
    assert second.status_code == 200
    assert second.json()['session']['id'] != sid


def test_parallel_start_creates_one_record(client, onboard):
    result, _ = onboard()
    body = {'user_id': result['user']['id'], 'exercise_id': 'squat', 'start_key': 'parallel-123456789'}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post('/sessions/start', json=body), range(4)))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert len({r.json()['session']['id'] for r in results}) == 1


@pytest.mark.parametrize('key', ['', 'short', 'x' * 65, '../invalid/key/key'])
def test_invalid_start_key(client, onboard, key):
    result, _ = onboard()
    assert client.post('/sessions/start', json={'user_id': result['user']['id'],
        'exercise_id': 'squat', 'start_key': key}).status_code == 422


def test_legacy_start_key_migration_is_repeatable(store):
    engine, _ = store
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE exercise_sessions (id INTEGER PRIMARY KEY, user_id INTEGER)'))
        conn.execute(text('INSERT INTO exercise_sessions VALUES (1, 1), (2, 1)'))
    migrate.migrate_schema()
    migrate.migrate_schema()
    with engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM exercise_sessions WHERE start_key IS NULL')).scalar() == 2
    assert any(i['name'] == 'uq_session_start_key' and i['unique'] for i in inspect(engine).get_indexes('exercise_sessions'))
