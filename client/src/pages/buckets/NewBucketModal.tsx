import { useEffect, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { subscribeSse, type PreviewExample } from '../../lib/sse'
import { useBuckets } from './useBuckets'

type Choice = 'positive' | 'near_miss' | 'rejected'
type ExampleState = PreviewExample & { initial: Exclude<Choice, 'rejected'>; choice: Choice }

const HINT = "We recommend confirming at least 2 positives + 2 near-misses before saving — but it's not required."


export function NewBucketModal({ onClose }: { onClose: () => void }) {
  const { create, previewDraft } = useBuckets()
  const [step, setStep] = useState<'form' | 'pending' | 'review'>('form')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [draftId, setDraftId] = useState<string | null>(null)
  const [examples, setExamples] = useState<ExampleState[]>([])
  const seenIds = examples.map(e => e.thread_id)

  // Subscribe to preview events keyed on draft_id.
  useEffect(() => {
    return subscribeSse((e) => {
      if (e.event !== 'bucket_draft_preview' || e.draft_id !== draftId) return
      const newOnes: ExampleState[] = [
        ...e.positives.map(ex => ({ ...ex, initial: 'positive' as const, choice: 'positive' as const })),
        ...e.near_misses.map(ex => ({ ...ex, initial: 'near_miss' as const, choice: 'near_miss' as const })),
      ]
      setExamples(prev => [...prev, ...newOnes])
      setStep('review')
    })
  }, [draftId])

  async function startPreview() {
    const { draft_id } = await previewDraft({ name, description, exclude_thread_ids: seenIds })
    setDraftId(draft_id); setStep('pending')
  }

  async function moreExamples() {
    const { draft_id } = await previewDraft({ name, description, exclude_thread_ids: seenIds })
    setDraftId(draft_id); setStep('pending')
  }

  function setChoice(threadId: string, choice: Choice) {
    setExamples(prev => prev.map(ex => ex.thread_id === threadId ? { ...ex, choice } : ex))
  }

  async function save() {
    const positives = examples.filter(e => e.choice === 'positive').map(toExampleIn)
    const negatives = examples.filter(e => e.choice === 'near_miss').map(toExampleIn)
    await create({ name, description, confirmed_positives: positives, confirmed_negatives: negatives })
    onClose()
  }

  return (
    <Backdrop onClose={onClose}>
      <div style={modalStyle}>
        <h3 style={{ margin: 0 }}>new bucket</h3>
        {step === 'form' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
            <label>name <input value={name} onChange={e => setName(e.target.value)} /></label>
            <label>what kind of email goes in this bucket?
              <textarea rows={4} value={description} onChange={e => setDescription(e.target.value)} />
            </label>
            <div>
              <button disabled={!name || !description} onClick={startPreview}>find examples</button>
              <button onClick={onClose} style={{ marginLeft: 8 }}>cancel</button>
            </div>
          </div>
        )}
        {step === 'pending' && <div style={{ marginTop: 16 }}>scanning your inbox… (~30-60s)</div>}
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
