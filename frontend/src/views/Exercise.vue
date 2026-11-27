<template>

  <div class="card">

    <h2>运动中监测</h2>
    <div v-if="startIntent && !session" role="status">
      <p>上一次开始请求尚未确认。先检查是否已建立训练；尚未查到时，请重新准备原动作的视频或摄像头，再点击开始。系统会沿用原请求，避免重复记录。</p>
      <button class="secondary" :disabled="busy" @click="initialize">检查上次开始结果</button>
    </div>
    <div v-if="!initialized && !busy">
      <p role="alert">训练页面未准备完成，请重新加载后再开始。</p>
      <button :disabled="busy" @click="initialize">重新加载</button>
    </div>
    <p v-if="planTarget" class="muted">训练计划 v{{ planTarget.version }} · {{ planTarget.exercise.name }} · 目标 {{ planTarget.exercise.sets }}组 × {{ planTarget.exercise.reps }}{{ planTarget.exercise.unit || '次' }}。这是计划目标，不代表已完成量。</p>
    <p v-if="planTarget && planTarget.status !== 'formal_prescription'" class="muted">此计划尚未人工审核通过。</p>
    <p v-if="session" class="muted">训练 #{{ session.id }} 已保存。刷新或离开后，可从训练历史继续。</p>
    <p v-if="savedPayload && (inputMode !== 'camera' || cameraFrames.length)" class="ok">训练输入已保存在服务端，可直接结束并生成报告。{{ inputMode === 'camera' ? '继续采集需重新打开摄像头。' : '刷新后不会恢复视频预览，已保存的姿态数据仍会用于报告。' }}</p>
    <p v-else-if="savedPayload && inputMode === 'camera'" class="muted">这次训练还没有姿态数据。请点击“继续训练”，全身入画后采集；也可以取消本次训练。</p>
    <p v-if="busy && !session && !videoProcessing" role="status">正在准备，请稍候…</p>
    <div v-if="session" role="status">
      <p>{{ saving ? '正在保存…' : draftDirty ? '有数据尚未保存' : saveState || '训练已建立' }}<span v-if="lastSavedAt"> · 最近保存 {{ lastSavedAt }}</span></p>
      <p v-if="saveError" role="alert">{{ saveError }}</p>
      <p v-if="inputMode === 'camera'">已采集 {{ cameraFrames.length }} / 1200 帧<span v-if="cameraFrames.length >= captureLimit">；已达到上限，请结束并保存本次训练。</span></p>
      <button class="secondary" :disabled="busy || saving || draftConflict" @click="retrySave">立即保存 / 重试</button>
      <router-link v-if="draftConflict" :to="{ path: '/history' }">返回记录核对训练</router-link>
      <p v-if="inputMode === 'camera'" class="muted">摄像头姿态每秒最多采样2帧，每10秒自动保存。未保存的数据在刷新后可能丢失；不会保存摄像头原视频。每次最多采集1200帧，约10分钟；达到上限后请结束本次训练。</p>
    </div>
    <router-link to="/history">查看训练历史 / 找回未完成训练</router-link>

    <p class="muted">

      选择视频或打开摄像头，准备好后点击“开始训练”。结束时生成报告；摄像头只保存姿态数据，不保存原视频。

    </p>

    <div class="row">

      <label class="tag gray">输入</label>

      <select v-model="inputMode" :disabled="!!session || busy || !!pendingStartBody || !!startIntent">

        <option value="video">离线视频（推荐验证）</option>

        <option value="camera">摄像头</option>

      </select>

      <select v-model="exerciseId" :disabled="!!session || busy || !!pendingStartBody || !!startIntent">

        <option v-for="e in exercises" :key="e.id" :value="e.id">{{ e.name }}</option>

      </select>

    </div>

    <div class="row" v-if="inputMode === 'video'">

      <label>用手机拍摄视频
        <input type="file" accept="video/*" capture="environment" :disabled="busy || !!session || !!pendingStartBody" @change="onVideoPicked" />
      </label>

      <label class="tag gray">演示样本</label>

      <select v-model="demoPickId" :disabled="busy || !!session || !!pendingStartBody" @change="onDemoPicked">

        <option value="">（选手动选文件或下方样本）</option>

        <option v-for="d in demoVideosFiltered" :key="d.id" :value="d.id">{{ d.label }}</option>

      </select>

      <button
        @click="loadRecommendedDemo"
        :disabled="busy || !!session || !!pendingStartBody || !recommendedDemo"
      >
        加载推荐样本
      </button>

    </div>

    <div class="row" v-if="inputMode === 'video'">

      <input

        type="file"

        accept="video/*"

        :disabled="busy || !!session || !!pendingStartBody"

        @change="onVideoPicked"

      />

      <span class="muted" v-if="videoLabel">{{ videoLabel }} · {{ mpFrameCount }} 姿态帧</span>
      <span class="muted">视频不超过100MB；浏览器解析限3分钟，建议先用10～30秒全身动作片段。</span>
      <button v-if="videoProcessing" class="secondary" @click="cancelVideoProcessing">取消解析</button>

      <button
        class="secondary"
        @click="reprocessVideo"
        :disabled="(!videoFile && !demoRelPath) || busy || !!session || !!pendingStartBody"
      >

        重新解析视频

      </button>

    </div>

    <div class="row" v-else>

      <button class="secondary" @click="switchCamera" :disabled="busy || cameraStarting || captureActive">{{ facingMode === 'user' ? '改用后置镜头' : '改用前置镜头' }}</button>
      <span v-if="captureActive" class="muted">请先暂停训练再切换镜头。</span>

      <button v-if="!session" @click="startCam" :disabled="camOn || cameraStarting || busy || !!cameraSupportIssue">{{ cameraStarting ? '正在打开摄像头…' : '打开摄像头' }}</button>

      <button v-if="!session" class="secondary" @click="stopCam" :disabled="!camOn && !cameraStarting">关闭摄像头</button>
      <template v-if="session">
        <button v-if="camOn && !paused" class="secondary" @click="pauseCapture" :disabled="busy">暂停训练</button>
        <button v-else @click="resumeCapture" :disabled="busy || cameraStarting || cameraFrames.length >= captureLimit || !!cameraSupportIssue">{{ cameraStarting ? '正在准备…' : '继续训练' }}</button>
        <span role="status">{{ camOn && poseReady && !paused ? '正在采集' : '已暂停，点击继续训练' }} · 摄像头采集 {{ captureTime }}</span>
      </template>

    </div>

    <div v-if="inputMode === 'camera'">
      <p v-if="cameraSupportIssue" class="err" role="alert">{{ cameraSupportIssue }}</p>
      <p class="muted">先把手机固定稳，全身入画并留出活动空间。切到后台会暂停采集，回来后点击“继续训练”。</p>
      <p v-if="session" role="status">
        {{ screenAwakeMessage }}
        <button v-if="awakeStatus === 'unavailable' && captureActive" class="secondary" @click="screenAwake.setActive(true)">重试保持亮屏</button>
      </p>
    </div>

    <div class="row">

      <button @click="start" :disabled="!initialized || !!session || busy || (!pendingStartBody && !canStart)">{{ pendingStartBody ? "重试开始" : "开始训练" }}</button>

      <button class="secondary" @click="finish" :disabled="!session || busy">结束并生成报告</button>
      <button class="secondary" v-if="session" @click="cancelSession" :disabled="busy">取消本次训练</button>

    </div>

    <p v-if="hint" class="ok">{{ hint }}</p>

    <p v-if="err" class="err" role="alert">{{ err }}</p>

    <div class="grid-2" style="margin-top:12px">

      <div class="cam-wrap" :class="{ 'offline-play': inputMode === 'video' && previewOn }">

        <video
          ref="videoEl"
          playsinline
          muted
          :controls="inputMode === 'video' && previewOn"
          @play="onVideoPlay"
          @pause="onVideoPause"
          @seeked="paintPoseOverlay"
          @timeupdate="paintPoseOverlay"
          @ended="onVideoEnded"
        ></video>

        <canvas ref="canvasEl"></canvas>

        <div v-if="!previewOn" class="hint">

          {{ inputMode === "video" ? savedPayload ? "已恢复保存的姿态数据，可直接生成报告。当前没有视频预览。" : "请选择演示样本或本地视频；解析后可直接播放，骨架会跟着走。" : "尚未开启摄像头。" }}

        </div>

      </div>

      <div>

        <div class="row" v-if="inputMode === 'video' && previewOn" style="margin-bottom:8px">

          <button class="secondary" @click="playWithPose" :disabled="busy || videoPlaying">播放</button>

          <button class="secondary" @click="pausePosePlayback" :disabled="busy || !videoPlaying">暂停</button>

          <button class="secondary" @click="replayWithPose" :disabled="busy">重播</button>

          <button
            class="secondary"
            @click="exportPoseJson"
            :disabled="busy || !overlayCocoFrames.length"
          >
            导出姿态 JSON
          </button>

        </div>

        <div class="stat"><span>姿态</span><b style="font-size:15px">{{ poseHint || "等待输入" }}</b></div>

        <div class="stat" v-if="liveHud.t != null" style="margin-top:8px">
          <span>播放位置</span>
          <b style="font-size:15px">{{ liveHud.t }} · 膝角 {{ liveHud.knee }}</b>
        </div>

        <div v-if="kneeSeries.length > 1" style="margin-top:12px">
          <p class="muted" style="margin:0 0 6px">膝角曲线（整段，°）· 绿点=当前时刻</p>
          <canvas ref="kneeChartEl" class="knee-chart" width="360" height="90"></canvas>
          <p class="muted" v-if="kneeStats">
            最小 {{ kneeStats.min }}° · 最大 {{ kneeStats.max }}° · 均值 {{ kneeStats.mean }}°
          </p>
        </div>

        <p v-if="session" style="margin-top:12px"><span class="tag on">会话 #{{ session.id }} 进行中</span></p>

        <p class="muted" v-if="inputMode === 'video' && (mpFrameCount || savedPayload)">

          视频已解析为姿态数据，结束训练后用于生成报告。

        </p>

        <ol class="muted" style="padding-left:18px">

          <li v-if="inputMode === 'video'">一键推荐 / 选视频 → 等待解析 → 播放看骨架</li>

          <li v-else>打开摄像头，全身入画</li>

          <li>开始训练 → 结束并生成报告 → 查看本次记录</li>

        </ol>

      </div>

    </div>

  </div>

