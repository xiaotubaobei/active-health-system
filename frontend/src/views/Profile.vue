<template>
  <div class="card profile-card">
    <header class="profile-header">
      <h1>个人档案</h1>
      <p>填写本人真实资料。当前方案按年龄组和健康标签匹配模板，尚未根据身高、体重和反馈制定个人运动量。</p>
      <p class="profile-note">个人档案用于训练计划参考，不代替医生诊断。</p>
    </header>

    <form class="profile-form" novalidate :aria-busy="busy" @submit.prevent="save">
      <fieldset class="form-fields" :disabled="busy">
        <div class="form-field">
          <label for="age-group">年龄段 <span class="required-mark">必填</span></label>
          <select
            id="age-group"
            v-model="form.age_group"
            required
            :aria-invalid="Boolean(fieldErrors.age_group)"
            :aria-describedby="fieldErrors.age_group ? 'age-error' : 'age-help'"
            @change="fieldChanged('age_group')"
          >
            <option value="" disabled>请选择年龄段</option>
            <option value="youth">青少年</option>
            <option value="middle_age">中年</option>
            <option value="elder">老年</option>
          </select>
          <p id="age-help" class="field-help">请选择与你当前情况相符的年龄段。</p>
          <p v-if="fieldErrors.age_group" id="age-error" class="field-error" role="alert">
            {{ fieldErrors.age_group }}
          </p>
        </div>

        <div class="form-field">
          <label for="height-cm">身高 <span class="required-mark">必填</span></label>
          <div class="number-control">
            <input
              id="height-cm"
              v-model.number="form.height_cm"
              type="number"
              min="0"
              max="300"
              step="any"
              inputmode="decimal"
              required
              :aria-invalid="Boolean(fieldErrors.height_cm)"
              :aria-describedby="fieldErrors.height_cm ? 'height-error' : 'height-help'"
              @input="fieldChanged('height_cm')"
              @blur="validateHeight"
            />
            <span class="unit">厘米（cm）</span>
          </div>
          <p id="height-help" class="field-help">可填写小数，范围为大于 0 且不超过 300 厘米。</p>
          <p v-if="fieldErrors.height_cm" id="height-error" class="field-error" role="alert">
            {{ fieldErrors.height_cm }}
          </p>
        </div>

        <div class="form-field">
          <label for="weight-kg">体重 <span class="required-mark">必填</span></label>
          <div class="number-control">
            <input
              id="weight-kg"
              v-model.number="form.weight_kg"
              type="number"
              min="0"
              max="700"
              step="any"
              inputmode="decimal"
              required
              :aria-invalid="Boolean(fieldErrors.weight_kg)"
              :aria-describedby="fieldErrors.weight_kg ? 'weight-error' : 'weight-help'"
              @input="fieldChanged('weight_kg')"
              @blur="validateWeight"
            />
            <span class="unit">千克（kg）</span>
          </div>
          <p id="weight-help" class="field-help">可填写小数，范围为大于 0 且不超过 700 千克。</p>
          <p v-if="fieldErrors.weight_kg" id="weight-error" class="field-error" role="alert">
            {{ fieldErrors.weight_kg }}
          </p>
        </div>

        <fieldset class="form-field goal-field" :aria-describedby="fieldErrors.goal ? 'goal-error' : 'goal-help'">
          <legend>训练目标 <span class="required-mark">必填</span></legend>
          <div class="choice-grid">
            <label v-for="option in GOAL_OPTIONS" :key="option.value" class="choice-card">
              <input
                v-model="form.goal"
                type="radio"
                name="training-goal"
                :value="option.value"
                required
                @change="fieldChanged('goal')"
              />
              <span><strong>{{ option.label }}</strong><small>{{ option.description }}</small></span>
            </label>
          </div>
          <p id="goal-help" class="field-help">如有疾病或身体不适，请先咨询医生。</p>
          <p v-if="fieldErrors.goal" id="goal-error" class="field-error" role="alert">
            {{ fieldErrors.goal }}
          </p>
        </fieldset>

        <fieldset class="health-field">
          <legend>健康情况</legend>
          <p class="field-help">可多选。这里的信息仅用于训练计划参考。</p>
          <div class="health-options">
            <label class="health-option none-option">
              <input
                v-model="noHealthConditions"
                type="checkbox"
                @change="selectNoHealthConditions"
              />
              <span>暂无已记录健康情况</span>
            </label>
            <label v-for="option in HEALTH_OPTIONS" :key="option.value" class="health-option">
              <input
                v-model="selectedHealthTags"
                type="checkbox"
                :value="option.value"
                @change="healthSelectionChanged"
              />
              <span>{{ option.label }}</span>
            </label>
          </div>
          <div v-if="unknownHealthTags.length && !noHealthConditions" class="unknown-health" role="status">
            <strong>其他已记录健康情况</strong>
            <p>有 {{ unknownHealthTags.length }} 项历史记录暂未提供中文名称，保存时会继续保留。</p>
          </div>
        </fieldset>
      </fieldset>

      <p v-if="err" class="save-error" role="alert" aria-live="assertive">{{ err }}</p>
      <p v-if="msg" class="save-success" role="status" aria-live="polite">{{ msg }}</p>

      <button class="save-button" type="submit" :disabled="busy">
        {{ busy ? "正在保存…" : "保存档案" }}
      </button>
    </form>
  </div>
  <AccountSecurity />
