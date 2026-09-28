import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import { RefreshPanel } from "@/components/RefreshPanel";
import { SearchIcon } from "@/components/icons";
import { SectionHeader } from "@/components/Sections";
import { StickerThumb } from "@/components/StickerThumb";
import { EmptyState, ErrorState, LoadingCards } from "@/components/States";
import { useAsync } from "@/hooks/useAsync";
import type { ManageListItem, MemeMetaPatch, ManageView, Thumbnail } from "@/types/api";
import { compact } from "@/utils/format";

const STATUS_TABS = [
  { key: "all", label: "全部" },
  { key: "certified", label: "已入池" },
  { key: "candidate", label: "未入池" },
];

const MAX_DESC = 600;
const MAX_TERMS = 12;
const MAX_TERM_LEN = 20;

/**
 * 认证标签的配色：双 UP 是绿，单 UP 是蓝（入了池但不是最强证据），
 * 未认证才是金色告警——准入看并集，所以只有两位都没做过的才算"没进池"。
 */
function certChipClass(item: Pick<ManageListItem, "cert_label" | "admitted">): string {
  if (item.cert_label === "双 UP 认证") return "bg-go-soft text-go";
  if (item.admitted) return "bg-nav-soft text-nav";
  return "bg-gold/20 text-[#B2750A]";
}

/** 封面到底是谁给的，得让人一眼看出来，别把人工挑的当成视频自带。 */
function coverOrigin(view: ManageView): { label: string; cls: string } {
  if (view.cover_url) return { label: "人工维护", cls: "bg-brand-soft text-brand" };
  if (view.auto_cover) return { label: "B站真实封面", cls: "bg-go-soft text-go" };
  if (view.effective_cover) return { label: "演示素材图", cls: "bg-gold/20 text-[#B2750A]" };
  return { label: "表情贴纸", cls: "bg-dusk-soft text-dusk" };
}

const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((item, i) => item === b[i]);

/** 站内自发跑起来的梗（两位 UP 没做过的）也要能进库被度量。 */
function NewMemeForm({ onCreated }: { onCreated: (id: number) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [terms, setTerms] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return setError("先给梗起个名");
    setBusy(true);
    setError("");
    try {
      const extras = terms.split(/[,，、\s]+/).map((item) => item.trim()).filter(Boolean);
      const result = await api.createMeme({ name: trimmed, aliases: extras, keywords: extras });
      setName("");
      setTerms("");
      setOpen(false);
      onCreated(result.meme.id);
    } catch (exc) {
      setError((exc as Error).message || "新增失败");
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button type="button" className="btn-ghost mb-3 w-full rounded-full" onClick={() => setOpen(true)}>
        ＋ 新增梗（两位 UP 没做过的热梗）
      </button>
    );
  }

  return (
    <div className="card mb-3 space-y-2 p-3">
      <input
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="梗名，如：胆子真的肥嘟嘟的"
        maxLength={20}
        className="field h-10"
      />
      <input
        value={terms}
        onChange={(event) => setTerms(event.target.value)}
        placeholder="别名/关键词，逗号分隔（用于搜到相关视频）"
        className="field h-10"
      />
      <div className="flex items-center gap-2">
        <button type="button" className="btn-primary h-9 rounded-full text-[13px]" onClick={submit} disabled={busy}>
          {busy ? "加入中…" : "加入梗库"}
        </button>
        <button type="button" className="link-quiet" onClick={() => setOpen(false)}>
          取消
        </button>
      </div>
      {error ? <p className="text-[12px] text-brand">{error}</p> : null}
      <p className="text-[11px] leading-relaxed text-ink-faint">
        新加的梗默认是候选梗，不会直接上榜单；采集到数据后仍要过双 UP 认证才进正式梗库。
      </p>
    </div>
  );
}

