"""首次基线必须来自明确提交的资料，不采用注册占位值。"""
import pytest

from app.models.entities import FitnessAssessment, FitnessBaseline, Prescription, User
from app.services.prescription import NoMatchingTemplate, pick_template


def profile_payload(client):
    response = client.post('/auth/register', json={
        'username': 'explicit-profile', 'password': 'test-password', 'privacy_consent': True,
    })
    assert response.status_code == 200
    uid = response.json()['user']['id']
    scale = next(s for s in client.get('/fitness/scales').json() if s['id'] == 'middle_elder')
    return {
        'user_id': uid, 'age_group': 'middle_age', 'height_cm': 161.7, 'weight_kg': 54.2,
        'goal': 'fitness', 'privacy_consent': True, 'scale_id': scale['id'],
        'scores': {item['key']: 63.5 for item in scale['items']},
    }


@pytest.mark.parametrize('missing', ['age_group', 'height_cm', 'weight_kg', 'goal'])
def test_onboarding_requires_explicit_profile_without_writing_baseline(client, store, missing):
    body = profile_payload(client)
    body.pop(missing)
    response = client.post('/onboarding/complete', json=body)
    assert response.status_code == 422
    assert any(error['loc'][-1] == missing for error in response.json()['detail'])
    with store[1]() as db:
        assert not db.get(User, body['user_id']).onboarding_done
        assert db.query(FitnessAssessment).count() == 0
        assert db.query(FitnessBaseline).count() == 0
        assert db.query(Prescription).count() == 0


def test_confirmed_measurements_preserved_in_profile_and_baseline(client, store):
    body = profile_payload(client)
    response = client.post('/onboarding/complete', json=body)
    assert response.status_code == 200, response.text
    for key in ['age_group', 'height_cm', 'weight_kg', 'goal']:
        assert response.json()['user'][key] == body[key]
        assert response.json()['baseline']['profile_snapshot'][key] == body[key]
    with store[1]() as db:
        baseline = db.query(FitnessBaseline).one()
        assert baseline.scores == body['scores']
        assert baseline.total_score == 63.5


@pytest.mark.parametrize('age,goal,tags', [
    ('middle_age', 'fitness', []), ('elder', 'medical', ['joint']),
])
def test_template_does_not_invent_unassessed_health_advice(age, goal, tags):
    _, payload = pick_template(age, goal, tags)
    assert payload['health_plan'] == {'diet': '', 'sleep': '', 'medication': '', 'psychology': ''}


def test_profile_without_scores_saves_and_first_later_assessment_becomes_baseline(client, store):
    body = profile_payload(client)
    scale_id, scores = body.pop('scale_id'), body.pop('scores')
    body['generate_prescription'] = False
    response = client.post('/onboarding/complete', json=body)
    assert response.status_code == 200, response.text
    assert response.json()['user']['onboarding_done']
    assert response.json()['baseline'] is None
    assert response.json()['prescription'] is None
    status = client.get('/onboarding/status', params={'user_id': body['user_id']}).json()
    assert status['onboarding_done'] and not status['has_baseline'] and not status['has_prescription']
    with store[1]() as db:
        assert db.query(FitnessAssessment).count() == db.query(FitnessBaseline).count() == 0
    # 基本建档后可使用记录工具；没有体测基线不被伪装成完成了体测。
    assert client.post('/sessions/start', json={'user_id': body['user_id'], 'exercise_id': 'squat'}).status_code == 200
    assessed = client.post('/fitness/assess', json={'user_id': body['user_id'], 'scale_id': scale_id, 'scores': scores})
    assert assessed.status_code == 200, assessed.text
    baseline = client.get('/onboarding/status', params={'user_id': body['user_id']}).json()['baseline']
    assert baseline['assessment_id'] == assessed.json()['id']
    assert baseline['scores'] == scores
    assert baseline['profile_snapshot']['weight_kg'] == 54.2
    client.put('/users/me', json={'weight_kg': 60})
    second = client.post('/fitness/assess', json={
        'user_id': body['user_id'], 'scale_id': scale_id, 'scores': {key: 0 for key in scores},
    })
    assert second.status_code == 200 and second.json()['total_score'] == 0
    with store[1]() as db:
        assert db.query(FitnessAssessment).count() == 2
        assert db.query(FitnessBaseline).count() == 1
    assert client.get('/onboarding/status', params={'user_id': body['user_id']}).json()['baseline'] == baseline