</template>

<script setup>
import { nextTick, reactive, ref } from "vue";
import api, { getUser, setUser } from "../api/client";
import AccountSecurity from "../components/AccountSecurity.vue";

const AGE_VALUES = ["youth", "middle_age", "elder"];
const GOAL_OPTIONS = [
  { value: "fitness", label: "提升体能", description: "以日常锻炼和体能提升为方向" },
  { value: "medical", label: "健康改善", description: "结合健康情况提供更谨慎的训练参考" },
];
const GOAL_VALUES = GOAL_OPTIONS.map((option) => option.value);
const HEALTH_OPTIONS = [
  { value: "cardio_risk", label: "心血管风险" },
  { value: "joint", label: "关节问题" },
  { value: "hypertension", label: "高血压" },
  { value: "diabetes", label: "糖尿病" },
];
const KNOWN_HEALTH_VALUES = new Set(HEALTH_OPTIONS.map((option) => option.value));
const HEIGHT_MAX = 300;
const WEIGHT_MAX = 700;

const user = getUser();
const initialTags = Array.isArray(user?.chronic_tags)
  ? user.chronic_tags.filter((tag) => typeof tag === "string" && tag.length > 0)
  : [];
const form = reactive({
  age_group: user?.age_group ?? "",
  height_cm: user?.height_cm ?? "",
  weight_kg: user?.weight_kg ?? "",
  goal: user?.goal ?? "",
});
const selectedHealthTags = ref(initialTags.filter((tag) => KNOWN_HEALTH_VALUES.has(tag)));
const unknownHealthTags = ref(initialTags.filter((tag) => !KNOWN_HEALTH_VALUES.has(tag)));
const noHealthConditions = ref(initialTags.length === 0);
const fieldErrors = reactive({ age_group: "", height_cm: "", weight_kg: "", goal: "" });
const msg = ref("");
const err = ref("");
const busy = ref(false);

function clearSavedState() {
  msg.value = "";
}

function fieldChanged(field) {
  clearSavedState();
  fieldErrors[field] = "";
  err.value = "";
}

function selectNoHealthConditions() {
  clearSavedState();
  err.value = "";
  if (noHealthConditions.value) selectedHealthTags.value = [];
}

function healthSelectionChanged() {
  clearSavedState();
  err.value = "";
  if (selectedHealthTags.value.length > 0) noHealthConditions.value = false;
}

function numberError(value, maximum, fieldName, unitName) {
  if (value === "" || value === null || value === undefined) return `请填写${fieldName}。`;
  const number = Number(value);
  if (!Number.isFinite(number)) return `${fieldName}必须填写为数字。`;
  if (number <= 0 || number > maximum) {
    return `${fieldName}应大于 0 且不超过 ${maximum} ${unitName}。`;
  }
  return "";
}

function validateHeight() {
  fieldErrors.height_cm = numberError(form.height_cm, HEIGHT_MAX, "身高", "厘米");
  return !fieldErrors.height_cm;
}

function validateWeight() {
  fieldErrors.weight_kg = numberError(form.weight_kg, WEIGHT_MAX, "体重", "千克");
  return !fieldErrors.weight_kg;
}

function validateForm() {
  fieldErrors.age_group = AGE_VALUES.includes(form.age_group) ? "" : "请选择年龄段。";
  fieldErrors.goal = GOAL_VALUES.includes(form.goal) ? "" : "请选择训练目标。";
  const heightValid = validateHeight();
  const weightValid = validateWeight();
  const valid = !fieldErrors.age_group && !fieldErrors.goal && heightValid && weightValid;
  if (!valid) {
    const missing = [form.age_group, form.height_cm, form.weight_kg, form.goal]
      .some((value) => value === "" || value === null || value === undefined);
    err.value = missing ? "请完成必填信息。" : "请检查标出的内容后再保存。";
  }
  return valid;
}

function tagsForSave() {
  if (noHealthConditions.value) return [];
  return [...selectedHealthTags.value, ...unknownHealthTags.value];
}

function saveErrorMessage(error) {
  const status = error?.response?.status;
  if (error?.code === "ECONNABORTED" || /timeout/i.test(error?.message || "") || [408, 504].includes(status)) {
    return "保存时间过长，请检查连接后重试。";
  }
  if (status === 401) return "登录状态已过期，请重新登录。";
  if (!error?.response || status >= 500) return "暂时无法保存，请稍后重试。";
  return "档案保存失败，请稍后重试。";
}

