import React, { useState } from 'react'

export const Collapsible = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className={className}>
      {React.Children.map(children, child => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as any, { isOpen, setIsOpen })
        }
        return child
      })}
    </div>
  )
}

export const CollapsibleTrigger = ({ children, isOpen, setIsOpen, className = '' }: any) => (
  <button
    onClick={() => setIsOpen(!isOpen)}
    className={`w-full text-left ${className}`}
  >
    {children}
  </button>
)

export const CollapsibleContent = ({ children, isOpen, className = '' }: any) => {
  if (!isOpen) return null
  return <div className={className}>{children}</div>
}