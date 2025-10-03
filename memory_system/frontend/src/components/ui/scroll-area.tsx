import React from 'react'

export const ScrollArea = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`overflow-y-auto overflow-x-hidden ${className}`} style={{ height: '100%', maxHeight: '100%' }}>
    {children}
  </div>
)