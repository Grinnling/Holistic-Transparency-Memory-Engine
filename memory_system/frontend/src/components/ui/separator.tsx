import React from 'react'

export const Separator = ({ className = '', orientation = 'horizontal' }: { className?: string; orientation?: 'horizontal' | 'vertical' }) => (
  <div className={`${orientation === 'horizontal' ? 'h-[1px] w-full' : 'h-full w-[1px]'} bg-border ${className}`} />
)