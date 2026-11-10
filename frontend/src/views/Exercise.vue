<template>

  <div class="card">

    <h2>运动中监测</h2>
    <p v-if="session" class="muted">训练 #{{ session.id }} 已保存。刷新或离开后，可从训练历史继续。</p>
    <p v-if="savedPayload" class="ok">已恢复原训练及保存的姿态数据，可直接结束生成报告。视频预览需重新选择文件；摄像头需重新打开。</p>
    <router-link to="/history">查看训练历史 / 找回未完成训练</router-link>

    <p class="muted">

      支持<strong>离线视频</strong>（默认服务端 <strong>RTMPose</strong> COCO-17）或实时摄像头（MediaPipe）；结束后上传姿态序列。

    </p>

    <div class="row">

      <label class="tag gray">输入</label>

      <select v-model="inputMode" :disabled="!!session || busy">

        <option value="video">离线视频（推荐验证）</option>

        <option value="camera">摄像头</option>

      </select>

      <select v-model="exerciseId" :disabled="!!session || busy">

        <option v-for="e in exercises" :key="e.id" :value="e.id">{{ e.name }}</option>

      </select>

    </div>

    <div class="row" v-if="inputMode === 'video'">

      <label class="tag gray">演示样本</label>

      <select v-model="demoPickId" :disabled="busy || !!session" @change="onDemoPicked">

        <option value="">（选手动选文件或下方样本）</option>

        <option v-for="d in demoVideosFiltered" :key="d.id" :value="d.id">{{ d.label }}</option>

      </select>

      <button
        @click="loadRecommendedDemo"
        :disabled="busy || !!session || !recommendedDemo"
      >
        一键推荐深蹲
      </button>

    </div>

    <div class="row" v-if="inputMode === 'video'">

      <input

        type="file"

        accept="video/*"

        :disabled="busy"

        @change="onVideoPicked"

      />

      <span class="muted" v-if="videoLabel">{{ videoLabel }} · {{ mpFrameCount }} 姿态帧</span>

      <button
        class="secondary"
        @click="reprocessVideo"
        :disabled="(!videoFile && !demoRelPath) || busy || !!session"
      >

        重新解析视频

      </button>

    </div>

    <div class="row" v-else>

      <button @click="startCam" :disabled="camOn || busy">打开摄像头</button>

      <button class="secondary" @click="stopCam" :disabled="!camOn">关闭摄像头</button>

    </div>

    <div class="row">

      <button @click="start" :disabled="!!session || busy || !canStart">开始会话</button>

      <button class="secondary" @click="finish" :disabled="!session || busy">结束并生成报告</button>
      <button class="secondary" v-if="session" @click="cancelSession" :disabled="busy">取消本次训练</button>

    </div>

    <p v-if="hint" class="ok">{{ hint }}</p>

    <p v-if="err" class="err">{{ err }}</p>

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

          {{ inputMode === "video" ? "请选择演示样本或本地视频；解析后可直接播放，骨架会跟着走。" : "尚未开启摄像头。" }}

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

        <p class="muted" v-if="inputMode === 'video'">

          离线 {{ offlinePoseLabel }}，约 6Hz 抽帧；finish 提交 COCO-17 pose_summary。

        </p>

        <ol class="muted" style="padding-left:18px">

          <li v-if="inputMode === 'video'">一键推荐 / 选视频 → 等待解析 → 播放看骨架</li>

          <li v-else>打开摄像头，全身入画</li>

          <li>开始会话 → 结束 → 查看 CoT 报告</li>

        </ol>

      </div>

    </div>

  </div>

</template>



<script setup>

import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { useRoute, useRouter } from "vue-router";

import api, { errorMessage, getUser } from "../api/client";

import { createPoseCamera } from "../composables/usePoseCamera";

import { processVideoFile } from "../composables/usePoseVideoFile";

import { processVideoServer } from "../composables/usePoseVideoServer";

import { isOfflineRtmpose } from "../config/poseModel.js";

import {
  anglesFromCocoKeypoints,
  buildPoseSummary,
  buildPoseSummaryFromServer,
  drawCoco17Skeleton,
  hintFromAngles,
  mp33FrameToCoco17Keypoints,
} from "../utils/poseFormat";



const user = getUser();