@pytest.mark.parametrize('partial', ['scale-only', 'scores-only', 'pose-only'])
def test_optional_assessment_does_not_silently_discard_partial_input(client, store, partial):
    body = profile_payload(client)
    if partial == 'scale-only':
        body.pop('scores')
    elif partial == 'scores-only':
        body.pop('scale_id')
    else:
        body.pop('scores')
        body.pop('scale_id')
        body['pose_baseline'] = {'source': 'camera'}
    assert client.post('/onboarding/complete', json=body).status_code == 422
    with store[1]() as db:
        assert not db.get(User, body['user_id']).onboarding_done
        assert db.query(FitnessAssessment).count() == db.query(FitnessBaseline).count() == 0


@pytest.mark.parametrize('age,goal,tags', [
    ('youth', 'medical', ['joint']),
    ('elder', 'medical', ['cardio_risk']),
    ('middle_age', 'medical', ['hypertension']),
    ('middle_age', 'medical', ['cardio_risk', 'joint']),
    ('middle_age', 'medical', []),
    ('unrecognized', 'fitness', []),
])
def test_template_never_falls_back_across_age_or_health_tags(age, goal, tags):
    with pytest.raises(NoMatchingTemplate):
        pick_template(age, goal, tags)


def test_unmatched_template_does_not_prevent_profile_or_baseline_save(client, store):
    body = profile_payload(client)
    body.update(goal='medical', chronic_tags=['hypertension'])
    response = client.post('/onboarding/complete', json=body)
    assert response.status_code == 200, response.text
    assert response.json()['baseline']['scores'] == body['scores']
    assert response.json()['user']['onboarding_done']
    assert response.json()['prescription'] is None
    assert '暂不生成' in response.json()['prescription_message']
    match = client.get('/prescriptions/availability', params={'user_id': body['user_id']})
    assert match.status_code == 200 and not match.json()['matched']
    assert client.post('/prescriptions/generate', json={'user_id': body['user_id']}).status_code == 422
    assert client.post('/demo/run-loop', json={'user_id': body['user_id']}).status_code == 422
    with store[1]() as db:
        assert db.query(Prescription).count() == 0
        assert db.query(FitnessAssessment).count() == db.query(FitnessBaseline).count() == 1


def test_unconfirmed_registration_defaults_cannot_generate_plan(client, store):
    body = profile_payload(client)
    match = client.get('/prescriptions/availability', params={'user_id': body['user_id']})
    assert match.status_code == 200 and not match.json()['matched']
    assert client.post('/prescriptions/generate', json={'user_id': body['user_id']}).status_code == 409
    with store[1]() as db:
        assert db.query(Prescription).count() == 0


def test_later_assessment_rejects_age_mismatch_without_changing_baseline(client, store, onboard):
    result, body = onboard(age='youth')
    scale = next(s for s in client.get('/fitness/scales').json() if s['id'] == 'middle_elder')
    response = client.post('/fitness/assess', json={
        'user_id': body['user_id'], 'scale_id': scale['id'], 'scores': {i['key']: 70 for i in scale['items']},
    })
    assert response.status_code == 422
    with store[1]() as db:
        assert db.query(FitnessAssessment).count() == db.query(FitnessBaseline).count() == 1
        assert db.query(FitnessBaseline).one().assessment_id == result['baseline']['assessment_id']
