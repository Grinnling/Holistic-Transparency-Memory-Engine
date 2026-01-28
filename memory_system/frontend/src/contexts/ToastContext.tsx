import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { ToastContainer } from '../components/ui/toast'

// Toast types
export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastAction {
  label: string
  onClick: () => void
}

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number
  action?: ToastAction
}

export interface ToastHistoryEntry extends Toast {
  timestamp: Date
  dismissed: boolean
}

export interface ToastOptions {
  type?: ToastType
  duration?: number
  action?: ToastAction
}

// Context interface
interface ToastContextValue {
  toasts: Toast[]
  addToast: (message: string, options?: ToastOptions) => string
  removeToast: (id: string) => void
  // Convenience methods
  success: (message: string, options?: Omit<ToastOptions, 'type'>) => string
  error: (message: string, options?: Omit<ToastOptions, 'type'>) => string
  warning: (message: string, options?: Omit<ToastOptions, 'type'>) => string
  info: (message: string, options?: Omit<ToastOptions, 'type'>) => string
  // History for reviewing past toasts
  history: ToastHistoryEntry[]
  clearHistory: () => void
}

// Default durations by type (ms)
const DEFAULT_DURATIONS: Record<ToastType, number> = {
  success: 3000,
  error: 5000,
  warning: 4000,
  info: 3000,
}

// Create context
const ToastContext = createContext<ToastContextValue | undefined>(undefined)

// Generate unique ID
let toastId = 0
const generateId = () => `toast-${++toastId}-${Date.now()}`

// Max history entries to keep
const MAX_HISTORY = 50

// Provider component
export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [history, setHistory] = useState<ToastHistoryEntry[]>([])

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    // Mark as dismissed in history
    setHistory((prev) => prev.map((h) =>
      h.id === id ? { ...h, dismissed: true } : h
    ))
  }, [])

  const clearHistory = useCallback(() => {
    setHistory([])
  }, [])

  const addToast = useCallback((message: string, options: ToastOptions = {}): string => {
    const id = generateId()
    const type = options.type || 'info'
    const duration = options.duration ?? DEFAULT_DURATIONS[type]

    const newToast: Toast = {
      id,
      type,
      message,
      duration,
      action: options.action,
    }

    setToasts((prev) => [...prev, newToast])

    // Add to history
    const historyEntry: ToastHistoryEntry = {
      ...newToast,
      timestamp: new Date(),
      dismissed: false,
    }
    setHistory((prev) => {
      const updated = [...prev, historyEntry]
      // Keep only the last MAX_HISTORY entries
      return updated.slice(-MAX_HISTORY)
    })

    // Auto-dismiss if duration is set (0 = persistent)
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, duration)
    }

    return id
  }, [removeToast])

  // Convenience methods
  const success = useCallback((message: string, options?: Omit<ToastOptions, 'type'>) => {
    return addToast(message, { ...options, type: 'success' })
  }, [addToast])

  const error = useCallback((message: string, options?: Omit<ToastOptions, 'type'>) => {
    return addToast(message, { ...options, type: 'error' })
  }, [addToast])

  const warning = useCallback((message: string, options?: Omit<ToastOptions, 'type'>) => {
    return addToast(message, { ...options, type: 'warning' })
  }, [addToast])

  const info = useCallback((message: string, options?: Omit<ToastOptions, 'type'>) => {
    return addToast(message, { ...options, type: 'info' })
  }, [addToast])

  const value: ToastContextValue = {
    toasts,
    addToast,
    removeToast,
    success,
    error,
    warning,
    info,
    history,
    clearHistory,
  }

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </ToastContext.Provider>
  )
}

// Hook to use toast
export const useToast = (): ToastContextValue => {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}

export default ToastContext