const router = useRouter();
const route = useRoute();
const savedPayload = ref(null);

const exercises = ref([]);

const exerciseId = ref("squat");

const session = ref(null);

const prescriptionId = ref(0);

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
  const pin = DEMO_PIN[0];
  return demoVideos.value.find((d) => d.rel_path === pin) || demoVideosFiltered.value[0] || null;
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
  const list = matched.length ? [...matched] : [...all];
  list.sort((a, b) => demoRank(a) - demoRank(b) || String(a.label).localeCompare(String(b.label)));
  return list.map((d) => {
    const rel = d.rel_path || "";
    if (DEMO_PIN.includes(rel) && !String(d.label).includes("推荐")) {
      return { ...d, label: `★推荐 ${d.label}` };
    }
    return d;
  });
});

const camOn = ref(false);

const previewOn = ref(false);

const hint = ref("");

const err = ref("");

const poseHint = ref("");

const busy = ref(true);

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

async function prepareVideoSrc(src) {
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
  v.src = src;
  await new Promise((resolve, reject) => {
    const onMeta = () => {
      v.removeEventListener("loadedmetadata", onMeta);
      resolve();
    };
    v.addEventListener("loadedmetadata", onMeta);
    v.onerror = () => reject(new Error("视频加载失败"));
  });
  v.currentTime = 0;
  previewOn.value = true;
  await new Promise((resolve) => {
    const done = () => {
      v.removeEventListener("seeked", done);
      resolve();
    };
    v.addEventListener("seeked", done);
    setTimeout(done, 300);
  });
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

  if (inputMode.value === "video") {
    return (
      mpFrames.value.length > 0 ||
      (serverPoseResult.value?.coco17_frames?.length ?? 0) > 0
    );
  }

  return camOn.value;

});



onMounted(async () => {
  try {

  const { data } = await api.get("/prescriptions/templates");

  const all = [...(data.fitness?.exercises || []), ...(data.medical?.exercises || [])];

  exercises.value = all;

  exerciseId.value = all[0]?.id || "squat";

  try {

    const cur = await api.get(`/prescriptions/current?user_id=${user.id}`);

    prescriptionId.value = cur.data.id;

    if (cur.data.exercises?.length) {

      exercises.value = cur.data.exercises;

      exerciseId.value = cur.data.exercises[0].id;

    }

  } catch {}

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

  await restoreSession();
  } catch (e) { err.value = errorMessage(e, "训练页面读取失败，请刷新重试"); }
  finally { busy.value = false; }
});

async function restoreSession() {
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
    session.value = row;
    exerciseId.value = row.exercise_id;
    if (!exercises.value.some(e => e.id === row.exercise_id)) exercises.value.push({ id: row.exercise_id, name: row.exercise_name });
    prescriptionId.value = row.prescription_id;
    inputMode.value = row.pose_summary?.source === "camera_live_only" ? "camera" : "video";
    savedPayload.value = { video_path: row.video_path || "", pose_summary: row.pose_summary || {} };
    hint.value = "已恢复未完成训练；保存的数据将用于生成报告。";
    localStorage.setItem("ah_last_session", String(row.id));
    await router.replace({ path: "/exercise", query: { session_id: row.id } });
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

async function onDemoPicked() {

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

  const file = ev.target.files?.[0];

  ev.target.value = "";

  if (!file) return;

  demoPickId.value = "";

  demoRelPath.value = "";

  videoFile.value = file;

  await runVideoProcess();

}



async function reprocessVideo() {

  if (!videoFile.value && !demoRelPath.value) return;

  await runVideoProcess();

}



async function runVideoProcess() {

  err.value = "";

  busy.value = true;

  mpFrames.value = [];

  serverPoseResult.value = null;

  overlayCocoFrames.value = [];

  stopPosePlayback();

  previewOn.value = false;

  try {

    if (isOfflineRtmpose()) {

      const pathRel = demoRelPath.value ? `data/demo_videos/${demoRelPath.value}` : null;

      const result = await processVideoServer({

        videoPathRel: pathRel,

        file: pathRel ? null : videoFile.value,

        sampleHz: 6,

        exerciseId: exerciseId.value,

        onProgress: (p) => {

          hint.value = p.message || `RTMPose ${Math.round(p.progress * 100)}%`;

        },

      });

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
        await prepareVideoSrc(`/api/demo-videos/file?rel=${encodeURIComponent(demoRelPath.value)}`);
      } else if (videoFile.value) {
        localObjectUrl = URL.createObjectURL(videoFile.value);
        await prepareVideoSrc(localObjectUrl);
      }
      await playWithPose();
      await persistDraft();

      return;

    }

    const result = await processVideoFile({

      video: videoEl.value,

      canvas: canvasEl.value,

      file: videoFile.value,

      sampleHz: 6,

      onProgress: (p) => {

        hint.value = p.message || `解析中 ${Math.round(p.progress * 100)}%`;

      },

    });

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
    await prepareVideoSrc(blobUrl);
    await playWithPose();
    await persistDraft();

  } catch (e) {

    const detail = e?.response?.data?.detail || e?.message || "视频解析失败";
    err.value =
      typeof detail === "string" && /姿态服务|8101|ECONNREFUSED|unavailable/i.test(detail)
        ? `${detail}（请确认已启动：cd ai_services/pose && python main.py）`
        : detail;

  } finally {

    busy.value = false;

  }

}



