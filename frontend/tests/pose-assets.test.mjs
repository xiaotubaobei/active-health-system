import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { crc32c, verifyModel, prepare } from '../scripts/prepare-pose-assets.mjs';

test('CRC32C matches the standard vector and rejects truncated/corrupt models', () => {
  assert.equal(crc32c(Buffer.from('123456789')), '4waSgw==');
  assert.throws(() => verifyModel(Buffer.from('html error page'), 'full'), /校验失败/);
  assert.throws(() => verifyModel(Buffer.alloc(9398198), 'full'), /校验失败/);
});

test('bad model download leaves existing public model intact and fails the build', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'health-pose-'));
  try {
    const wasmDir = path.join(root, 'node_modules/@mediapipe/tasks-vision/wasm');
    await mkdir(wasmDir, { recursive: true });
    for (const name of ['vision_wasm_internal.js', 'vision_wasm_internal.wasm',
      'vision_wasm_nosimd_internal.js', 'vision_wasm_nosimd_internal.wasm']) await writeFile(path.join(wasmDir, name), 'fixture');
    const modelDir = path.join(root, 'public/models');
    await mkdir(modelDir, { recursive: true });
    const destination = path.join(modelDir, 'pose_landmarker_full.task');
    await writeFile(destination, 'old model');
    await assert.rejects(prepare({ root, variant: 'full', modelFile: '', fetcher: async () => ({
      ok: true, arrayBuffer: async () => Buffer.from('bad download'),
    }) }), /校验失败/);
    assert.equal(await readFile(destination, 'utf8'), 'old model');
    await assert.rejects(readFile(path.join(root, 'public/pose-assets.json')));
  } finally { await rm(root, { recursive: true, force: true }); }
});
