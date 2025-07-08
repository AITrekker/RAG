import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Loader2, Zap, FileText, Download, Upload, Search, Brain, CheckCircle } from "lucide-react"
import { cn } from "../../lib/utils"

// Loading Spinner Variants
interface LoadingSpinnerProps {
  size?: "sm" | "default" | "lg" | "xl"
  variant?: "default" | "pulse" | "bounce" | "orbit" | "bars" | "dots"
  color?: "blue" | "green" | "purple" | "orange" | "red"
  className?: string
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = "default",
  variant = "default",
  color = "blue",
  className
}) => {
  const sizeClasses = {
    sm: "w-4 h-4",
    default: "w-6 h-6",
    lg: "w-8 h-8",
    xl: "w-12 h-12"
  }

  const colorClasses = {
    blue: "text-blue-500",
    green: "text-green-500",
    purple: "text-purple-500",
    orange: "text-orange-500",
    red: "text-red-500"
  }

  if (variant === "pulse") {
    return (
      <motion.div
        className={cn(
          "rounded-full border-2 border-current border-t-transparent",
          sizeClasses[size],
          colorClasses[color],
          className
        )}
        animate={{ rotate: 360, scale: [1, 1.1, 1] }}
        transition={{ 
          rotate: { duration: 1, repeat: Infinity, ease: "linear" },
          scale: { duration: 2, repeat: Infinity, ease: "easeInOut" }
        }}
      />
    )
  }

  if (variant === "bounce") {
    return (
      <div className={cn("flex space-x-1", className)}>
        {[0, 1, 2].map((index) => (
          <motion.div
            key={index}
            className={cn(
              "rounded-full bg-current",
              size === "sm" ? "w-1 h-1" : size === "lg" ? "w-3 h-3" : size === "xl" ? "w-4 h-4" : "w-2 h-2",
              colorClasses[color]
            )}
            animate={{
              y: [0, -8, 0],
              opacity: [0.5, 1, 0.5]
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              delay: index * 0.2
            }}
          />
        ))}
      </div>
    )
  }

  if (variant === "orbit") {
    return (
      <div className={cn("relative", sizeClasses[size], className)}>
        <motion.div
          className={cn("absolute inset-0 border-2 border-current/20 rounded-full", colorClasses[color])}
        />
        <motion.div
          className={cn("absolute top-0 left-1/2 w-1 h-1 bg-current rounded-full -translate-x-1/2", colorClasses[color])}
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: `0.125rem ${parseInt(sizeClasses[size].split(' ')[0].slice(2)) * 4 / 2}px` }}
        />
      </div>
    )
  }

  if (variant === "bars") {
    return (
      <div className={cn("flex space-x-1", className)}>
        {[0, 1, 2, 3].map((index) => (
          <motion.div
            key={index}
            className={cn(
              "bg-current",
              size === "sm" ? "w-0.5 h-3" : size === "lg" ? "w-1 h-6" : size === "xl" ? "w-1.5 h-8" : "w-1 h-4",
              colorClasses[color]
            )}
            animate={{
              scaleY: [1, 2, 1],
              opacity: [0.5, 1, 0.5]
            }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              delay: index * 0.1
            }}
          />
        ))}
      </div>
    )
  }

  if (variant === "dots") {
    return (
      <div className={cn("flex space-x-1", className)}>
        {[0, 1, 2].map((index) => (
          <motion.div
            key={index}
            className={cn(
              "rounded-full bg-current",
              size === "sm" ? "w-1 h-1" : size === "lg" ? "w-3 h-3" : size === "xl" ? "w-4 h-4" : "w-2 h-2",
              colorClasses[color]
            )}
            animate={{
              scale: [1, 1.5, 1],
              opacity: [0.5, 1, 0.5]
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              delay: index * 0.2
            }}
          />
        ))}
      </div>
    )
  }

  // Default spinner
  return (
    <Loader2 
      className={cn(
        "animate-spin",
        sizeClasses[size],
        colorClasses[color],
        className
      )} 
    />
  )
}

// Smart Loading Component with Context
interface SmartLoadingProps {
  isLoading: boolean
  loadingText?: string
  loadingIcon?: React.ReactNode
  size?: "sm" | "default" | "lg"
  variant?: "overlay" | "inline" | "replace"
  children: React.ReactNode
  className?: string
  spinnerVariant?: LoadingSpinnerProps["variant"]
}

