import { useSyncExternalStore } from "react"

const MOBILE_BREAKPOINT = 768

function subscribe(onChange: () => void) {
  const query = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
  query.addEventListener("change", onChange)
  return () => query.removeEventListener("change", onChange)
}

function getSnapshot() {
  return window.innerWidth < MOBILE_BREAKPOINT
}

function getServerSnapshot() {
  return false
}

export function useIsMobile() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
