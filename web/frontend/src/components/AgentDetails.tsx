import type { ModelProfile } from "../api";
import { tokenLabel } from "../modelChoices";

const support = (value?: boolean | null) => value === true ? "Yes" : value === false ? "No" : "Unknown";
const dollars = (value?: number | null) => value == null ? "Unknown" : `$${value.toLocaleString("en-US", { maximumFractionDigits: 4 })}`;

export default function AgentDetails({ profile, browser = false }: { profile?: ModelProfile; browser?: boolean }) {
  const contexts = profile?.context_budgets?.length ? profile.context_budgets.map(tokenLabel).join(" / ") : "Unknown";
  const effort = profile?.efforts.length ? profile.efforts.join(" · ") : "Levels unknown";
  return <div className="agent-details">
    <dl className="agent-facts">
      <div><dt>Context</dt><dd>{contexts}</dd></div>
      <div><dt>Reasoning</dt><dd title={effort}>{support(profile?.reasoning)}</dd></div>
      <div><dt>Image input</dt><dd>{support(profile?.vision)}</dd></div>
      <div><dt>Tools</dt><dd>{support(profile?.tools)}</dd></div>
      <div><dt>Max output</dt><dd>{profile?.max_output_tokens ? tokenLabel(profile.max_output_tokens) : "Unknown"}</dd></div>
    </dl>
    <div className="small muted">Reasoning levels: {profile?.efforts.length ? effort : "Unknown"}
      {profile?.default_effort && <> · Default: <strong>{profile.default_effort}</strong></>}
    </div>
    <div className="small muted agent-pricing" title={profile?.pricing?.note}>
      {browser ? "API reference price" : "API price"} / 1M tokens: <strong>{dollars(profile?.pricing?.input)}</strong> input · <strong>{dollars(profile?.pricing?.output)}</strong> output
    </div>
    {browser && <small className="muted">Browser login uses your subscription’s access and limits; API prices do not describe its charges.</small>}
    {profile?.source_label && <small className="muted agent-source">
      {profile.source_url ? <a href={profile.source_url} target="_blank" rel="noreferrer">{profile.source_label}</a> : profile.source_label}
      {profile.verified_at && <> · {profile.lookup_status === "live" ? "Refreshed" : "Published details checked"} {new Date(profile.verified_at).toLocaleDateString()}</>}
      {profile.pricing && !browser && <> · Starting rates; actual charges vary.</>}
    </small>}
    {profile?.lookup_status === "unavailable" && <small className="muted">Live details unavailable. Showing published details where known.</small>}
  </div>;
}
