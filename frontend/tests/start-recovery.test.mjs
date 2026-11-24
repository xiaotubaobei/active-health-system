import test from 'node:test';
import assert from 'node:assert/strict';
import { createStartRecovery } from '../src/utils/startRecovery.js';

function fixture() {
  const values = new Map();
  const storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  return { values, storage, forUser: userId => createStartRecovery({ storage, userId,
    api: {}, randomKey: () => 'test-start-key-123456' }) };
}
const input = { exercise_id: 'squat', prescription_id: 2, input_mode: 'video' };

test('pending starts are scoped by user and retain only recovery metadata', () => {
  const f = fixture(), owner = f.forUser(1), other = f.forUser(2);
  const intent = owner.begin({ ...input, pose_summary: { frames: ['private'] }, video_path: 'private.mp4' });
  assert.deepEqual(owner.read(), { start_key: 'test-start-key-123456', ...input });
  assert.equal(other.read(), null);
  assert.equal(JSON.stringify(intent).includes('private'), false);
  assert.deepEqual(owner.begin(input), intent);
  assert.throws(() => owner.begin({ ...input, exercise_id: 'push_up' }), /检查上次/);
  owner.clear('different-key'); assert.ok(owner.read());
  owner.clear(intent.start_key); assert.equal(owner.read(), null);
});

test('invalid saved metadata is discarded and storage failure prevents sending', () => {
  const f = fixture(), recovery = f.forUser(1);
  for (const raw of ['null', '{broken', JSON.stringify({ ...input, start_key: 1234567890123456 }),
    JSON.stringify({ ...input, start_key: 'valid-start-key-123', prescription_id: -1 })]) {
    f.values.set('ah_pending_start:1', raw);
    assert.equal(recovery.read(), null);
    assert.equal(f.values.size, 0);
  }
  f.storage.setItem = () => { throw new Error('quota'); };
  assert.throws(() => recovery.begin(input), /浏览器无法保存/);
});