</template>



<script setup>

import { onBeforeRouteLeave } from "vue-router";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { useRoute, useRouter } from "vue-router";

import api, { errorMessage, getUser } from "../api/client";

import { createPoseCamera } from "../composables/usePoseCamera";

import { processVideoFile } from "../composables/usePoseVideoFile";

import { processVideoServer } from "../composables/usePoseVideoServer";

import { createCaptureClock } from "../utils/captureClock.js";
import { cameraSupportError, cameraErrorMessage } from '../utils/cameraAccess.js';
import { createScreenAwake } from '../utils/screenAwake.js';
import { createStartRecovery } from '../utils/startRecovery.js';
import { validateVideoFile, checkAborted, loadVideoSource, seekVideo } from '../utils/videoInput.js';

import { isOfflineRtmpose } from "../config/poseModel.js";

import {
  anglesFromCocoKeypoints,
  buildPoseSummary,
  buildPoseSummaryFromServer,
  drawCoco17Skeleton,
  hintFromAngles,
  mp33FrameToCoco17Keypoints,
  landmarksToMp33Frame,
} from "../utils/poseFormat";



const user = getUser();

const router = useRouter();
const route = useRoute();
const savedPayload = ref(null);
const cameraFrames = ref([]);
const pendingStartBody = ref(null);
const startIntent = ref(null), initialized = ref(false);
const startRecovery = createStartRecovery({ storage: sessionStorage, userId: user.id, api,
  randomKey: () => crypto.randomUUID() });