async function startCam() {

  err.value = "";

  try {

    cameraCtl = createPoseCamera({

      video: videoEl.value,

      canvas: canvasEl.value,

      onHint: (t) => {

        poseHint.value = t;

      },

    });

    await cameraCtl.start();

    camOn.value = true;

    previewOn.value = true;

    hint.value = "摄像头已打开";

  } catch (e) {

    err.value = "无法打开摄像头：" + (e?.message || "请检查权限");

  }

}



function stopCam() {

  cameraCtl?.stop();

  cameraCtl = null;

  camOn.value = false;

  previewOn.value = false;

  poseHint.value = "";

}



async function start() {

  err.value = "";

  busy.value = true;

  try {

    const name = exercises.value.find((e) => e.id === exerciseId.value)?.name || exerciseId.value;

    const { data } = await api.post("/sessions/start", {

      user_id: user.id,

      exercise_id: exerciseId.value,

      exercise_name: name,

      prescription_id: prescriptionId.value,
      ...buildSubmission(),

    });

    session.value = data.session;
    await router.replace({ path: "/exercise", query: { session_id: data.session.id } });

    hint.value =

      inputMode.value === "video"

        ? "会话已开始（离线序列已就绪），可直接结束生成报告"

        : "会话已开始，请完成若干次动作后结束会话";

    localStorage.setItem("ah_last_session", String(data.session.id));

    if (inputMode.value === "camera" && !camOn.value) await startCam();

  } catch (e) {

    err.value = e?.response?.data?.detail || "开始会话失败";

  } finally {

    busy.value = false;

  }

}



function buildSubmission() {
  if (savedPayload.value && !serverPoseResult.value?.coco17_frames?.length && !mpFrames.value.length && !camOn.value) return savedPayload.value;
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
        videoPath = `uploads/offline/${videoMeta.value.fileName}`;
      }
    }



  return { video_path: videoPath, pose_summary: poseSummary };
}

async function persistDraft() {
  if (!session.value) return;
  const submission = buildSubmission();
  await api.put(`/sessions/${session.value.id}/draft`, submission, { params: { user_id: user.id } });
  savedPayload.value = submission;
}

async function finish() {

  err.value = "";

  busy.value = true;

  stopPosePlayback();

  try {

    const submission = buildSubmission();

    const { data } = await api.post(`/sessions/${session.value.id}/finish`, {

      ...submission,

    });

    localStorage.setItem("ah_last_session", String(data.session.id));

    session.value = null;

    stopCam();

    hint.value = `报告已生成（姿态帧 ${submission.pose_summary.sequences?.coco17?.frames?.length ?? 0}）…`;

    router.push({ path: "/report", query: { session_id: data.session.id } });

  } catch (e) {

    err.value = e?.response?.data?.detail || "结束会话失败";

  } finally {

    busy.value = false;

  }

}



onBeforeUnmount(() => {
  stopPosePlayback();
  stopCam();
  if (localObjectUrl) {
    URL.revokeObjectURL(localObjectUrl);
    localObjectUrl = null;
  }
});

</script>


