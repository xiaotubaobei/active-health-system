from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from app.models.entities import Prescription, PrescriptionReview, User


def login(client, name):
    client.cookies.clear()  # 模拟不同浏览器，避免登录轮换撤销另一个测试身份。
    response = client.post('/auth/login', json={'username': name, 'password': 'test-password'})
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['token']}"}


def reviewer(client, store, name='review-doctor', role='physician'):
    client.cookies.clear()
    response = client.post('/auth/register', json={
        'username': name, 'password': 'test-password', 'privacy_consent': True,
    })
    assert response.status_code == 200
    uid = response.json()['user']['id']
    with store[1]() as db:
        db.get(User, uid).role = role
        db.commit()
    return login(client, name), uid


def submit(client, pid, headers, name='review-doctor', **extra):
    return client.post(f'/prescriptions/{pid}/reviews', headers=headers, json={
        'reviewer_username': name, 'consent': True, 'request_note': '请检查此版安排', **extra,
    })


def decision(client, rid, headers, value='approved', note='已核对当前资料与处方'):
    return client.post(f'/prescriptions/reviews/{rid}/decision', headers=headers,
                       json={'decision': value, 'note': note})


def setup_review(client, store, onboard):
    owner, _ = onboard('review-owner')
    pid = owner['prescription']['id']
    owner_headers = login(client, 'review-owner')
    doctor, did = reviewer(client, store)
    return owner, pid, owner_headers, doctor, did


def test_approve_preserves_snapshot_and_private_ownership(client, store, onboard):
    owner, pid, patient, doctor, did = setup_review(client, store, onboard)
    response = submit(client, pid, patient)
    assert response.status_code == 200, response.text
    review = response.json()
    rid = review['id']
    assert review['status'] == 'pending' and review['reviewer_id'] == did
    assert review['profile_snapshot']['assessment']['total_score'] == 70
    assert 'password' not in str(review) and 'pose_baseline' not in str(review)
    assert client.get('/prescriptions/reviews/inbox', headers=doctor).json()['total'] == 1
    assert client.get(f"/users/me?user_id={owner['user']['id']}", headers=doctor).status_code == 404
    assert client.get(f"/prescriptions/current?user_id={owner['user']['id']}", headers=doctor).status_code == 404
    assert decision(client, rid, doctor).status_code == 200
    current = client.get(f"/prescriptions/current?user_id={owner['user']['id']}", headers=patient).json()
    assert current['status'] == 'formal_prescription' and current['version'] == 1
    assert decision(client, rid, doctor, 'rejected', '覆盖意见').status_code == 409
    record = client.get('/prescriptions/reviews/mine', headers=patient).json()['items'][0]
    assert record['status'] == 'approved' and record['decided_at']
    assert record['prescription_snapshot'] == review['prescription_snapshot']
    assert record['prescription_snapshot']['status'] == 'pre_prescription'
    assert record['decision_note'] == '已核对当前资料与处方'
    assert submit(client, pid, patient).status_code == 409
    assert client.get('/prescriptions/reviews/inbox?status=approved', headers=doctor).json()['total'] == 1


def test_consent_identity_roles_and_duplicate_submission(client, store, onboard):
    owner, pid, patient, doctor, _ = setup_review(client, store, onboard)
    assert submit(client, pid, patient, consent=False).status_code == 400
    for name in ['no-such-person', 'review-owner']:
        assert submit(client, pid, patient, name).status_code == 400
    assert submit(client, pid, doctor).status_code == 404
    assert client.get('/prescriptions/reviews/inbox', headers=patient).status_code == 403
    assert submit(client, pid, patient).status_code == 200
    assert submit(client, pid, patient).status_code == 409
    assert client.post(f'/prescriptions/{pid}/advance', headers=patient).status_code == 403
    with store[1]() as db:
        db.get(User, owner['user']['id']).role = 'physician'
        db.commit()
    assert client.post(f'/prescriptions/{pid}/advance', headers=patient).status_code == 409
    assert submit(client, pid, patient, request_note='x' * 2001).status_code == 422