function applySavedProfile(data) {
  form.age_group = data.age_group;
  form.height_cm = data.height_cm;
  form.weight_kg = data.weight_kg;
  form.goal = data.goal;
  const returnedTags = Array.isArray(data.chronic_tags) ? data.chronic_tags : [];
  selectedHealthTags.value = returnedTags.filter((tag) => KNOWN_HEALTH_VALUES.has(tag));
  unknownHealthTags.value = returnedTags.filter((tag) => !KNOWN_HEALTH_VALUES.has(tag));
  noHealthConditions.value = returnedTags.length === 0;
}

async function save() {
  if (busy.value) return;
  msg.value = "";
  err.value = "";
  if (!validateForm()) {
    await nextTick();
    document.querySelector('[aria-invalid="true"]')?.focus();
    return;
  }

  busy.value = true;
  try {
    const { data } = await api.put(`/users/me?user_id=${user.id}`, {
      age_group: form.age_group,
      height_cm: Number(form.height_cm),
      weight_kg: Number(form.weight_kg),
      goal: form.goal,
      chronic_tags: tagsForSave(),
    });
    setUser({ ...getUser(), ...data });
    applySavedProfile(data);
    await nextTick();
    msg.value = "个人档案已保存；已有训练计划不会自动重算。";
  } catch (error) {
    err.value = saveErrorMessage(error);
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.profile-card {
  box-sizing: border-box;
  width: 100%;
  max-width: 820px;
}
.profile-header { padding-bottom: 22px; border-bottom: 1px solid var(--line); }
.profile-header h1 { margin: 0; font-size: 1.9rem; }
.profile-header p { margin: 10px 0 0; color: var(--muted); line-height: 1.65; }
.profile-header .profile-note { margin-top: 4px; font-size: 0.9rem; }
.profile-form { margin-top: 24px; }
.form-fields,
.goal-field,
.health-field { min-width: 0; margin: 0; padding: 0; border: 0; }
.form-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 24px 28px; }
.form-field > label,
.form-field > legend,
.health-field > legend { display: block; margin-bottom: 8px; font-weight: 700; }
.required-mark {
  margin-left: 6px;
  color: var(--bad);
  font-size: 0.78rem;
  font-weight: 600;
}
.form-field select,
.number-control { box-sizing: border-box; width: 100%; }
.form-field select { min-height: 44px; color: inherit; background: rgba(255, 255, 255, 0.04); }
.number-control { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: stretch; }
.number-control input {
  box-sizing: border-box;
  width: 100%;
  min-height: 44px;
  border-radius: 6px 0 0 6px;
  color: inherit;
  background: rgba(255, 255, 255, 0.04);
}
.unit {
  display: flex;
  align-items: center;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-left: 0;
  border-radius: 0 6px 6px 0;
  color: var(--muted);
  white-space: nowrap;
}
.field-help,
.field-error { margin: 7px 0 0; font-size: 0.88rem; line-height: 1.55; }
.field-help { color: var(--muted); }
.field-error { color: var(--bad); overflow-wrap: anywhere; }
.goal-field { grid-column: 1 / -1; }
.choice-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.choice-card {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 9px;
  cursor: pointer;
}
.choice-card:has(input:checked) { border-color: var(--accent); background: rgba(61, 165, 112, 0.1); }
.choice-card input { margin-top: 4px; }
.choice-card strong,
.choice-card small { display: block; }
.choice-card small { margin-top: 4px; color: var(--muted); line-height: 1.45; }
.health-field {
  grid-column: 1 / -1;
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.025);
}
.health-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 18px; margin-top: 14px; }
.health-option { display: flex; gap: 9px; align-items: center; min-height: 32px; }
.none-option { grid-column: 1 / -1; padding-bottom: 9px; border-bottom: 1px solid var(--line); }
.unknown-health {
  margin-top: 14px;
  padding: 11px 13px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--muted);
}
.unknown-health strong { color: inherit; }
.unknown-health p { margin: 5px 0 0; line-height: 1.55; }
.save-error,
.save-success {
  margin: 20px 0 0;
  padding: 11px 13px;
  border-radius: 8px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.save-error { border: 1px solid var(--bad); color: var(--bad); background: rgba(214, 83, 83, 0.08); }
.save-success { border: 1px solid var(--accent); color: var(--accent); background: rgba(61, 165, 112, 0.08); }
.save-button { min-width: 150px; min-height: 44px; margin-top: 22px; font-weight: 700; }
.form-fields:disabled { opacity: 0.72; }
@media (max-width: 700px) {
  .profile-header { padding-bottom: 18px; }
  .profile-header h1 { font-size: 1.65rem; }
  .profile-form { margin-top: 20px; }
  .form-fields,
  .choice-grid,
  .health-options { grid-template-columns: minmax(0, 1fr); }
  .form-fields { gap: 20px; }
  .goal-field,
  .health-field,
  .none-option { grid-column: auto; }
  .health-field { padding: 14px; }
  .save-button { width: 100%; }
}
</style>
