import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { subscribeSse, type PreviewExample } from '../../lib/sse'
import {
  postBucketDraftPreview, getBucketDraftPreview,
  type Bucket, type BucketExampleIn,
} from '../../lib/api'

type Choice = 'positive' | 'near_miss' | 'rejected'
type ExampleState = PreviewExample & { initial: Exclude<Choice, 'rejected'>; choice: Choice }

const HINT = "We recommend confirming at least 2 positives + 2 near-misses before saving — but it's not required."


// onSave is owned by Home's useBuckets instance so its bucket list refreshes
// after creation. Calling useBuckets() here would create a separate state
// instance that nobody renders from, leaving the toolbar/filter dropdown
// stale until a page reload.
export function NewBucketModal({ onClose, onSave }: {
  onClose: () => void
  onSave: (body: {
    name: string; description: string
    confirmed_positives: BucketExampleIn[]; confirmed_negatives: BucketExampleIn[]
  }) => Promise<Bucket>
}) {
  const [step, setStep] = useState<'form' | 'pending' | 'review'>('form')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [draftId, setDraftId] = useState<string | null>(null)
  const [examples, setExamples] = useState<ExampleState[]>([])
  const seenIds = examples.map(e => e.thread_id)

  // Idempotent apply: a result for a given draft_id can arrive via SSE OR
  // via the polling fallback (or both, in either order). appliedRef ensures
  // we only push examples + flip step once per draft_id.
  const appliedRef = useRef<Set<string>>(new Set())

  function applyPreview(forDraftId: string,
                        positives: PreviewExample[], nearMisses: PreviewExample[]) {
    if (appliedRef.current.has(forDraftId)) return
    appliedRef.current.add(forDraftId)
    const newOnes: ExampleState[] = [
      ...positives.map(ex => ({ ...ex, initial: 'positive' as const, choice: 'positive' as const })),
      ...nearMisses.map(ex => ({ ...ex, initial: 'near_miss' as const, choice: 'near_miss' as const })),
    ]
    setExamples(prev => [...prev, ...newOnes])
    setStep('review')
  }

  // Fast path: SSE push when the worker publishes.
  useEffect(() => {
    return subscribeSse((e) => {
      if (e.event !== 'bucket_draft_preview' || e.draft_id !== draftId) return
      applyPreview(e.draft_id, e.positives, e.near_misses)
    })
  }, [draftId])

  // Safety net: poll the cache every 5s while pending. SSE-delivery loss
  // (connection blip during the ~40s scoring window, browser tab throttling,
  // redis pubsub having no subscriber at the publish moment) used to make
  // this feature ~50/50; polling decouples correctness from connection life.
  // Stops on success, on draftId change (user clicked "more examples"),
  // or on unmount.
  useEffect(() => {
    if (step !== 'pending' || !draftId) return
    const localId = draftId
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    async function tick() {
      if (cancelled || appliedRef.current.has(localId)) return
      try {
        const r = await getBucketDraftPreview(localId)
        if (cancelled) return
        if (r.status === 'ready') {
          applyPreview(localId, r.positives, r.near_misses)
          return
        }
        if (r.status === 'gone') {
          console.warn('[bucket draft preview] cache expired before result arrived')
          return  // give up; user can click "find examples" again
        }
      } catch (e) {
        console.error('[bucket draft preview] poll failed', e)
      }
      timer = setTimeout(tick, 5000)
    }

    // Start at 5s — let SSE win on the happy path (~40s scoring), and only
    // burn HTTP requests if SSE doesn't deliver.
    timer = setTimeout(tick, 5000)

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [draftId, step])

  async function startPreview() {
    const { draft_id } = await postBucketDraftPreview({ name, description, exclude_thread_ids: seenIds })
    setDraftId(draft_id); setStep('pending')
  }

  async function moreExamples() {
    const { draft_id } = await postBucketDraftPreview({ name, description, exclude_thread_ids: seenIds })
    setDraftId(draft_id); setStep('pending')
  }

  function setChoice(threadId: string, choice: Choice) {
    setExamples(prev => prev.map(ex => ex.thread_id === threadId ? { ...ex, choice } : ex))
  }

  async function save() {
    const positives = examples.filter(e => e.choice === 'positive').map(toExampleIn)
    const negatives = examples.filter(e => e.choice === 'near_miss').map(toExampleIn)
    await onSave({ name, description, confirmed_positives: positives, confirmed_negatives: negatives })
    onClose()
  }

  return (
    <Backdrop onClose={onClose}>
      <div style={modalStyle}>
        <h3 style={{ margin: 0 }}>new bucket</h3>
        {step === 'form' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
            <label style={fieldLabelStyle}>
              <span>name</span>
              <input
                style={inputStyle}
                value={name}
                onChange={e => setName(e.target.value)}
              />
            </label>
            <label style={fieldLabelStyle}>
              <span>what kind of email goes in this bucket?</span>
              <textarea
                style={textareaStyle}
                rows={4}
                value={description}
                onChange={e => setDescription(e.target.value)}
              />
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button disabled={!name || !description} onClick={startPreview}>find examples</button>
              <button onClick={onClose}>cancel</button>
            </div>
          </div>
        )}
        {step === 'pending' && <div style={{ marginTop: 16 }}>Scanning your inbox, one minute ...</div>}
        {step === 'review' && (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 12 }}>{HINT}</div>
            {examples.map(ex => (
              <ExampleRow key={ex.thread_id} ex={ex} onChoice={c => setChoice(ex.thread_id, c)} />
            ))}
            <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
              <button onClick={save}>save</button>
              <button onClick={moreExamples}>more examples</button>
              <button onClick={onClose}>cancel</button>
            </div>
          </div>
        )}
      </div>
    </Backdrop>
  )
}