const poseReady = ref(false), paused = ref(false), activeMs = ref(0);
const cameraSupportIssue = computed(() => cameraSupportError());
const awakeStatus = ref('idle');
const screenAwake = createScreenAwake({ onChange: status => { awakeStatus.value = status; } });
const captureActive = computed(() => !!session.value && inputMode.value === 'camera' && camOn.value && poseReady.value && !paused.value && !busy.value);
const screenAwakeMessage = computed(() => {
  if (!captureActive.value) return '采集暂停时不保持亮屏；继续训练后会重新尝试。';
  if (awakeStatus.value === 'active') return '已开启训练期间保持亮屏，暂停或离开后自动释放。';
  if (awakeStatus.value === 'requesting') return '正在尝试保持亮屏…';
  return '当前未能自动保持亮屏，请将手机自动锁屏时间调长；锁屏或离开页面会暂停采集。';
});
const captureClock = createCaptureClock();
let clockTimer = null;
const videoProcessing = ref(false);
let videoProcessAbort = null;
function cancelVideoProcessing() { videoProcessAbort?.abort(); }
const captureTime = computed(() => {
  const seconds = Math.floor(activeMs.value / 1000);
  return `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`;
});
function syncClock() {
  if (session.value && inputMode.value === 'camera' && camOn.value && poseReady.value && !paused.value && !busy.value) captureClock.start();
  else captureClock.pause();
  activeMs.value = captureClock.elapsed();
}
function cameraPayload(payload) {
  syncClock();
  return { ...payload, pose_summary: { ...payload.pose_summary, capture_session: { active_ms: activeMs.value } } };
}
function pauseCapture() {
  if (!session.value || inputMode.value !== 'camera') return;
  paused.value = true;
  stopCam();
  changeVersion++; draftDirty.value = true;
  retrySave();
}
async function resumeCapture() {
  if (cameraFrames.value.length >= captureLimit) return;
  if (camOn.value && !poseReady.value) stopCam();
  await startCam();
  if (camOn.value && poseReady.value) { paused.value = false; syncClock(); }
  else if (camOn.value) {
    stopCam();
    err.value = '姿态模型未能加载，请检查网络后点击继续训练重试。';
  }
}
const captureLimit = 1200;
const saveState = ref(''), saveError = ref(''), lastSavedAt = ref('');
const draftDirty = ref(false), draftConflict = ref(false), saving = ref(false);
let changeVersion = 0, savePromise = null, autosaveTimer = null, lastCapture = 0;
let cameraOffset = 0, cameraBase = 0;
function captureFrame(landmarks) {
  if (!session.value || busy.value || paused.value || inputMode.value !== 'camera') return;
  const now = performance.now();
  if (now - lastCapture < 500) return;
  lastCapture = now;
  if (cameraFrames.value.length >= captureLimit) {
    pauseCapture();
    poseHint.value = '已达到1200帧采集上限，请结束并保存，再开始新的训练。';
    return;
  }
  cameraOffset = Math.round(now - cameraBase);
  cameraFrames.value.push(landmarksToMp33Frame(landmarks, cameraOffset, cameraFrames.value.length));
  changeVersion++;
  draftDirty.value = true;
  if (cameraFrames.value.length >= captureLimit) {
    pauseCapture();
    poseHint.value = '已达到1200帧采集上限，已暂停，请结束并保存本次训练。';
  }
}
function beforeUnload(event) {
  if (session.value && (draftDirty.value || saving.value)) { event.preventDefault(); event.returnValue = ''; }
}
function retrySave() { persistDraft().catch(() => {}); }
function onVisibility() {
  if (!document.hidden) return;
  if (inputMode.value === 'camera' && (camOn.value || cameraStarting.value)) {
    if (session.value) pauseCapture();
    else stopCam();
    hint.value = session.value ? '已切到后台，训练采集已暂停并尝试保存。回来后点击继续训练。' : '已切到后台，摄像头已关闭。回来后请重新打开。';
  }
  else if (draftDirty.value && !busy.value) retrySave();
}


const exercises = ref([]);

const exerciseId = ref("squat");

const session = ref(null);

const prescriptionId = ref(0);
const loadedPlan = ref(null);
const planLinkError = ref(false);
const planTarget = computed(() => session.value
  ? (session.value.plan_snapshot?.exercise ? session.value.plan_snapshot : null)
  : loadedPlan.value && exercises.value.some(e => e.id === exerciseId.value) && { version: loadedPlan.value.version, status: loadedPlan.value.status,
      exercise: exercises.value.find(e => e.id === exerciseId.value) });

const videoEl = ref(null);

const canvasEl = ref(null);

const kneeChartEl = ref(null);

const inputMode = ref("video");

const videoFile = ref(null);

const mpFrames = ref([]);

const serverPoseResult = ref(null);

const videoMeta = ref({ width: 0, height: 0, fileName: "" });

const liveHud = ref({ t: null, knee: "—" });

const mpFrameCount = computed(() => {
  if (serverPoseResult.value?.coco17_frames?.length) {
    return serverPoseResult.value.coco17_frames.length;
  }
  return mpFrames.value.length;
});

const offlinePoseLabel = computed(() =>
  isOfflineRtmpose() ? "RTMPose（服务端 COCO-17）" : "MediaPipe（浏览器 MP33）",
);

const videoLabel = computed(
  () => videoMeta.value.fileName || demoRelPath.value || videoFile.value?.name || "",
);

const recommendedDemo = computed(() => {
  return demoVideosFiltered.value[0] || null;
});

