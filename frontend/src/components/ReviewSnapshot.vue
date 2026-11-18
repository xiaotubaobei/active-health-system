<template>
  <div class="review-snapshot">
    <h4>送审快照 · v{{ prescription.version }}</h4>
    <p>{{ prescription.library === 'medical' ? '医疗模板' : '健身模板' }} · {{ prescription.mode }}</p>
    <p>强度：{{ prescription.intensity }}；频次：{{ prescription.frequency }}；时长：{{ prescription.duration }}</p>
    <p>周期：{{ prescription.cycle }}；运动量：{{ prescription.volume || '未填写' }}；进阶：{{ prescription.progression || '未填写' }}</p>
    <ul>
      <li v-for="e in prescription.exercises || []" :key="e.id">{{ e.name }}：{{ e.sets }}组 × {{ e.reps }}{{ e.unit || '次' }}</li>
    </ul>
    <p v-for="(value, key) in prescription.health_plan || {}" :key="key">{{ healthLabels[key] || key }}：{{ value || '未填写' }}</p>
    <p class="muted">{{ prescription.notes }}</p>
    <h4>用户授权提供的档案与最近测评</h4>
    <p>年龄组：{{ ageLabels[profile.age_group] || profile.age_group }}；身高 {{ profile.height_cm }} cm；体重 {{ profile.weight_kg }} kg</p>
    <p>目标：{{ profile.goal === 'medical' ? '医疗健康' : '健身' }}；慢病标签：{{ profile.chronic_tags?.join('、') || '未填写' }}</p>
    <template v-if="profile.assessment">
      <p>最近测评：{{ profile.assessment.scale_id }}；总分 {{ profile.assessment.total_score }}；等级 {{ profile.assessment.level }}</p>
      <p>测评时间：{{ formatTime(profile.assessment.created_at) }}</p>
      <ul><li v-for="(score, key) in profile.assessment.scores" :key="key">{{ key }}：{{ score }}</li></ul>
    </template>
    <p v-else class="muted">尚无测评记录，请审核人按实际情况决定是否退回补充。</p>
  </div>
</template>

<script setup>
import { formatTime } from '../utils/reviewFormat';
defineProps({ prescription: { type: Object, required: true }, profile: { type: Object, required: true } });
const healthLabels = { diet: '饮食', sleep: '睡眠', medication: '用药', psychology: '心理' };
const ageLabels = { youth: '青少年', middle_age: '中年', elder: '老年' };
</script>
