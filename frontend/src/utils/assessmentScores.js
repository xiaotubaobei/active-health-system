// A catalog refresh must not silently turn missing or malformed items into an empty assessment.
export function validScale(scale) {
  if (!scale || typeof scale.id !== "string" || !Array.isArray(scale.items) || !scale.items.length) return false;
  const keys = new Set();
  return scale.items.every(item => {
    if (!item || typeof item.key !== "string" || !item.key.trim() || keys.has(item.key)) return false;
    keys.add(item.key);
    const limit = item.max_score ?? 100;
    return typeof limit === "number" && Number.isFinite(limit) && limit > 0
      && typeof item.weight === "number" && Number.isFinite(item.weight) && item.weight > 0;
  });
}

export const maxScore = item => item.max_score ?? 100;

export function scoreError(item, value) {
  if (value === undefined || value === null || value === "" || (typeof value === "string" && !value.trim())) {
    return `请填写「${item.name}」的体测换算分，不能留空。`;
  }
  if (!["number", "string"].includes(typeof value) || !Number.isFinite(Number(value))) {
    return `「${item.name}」请输入有效数字，可填小数。`;
  }
  if (Number(value) < 0 || Number(value) > maxScore(item)) {
    return `「${item.name}」须在 0–${maxScore(item)} 分之间。`;
  }
  return "";
}