const kneeSeries = computed(() => {
  const frames = overlayCocoFrames.value || [];
  return frames.map((f) => {
    const ang = anglesFromCocoKeypoints(f.keypoints || []);
    const knee = ang.knee_flexion_l ?? ang.knee_flexion_r;
    return { t_ms: f.t_ms || 0, knee: knee == null ? null : Number(knee) };
  });
});

const kneeStats = computed(() => {
  const vals = kneeSeries.value.map((x) => x.knee).filter((v) => v != null);
  if (!vals.length) return null;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const mean = Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
  return { min, max, mean };
});

/** 展示优先样本（全身/动作清晰）；半身自拍类沉底 */
const DEMO_PIN = [
  "squat/repcount_stu4_66.mp4",
  "squat/repcount_stu1_68.mp4",
  "squat/infinite_000000.mp4",
  "jump_jack/repcount_stu6_18.mp4",
  "push_up/repcount_stu7_49.mp4",
];
const DEMO_DEMOTE = ["squat/repcount_stu6_62.mp4"];

function demoRank(d) {
  const rel = d.rel_path || "";
  const pin = DEMO_PIN.indexOf(rel);
  if (pin >= 0) return pin;
  if (DEMO_DEMOTE.includes(rel)) return 900;
  return 100;
}

/** 与当前动作类型匹配的演示样本；推荐置顶 */
const demoVideosFiltered = computed(() => {
  const all = demoVideos.value;
  if (!all.length) return [];
  const matched = all.filter((d) => d.exercise_id === exerciseId.value);
  const list = [...matched];
  list.sort((a, b) => demoRank(a) - demoRank(b) || String(a.label).localeCompare(String(b.label)));
  return list.map((d) => {
    const rel = d.rel_path || "";
    if (DEMO_PIN.includes(rel) && !String(d.label).includes("推荐")) {
      return { ...d, label: `★推荐 ${d.label}` };
    }
    return d;
  });
});

watch(inputMode, () => {
  if (session.value) return;
  stopCam(); stopPosePlayback();
  mpFrames.value = []; serverPoseResult.value = null; overlayCocoFrames.value = [];
  savedPayload.value = null; videoFile.value = null; demoRelPath.value = ''; demoPickId.value = '';
  videoMeta.value = { width: 0, height: 0, fileName: '' };
  if (localObjectUrl) { URL.revokeObjectURL(localObjectUrl); localObjectUrl = null; }
});

const camOn = ref(false);
const cameraStarting = ref(false);
const facingMode = ref('user');

async function switchCamera() {
  if (busy.value || cameraStarting.value || captureActive.value) return;
  const reopen = camOn.value;
  stopCam();
  facingMode.value = facingMode.value === 'user' ? 'environment' : 'user';
  if (reopen) await startCam();
}

const previewOn = ref(false);

const hint = ref("");

const err = ref("");

const poseHint = ref("");

const busy = ref(true);
watch(captureActive, active => { screenAwake.setActive(active); }, { flush: 'sync' });

const demoVideos = ref([]);

const demoPickId = ref("");

const demoRelPath = ref("");

const videoPlaying = ref(false);

const overlayCocoFrames = ref([]);

let cameraCtl = null;

let playbackRaf = 0;

let localObjectUrl = null;

function nearestCocoFrame(frames, tMs) {
  if (!frames?.length) return null;
  let best = frames[0];
  let bestD = Math.abs((frames[0].t_ms || 0) - tMs);
  for (let i = 1; i < frames.length; i++) {
    const d = Math.abs((frames[i].t_ms || 0) - tMs);
    if (d < bestD) {
      best = frames[i];
      bestD = d;
    }
  }
  return best;
}

function stopPosePlayback() {
  if (playbackRaf) {
    cancelAnimationFrame(playbackRaf);
    playbackRaf = 0;
  }
  videoPlaying.value = false;
  const v = videoEl.value;
  if (v && !v.paused) v.pause();
}

/** 离线：只在透明 canvas 上叠骨架，底下是可播的 video */
function paintPoseOverlay() {
  const video = videoEl.value;
  const canvas = canvasEl.value;
  if (!video || !canvas || inputMode.value !== "video") return;
  const w = video.videoWidth || videoMeta.value.width || 640;
  const h = video.videoHeight || videoMeta.value.height || 480;
  if (!w || !h) return;
  if (canvas.width !== w) canvas.width = w;
  if (canvas.height !== h) canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  const frame = nearestCocoFrame(overlayCocoFrames.value, video.currentTime * 1000);
  if (frame?.keypoints) {
    drawCoco17Skeleton(ctx, frame.keypoints, w, h);
    poseHint.value = hintFromAngles(anglesFromCocoKeypoints(frame.keypoints));
  }
}

function playbackTick() {
  paintPoseOverlay();
  const v = videoEl.value;
  if (v && !v.paused && !v.ended) {
    playbackRaf = requestAnimationFrame(playbackTick);
  } else {
    videoPlaying.value = false;
    playbackRaf = 0;
    paintPoseOverlay();
  }
}

function onVideoPlay() {
  videoPlaying.value = true;
  if (playbackRaf) cancelAnimationFrame(playbackRaf);
  playbackRaf = requestAnimationFrame(playbackTick);
}

function onVideoPause() {
  videoPlaying.value = false;
  if (playbackRaf) {
    cancelAnimationFrame(playbackRaf);
    playbackRaf = 0;
  }
  paintPoseOverlay();
}

function onVideoEnded() {
  videoPlaying.value = false;
  if (playbackRaf) {
    cancelAnimationFrame(playbackRaf);
    playbackRaf = 0;
  }
  paintPoseOverlay();
}

