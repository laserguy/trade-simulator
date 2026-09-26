import type { Activity } from '../api'

// The run in progress, at the top of the Decision log (D28). Live only: not kept after the run.

export function LiveRun({ activity }: { activity: Activity | null }) {
  if (!activity?.active) return null
  return (
    <div className="run live">
      <div className="live-head">
        <span className="pill running"><span className="dot" />{activity.label ?? 'Run'} in progress</span>
        <span className="muted small">Updates live · shown only while the run is going</span>
      </div>
      <ol className="timeline">
        {activity.events.map((e, i) => (
          <li key={i}>
            <span className="t muted num">{new Date(e.at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            <span className="actor">{e.actor}</span>
            <span>{e.text}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