function TermList({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const [text, setText] = useState("");
  const [warn, setWarn] = useState("");

  const add = () => {
    const term = text.trim();
    if (!term) return;
    if (term.length > MAX_TERM_LEN) {
      setWarn(`单个${label}不超过 ${MAX_TERM_LEN} 字`);
      return;
    }
    if (value.includes(term)) {
      setWarn(`「${term}」已经在了`);
      setText("");
      return;
    }
    if (value.length >= MAX_TERMS) {
      setWarn(`${label}最多 ${MAX_TERMS} 个`);
      return;
    }
    onChange([...value, term]);
    setText("");
    setWarn("");
  };

  return (
    <div>
      <div className="mb-2 flex items-baseline gap-2">
        <span className="text-[15px] font-bold">{label}</span>
        <span className="text-[12px] text-ink-faint">{hint}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {value.map((term) => (
          <span key={term} className="chip bg-rail text-ink-soft">
            {term}
            <button
              type="button"
              aria-label={`删除${label} ${term}`}
              onClick={() => onChange(value.filter((item) => item !== term))}
              className="ml-0.5 text-ink-faint hover:text-brand"
            >
              ×
            </button>
          </span>
        ))}
        {!value.length ? <span className="text-[13px] text-ink-faint">暂无</span> : null}
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <input
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setWarn("");
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              add();
            }
          }}
          placeholder={`输入${label}后回车添加`}
          className="field h-10 max-w-[240px] flex-1"
        />
        <button type="button" className="btn-ghost h-10 rounded-full" onClick={add}>
          添加
        </button>
        {warn ? <span className="text-[12px] text-brand">{warn}</span> : null}
      </div>
    </div>
  );
}