async function prepareVideoSrc(src, signal) {
  stopPosePlayback();
  const v = videoEl.value;
  if (!v) return;
  if (localObjectUrl && localObjectUrl !== src) {
    URL.revokeObjectURL(localObjectUrl);
    localObjectUrl = null;
  }
  if (typeof src === "string" && src.startsWith("blob:")) {
    localObjectUrl = src;
  }
  await loadVideoSource(v, src, { signal });
  await seekVideo(v, 0, { signal });
  checkAborted(signal);
  previewOn.value = true;
  paintPoseOverlay();
}

async function playWithPose() {
  const v = videoEl.value;
  if (!v?.src || !overlayCocoFrames.value.length) return;
  try {
    await v.play();
  } catch {
    err.value = "浏览器阻止自动播放，请用视频下方控件或再点「播放」";
    return;
  }
}

function pausePosePlayback() {
  stopPosePlayback();
  paintPoseOverlay();
}

async function replayWithPose() {
  const v = videoEl.value;
  if (!v?.src) return;
  stopPosePlayback();
  v.currentTime = 0;
  await playWithPose();
}

const canStart = computed(() => {
  if (!initialized.value || planLinkError.value) return false;

  if (inputMode.value === "video") {
    return (
      mpFrames.value.length > 0 ||
      (serverPoseResult.value?.coco17_frames?.length ?? 0) > 0
    );
  }

  return camOn.value && poseReady.value;

});



async function initialize() {
  if (session.value) return;
  busy.value = true; initialized.value = false; err.value = ''; planLinkError.value = false;
  try {

  startIntent.value = startRecovery.read();
  if (startIntent.value) {
    const row = await startRecovery.lookup(startIntent.value);
    if (row) {
      await adoptSession(row, true);
      initialized.value = true;
      return;
    }
  }

  if (route.query.session_id) {
    await restoreSession();
    initialized.value = true;
    return;
  }

  const { data } = await api.get("/prescriptions/templates");

  const all = [...(data.fitness?.exercises || []), ...(data.medical?.exercises || [])];

  exercises.value = all;

  exerciseId.value = all[0]?.id || "squat";

  try {

    const cur = await api.get(`/prescriptions/current?user_id=${user.id}`);

    prescriptionId.value = cur.data.id;
    loadedPlan.value = cur.data;

    if (cur.data.exercises?.length) {

      exercises.value = cur.data.exercises;

      exerciseId.value = cur.data.exercises[0].id;

    }

  } catch (error) {
    if (error?.response?.status !== 404) throw error;
    prescriptionId.value = 0; loadedPlan.value = null;
  }

  if (startIntent.value) {
    exerciseId.value = startIntent.value.exercise_id;
    prescriptionId.value = startIntent.value.prescription_id;
    inputMode.value = startIntent.value.input_mode;
    if (loadedPlan.value?.id !== prescriptionId.value) {
      loadedPlan.value = null;
      exercises.value = all;
    }
    if (!exercises.value.some(e => e.id === exerciseId.value)) exercises.value.push({ id: exerciseId.value, name: exerciseId.value });
  } else if (route.query.prescription_id && !route.query.session_id) {
    if (String(loadedPlan.value?.id) !== String(route.query.prescription_id)) {
      planLinkError.value = true;
      throw new Error('训练计划已更新或无法读取，请返回训练计划重新选择。');
    }
    if (!exercises.value.some(e => e.id === route.query.exercise_id)) {
      planLinkError.value = true;
      throw new Error('该动作不在当前训练计划中，请返回重新选择。');
    }
    exerciseId.value = route.query.exercise_id;
  }

  try {

    const { data } = await api.get("/demo-videos/manifest");

    demoVideos.value = data.videos || [];

    if (demoVideos.value.length) {
      const base = `离线演示已就绪：${demoVideos.value.length} 个样本（RepCount + InfiniteRep）`;
      hint.value = isOfflineRtmpose()
        ? `${base}；解析走本地 RTMPose（需 AI 服务 8101）`
        : `${base}；解析走浏览器 MediaPipe`;
    } else {

      hint.value = "演示清单为空，请在项目根运行: python scripts/setup_offline_demo.py";

    }

  } catch (e) {

    demoVideos.value = [];

    const detail = e?.response?.data?.detail;

    hint.value =

      typeof detail === "string"

        ? detail

        : "无法加载演示样本（请启动后端并运行 python scripts/sync_demo_videos.py）";

  }

  if (isOfflineRtmpose()) {
    try {
      const { data: est } = await api.get("/pose/estimator");
      if (est?.estimator) {
        hint.value = `${hint.value || ""} · RTMPose: ${est.estimator}`.replace(/^ · /, "");
      }
    } catch {
      err.value =
        "RTMPose（8101）未就绪。请另开终端：cd ai_services/pose && python main.py";
    }
  }

  if (!startIntent.value) await restoreSession();
  initialized.value = true;
  } catch (e) { err.value = errorMessage(e, "训练页面读取失败，请刷新重试"); }
  finally { busy.value = false; }
}
onMounted(initialize);

async function adoptSession(row, restored = false) {
  if (row.status !== 'running') {
    stopCam();
    await router.replace(row.status === 'finished'
      ? { path: '/report', query: { session_id: row.id } } : { path: '/history' });
  } else {
    session.value = row;
    exerciseId.value = row.exercise_id;
    if (!exercises.value.some(e => e.id === row.exercise_id)) exercises.value.push({ id: row.exercise_id, name: row.exercise_name });
    prescriptionId.value = row.prescription_id;
    inputMode.value = ['camera_live_only', 'camera'].includes(row.pose_summary?.source) ? 'camera' : 'video';
    savedPayload.value = { video_path: row.video_path || '', pose_summary: row.pose_summary || {} };
    cameraFrames.value = row.pose_summary?.sequences?.mediapipe33?.frames || [];
    cameraOffset = cameraFrames.value.at(-1)?.t_ms || 0;
    cameraBase = performance.now() - cameraOffset;
    captureClock.reset(row.pose_summary?.capture_session?.active_ms);
    activeMs.value = captureClock.elapsed(); paused.value = !camOn.value;
    lastSavedAt.value = ''; draftDirty.value = false;
    localStorage.setItem('ah_last_session', String(row.id));
    await router.replace({ path: '/exercise', query: { session_id: row.id } });
    hint.value = restored ? '已找回上次建立的训练，没有重复创建。保存的数据将用于生成报告。'
      : inputMode.value === 'video' ? '训练已建立，可回看视频后生成报告。' : '训练已开始，请全身入画。中途可暂停。';
  }
  if (startIntent.value && row.start_key === startIntent.value.start_key) {
    startRecovery.clear(startIntent.value.start_key);
    startIntent.value = null;
  }
  pendingStartBody.value = null;
}

