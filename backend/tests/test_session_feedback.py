import pytest
from sqlalchemy import inspect

from app import migrate
from app.models.entities import BehaviorReport, ExerciseSession, KbEntry, Prescription, SessionFeedback


def finished(client, onboard):
    result, _ = onboard()
    session = client.post('/sessions/start', json={
        'user_id': result['user']['id'], 'exercise_id': 'squat',
        'prescription_id': result['prescription']['id'],
    }).json()['session']
    assert client.post(f"/sessions/{session['id']}/finish", json={}).status_code == 200
    return result, session['id']


def answers(**changes):
    return dict(expected_revision=0, performed=True, completion='partial', effort='hard',
                discomfort=True, note='最后一组没有完成', **changes)


def test_feedback_round_trip_edit_and_no_automatic_plan_or_score(client, onboard, store):
    result, session_id = finished(client, onboard)
    url = f'/sessions/{session_id}/feedback'
    assert client.get(url).json() == {'feedback': None}
    report = client.get(f'/reports/{session_id}').json()
    saved = client.put(url, json=answers()).json()['feedback']
    assert saved['user_id'] == result['user']['id']
    assert saved['revision'] == 1
    assert saved['completion'] == 'partial' and saved['discomfort'] is True
    assert client.get(url).json()['feedback'] == saved
    updated = client.put(url, json={**answers(), 'expected_revision': 1, 'note': '  修改后的说明  '})
    assert updated.status_code == 200, updated.text
    assert updated.json()['feedback']['revision'] == 2
    assert updated.json()['feedback']['note'] == '修改后的说明'
    assert client.get(f'/reports/{session_id}').json() == report
    with store[1]() as db:
        assert db.query(SessionFeedback).count() == 1
        assert db.query(BehaviorReport).count() == 1
        assert db.query(KbEntry).count() == 1
        assert db.query(Prescription).count() == 1
        assert db.get(ExerciseSession, session_id).status == 'finished'
        assert db.get(Prescription, result['prescription']['id']).version == 1


def test_lost_create_and_edit_response_retry_is_idempotent(client, onboard):
    _, session_id = finished(client, onboard)
    url = f'/sessions/{session_id}/feedback'
    first = client.put(url, json=answers()).json()
    assert client.put(url, json=answers()).json() == first
    edit = {**answers(), 'expected_revision': 1, 'note': '补充说明'}
    second = client.put(url, json=edit).json()
    assert second['feedback']['revision'] == 2
    assert client.put(url, json=edit).json() == second
    # Saving an unchanged record is also a no-op, including its saved time.
    assert client.put(url, json={**edit, 'expected_revision': 2}).json() == second


def test_stale_page_cannot_overwrite_new_feedback(client, onboard):
    _, session_id = finished(client, onboard)
    url = f'/sessions/{session_id}/feedback'
    first = client.put(url, json=answers()).json()
    assert client.put(url, json={**answers(), 'note': '另一页覆盖'}).status_code == 409
    second = client.put(url, json={**answers(), 'expected_revision': 1, 'effort': 'moderate'}).json()
    stale = client.put(url, json={**answers(), 'expected_revision': 1, 'note': '过期页面'})
    assert stale.status_code == 409
    assert client.get(url).json() == second
    # A very old identical payload cannot conceal intervening revisions.
    third = client.put(url, json={**answers(), 'expected_revision': 2}).json()
    assert third['feedback']['revision'] == 3
    assert client.put(url, json=answers()).status_code == 409
    assert first['feedback']['revision'] == 1


def test_demo_feedback_has_no_self_reported_training_results(client, onboard):
    _, session_id = finished(client, onboard)
    url = f'/sessions/{session_id}/feedback'
    client.put(url, json=answers())
    body = dict(expected_revision=1, performed=False, note='只是试用视频')
    saved = client.put(url, json=body).json()['feedback']
    assert saved['performed'] is False
    assert saved['completion'] is saved['effort'] is saved['discomfort'] is None
    assert client.put(url, json={**body, 'discomfort': False}).status_code == 422


@pytest.mark.parametrize('field,value', [
    ('performed', 'true'), ('expected_revision', True), ('expected_revision', -1),
    ('completion', 'unknown'), ('completion', None), ('effort', 'unknown'),
    ('effort', None), ('discomfort', 'false'), ('discomfort', None), ('note', '字' * 1001),
])
def test_invalid_feedback_does_not_write(client, onboard, store, field, value):
    _, session_id = finished(client, onboard)
    response = client.put(f'/sessions/{session_id}/feedback', json={**answers(), field: value})
    assert response.status_code == 422
    with store[1]() as db:
        assert db.query(SessionFeedback).count() == 0


def test_feedback_requires_finished_session_and_real_record(client, onboard, store):
    result, _ = onboard()
    session_id = client.post('/sessions/start', json={
        'user_id': result['user']['id'], 'exercise_id': 'squat',
    }).json()['session']['id']
    url = f'/sessions/{session_id}/feedback'
    for method in ('get', 'put'):
        kwargs = {'json': answers()} if method == 'put' else {}
        assert getattr(client, method)(url, **kwargs).status_code == 409
        assert getattr(client, method)('/sessions/999999/feedback', **kwargs).status_code == 404
    assert client.post(f'/sessions/{session_id}/cancel', params={'user_id': result['user']['id']}).status_code == 200
    assert client.put(url, json=answers()).status_code == 409
    with store[1]() as db:
        assert db.query(SessionFeedback).count() == 0


def test_feedback_is_private_and_requires_login_and_csrf(client, onboard):
    owner, session_id = finished(client, onboard)
    url = f'/sessions/{session_id}/feedback'
    assert client.put(url, json=answers()).status_code == 200
    onboard('other-user')
    assert client.get(url).status_code == 404
    assert client.put(url, json=answers()).status_code == 404
    client.post('/auth/login', json={'username': owner['user']['username'], 'password': 'test-password'})
    client.headers.pop('X-Requested-With')
    assert client.put(url, json=answers()).status_code == 403
    client.headers['X-Requested-With'] = 'ActiveHealth'
    assert client.post('/auth/logout').status_code == 200
    assert client.get(url).status_code == 401
    assert client.put(url, json=answers()).status_code == 401


def test_new_feedback_table_is_created_without_changing_existing_sessions(client, onboard, store):
    _, session_id = finished(client, onboard)
    before = client.get(f'/reports/{session_id}').json()
    # Simulate an existing installation upgrading from before this feature.
    SessionFeedback.__table__.drop(store[0])
    migrate.migrate_schema()
    migrate.migrate_schema()
    assert 'session_feedback' in inspect(store[0]).get_table_names()
    assert client.get(f'/reports/{session_id}').json() == before
    assert client.put(f'/sessions/{session_id}/feedback', json=answers()).status_code == 200
