import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { Loader2, CheckCircle, AlertCircle } from "lucide-react"
import { cn } from "../../lib/utils"

const animatedButtonVariants = cva(
  "relative inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 overflow-hidden",
  {
    variants: {
      variant: {
        default: "bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:from-blue-600 hover:to-blue-700 shadow-lg hover:shadow-xl hover:shadow-blue-500/25",
        destructive: "bg-gradient-to-r from-red-500 to-red-600 text-white hover:from-red-600 hover:to-red-700 shadow-lg hover:shadow-xl hover:shadow-red-500/25",
        outline: "border-2 border-blue-500 bg-transparent text-blue-500 hover:bg-blue-50 hover:border-blue-600 hover:shadow-lg hover:shadow-blue-500/10",
        ghost: "hover:bg-blue-50 hover:text-blue-600 transition-all duration-200",
        success: "bg-gradient-to-r from-green-500 to-green-600 text-white hover:from-green-600 hover:to-green-700 shadow-lg hover:shadow-xl hover:shadow-green-500/25",
        warning: "bg-gradient-to-r from-orange-500 to-orange-600 text-white hover:from-orange-600 hover:to-orange-700 shadow-lg hover:shadow-xl hover:shadow-orange-500/25",
        pulse: "bg-gradient-to-r from-purple-500 to-pink-500 text-white animate-pulse shadow-lg",
        glow: "bg-gradient-to-r from-cyan-500 to-blue-500 text-white shadow-cyan-500/50 hover:shadow-cyan-500/75 shadow-lg hover:shadow-xl transition-all duration-300",
        premium: "bg-gradient-to-r from-purple-600 via-purple-700 to-indigo-600 text-white hover:from-purple-700 hover:via-purple-800 hover:to-indigo-700 shadow-lg hover:shadow-xl hover:shadow-purple-500/25",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3 text-xs",
        lg: "h-12 rounded-lg px-8 text-base",
        xl: "h-14 rounded-xl px-10 text-lg",
        icon: "h-10 w-10",
        "icon-sm": "h-8 w-8",
        "icon-lg": "h-12 w-12",
      },
      animation: {
        none: "",
        bounce: "",
        slide: "",
        rotate: "",
        wiggle: "",
        shake: "",
        pulse: "",
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default",
      animation: "bounce",
    },
  }
)

type ButtonState = "idle" | "loading" | "success" | "error"

export interface AnimatedButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof animatedButtonVariants> {
  asChild?: boolean
  loading?: boolean
  state?: ButtonState
  icon?: React.ReactNode
  rightIcon?: React.ReactNode
  badge?: string | number
  ripple?: boolean
  shimmer?: boolean
  successMessage?: string
  errorMessage?: string
}

const AnimatedButton = React.forwardRef<HTMLButtonElement, AnimatedButtonProps>(
  ({ 
    className, 
    variant, 
    size, 
    animation, 
    asChild = false, 
    loading = false,
    state = "idle",
    icon, 
    rightIcon,
    badge, 
    ripple = true,
    shimmer = false,
    successMessage,
    errorMessage,
    children, 
    onClick,
    disabled,
    ...props 
  }, ref) => {
    const [buttonState] = React.useState<ButtonState>(state)
    const [ripples, setRipples] = React.useState<Array<{ id: number; x: number; y: number }>>([])
    const [showMessage] = React.useState(false)
    
    const Comp = asChild ? Slot : "button"
    
    // Handle click with ripple effect
    const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
      if (disabled || loading) return
      
      // Create ripple effect
      if (ripple) {
        const rect = event.currentTarget.getBoundingClientRect()
        const x = event.clientX - rect.left
        const y = event.clientY - rect.top
        const newRipple = { id: Date.now(), x, y }
        setRipples(prev => [...prev, newRipple])
        
        // Remove ripple after animation
        setTimeout(() => {
          setRipples(prev => prev.filter(r => r.id !== newRipple.id))
        }, 600)
      }
      
      onClick?.(event)
    }
    
    // Animation variants based on animation prop
    const getAnimationVariants = () => {
      switch (animation) {
        case "bounce":
          return {
            hover: { scale: 1.05 },
            tap: { scale: 0.95 }
          }
        case "slide":
          return {
            hover: { y: -2 },
            tap: { y: 0 }
          }
        case "rotate":
          return {
            hover: { rotate: 3 },
            tap: { rotate: 0 }
          }
        case "wiggle":
          return {
            hover: { rotate: [0, -3, 3, -3, 0] },
            tap: { scale: 0.95 }
          }
        case "shake":
          return {
            hover: { x: [0, -2, 2, -2, 0] },
            tap: { scale: 0.95 }
          }
        case "pulse":
          return {
            hover: { scale: [1, 1.05, 1] },
            tap: { scale: 0.95 }
          }
        default:
          return {}
      }
    }
    
    // Get appropriate icon based on state
    const getStateIcon = () => {
      if (loading || buttonState === "loading") {
        return <Loader2 className="w-4 h-4 animate-spin" />
      }
      if (buttonState === "success") {
        return <CheckCircle className="w-4 h-4" />
      }
      if (buttonState === "error") {
        return <AlertCircle className="w-4 h-4" />
      }
      return icon
    }
    
    // Get current variant based on state
    const getCurrentVariant = () => {
      if (buttonState === "success") return "success"
      if (buttonState === "error") return "destructive"
      return variant
    }
    
    const isLoading = loading || buttonState === "loading"
    const isDisabled = disabled || isLoading
    
    return (
      <motion.div className="relative inline-block">
        <motion.button
          className={cn(animatedButtonVariants({ 
            variant: getCurrentVariant(), 
            size, 
            animation, 
            className 
          }))}
          ref={ref}
          disabled={isDisabled}
          onClick={handleClick}
          variants={getAnimationVariants()}
          whileHover={!isDisabled ? "hover" : undefined}
          whileTap={!isDisabled ? "tap" : undefined}
          transition={{ type: "spring", stiffness: 400, damping: 10 }}
          {...props}
        >
          {/* Shimmer effect */}
          {shimmer && (
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
              animate={{ x: ["-100%", "100%"] }}
              transition={{ 
                repeat: Infinity, 
                duration: 2, 
                ease: "linear",
                repeatDelay: 3 
              }}
            />
          )}
          
          {/* Ripple effects */}
          <AnimatePresence>
            {ripples.map((ripple) => (
              <motion.span
                key={ripple.id}
                className="absolute bg-white/30 rounded-full pointer-events-none"
                style={{
                  left: ripple.x - 10,
                  top: ripple.y - 10,
                }}
                initial={{ width: 0, height: 0, opacity: 0.5 }}
                animate={{ 
                  width: 200, 
                  height: 200, 
                  opacity: 0,
                  left: ripple.x - 100,
                  top: ripple.y - 100,
                }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.6, ease: "easeOut" }}
              />
            ))}
          </AnimatePresence>
          
          {/* Button content */}
          <motion.div
            className="flex items-center justify-center gap-2 relative z-10"
            animate={isLoading ? { opacity: 0.7 } : { opacity: 1 }}
          >
            <AnimatePresence mode="wait">
              {getStateIcon() && (
                <motion.div
                  key={buttonState}
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  {getStateIcon()}
                </motion.div>
              )}
            </AnimatePresence>
            
            {children && (
              <motion.span
                animate={isLoading ? { opacity: 0.7 } : { opacity: 1 }}
              >
                {children}
              </motion.span>
            )}
            
            {rightIcon && !isLoading && (
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.1 }}
              >
                {rightIcon}
              </motion.div>
            )}
          </motion.div>
          
          {/* Badge */}
          {badge && (
            <motion.span
              className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full min-w-[20px] h-5 flex items-center justify-center z-20"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 500, delay: 0.2 }}
            >
              {badge}
            </motion.span>
          )}
        </motion.button>
        
        {/* Success/Error Messages */}
        <AnimatePresence>
          {showMessage && (buttonState === "success" || buttonState === "error") && (
            <motion.div
              className={cn(
                "absolute top-full left-1/2 transform -translate-x-1/2 mt-2 px-3 py-1 rounded-md text-xs font-medium whitespace-nowrap z-30",
                buttonState === "success" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
              )}
              initial={{ opacity: 0, y: -10, scale: 0.8 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.8 }}
              transition={{ type: "spring", stiffness: 400, damping: 10 }}
            >
              {buttonState === "success" ? successMessage : errorMessage}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    )
  }
)

AnimatedButton.displayName = "AnimatedButton"

export { AnimatedButton, animatedButtonVariants }