export default function Manage() {
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState({
    cover_url: "",
    description: "",
    aliases: [] as string[],
    keywords: [] as string[],
  });
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  const list = useAsync(() => api.manageMemes({ status, search }), [status, search]);
  const items = list.data?.items ?? [];

  // 默认选中列表第一条，进来就有可编辑对象，不留空面板
  useEffect(() => {
    if (!items.length) return;
    setSelected((current) =>
      current != null && items.some((item) => item.id === current) ? current : items[0].id,
    );
  }, [items]);

  const detail = useAsync<ManageView | null>(
    () => (selected ? api.manageMeme(selected) : Promise.resolve(null)),
    [selected],
  );
  const view = detail.data;

  useEffect(() => {
    if (!view) return;
    setDraft({
      cover_url: view.cover_url,
      description: view.description,
      aliases: [...view.aliases],
      keywords: [...view.keywords],
    });
    setFlash(null);
  }, [view?.id]);

  const patch = useMemo<MemeMetaPatch>(() => {
    if (!view) return {};
    const out: MemeMetaPatch = {};
    if (draft.cover_url !== view.cover_url) out.cover_url = draft.cover_url;
    if (draft.description !== view.description) out.description = draft.description;
    if (!sameList(draft.aliases, view.aliases)) out.aliases = draft.aliases;
    if (!sameList(draft.keywords, view.keywords)) out.keywords = draft.keywords;
    return out;
  }, [draft, view]);

  const dirty = Object.keys(patch).length > 0;

  const save = async () => {
    if (!view || !dirty) return;
    setBusy(true);
    setFlash(null);
    try {
      const result = await api.saveMemeMeta(view.id, patch);
      detail.setData(result.meme);
      list.reload();
      setFlash({ tone: "ok", text: `已保存：${result.changed.join("、")}` });
    } catch (error) {
      setFlash({ tone: "bad", text: (error as Error).message || "保存失败" });
    } finally {
      setBusy(false);
    }
  };

  const thumbOf = (image: string): Thumbnail => ({
    emoji: view ? (items.find((item) => item.id === view.id)?.thumbnail.emoji ?? "🎬") : "🎬",
    color: items.find((item) => item.id === view?.id)?.thumbnail.color ?? "#FFE9E4",
    image,
  });

  return (
    <div className="px-5 pb-12 pt-8 lg:px-[33px]">
      <SectionHeader emoji="🛠️" title="梗管理" />
      <p className="-mt-2 mb-6 text-[15px] text-ink-mute">
        人工只维护<span className="font-semibold text-ink">封面、介绍、别名、关键词</span>
        这四样；热度、生命周期与赶梗结论由算法算出，这里改不到。
      </p>

      <RefreshPanel onDone={() => list.reload()} />

      <div className="flex flex-col gap-6 xl:flex-row">
        {/* ---------------- 左：梗列表 ---------------- */}
        <aside className="w-full shrink-0 xl:w-[300px]">
          <NewMemeForm
            onCreated={(id) => {
              setSelected(id);
              list.reload();
            }}
          />
          <div className="relative mb-3">
            <SearchIcon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-mute" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜名称 / 别名 / 关键词"
              className="h-11 w-full rounded-full border border-line bg-surface pl-10 pr-3 text-[14px] outline-none focus:border-nav/40"
            />
          </div>
          <div className="mb-3 flex gap-2">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setStatus(tab.key)}
                className={[
                  "rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition",
                  status === tab.key ? "bg-nav-soft text-nav" : "bg-[#F6FAFE] text-ink-mute hover:text-ink",
                ].join(" ")}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {list.loading ? (
            <LoadingCards count={4} />
          ) : list.error ? (
            <ErrorState message={list.error} onRetry={list.reload} />
          ) : !items.length ? (
            <EmptyState title="没有匹配的梗" description="换个关键词或筛选试试。" />
          ) : (
            <ul className="max-h-[640px] space-y-1.5 overflow-y-auto pr-1">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(item.id)}
                    className={[
                      "flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition",
                      selected === item.id ? "bg-nav-soft" : "hover:bg-rail",
                    ].join(" ")}
                  >
                    <StickerThumb
                      thumbnail={item.thumbnail}
                      ratio="1/1"
                      emojiSize={15}
                      rounded="rounded-lg"
                      className="w-[38px] shrink-0"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[14px] font-bold">{item.name}</span>
                      <span className="block truncate text-[12px] text-ink-faint">
                        {item.hotness == null ? "不在榜单（未入池或还没采到数据）" : `热度 ${item.hotness}`}
                      </span>
                    </span>
                    {item.has_manual_cover ? (
                      <span className="chip shrink-0 bg-brand-soft px-1.5 py-0.5 text-[10px] text-brand">人工</span>
                    ) : null}
                    {item.admitted && item.verification_state === "unverified" ? (
                      <span
                        className="chip shrink-0 bg-gold/20 px-1.5 py-0.5 text-[10px] text-[#B2750A]"
                        title="认证位来自人工整理或演示数据，没有在 UP 主真实投稿里命中；真实模式下不进榜单"
                      >
                        未核验
                      </span>
                    ) : null}
                    <span
                      className={`chip shrink-0 px-1.5 py-0.5 text-[10px] ${certChipClass(item)}`}
                      title={
                        item.admitted
                          ? `已入池：证据来自 ${item.certified_by.join("、")}（认证窗口 ${list.data?.cert_window_days ?? 90} 天滚动）`
                          : "两位 UP 主都没介绍过，未通过发现层准入"
                      }
                    >
                      {item.cert_label}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {list.data ? (
            <p className="mt-3 text-[12px] text-ink-faint">
              共 {list.data.total} 个 · 入池 {list.data.in_pool_count} 个（双 UP{" "}
              {list.data.certified_count} 个）· 未入池 {list.data.out_of_pool_count} 个 · 人工封面{" "}
              {list.data.managed_count} 个
              <br />
              准入看并集：任一 UP 主在 {list.data.cert_window_days} 天内介绍过即入池
            </p>
          ) : null}
        </aside>

        {/* ---------------- 右：编辑表单 ---------------- */}
        <section className="min-w-0 flex-1">
          {detail.loading ? (
            <LoadingCards count={3} />
          ) : detail.error ? (
            <ErrorState message={detail.error} onRetry={detail.reload} />
          ) : !view ? (
            <EmptyState title="左边挑一个梗" description="封面、介绍、别名、关键词都在这里改。" />
          ) : (
            <div className="space-y-5">
              <div className="card p-5">
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-[22px] font-black">{view.name}</h2>
                  <span className={`chip ${coverOrigin(view).cls}`}>{coverOrigin(view).label}</span>
                  <span className="chip bg-rail text-ink-mute">
                    {view.data_source === "bilibili"
                      ? "B站真实数据"
                      : view.data_source === "pending"
                        ? "待采集"
                        : "演示数据"}
                  </span>
                  <span
                    className={`chip ${certChipClass(view)}`}
                    title={
                      view.admitted
                        ? `证据来自 ${view.certified_by.join("、")}`
                        : "两位 UP 主都没介绍过，未通过发现层准入"
                    }
                  >
                    {view.cert_label}
                  </span>
                  {view.admitted && view.verification_state === "unverified" ? (
                    <span
                      className="chip bg-gold/20 text-[#B2750A]"
                      title="认证位来自人工整理或演示数据，没有在 UP 主真实投稿里命中；真实模式下不进榜单"
                    >
                      未在线核验
                    </span>
                  ) : null}
                  {view.admitted ? null : (
                    <span className="chip bg-gold/20 text-[#B2750A]">未入池，不进榜单</span>
                  )}
                  <Link to={`/meme/${view.id}`} className="link-quiet ml-auto">
                    查看详情页
                  </Link>
                </div>

                <div className="mt-5 flex flex-col gap-5 lg:flex-row">
                  <div className="w-full max-w-[300px] shrink-0">
                    <StickerThumb
                      thumbnail={thumbOf(draft.cover_url || view.auto_cover || view.effective_cover)}
                      ratio="10/7"
                      emojiSize={44}
                      rounded="rounded-xl"
                    />
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="btn-ghost rounded-full text-[12px]"
                        onClick={() => setDraft((value) => ({ ...value, cover_url: "" }))}
                        disabled={!draft.cover_url}
                      >
                        恢复自动封面
                      </button>
                      {view.card ? (
                        <span className="self-center text-[12px] text-ink-faint">
                          当前热度 {view.card.hotness} · {view.card.stage_label}
                        </span>
                      ) : null}
                    </div>
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="mb-2 text-[15px] font-bold">从已采集的视频封面里挑</div>
                    {view.cover_options.length ? (
                      <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-4">
                        {view.cover_options.map((option) => {
                          const active = option.cover === draft.cover_url;
                          return (
                            <button
                              key={option.cover}
                              type="button"
                              title={`${option.title} · ${compact(option.view)}播放`}
                              onClick={() => setDraft((value) => ({ ...value, cover_url: option.cover }))}
                              className={[
                                "overflow-hidden rounded-xl border-2 bg-surface text-left transition",
                                active ? "border-brand" : "border-transparent hover:border-line",
                              ].join(" ")}
                            >
                              <img
                                src={option.cover}
                                alt=""
                                loading="lazy"
                                referrerPolicy="no-referrer"
                                className="aspect-[10/7] w-full object-cover"
                              />
                              <span className="block truncate px-1.5 py-1 text-[11px] text-ink-mute">
                                {compact(option.view)}播放
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="rounded-xl bg-rail px-3.5 py-3 text-[13px] leading-relaxed text-ink-mute">
                        这个梗还没有采集到带封面的真实视频，暂时没得挑。
                        可以先粘一个图片地址，或等下一次采集。
                      </p>
                    )}

                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <input
                        value={draft.cover_url}
                        onChange={(event) => setDraft((value) => ({ ...value, cover_url: event.target.value }))}
                        placeholder="或粘贴图片地址：https://…／站内 /thumbs/…"
                        className="field h-10 min-w-[240px] flex-1"
                      />
                      <span className="text-[12px] text-ink-faint">留空 = 自动取播放量最高视频的封面</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="card space-y-5 p-5">
                <div>
                  <div className="mb-2 flex items-baseline gap-2">
                    <span className="text-[15px] font-bold">介绍</span>
                    <span className="text-[12px] text-ink-faint">详情页梗名下方那句话，最长 {MAX_DESC} 字</span>
                  </div>
                  <textarea
                    value={draft.description}
                    maxLength={MAX_DESC + 50}
                    rows={3}
                    onChange={(event) => setDraft((value) => ({ ...value, description: event.target.value }))}
                    placeholder="一句话说清这个梗是什么、怎么玩"
                    className="field resize-y leading-relaxed"
                  />
                  <div className={`mt-1 text-right text-[12px] ${draft.description.length > MAX_DESC ? "text-brand" : "text-ink-faint"}`}>
                    {draft.description.length}/{MAX_DESC}
                  </div>
                </div>

                <TermList
                  label="别名"
                  hint="叫法不同也能搜到它"
                  value={draft.aliases}
                  onChange={(next) => setDraft((value) => ({ ...value, aliases: next }))}
                />
                <TermList
                  label="关键词"
                  hint="参与相关性判定，影响后续采集与视频筛选"
                  value={draft.keywords}
                  onChange={(next) => setDraft((value) => ({ ...value, keywords: next }))}
                />
              </div>

              <div className="card p-5">
                <div className="flex flex-wrap items-baseline gap-2">
                  <h3 className="text-[18px] font-bold">这个梗采信了哪些视频</h3>
                  <span className="text-[12px] text-ink-faint">
                    共 {view.sample_videos.accepted} 条 · 播放合计 {compact(view.sample_videos.views)}
                    ；列表里的每一条都真的进了热度计算
                  </span>
                </div>
                {view.sample_videos.items.length ? (
                  <ul className="mt-3 space-y-2">
                    {view.sample_videos.items.map((video) => (
                      <li key={video.bvid} className="flex items-start gap-3 rounded-xl bg-rail px-3 py-2.5">
                        <span className="min-w-0 flex-1">
                          <a
                            href={video.url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="line-clamp-1 text-[14px] font-semibold hover:text-nav"
                          >
                            {video.title}
                          </a>
                          <span className="mt-0.5 block truncate text-[12px] text-ink-faint">
                            @{video.author} · {compact(video.view)}播放 · 命中词：
                            {video.matched_terms.join("、") || "—"}
                          </span>
                        </span>
                        <span
                          className={`chip shrink-0 ${
                            video.relevance_score >= 0.8 ? "bg-go-soft text-go" : "bg-gold/20 text-[#B2750A]"
                          }`}
                          title="相关性打分：命中梗名最高，短别名/关键词只能算弱证据"
                        >
                          {video.relevance_score.toFixed(2)}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 rounded-xl bg-rail px-3.5 py-3 text-[13px] text-ink-mute">
                    这个梗目前一条采信样本都没有——热度不会计入榜单。多半是梗名/别名太口语，
                    B 站搜回来的都是字面撞车的无关内容；可以在上面改别名或关键词后重采。
                  </p>
                )}
              </div>

              <div className="card flex flex-wrap items-center gap-3 p-4">
                <button type="button" className="btn-primary rounded-full" onClick={save} disabled={!dirty || busy}>
                  {busy ? "保存中…" : dirty ? "保存修改" : "没有改动"}
                </button>
                {dirty ? (
                  <span className="text-[13px] text-ink-mute">
                    待保存：{Object.keys(patch).join("、")}
                  </span>
                ) : (
                  <span className="text-[13px] text-ink-faint">改任意字段后即可保存</span>
                )}
                {flash ? (
                  <span className={`ml-auto text-[13px] ${flash.tone === "ok" ? "text-go" : "text-brand"}`}>
                    {flash.text}
                  </span>
                ) : null}
              </div>

              <p className="text-[12px] leading-relaxed text-ink-faint">{view.note}。</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
