import React from 'react'

export const Progress = ({ value, max = 100, className = '' }: { value: number; max?: number; className?: string }) => {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100))

  return (
    <div className={`relative h-4 w-full overflow-hidden rounded-full bg-secondary ${className}`}>
      <div
        className="h-full bg-primary transition-all"
        style={{ width: `${percentage}%` }}
      />
    </div>
  )
}