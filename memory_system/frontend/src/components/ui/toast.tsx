import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from "lucide-react"

const toastVariants = cva(
  "pointer-events-auto relative flex w-full items-center justify-between space-x-4 overflow-hidden rounded-md border p-4 pr-8 shadow-lg transition-all",
  {
    variants: {
      variant: {
        success: "bg-gray-800 border-gray-600 text-gray-100",
        error: "bg-red-900/90 border-red-700 text-red-100",
        warning: "bg-yellow-900/90 border-yellow-700 text-yellow-100",
        info: "bg-blue-900/90 border-blue-700 text-blue-100",
      },
    },
    defaultVariants: {
      variant: "info",
    },
  }
)

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const iconColorMap = {
  success: "text-gray-400",
  error: "text-red-400",
  warning: "text-yellow-400",
  info: "text-blue-400",
}

export interface ToastProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof toastVariants> {
  id: string
  message: string
  onDismiss?: (id: string) => void
  action?: {
    label: string
    onClick: () => void
  }
}

const Toast = React.forwardRef<HTMLDivElement, ToastProps>(
  ({ className, variant = "info", id, message, onDismiss, action, ...props }, ref) => {
    const Icon = iconMap[variant || "info"]
    const iconColor = iconColorMap[variant || "info"]

    return (
      <div
        ref={ref}
        className={cn(toastVariants({ variant }), className)}
        {...props}
      >
        <div className="flex items-center gap-3">
          <Icon className={cn("h-5 w-5 flex-shrink-0", iconColor)} />
          <p className="text-sm font-medium">{message}</p>
        </div>

        <div className="flex items-center gap-2">
          {action && (
            <button
              onClick={action.onClick}
              className="text-xs font-medium underline underline-offset-2 hover:opacity-80"
            >
              {action.label}
            </button>
          )}
        </div>

        {onDismiss && (
          <button
            onClick={() => onDismiss(id)}
            className="absolute right-2 top-2 rounded-md p-1 opacity-70 hover:opacity-100 transition-opacity"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    )
  }
)
Toast.displayName = "Toast"

export interface ToastContainerProps {
  toasts: Array<{
    id: string
    type: "success" | "error" | "warning" | "info"
    message: string
    action?: {
      label: string
      onClick: () => void
    }
  }>
  onDismiss: (id: string) => void
}

const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onDismiss }) => {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]">
      {toasts.slice(0, 3).map((toast) => (
        <Toast
          key={toast.id}
          id={toast.id}
          variant={toast.type}
          message={toast.message}
          action={toast.action}
          onDismiss={onDismiss}
          className="animate-slide-in"
        />
      ))}
    </div>
  )
}

export { Toast, ToastContainer, toastVariants }
