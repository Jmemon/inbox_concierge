import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  type Bucket, type BucketExampleIn,
  getBuckets, createBucket, patchBucket, deleteBucket,
} from '../../lib/api'


export function useBuckets() {
  const [buckets, setBuckets] = useState<Bucket[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try { setBuckets((await getBuckets()).buckets) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const byId = useMemo(() => Object.fromEntries(buckets.map(b => [b.id, b])), [buckets])
  const customBuckets = useMemo(() => buckets.filter(b => !b.is_default), [buckets])

  const create = useCallback(async (body: {
    name: string; description: string;
    confirmed_positives: BucketExampleIn[]; confirmed_negatives: BucketExampleIn[];
  }) => { const b = await createBucket(body); await refresh(); return b }, [refresh])

  const rename = useCallback(async (id: string, name: string) => {
    await patchBucket(id, name); await refresh()
  }, [refresh])

  const softDelete = useCallback(async (id: string) => {
    await deleteBucket(id); await refresh()
  }, [refresh])

  return { buckets, byId, customBuckets, loading, refresh, create, rename, softDelete }
}