async function restoreSession() {
  if (route.query.prescription_id && !route.query.session_id) return;
  const raw = route.query.session_id || localStorage.getItem("ah_last_session");
  if (!raw) return;
  if (!/^\d+$/.test(String(raw)) || Number(raw) < 1) {
    if (route.query.session_id) throw new Error("训练编号无效");
    return;
  }
  try {
    const { data } = await api.get(`/sessions/${raw}`, { params: { user_id: user.id } });
    const row = data.session;
    if (row.status !== "running") {
      if (route.query.session_id) {
        if (row.status === "finished") await router.replace({ path: "/report", query: { session_id: row.id } });
        else err.value = "这次训练已取消，请开始新的训练。";
      }
      return;
    }
    await adoptSession(row, true);
  } catch (e) {
    if (route.query.session_id) throw e;
    if (e?.response?.status !== 404) throw e;
  }
}

async function cancelSession() {
  busy.value = true;
  err.value = "";
  try {
    await api.post(`/sessions/${session.value.id}/cancel`, null, { params: { user_id: user.id } });
    localStorage.removeItem("ah_last_session");
    session.value = null;
    stopCam();
    await router.push("/history");
  } catch (e) { err.value = errorMessage(e, "取消失败，请重试"); }
  finally { busy.value = false; }
}

async function loadRecommendedDemo() {
  if (busy.value || session.value || pendingStartBody.value || !recommendedDemo.value) return;
  demoPickId.value = recommendedDemo.value.id;
  await onDemoPicked();
}

async function onDemoPicked() {
  if (session.value || pendingStartBody.value || busy.value) return;

  if (!demoPickId.value) return;

  const pick = demoVideos.value.find((d) => d.id === demoPickId.value);

  if (!pick) return;

  err.value = "";

  busy.value = true;

  try {

    const res = await api.get("/demo-videos/file", {

      params: { rel: pick.rel_path },

      responseType: "blob",

      timeout: 120000,

    });

    videoFile.value = new File([res.data], pick.file_name, { type: "video/mp4" });

    demoRelPath.value = pick.rel_path;

    if (pick.exercise_id && exercises.value.some((e) => e.id === pick.exercise_id)) {

      exerciseId.value = pick.exercise_id;

    }

    await runVideoProcess();

  } catch (e) {

    err.value = e?.response?.data?.detail || e?.message || "加载演示视频失败";

  } finally {

    busy.value = false;

  }

}



async function onVideoPicked(ev) {
  if (session.value || pendingStartBody.value || busy.value) return;

  const file = ev.target.files?.[0];

  ev.target.value = "";

  if (!file) return;
  try { validateVideoFile(file); }
  catch (error) { err.value = error.message; return; }

  demoPickId.value = "";

  demoRelPath.value = "";

  videoFile.value = file;

  await runVideoProcess();

}



async function reprocessVideo() {
  if (session.value || pendingStartBody.value || busy.value) return;

  if (!videoFile.value && !demoRelPath.value) return;

  await runVideoProcess();

}



async function runVideoProcess() {
  const controller = new AbortController();
  videoProcessAbort = controller;
  videoProcessing.value = true;
  const signal = controller.signal;

  err.value = "";

  busy.value = true;

  mpFrames.value = [];

  serverPoseResult.value = null;

  overlayCocoFrames.value = [];

  stopPosePlayback();

  previewOn.value = false;

  try {
    validateVideoFile(videoFile.value);

    if (isOfflineRtmpose()) {

      const pathRel = demoRelPath.value ? `data/demo_videos/${demoRelPath.value}` : null;

      const result = await processVideoServer({

        videoPathRel: pathRel,

        file: pathRel ? null : videoFile.value,

        sampleHz: 6,
        signal,

        exerciseId: exerciseId.value,

        onProgress: (p) => {

          hint.value = p.message || `RTMPose ${Math.round(p.progress * 100)}%`;

        },

      });
      checkAborted(signal);

      serverPoseResult.value = result.serverResult;

      overlayCocoFrames.value = result.cocoFrames || [];

      videoMeta.value = {

        width: result.width,

        height: result.height,

        fileName: videoFile.value?.name || pathRel?.split("/").pop() || "",

      };

      poseHint.value = result.hint;

      hint.value = `RTMPose 完成：${result.cocoFrames.length} 帧 COCO-17（约 ${result.durationSec.toFixed(1)}s），正在播放…`;

      if (demoRelPath.value) {
        await prepareVideoSrc(`/api/demo-videos/file?rel=${encodeURIComponent(demoRelPath.value)}`, signal);
      } else if (videoFile.value) {
        localObjectUrl = URL.createObjectURL(videoFile.value);
        await prepareVideoSrc(localObjectUrl, signal);
      }
      await playWithPose();
      checkAborted(signal);
      await persistDraft();

      return;

    }

    const result = await processVideoFile({

      video: videoEl.value,

      canvas: canvasEl.value,

      file: videoFile.value,

      sampleHz: 6,
      signal,

      onProgress: (p) => {

        hint.value = p.message || `解析中 ${Math.round(p.progress * 100)}%`;

      },

    });
    checkAborted(signal);

    mpFrames.value = result.mpFrames;
    overlayCocoFrames.value = result.mpFrames.map(mp33FrameToCoco17Keypoints);

    videoMeta.value = {

      width: result.width,

      height: result.height,

      fileName: videoFile.value.name,

    };

    poseHint.value = result.hint;

    hint.value = `MediaPipe 完成：${result.mpFrames.length} 帧（约 ${result.durationSec.toFixed(1)}s），正在播放…`;

    // processVideoFile 会清空 video.src，需重新挂上本地文件再播
    const blobUrl = URL.createObjectURL(videoFile.value);
    await prepareVideoSrc(blobUrl, signal);
    await playWithPose();
    checkAborted(signal);
    await persistDraft();

  } catch (e) {
    if (signal.aborted || e?.name === 'AbortError' || e?.code === 'ERR_CANCELED') {
      mpFrames.value = []; serverPoseResult.value = null; overlayCocoFrames.value = [];
      previewOn.value = false; hint.value = '已取消解析，可重新选择视频。';
      stopPosePlayback();
      if (videoEl.value) {
        videoEl.value.pause();
        videoEl.value.removeAttribute('src');
        videoEl.value.load();
      }
      if (localObjectUrl) { URL.revokeObjectURL(localObjectUrl); localObjectUrl = null; }
      return;
    }

    const detail = e?.response?.data?.detail || e?.message || "视频解析失败";
    err.value =
      typeof detail === "string" && /姿态服务|8101|ECONNREFUSED|unavailable/i.test(detail)
        ? `${detail}（请确认已启动：cd ai_services/pose && python main.py）`
        : detail;

  } finally {
    if (videoProcessAbort === controller) {
      videoProcessAbort = null;
      videoProcessing.value = false;
    }

    busy.value = false;

  }

}



