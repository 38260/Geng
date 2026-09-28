/**
 * 精选推荐：每个阶段挑一个最能打的，保证首屏能看到不同状态的梗，
 * 而不是五个一模一样的"正在爆"。规则与 Web 端 Home.pickFeatured 一致。
 */
import type { LifecycleStage, MemeCard } from "@/types/api";

const FEATURED_STAGES: LifecycleStage[] = ["explosive", "rising", "plateau", "sprouting"];

export function pickFeatured(all: MemeCard[], size = 4): MemeCard[] {
  const picked: MemeCard[] = [];
  for (const stage of FEATURED_STAGES) {
    const best = all
      .filter((item) => item.stage === stage)
      .sort((a, b) => b.hotness - a.hotness)
      .find((item) => !picked.some((existing) => existing.id === item.id));
    if (best) picked.push(best);
  }
  for (const item of all) {
    if (picked.length >= size) break;
    if (!picked.some((existing) => existing.id === item.id)) picked.push(item);
  }
  return picked.slice(0, size);
}