def test_other_reviewer_cannot_read_or_decide(client, store, onboard):
    _, pid, patient, doctor, _ = setup_review(client, store, onboard)
    other, _ = reviewer(client, store, 'another-doctor')
    rid = submit(client, pid, patient).json()['id']
    assert client.get('/prescriptions/reviews/inbox', headers=other).json()['total'] == 0
    assert decision(client, rid, other).status_code == 404
    assert decision(client, rid, patient).status_code == 403
    assert client.post(f'/prescriptions/reviews/{rid}/cancel', headers=doctor).status_code == 404
    assert client.get('/prescriptions/reviews/mine', headers=other).json()['total'] == 0
    assert client.get('/prescriptions/reviews/inbox?status=all', headers=doctor).status_code == 422
    assert client.get('/prescriptions/reviews/mine?limit=101', headers=patient).status_code == 422


@pytest.mark.parametrize('medical', [False, True])
def test_specialist_scope_and_revoked_role(client, store, onboard, medical):
    owner, pid, patient, doctor, did = setup_review(client, store, onboard)
    specialist, sid = reviewer(client, store, 'review-specialist', 'prescription_specialist')
    if medical:
        with store[1]() as db:
            db.get(Prescription, pid).library = 'medical'
            db.commit()
        assert submit(client, pid, patient, 'review-specialist').status_code == 400
    rid = submit(client, pid, patient, 'review-doctor' if medical else 'review-specialist').json()['id']
    active_reviewer = doctor if medical else specialist
    active_id = did if medical else sid
    with store[1]() as db:
        db.get(User, active_id).role = 'prescription_specialist' if medical else 'user'
        db.commit()
    assert decision(client, rid, active_reviewer).status_code == 403
    inbox = client.get('/prescriptions/reviews/inbox', headers=active_reviewer)
    assert (inbox.json()['total'] == 0) if medical else (inbox.status_code == 403)
    with store[1]() as db:
        db.get(User, active_id).role = 'physician' if medical else 'prescription_specialist'
        db.commit()
    assert decision(client, rid, active_reviewer).status_code == 200


def test_reject_resubmit_and_withdraw(client, store, onboard):
    owner, pid, patient, doctor, _ = setup_review(client, store, onboard)
    first = submit(client, pid, patient).json()['id']
    assert decision(client, first, doctor, note='   ').status_code == 422
    assert decision(client, first, doctor, value='not-a-decision').status_code == 422
    assert decision(client, first, doctor, 'rejected', '请补充测评说明').status_code == 200
    second = submit(client, pid, patient, request_note='已补充说明').json()['id']
    assert second != first
    assert client.post(f'/prescriptions/reviews/{second}/cancel', headers=patient).status_code == 200
    assert decision(client, second, doctor).status_code == 404
    assert client.get('/prescriptions/reviews/inbox', headers=doctor).json()['total'] == 0
    assert client.post(f'/prescriptions/reviews/{first}/cancel', headers=patient).status_code == 409
    assert client.post(f'/prescriptions/reviews/{second}/cancel', headers=patient).status_code == 409
    records = client.get('/prescriptions/reviews/mine', headers=patient).json()
    assert [r['status'] for r in records['items']] == ['cancelled', 'rejected']
    assert client.get(f"/prescriptions/current?user_id={owner['user']['id']}", headers=patient).json()['status'] == 'pre_prescription'
    assert submit(client, pid, patient).status_code == 200


def test_new_version_supersedes_pending_and_snapshot_is_fixed(client, store, onboard):
    owner, pid, patient, doctor, _ = setup_review(client, store, onboard)
    original = submit(client, pid, patient).json()
    client.put('/users/me', headers=patient, json={'weight_kg': 80})
    new = client.post('/prescriptions/generate', headers=patient, json={'user_id': owner['user']['id']})
    assert new.status_code == 200 and new.json()['version'] == 2
    record = client.get('/prescriptions/reviews/mine', headers=patient).json()['items'][0]
    assert record['status'] == 'superseded'
    assert record['profile_snapshot']['weight_kg'] == original['profile_snapshot']['weight_kg']
    assert decision(client, record['id'], doctor).status_code == 404
    assert client.get('/prescriptions/reviews/inbox', headers=doctor).json()['total'] == 0
    assert submit(client, pid, patient).status_code == 409
    assert submit(client, new.json()['id'], patient).status_code == 200