export const SmartLoading: React.FC<SmartLoadingProps> = ({
  isLoading,
  loadingText = "Loading...",
  loadingIcon,
  size = "default",
  variant = "overlay",
  children,
  className,
  spinnerVariant = "default"
}) => {
  if (variant === "replace") {
    return (
      <AnimatePresence mode="wait">
        {isLoading ? (
          <motion.div
            key="loading"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className={cn("flex items-center justify-center gap-3 py-8", className)}
          >
            {loadingIcon || <LoadingSpinner size={size} variant={spinnerVariant} />}
            <motion.span
              className="text-gray-600 font-medium"
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              {loadingText}
            </motion.span>
          </motion.div>
        ) : (
          <motion.div
            key="content"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    )
  }

  if (variant === "inline") {
    return (
      <div className={cn("relative", className)}>
        <AnimatePresence>
          {isLoading && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex items-center gap-2 mb-4 text-blue-600"
            >
              {loadingIcon || <LoadingSpinner size="sm" variant={spinnerVariant} />}
              <span className="text-sm font-medium">{loadingText}</span>
            </motion.div>
          )}
        </AnimatePresence>
        <motion.div
          animate={{ opacity: isLoading ? 0.6 : 1 }}
          transition={{ duration: 0.2 }}
        >
          {children}
        </motion.div>
      </div>
    )
  }

  // Overlay variant (default)
  return (
    <div className={cn("relative", className)}>
      <motion.div
        animate={{ opacity: isLoading ? 0.3 : 1 }}
        transition={{ duration: 0.2 }}
      >
        {children}
      </motion.div>
      
      <AnimatePresence>
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-white/80 backdrop-blur-sm flex items-center justify-center rounded-lg"
          >
            <motion.div
              className="flex items-center gap-3 bg-white px-6 py-4 rounded-lg shadow-lg border"
              initial={{ scale: 0.8, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.8, y: 20 }}
              transition={{ type: "spring", stiffness: 400, damping: 10 }}
            >
              {loadingIcon || <LoadingSpinner size={size} variant={spinnerVariant} />}
              <span className="text-gray-700 font-medium">{loadingText}</span>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// Progress Bar Component
interface ProgressBarProps {
  progress: number
  size?: "sm" | "default" | "lg"
  variant?: "default" | "gradient" | "striped" | "pulse"
  color?: "blue" | "green" | "purple" | "orange" | "red"
  showLabel?: boolean
  label?: string
  className?: string
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  size = "default",
  variant = "default",
  color = "blue",
  showLabel = false,
  label,
  className
}) => {
  const sizeClasses = {
    sm: "h-1",
    default: "h-2",
    lg: "h-3"
  }

  const colorClasses = {
    blue: "bg-blue-500",
    green: "bg-green-500",
    purple: "bg-purple-500",
    orange: "bg-orange-500",
    red: "bg-red-500"
  }

  const gradientClasses = {
    blue: "bg-gradient-to-r from-blue-400 to-blue-600",
    green: "bg-gradient-to-r from-green-400 to-green-600",
    purple: "bg-gradient-to-r from-purple-400 to-purple-600",
    orange: "bg-gradient-to-r from-orange-400 to-orange-600",
    red: "bg-gradient-to-r from-red-400 to-red-600"
  }

  return (
    <div className={cn("space-y-2", className)}>
      {showLabel && (
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium text-gray-700">
            {label || "Progress"}
          </span>
          <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
        </div>
      )}
      
      <div className={cn(
        "w-full bg-gray-200 rounded-full overflow-hidden",
        sizeClasses[size]
      )}>
        <motion.div
          className={cn(
            "h-full rounded-full relative",
            variant === "gradient" ? gradientClasses[color] : colorClasses[color],
            variant === "striped" && "bg-stripes",
            variant === "pulse" && "animate-pulse"
          )}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          {variant === "striped" && (
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
              animate={{ x: ["-100%", "100%"] }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            />
          )}
        </motion.div>
      </div>
    </div>
  )
}

// Contextual Loading States for RAG
export const RAGLoadingStates = {
  QueryProcessing: () => (
    <SmartLoading
      isLoading={true}
      loadingText="Processing your query..."
      loadingIcon={<Brain className="w-5 h-5 text-blue-500 animate-pulse" />}
      variant="inline"
      spinnerVariant="orbit"
    >
      <div />
    </SmartLoading>
  ),

  DocumentSync: ({ progress }: { progress: number }) => (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Upload className="w-5 h-5 text-green-500" />
        <span className="font-medium">Syncing documents...</span>
      </div>
      <ProgressBar
        progress={progress}
        variant="gradient"
        color="green"
        showLabel
        label="Upload Progress"
      />
    </div>
  ),

  EmbeddingGeneration: () => (
    <div className="flex items-center gap-3 text-purple-600">
      <LoadingSpinner variant="dots" color="purple" />
      <span className="font-medium">Generating embeddings...</span>
    </div>
  ),

  VectorSearch: () => (
    <div className="flex items-center gap-3 text-blue-600">
      <Search className="w-5 h-5 animate-bounce" />
      <span className="font-medium">Searching knowledge base...</span>
    </div>
  ),

  Success: ({ message }: { message: string }) => (
    <motion.div
      className="flex items-center gap-3 text-green-600"
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 400, damping: 10 }}
    >
      <CheckCircle className="w-5 h-5" />
      <span className="font-medium">{message}</span>
    </motion.div>
  )
}

// Skeleton Loading Components
interface SkeletonProps {
  className?: string
  variant?: "text" | "rectangular" | "circular" | "rounded"
  animation?: "pulse" | "wave" | "shimmer"
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className,
  variant = "rectangular",
  animation = "pulse"
}) => {
  const baseClasses = "bg-gray-200"
  
  const variantClasses = {
    text: "h-4 rounded",
    rectangular: "rounded",
    circular: "rounded-full",
    rounded: "rounded-lg"
  }

  const animationClasses = {
    pulse: "animate-pulse",
    wave: "",
    shimmer: "relative overflow-hidden"
  }

  return (
    <div className={cn(
      baseClasses,
      variantClasses[variant],
      animationClasses[animation],
      className
    )}>
      {animation === "shimmer" && (
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-white/60 to-transparent"
          animate={{ x: ["-100%", "100%"] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
        />
      )}
    </div>
  )
}

export const QuerySkeleton: React.FC = () => (
  <div className="space-y-4">
    <Skeleton variant="text" className="w-3/4 h-6" />
    <Skeleton variant="rectangular" className="w-full h-32" />
    <div className="flex gap-2">
      <Skeleton variant="rectangular" className="w-20 h-8" />
      <Skeleton variant="rectangular" className="w-16 h-8" />
    </div>
  </div>
)