async function startCam() {
  if (cameraStarting.value || camOn.value) return;
  if (cameraSupportIssue.value) { err.value = cameraSupportIssue.value; return; }
  cameraStarting.value = true;
  let controller;

  err.value = "";

  try {

    cameraBase = performance.now() - cameraOffset;
    lastCapture = 0;
    cameraCtl = createPoseCamera({
      facingMode: facingMode.value,

      video: videoEl.value,

      canvas: canvasEl.value,

      onFrame: captureFrame,
      onReady: ready => { poseReady.value = ready; syncClock(); },
      onInterrupted: () => {
        if (session.value) pauseCapture();
        else stopCam();
        hint.value = session.value ? '摄像头连接已中断，训练已暂停并尝试保存。检查权限或设备连接后点击继续训练。' : '摄像头连接已中断，请检查权限或设备连接后重新打开。';
      },
      onHint: (t) => {

        poseHint.value = t;

      },

    });

    controller = cameraCtl;
    const opened = await controller.start();
    if (!opened || cameraCtl !== controller) return;

    cameraBase = performance.now() - cameraOffset;
    camOn.value = true;
    syncClock();

    previewOn.value = true;

    hint.value = "摄像头已打开";

  } catch (e) {

    if (controller && cameraCtl !== controller) return;
    stopCam();
    err.value = cameraSupportIssue.value || cameraErrorMessage(e);
  } finally {
    if (cameraCtl === controller) cameraStarting.value = false;

  }

}



function stopCam() {
  camOn.value = false; poseReady.value = false;
  syncClock();
  cameraStarting.value = false;

  cameraCtl?.stop();

  cameraCtl = null;

  camOn.value = false;

  previewOn.value = false;

  poseHint.value = "";

}



async function start() {
  if (!initialized.value || planLinkError.value || busy.value || session.value || (!pendingStartBody.value && !canStart.value)) return;
  const recovering = !!startIntent.value;
  err.value = ''; busy.value = true;
  try {
    if (!pendingStartBody.value) {
      startIntent.value = startRecovery.begin({ exercise_id: exerciseId.value,
        prescription_id: prescriptionId.value, input_mode: inputMode.value });
      const name = exercises.value.find(e => e.id === exerciseId.value)?.name || exerciseId.value;
      pendingStartBody.value = JSON.parse(JSON.stringify({
        user_id: user.id, exercise_id: exerciseId.value, exercise_name: name,
        prescription_id: prescriptionId.value, start_key: startIntent.value.start_key, ...buildSubmission(),
      }));
    }
    // Keep the exact request after a lost response; the server returns the original record.
    const { data } = await api.post('/sessions/start', pendingStartBody.value);
    await adoptSession(data.session);
  } catch (e) {
    // An invalid first attempt is safe to discard. A prior uncertain attempt may still commit.
    if (!recovering && [400, 422].includes(e?.response?.status) && startIntent.value) {
      startRecovery.clear(startIntent.value.start_key);
      startIntent.value = null; pendingStartBody.value = null;
    }
    err.value = errorMessage(e, startIntent.value
      ? '开始请求未确认，请点击“重试开始”或“检查上次开始结果”。刷新后也会先检查原请求。'
      : '无法准备开始记录，请允许本站保存数据后重试。');
  } finally { busy.value = false; syncClock(); }
}

