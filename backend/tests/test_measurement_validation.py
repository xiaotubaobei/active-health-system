import pytest
from pydantic import ValidationError

from app.models.entities import BodyMetrics
from app.schemas.dto import BodyParseIn, UserUpdate


def test_invalid_profile_updates_do_not_change_saved_profile(client, onboard):
    result, _ = onboard()
    original = client.get('/users/me').json()
    for invalid in [
        {'height_cm': 0}, {'height_cm': -1}, {'height_cm': 301},
        {'weight_kg': 0}, {'weight_kg': 701},
        {'age_group': 'unknown'}, {'goal': 'unknown'},
    ]:
        response = client.put('/users/me', json={**invalid, 'chronic_tags': ['must-not-save']})
        assert response.status_code == 422, response.text
        assert client.get('/users/me').json() == original
    response = client.put('/users/me', json={'height_cm': 171.5, 'weight_kg': 66.2})
    assert response.status_code == 200
    assert response.json()['height_cm'] == 171.5
    assert response.json()['weight_kg'] == 66.2


def test_invalid_body_measurements_are_never_archived(client, onboard, store):
    result, _ = onboard()
    body = {'user_id': result['user']['id'], 'waist_cm': 80, 'hip_cm': 95}
    for invalid in [
        {'waist_cm': -10}, {'waist_cm': 0}, {'waist_cm': 301},
        {'hip_cm': 0}, {'hip_cm': -1}, {'hip_cm': 301},
        {'body_fat': -1}, {'body_fat': 101},
    ]:
        response = client.post('/body/parse', json={**body, **invalid})
        assert response.status_code == 422, response.text
    with store[1]() as db:
        assert db.query(BodyMetrics).count() == 0
    response = client.post('/body/parse', json={**body, 'waist_cm': 80.5, 'body_fat': 20})
    assert response.status_code == 200, response.text
    assert response.json()['current']['whr'] == round(80.5 / 95, 3)
    assert response.json()['current']['parsing_result']['mode'] == 'local_fallback'
    with store[1]() as db:
        assert db.query(BodyMetrics).count() == 1


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_measurements_are_rejected(value):
    for model, field in [(UserUpdate, 'height_cm'), (UserUpdate, 'weight_kg'),
                         (BodyParseIn, 'waist_cm'), (BodyParseIn, 'hip_cm'), (BodyParseIn, 'body_fat')]:
        with pytest.raises(ValidationError):
            model.model_validate({'user_id': 1, field: value})