function ExampleRow({ ex, onChoice }: { ex: ExampleState; onChoice: (c: Choice) => void }) {
  return (
    <div style={{ borderBottom: '1px solid #eee', padding: '12px 0' }}>
      <div style={{ fontSize: 13 }}>
        <strong>{ex.subject}</strong> from <span style={{ color: '#666' }}>{ex.sender}</span>
      </div>
      <blockquote style={{ borderLeft: '3px solid #ccc', margin: '8px 0', padding: '0 8px',
                            color: '#444', fontSize: 13 }}>
        {ex.snippet}
      </blockquote>
      <div style={{ fontSize: 12, color: '#666', fontStyle: 'italic' }}>why: {ex.rationale}</div>
      <div style={{ marginTop: 8, display: 'flex', gap: 12, fontSize: 13 }}>
        {(['positive', 'near_miss', 'rejected'] as Choice[]).map(c => (
          <label key={c} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <input type="radio" name={ex.thread_id} checked={ex.choice === c}
                   onChange={() => onChoice(c)} />
            {c === 'near_miss' ? 'near-miss' : c}
            {ex.initial === c && <span style={{ color: '#999' }}> (suggested)</span>}
          </label>
        ))}
      </div>
    </div>
  )
}


function toExampleIn(ex: ExampleState) {
  return { sender: ex.sender, subject: ex.subject, snippet: ex.snippet, rationale: ex.rationale }
}


const modalStyle: CSSProperties = {
  background: '#fff', padding: 24, borderRadius: 8, maxWidth: 720, width: '90%',
  maxHeight: '80vh', overflowY: 'auto',
}

// Form field label: label text sits above its input on its own line so inputs
// don't get squeezed inline next to the prompt.
const fieldLabelStyle: CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 6, fontSize: 14,
}

const inputStyle: CSSProperties = {
  width: '100%', boxSizing: 'border-box', padding: '6px 8px', fontSize: 14,
  borderRadius: 4, border: '1px solid #ccc',
}

const textareaStyle: CSSProperties = {
  ...inputStyle, fontFamily: 'inherit', resize: 'vertical',
}

function Backdrop({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }}>
      <div onClick={e => e.stopPropagation()}>{children}</div>
    </div>
  )
}
