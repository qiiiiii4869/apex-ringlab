import {validRing} from "./geometry.mjs";

export const SESSION_KEY = "ringlab-current-match-v1";

export function savedPrefix(rings) {
  const prefix = [];
  for (const ring of rings.slice(0, 3)) {
    if (!validRing(ring)) break;
    prefix.push({stage:prefix.length+1,x:Number(ring.x),y:Number(ring.y),r:Number(ring.r)});
  }
  return prefix;
}

export function mergeRings(existing, incoming) {
  if (!incoming.length) throw new Error("请确认至少一个识别圈的圈次。");
  const merged = existing.map(ring=>({...ring}));
  const stages = new Set(merged.map(ring=>ring.stage));
  for (const ring of incoming) {
    if (!Number.isInteger(ring.stage) || ring.stage<1 || ring.stage>3 || !validRing(ring)) throw new Error("圈次或圈位无效。");
    if (stages.has(ring.stage)) throw new Error(`第 ${ring.stage} 圈已保存或重复选择，请只补充后续圈；另一把游戏请先开始新对局。`);
    stages.add(ring.stage);
    merged.push({stage:ring.stage,x:Math.round(Number(ring.x)),y:Math.round(Number(ring.y)),r:Math.round(Number(ring.r))});
  }
  merged.sort((a,b)=>a.stage-b.stage);
  for (let i=0;i<merged.length;i++) {
    if (merged[i].stage!==i+1) throw new Error("请按顺序补齐圈次：已有首圈时可直接添加第 2 圈，不能跳过第 2 圈添加第 3 圈。");
    if (i) {
      const prev=merged[i-1], ring=merged[i];
      if (ring.r>=prev.r || Math.hypot(ring.x-prev.x,ring.y-prev.y)+ring.r>prev.r+50) throw new Error("新圈没有包含在本局上一圈内，请核对圈次、识别位置，或开始新对局。");
    }
  }
  return merged;
}

export function restoreSession(value) {
  if (!value) return null;
  try {
    const saved=JSON.parse(value);
    if (saved.version!==1 || !Number.isInteger(saved.count) || saved.count<1 || saved.count>3
        || !Array.isArray(saved.rings) || saved.rings.length!==3) return null;
    const rings=saved.rings.map(ring=>{
      if (!ring || typeof ring!=="object") throw new Error("Invalid session");
      const copy={};
      for (const key of ["x","y","r"]) {
        if (ring[key]===undefined || ring[key]==="") continue;
        if (typeof ring[key]!=="number" && typeof ring[key]!=="string") continue;
        if (!Number.isFinite(Number(ring[key])) || Number(ring[key])<0 || Number(ring[key])>16384) continue;
        copy[key]=ring[key];
      }
      return copy;
    });
    return {rings,count:saved.count};
  } catch { return null; }
}
