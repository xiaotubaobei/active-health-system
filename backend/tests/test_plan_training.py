from sqlalchemy import text
from app import migrate
from app.models.entities import Prescription, KbEntry


def test_plan_target_is_server_snapshot(client, onboard, store):
    result, _ = onboard()
    plan = result['prescription']
    exercise = plan['exercises'][0]
    response = client.post('/sessions/start', json={
        'user_id': result['user']['id'], 'prescription_id': plan['id'],
        'exercise_id': exercise['id'], 'exercise_name': 'forged name',
    })
    assert response.status_code == 200, response.text
    row = response.json()['session']
    assert row['exercise_name'] == exercise['name']
    assert row['plan_snapshot']['exercise'] == exercise
    assert row['plan_snapshot']['version'] == plan['version']
    with store[1]() as db:
        saved = db.get(Prescription, plan['id'])
        saved.exercises = []
        saved.version = 99
        db.commit()
    restored = client.get(f"/sessions/{row['id']}", params={'user_id': result['user']['id']})
    assert restored.json()['session']['plan_snapshot'] == row['plan_snapshot']
    assert client.post(f"/sessions/{row['id']}/finish", json={}).status_code == 200
    with store[1]() as db:
        assert db.query(KbEntry).filter_by(session_id=row['id']).one().prescription_version == plan['version']


def test_reject_action_outside_plan(client, onboard):
    result, _ = onboard()
    response = client.post('/sessions/start', json={
        'user_id': result['user']['id'], 'prescription_id': result['prescription']['id'],
        'exercise_id': 'not-in-plan',
    })
    assert response.status_code == 400


def test_free_training_has_no_plan_target(client, onboard):
    result, _ = onboard()
    response = client.post('/sessions/start', json={
        'user_id': result['user']['id'], 'exercise_id': 'squat',
    })
    assert response.status_code == 200
    assert response.json()['session']['plan_snapshot'] == {}


def test_legacy_session_snapshot_migration(store):
    engine, _ = store
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE exercise_sessions (id INTEGER PRIMARY KEY)'))
        conn.execute(text('INSERT INTO exercise_sessions (id) VALUES (1)'))
    migrate.migrate_schema()
    migrate.migrate_schema()
    with engine.connect() as conn:
        assert conn.execute(text('SELECT plan_snapshot FROM exercise_sessions WHERE id=1')).scalar() == '{}'
