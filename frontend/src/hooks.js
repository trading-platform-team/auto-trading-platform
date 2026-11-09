import { useEffect, useRef, useState } from 'react'
import { alertsSocketUrl } from './api.js'

// ms마다 fn()을 호출해 결과를 state로 보관
export function usePolling(fn, ms, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    let alive = true
    const load = () =>
      fnRef
        .current()
        .then((d) => alive && (setData(d), setError(null)))
        .catch((e) => alive && setError(e.message))
    load()
    const id = setInterval(load, ms)
    return () => {
      alive = false
      clearInterval(id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, ...deps])

  return { data, error }
}

// 실시간 알림 WebSocket (끊기면 3초 후 재연결)
export function useAlertSocket(onAlert) {
  const [connected, setConnected] = useState(false)
  const cb = useRef(onAlert)
  cb.current = onAlert

  useEffect(() => {
    let ws
    let timer
    let closed = false
    const connect = () => {
      ws = new WebSocket(alertsSocketUrl())
      ws.onopen = () => setConnected(true)
      ws.onmessage = (e) => {
        try {
          cb.current(JSON.parse(e.data))
        } catch {
          /* 잘못된 메시지 무시 */
        }
      }
      ws.onclose = () => {
        setConnected(false)
        if (!closed) timer = setTimeout(connect, 3000)
      }
    }
    connect()
    return () => {
      closed = true
      clearTimeout(timer)
      ws?.close()
    }
  }, [])

  return connected
}