function buildSubmission() {
  if (inputMode.value === 'camera' && cameraFrames.value.length) {
    return cameraPayload({ video_path: '', pose_summary: buildPoseSummary({
      sessionId: session.value?.id, exerciseId: exerciseId.value,
      exerciseName: session.value?.exercise_name || exerciseId.value,
      mpFrames: cameraFrames.value, source: 'camera',
      width: videoEl.value?.videoWidth || 640, height: videoEl.value?.videoHeight || 480,
    }) });
  }
  if (savedPayload.value && !serverPoseResult.value?.coco17_frames?.length && !mpFrames.value.length && !camOn.value) return inputMode.value === 'camera' ? cameraPayload(savedPayload.value) : savedPayload.value;
    const name = exercises.value.find((e) => e.id === exerciseId.value)?.name || exerciseId.value;

    let poseSummary;

    if (inputMode.value === "video" && serverPoseResult.value?.coco17_frames?.length) {

      poseSummary = buildPoseSummaryFromServer({

        sessionId: session.value?.id ?? null,

        exerciseId: exerciseId.value,

        exerciseName: name,

        serverResult: serverPoseResult.value,

        source: "offline_video",

        videoFileName: videoMeta.value.fileName,

      });

    } else if (inputMode.value === "video" && mpFrames.value.length) {

      poseSummary = buildPoseSummary({

        sessionId: session.value?.id ?? null,

        exerciseId: exerciseId.value,

        exerciseName: name,

        mpFrames: mpFrames.value,

        source: "offline_video",

        videoFileName: videoMeta.value.fileName,

        width: videoMeta.value.width,

        height: videoMeta.value.height,

      });

    } else {

      poseSummary = {

        schema_version: "1.0.0",

        exercise_id: exerciseId.value,

        source: "camera_live_only",

        live_hint: poseHint.value,

        sequences: { mediapipe33: { frames: [] }, coco17: { frames: [] } },

      };

    }

    let videoPath = "";
    if (inputMode.value === "video" && videoMeta.value.fileName) {
      if (serverPoseResult.value?.upload_rel) {
        videoPath = serverPoseResult.value.upload_rel;
      } else if (demoRelPath.value) {
        videoPath = `demo_videos/${demoRelPath.value}`;
      } else if (serverPoseResult.value?.resolved_path) {
        videoPath = serverPoseResult.value.resolved_path;
      } else {
        // Browser-only analysis does not upload or persist the local video file.
        videoPath = "";
      }
    }



  const payload = { video_path: videoPath, pose_summary: poseSummary };
  return inputMode.value === 'camera' ? cameraPayload(payload) : payload;
}

async function persistDraft() {
  if (!session.value) return;
  if (draftConflict.value) throw new Error('请重新打开训练，核对其他页面保存的内容。');
  if (savePromise) { await savePromise; return persistDraft(); }
  const id = session.value.id, version = changeVersion;
  // Freeze the payload: camera capture may continue while the request is in flight.
  const submission = JSON.parse(JSON.stringify(buildSubmission()));
  saving.value = true; saveError.value = ''; saveState.value = '正在保存…';
  savePromise = (async () => {
    try {
      const { data } = await api.put(`/sessions/${id}/draft`, {
        ...submission, expected_revision: session.value.draft_revision || 0,
      }, { params: { user_id: user.id } });
      if (session.value?.id !== id) return;
      session.value.draft_revision = data.session.draft_revision;
      savedPayload.value = submission;
      draftDirty.value = changeVersion !== version;
      lastSavedAt.value = new Date().toLocaleTimeString();
      saveState.value = '已保存';
    } catch (e) {
      draftDirty.value = true;
      draftConflict.value = e?.response?.status === 409;
      saveError.value = errorMessage(e, '保存失败，数据暂留在当前页面，请保持页面打开并重试。');
      saveState.value = '尚未保存';
      throw e;
    } finally { saving.value = false; }
  })();
  try { await savePromise; } finally { savePromise = null; }
}


async function finish() {
  if (inputMode.value === 'camera' && !cameraFrames.value.length) {
    err.value = '还没有采集到姿态，请全身入画并继续训练；也可以取消本次训练。';
    return;
  }
  if (inputMode.value === 'camera') { paused.value = true; stopCam(); }

  err.value = "";

  busy.value = true;

  stopPosePlayback();

  try {

    await persistDraft();
    const submission = buildSubmission();

    const { data } = await api.post(`/sessions/${session.value.id}/finish`, {

      ...submission, expected_revision: session.value.draft_revision || 0,

    });

    localStorage.setItem("ah_last_session", String(data.session.id));

    session.value = null;

    stopCam();

    hint.value = `报告已生成（姿态帧 ${submission.pose_summary.sequences?.coco17?.frames?.length ?? 0}）…`;

    router.push({ path: "/report", query: { session_id: data.session.id } });

  } catch (e) {

    // A timed-out finish may already have committed. Recover its report instead of creating another session.
    try {
      const { data } = await api.get(`/sessions/${session.value.id}`, { params: { user_id: user.id } });
      if (data.session.status === 'finished') {
        const id = session.value.id;
        session.value = null; draftDirty.value = false; stopCam();
        await router.push({ path: '/report', query: { session_id: id } });
        return;
      }
    } catch { /* retain the original error and local data */ }
    err.value = errorMessage(e, '结束训练失败，数据保留在当前页面。请重试结束，不要重新开始训练。');

  } finally {

    busy.value = false;

  }

}



onMounted(() => {
  clockTimer = setInterval(syncClock, 250);
  window.addEventListener('beforeunload', beforeUnload);
  window.addEventListener('online', retrySave);
  document.addEventListener('visibilitychange', onVisibility);
  autosaveTimer = setInterval(() => {
    if (session.value && draftDirty.value && !busy.value && !saving.value && !draftConflict.value) retrySave();
  }, 10000);
});
onBeforeRouteLeave(() => {
  if (session.value && (draftDirty.value || saving.value)) {
    return window.confirm('还有训练数据没有保存。离开会丢失这些数据，确定离开吗？');
  }
});
onBeforeUnmount(() => {
  screenAwake.dispose();
  cancelVideoProcessing();
  clearInterval(autosaveTimer);
  clearInterval(clockTimer);
  window.removeEventListener('beforeunload', beforeUnload);
  window.removeEventListener('online', retrySave);
  document.removeEventListener('visibilitychange', onVisibility);
  stopPosePlayback();
  stopCam();
  if (localObjectUrl) {
    URL.revokeObjectURL(localObjectUrl);
    localObjectUrl = null;
  }
});

</script>


