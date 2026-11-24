import { copyFile, mkdir, readFile, writeFile, rename, unlink } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// Fixed Google float16 model version 1; byte sizes and CRC32C from upstream metadata.
export const MODELS = {
  lite: { size: 5777746, crc32c: 'Y2/V6A==' },
  full: { size: 9398198, crc32c: '3AUZ9Q==' },
  heavy: { size: 30664242, crc32c: '0kDHiw==' },
};
const table = Array.from({ length: 256 }, (_, value) => {
  for (let bit = 0; bit < 8; bit++) value = (value >>> 1) ^ (value & 1 ? 0x82f63b78 : 0);
  return value >>> 0;
});
export function crc32c(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) crc = table[(crc ^ byte) & 255] ^ (crc >>> 8);
  const output = Buffer.alloc(4);
  output.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
  return output.toString('base64');
}
export function verifyModel(bytes, variant) {
  const expected = MODELS[variant];
  if (!expected || bytes.length !== expected.size || crc32c(bytes) !== expected.crc32c) {
    throw new Error(`姿态模型 ${variant} 校验失败，请重新下载官方版本1模型`);
  }
}

export async function prepare({ root = fileURLToPath(new URL('../', import.meta.url)),
  variant = (process.env.VITE_POSE_LANDMARKER || 'full').toLowerCase(),
  modelFile = process.env.POSE_MODEL_FILE, fetcher = fetch } = {}) {
  if (!MODELS[variant]) throw new Error('VITE_POSE_LANDMARKER 仅支持 lite/full/heavy');
  const publicDir = path.join(root, 'public');
  const wasmDir = path.join(publicDir, 'wasm');
  const modelDir = path.join(publicDir, 'models');
  await mkdir(wasmDir, { recursive: true });
  await mkdir(modelDir, { recursive: true });
  const wasmNames = ['vision_wasm_internal.js', 'vision_wasm_internal.wasm',
    'vision_wasm_nosimd_internal.js', 'vision_wasm_nosimd_internal.wasm'];
  for (const name of wasmNames) {
    await copyFile(path.join(root, 'node_modules/@mediapipe/tasks-vision/wasm', name), path.join(wasmDir, name));
  }
  const name = `pose_landmarker_${variant}.task`;
  const destination = path.join(modelDir, name);
  const source = `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_${variant}/float16/1/${name}`;
  let bytes;
  if (modelFile) {
    bytes = await readFile(modelFile);
    verifyModel(bytes, variant);
  } else {
    try { bytes = await readFile(destination); verifyModel(bytes, variant); }
    catch { bytes = null; }
  }
  if (!bytes) {
    console.log(`首次准备姿态模型 ${variant}，约 ${Math.ceil(MODELS[variant].size / 1e6)}MB…`);
    const response = await fetcher(source, { signal: AbortSignal.timeout(120000) });
    if (!response.ok) throw new Error(`模型下载失败：HTTP ${response.status}`);
    bytes = Buffer.from(await response.arrayBuffer());
    verifyModel(bytes, variant);
  }
  // Never leave a partially downloaded model at the public path.
  const temporary = `${destination}.${process.pid}.tmp`;
  try { await writeFile(temporary, bytes); await rename(temporary, destination); }
  finally { await unlink(temporary).catch(() => {}); }
  const manifest = {
    variant, mediapipe_version: '0.10.14', source,
    license: 'Apache-2.0', license_url: 'https://www.apache.org/licenses/LICENSE-2.0',
    model: { path: `/models/${name}`, size: bytes.length,
      sha256: createHash('sha256').update(bytes).digest('hex'), crc32c: MODELS[variant].crc32c },
    wasm: wasmNames.map(name => `/wasm/${name}`),
  };
  await writeFile(path.join(publicDir, 'pose-assets.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(`姿态资源已就绪：${variant}，手机运行时从本站加载。`);
  return manifest;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  prepare().catch(error => {
    console.error(`姿态资源准备失败：${error.message}\n可把官方模型下载到本机后设置 POSE_MODEL_FILE 再重试。`);
    process.exitCode = 1;
  });
}
