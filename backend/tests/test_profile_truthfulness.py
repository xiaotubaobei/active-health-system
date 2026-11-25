"""首次基线必须来自明确提交的资料，不采用注册占位值。"""
import pytest

from app.models.entities import FitnessAssessment, FitnessBaseline, Prescription, User
from app.services.prescription import pick_template


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
