export const reviewStatus = { pending: '待审核', approved: '已通过', rejected: '已退回', cancelled: '已撤回', superseded: '新版生成，已失效' };
export const roleLabel = { physician: '医师', prescription_specialist: '处方师' };
export function formatTime(value) {
  if (!value) return '—';
  // 后端保存 UTC 无时区时间，显式按 UTC 解析，浏览器转换为本地时间。
  return new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`).toLocaleString('zh-CN');
}