def test_unmatched_generation_keeps_existing_version_and_pending_review(client, store, onboard):
    owner, pid, patient, _, _ = setup_review(client, store, onboard)
    original = submit(client, pid, patient).json()
    response = client.put('/users/me', headers=patient, json={'goal': 'medical', 'chronic_tags': ['unknown-condition']})
    assert response.status_code == 200
    response = client.post('/prescriptions/generate', headers=patient, json={'user_id': owner['user']['id']})
    assert response.status_code == 422
    record = client.get('/prescriptions/reviews/mine', headers=patient).json()['items'][0]
    assert record == original
    current = client.get('/prescriptions/current', headers=patient, params={'user_id': owner['user']['id']}).json()
    assert current['id'] == pid and current['version'] == 1
    with store[1]() as db:
        assert db.query(Prescription).count() == 1
        assert db.query(PrescriptionReview).one().pending_prescription_id == pid


def test_changed_prescription_cannot_be_approved(client, store, onboard):
    _, pid, patient, doctor, _ = setup_review(client, store, onboard)
    rid = submit(client, pid, patient).json()['id']
    with store[1]() as db:
        db.get(Prescription, pid).intensity = '内容已变更'
        db.commit()
    assert decision(client, rid, doctor).status_code == 409
    with store[1]() as db:
        assert db.get(PrescriptionReview, rid).status == 'pending'
        assert db.get(Prescription, pid).status == 'pre_prescription'


def test_parallel_submission_and_decisions_only_save_once(client, store, onboard):
    _, pid, patient, doctor, _ = setup_review(client, store, onboard)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(client, pid, patient), range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    rid = next(r.json()['id'] for r in results if r.status_code == 200)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda value: decision(client, rid, doctor, value), ['approved', 'rejected']))
    assert sorted(r.status_code for r in results) == [200, 409]
    saved = next(r.json() for r in results if r.status_code == 200)
    with store[1]() as db:
        assert db.query(PrescriptionReview).count() == 1
        assert db.get(PrescriptionReview, rid).status == saved['status']
        assert db.get(Prescription, pid).status == ('formal_prescription' if saved['status'] == 'approved' else 'pre_prescription')


@pytest.mark.parametrize('operation', ['generate', 'cancel'])
def test_new_version_or_withdraw_racing_with_approval(client, store, onboard, operation):
    owner, pid, patient, doctor, _ = setup_review(client, store, onboard)
    rid = submit(client, pid, patient).json()['id']

    def owner_action():
        if operation == 'generate':
            return client.post('/prescriptions/generate', headers=patient,
                               json={'user_id': owner['user']['id']})
        return client.post(f'/prescriptions/reviews/{rid}/cancel', headers=patient)

    with ThreadPoolExecutor(max_workers=2) as pool:
        changing = pool.submit(owner_action)
        approving = pool.submit(decision, client, rid, doctor)
        changed, approved = changing.result(), approving.result()

    with store[1]() as db:
        review = db.get(PrescriptionReview, rid)
        old = db.get(Prescription, pid)
        assert review.pending_prescription_id is None
        if operation == 'generate':
            assert changed.status_code == 200
            assert approved.status_code in {200, 404, 409}
            assert review.status == ('approved' if approved.status_code == 200 else 'superseded')
            latest = db.get(Prescription, changed.json()['id'])
            assert latest.version == 2 and latest.status == 'pre_prescription'
        else:
            assert sorted([changed.status_code, approved.status_code]) in ([200, 404], [200, 409])
            assert review.status == ('cancelled' if changed.status_code == 200 else 'approved')
        assert old.status == ('formal_prescription' if review.status == 'approved' else 'pre_prescription')


def test_role_tool_uses_existing_account_and_revokes_sessions(client, store):
    path = Path(__file__).resolve().parents[2] / 'scripts' / 'set_user_role.py'
    spec = spec_from_file_location('set_user_role', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    response = client.post('/auth/register', json={'username': 'role-person', 'password': 'test-password', 'privacy_consent': True})
    assert response.status_code == 200
    with store[1]() as db:
        for name, role in [('missing-person', 'physician'), ('demo', 'physician'), ('role-person', 'admin')]:
            with pytest.raises(ValueError):
                module.set_role(db, name, role)
        assert module.set_role(db, 'role-person', 'physician') == 'user'
    assert client.get('/users/me').status_code == 401
    headers = login(client, 'role-person')
    assert client.get('/users/me', headers=headers).json()['role'] == 'physician'
