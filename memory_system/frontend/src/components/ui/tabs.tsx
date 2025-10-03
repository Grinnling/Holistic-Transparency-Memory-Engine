import React from 'react'

export const Tabs = ({ children, className = '', defaultValue, value, onValueChange }: any) => {
  const [activeTab, setActiveTab] = React.useState(value || defaultValue)

  React.useEffect(() => {
    if (value !== undefined) {
      setActiveTab(value)
    }
  }, [value])

  return (
    <div className={className}>
      {React.Children.map(children, child => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child, { activeTab, setActiveTab: onValueChange || setActiveTab })
        }
        return child
      })}
    </div>
  )
}

export const TabsList = ({ children, className = '', activeTab, setActiveTab }: any) => (
  <div className={`inline-flex h-10 items-center justify-center rounded-md bg-gray-100 p-1 text-gray-600 ${className}`}>
    {React.Children.map(children, child => {
      if (React.isValidElement(child)) {
        return React.cloneElement(child, { activeTab, setActiveTab })
      }
      return child
    })}
  </div>
)

export const TabsTrigger = ({ children, value, className = '', activeTab, setActiveTab }: any) => (
  <button
    onClick={() => setActiveTab(value)}
    className={`inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium transition-all focus:outline-none disabled:pointer-events-none disabled:opacity-50 ${
      activeTab === value ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
    } ${className}`}
  >
    {children}
  </button>
)

export const TabsContent = ({ children, value, className = '', activeTab }: any) => {
  if (activeTab !== value) return null
  return <div className={className}>{children}</div>
}