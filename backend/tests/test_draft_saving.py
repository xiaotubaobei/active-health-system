from sqlalchemy import text
from app import migrate


def setup_session(client, onboard):
    result, _ = onboard()
    uid = result['user']['id']
    row = client.post('/sessions/start', json={'user_id': uid, 'exercise_id': 'squat'}).json()['session']
    return uid, row['id']


def test_stale_draft_does_not_overwrite_saved_frames(client, onboard):
    uid, sid = setup_session(client, onboard)
    url = f'/sessions/{sid}/draft?user_id={uid}'
    body = {'pose_summary': {'source': 'camera', 'frames': [1, 2]}, 'expected_revision': 0}
    saved = client.put(url, json=body)
    assert saved.status_code == 200
    assert saved.json()['session']['draft_revision'] == 1
    stale = client.put(url, json={**body, 'pose_summary': {'frames': []}})
    assert stale.status_code == 409
    restored = client.get(f'/sessions/{sid}?user_id={uid}').json()['session']
    assert restored['pose_summary'] == body['pose_summary']
    assert client.put(url, json={**body, 'expected_revision': 1}).json()['session']['draft_revision'] == 2


def test_stale_finish_rejected_and_retry_reuses_report(client, onboard):
    uid, sid = setup_session(client, onboard)
    assert client.put(f'/sessions/{sid}/draft?user_id={uid}', json={
        'pose_summary': {'source': 'camera'}, 'expected_revision': 0}).status_code == 200
    assert client.post(f'/sessions/{sid}/finish', json={'expected_revision': 0}).status_code == 409
    finished = client.post(f'/sessions/{sid}/finish', json={'expected_revision': 1})
    assert finished.status_code == 200
    repeated = client.post(f'/sessions/{sid}/finish', json={'expected_revision': 0})
    assert repeated.status_code == 200
    assert repeated.json()['report']['id'] == finished.json()['report']['id']
    assert client.put(f'/sessions/{sid}/draft?user_id={uid}', json={}).status_code == 409


def test_draft_revision_migration_preserves_old_records(store):
    engine, _ = store
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE exercise_sessions (id INTEGER PRIMARY KEY)'))
        conn.execute(text('INSERT INTO exercise_sessions (id) VALUES (1)'))
    migrate.migrate_schema()
    migrate.migrate_schema()
    with engine.connect() as conn:
        assert conn.execute(text('SELECT draft_revision FROM exercise_sessions WHERE id=1')).scalar() == 0
