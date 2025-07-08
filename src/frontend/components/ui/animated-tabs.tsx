import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "../../lib/utils"

interface TabItem {
  id: string
  label: string
  icon?: React.ReactNode
  badge?: number | string
  disabled?: boolean
  color?: string
}

interface AnimatedTabsProps {
  tabs: TabItem[]
  activeTab: string
  onTabChange: (tabId: string) => void
  variant?: "default" | "pills" | "underline" | "cards"
  size?: "sm" | "default" | "lg"
  orientation?: "horizontal" | "vertical"
  className?: string
  tabClassName?: string
  contentClassName?: string
  showBackground?: boolean
  staggerDelay?: number
}

const tabVariants = {
  default: {
    base: "relative flex items-center gap-2 px-4 py-2 font-medium text-sm rounded-lg transition-all duration-200",
    active: "bg-white text-gray-900 shadow-md",
    inactive: "text-gray-600 hover:text-gray-900 hover:bg-white/50"
  },
  pills: {
    base: "relative flex items-center gap-2 px-4 py-2 font-medium text-sm rounded-full transition-all duration-200",
    active: "bg-blue-500 text-white shadow-lg shadow-blue-500/25",
    inactive: "text-gray-600 hover:text-blue-600 hover:bg-blue-50"
  },
  underline: {
    base: "relative flex items-center gap-2 px-4 py-2 font-medium text-sm transition-all duration-200 border-b-2 border-transparent",
    active: "text-blue-600 border-blue-500",
    inactive: "text-gray-600 hover:text-gray-900 hover:border-gray-300"
  },
  cards: {
    base: "relative flex items-center gap-2 px-4 py-3 font-medium text-sm rounded-xl transition-all duration-200 border",
    active: "bg-gradient-to-r from-blue-500 to-blue-600 text-white border-blue-500 shadow-lg shadow-blue-500/25",
    inactive: "text-gray-600 hover:text-gray-900 border-gray-200 hover:border-gray-300 hover:bg-gray-50"
  }
}

export const AnimatedTabs: React.FC<AnimatedTabsProps> = ({
  tabs,
  activeTab,
  onTabChange,
  variant = "default",
  size = "default",
  orientation = "horizontal",
  className,
  tabClassName,
  contentClassName,
  showBackground = true,
  staggerDelay = 0.1
}) => {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const [tabDimensions, setTabDimensions] = React.useState<Record<string, { width: number; height: number; x: number; y: number }>>({})

  // Measure tab dimensions for smooth animations
  React.useEffect(() => {
    if (!containerRef.current) return

    const measureTabs = () => {
      const container = containerRef.current
      if (!container) return

      const newDimensions: Record<string, { width: number; height: number; x: number; y: number }> = {}
      
      tabs.forEach((tab) => {
        const tabElement = container.querySelector(`[data-tab-id="${tab.id}"]`) as HTMLElement
        if (tabElement) {
          const rect = tabElement.getBoundingClientRect()
          const containerRect = container.getBoundingClientRect()
          
          newDimensions[tab.id] = {
            width: rect.width,
            height: rect.height,
            x: rect.left - containerRect.left,
            y: rect.top - containerRect.top
          }
        }
      })
      
      setTabDimensions(newDimensions)
    }

    measureTabs()
    
    const resizeObserver = new ResizeObserver(measureTabs)
    resizeObserver.observe(containerRef.current)
    
    return () => resizeObserver.disconnect()
  }, [tabs, activeTab])

  const activeTabDimensions = tabDimensions[activeTab]
  const variants = tabVariants[variant]

  const containerClass = cn(
    "relative",
    orientation === "horizontal" ? "flex space-x-2" : "flex flex-col space-y-2",
    showBackground && variant === "default" && "bg-gray-100 p-2 rounded-xl",
    showBackground && variant === "pills" && "bg-gray-100 p-2 rounded-full",
    className
  )

  return (
    <div ref={containerRef} className={containerClass}>
      {/* Background indicator for active tab */}
      {variant === "underline" && activeTabDimensions && (
        <motion.div
          className="absolute bottom-0 h-0.5 bg-blue-500 rounded-full"
          layoutId="activeIndicator"
          initial={false}
          animate={{
            x: activeTabDimensions.x,
            width: activeTabDimensions.width,
          }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
        />
      )}

      {tabs.map((tab, index) => {
        const isActive = activeTab === tab.id
        const isDisabled = tab.disabled

        return (
          <motion.button
            key={tab.id}
            data-tab-id={tab.id}
            onClick={() => !isDisabled && onTabChange(tab.id)}
            className={cn(
              variants.base,
              isActive ? variants.active : variants.inactive,
              isDisabled && "opacity-50 cursor-not-allowed",
              size === "sm" && "px-3 py-1.5 text-xs",
              size === "lg" && "px-6 py-3 text-base",
              tab.color && !isActive && `hover:text-${tab.color}-600 hover:bg-${tab.color}-50`,
              tab.color && isActive && variant === "pills" && `bg-${tab.color}-500 shadow-${tab.color}-500/25`,
              tab.color && isActive && variant === "cards" && `from-${tab.color}-500 to-${tab.color}-600 border-${tab.color}-500 shadow-${tab.color}-500/25`,
              tabClassName
            )}
            disabled={isDisabled}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * staggerDelay }}
            whileHover={!isDisabled ? { scale: 1.02 } : undefined}
            whileTap={!isDisabled ? { scale: 0.98 } : undefined}
          >
            {/* Active tab background (for variants that need it) */}
            {isActive && (variant === "default" || variant === "pills" || variant === "cards") && (
              <motion.div
                className={cn(
                  "absolute inset-0 rounded-lg",
                  variant === "pills" && "rounded-full",
                  variant === "cards" && "rounded-xl",
                  tab.color ? `bg-${tab.color}-500` : "bg-blue-500",
                  variant === "default" && "bg-white"
                )}
                layoutId={`activeBackground-${variant}`}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}

            {/* Tab content */}
            <motion.div
              className="relative z-10 flex items-center gap-2"
              animate={{
                color: isActive && variant !== "underline" ? 
                  (variant === "default" ? "#1f2937" : "#ffffff") : undefined
              }}
            >
              {/* Icon with animation */}
              {tab.icon && (
                <motion.div
                  animate={{
                    rotate: isActive ? [0, 10, -10, 0] : 0,
                    scale: isActive ? 1.1 : 1
                  }}
                  transition={{ duration: 0.6 }}
                >
                  {tab.icon}
                </motion.div>
              )}

              {/* Label */}
              <span className={cn(
                "transition-all duration-200",
                isActive && "font-semibold"
              )}>
                {tab.label}
              </span>

              {/* Badge */}
              {tab.badge && (
                <motion.span
                  className={cn(
                    "text-xs rounded-full min-w-[18px] h-[18px] flex items-center justify-center",
                    isActive 
                      ? "bg-white/20 text-white" 
                      : "bg-red-500 text-white"
                  )}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 500, delay: 0.2 }}
                >
                  {tab.badge}
                </motion.span>
              )}
            </motion.div>

            {/* Hover effect */}
            <motion.div
              className="absolute inset-0 rounded-lg opacity-0 bg-gradient-to-r from-blue-500/10 to-purple-500/10"
              whileHover={{ opacity: isActive ? 0 : 1 }}
              transition={{ duration: 0.2 }}
            />
          </motion.button>
        )
      })}
    </div>
  )
}

// Content container with page transitions
interface AnimatedTabContentProps {
  activeTab: string
  children: React.ReactNode
  className?: string
  animation?: "slide" | "fade" | "scale" | "flip"
  direction?: "left" | "right" | "up" | "down"
}

export const AnimatedTabContent: React.FC<AnimatedTabContentProps> = ({
  activeTab,
  children,
  className,
  animation = "slide",
  direction = "right"
}) => {
  const getAnimationVariants = () => {
    switch (animation) {
      case "slide":
        const slideDirection = {
          left: { x: -20 },
          right: { x: 20 },
          up: { y: -20 },
          down: { y: 20 }
        }
        return {
          initial: { opacity: 0, ...slideDirection[direction] },
          animate: { opacity: 1, x: 0, y: 0 },
          exit: { opacity: 0, x: direction === "left" ? 20 : direction === "right" ? -20 : 0, y: direction === "up" ? 20 : direction === "down" ? -20 : 0 }
        }
      
      case "fade":
        return {
          initial: { opacity: 0 },
          animate: { opacity: 1 },
          exit: { opacity: 0 }
        }
      
      case "scale":
        return {
          initial: { opacity: 0, scale: 0.9 },
          animate: { opacity: 1, scale: 1 },
          exit: { opacity: 0, scale: 0.9 }
        }
      
      case "flip":
        return {
          initial: { opacity: 0, rotateY: 90 },
          animate: { opacity: 1, rotateY: 0 },
          exit: { opacity: 0, rotateY: -90 }
        }
      
      default:
        return {
          initial: { opacity: 0 },
          animate: { opacity: 1 },
          exit: { opacity: 0 }
        }
    }
  }

  return (
    <div className={cn("relative", className)}>
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          variants={getAnimationVariants()}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={{ duration: 0.3, ease: "easeInOut" }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

// Example usage component
export const RAGTabNavigation: React.FC = () => {
  const [activeTab, setActiveTab] = React.useState("search")

  const tabs: TabItem[] = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: <div className="w-4 h-4 bg-blue-500 rounded"></div>,
      color: "blue"
    },
    {
      id: "search",
      label: "Search",
      icon: <div className="w-4 h-4 bg-green-500 rounded"></div>,
      badge: 3,
      color: "green"
    },
    {
      id: "sync",
      label: "Sync",
      icon: <div className="w-4 h-4 bg-purple-500 rounded"></div>,
      color: "purple"
    },
    {
      id: "audit",
      label: "Audit",
      icon: <div className="w-4 h-4 bg-orange-500 rounded"></div>,
      badge: "New",
      color: "orange"
    }
  ]

  return (
    <div className="space-y-6">
      <AnimatedTabs
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        variant="pills"
        staggerDelay={0.05}
      />
      
      <AnimatedTabContent
        activeTab={activeTab}
        animation="slide"
        direction="right"
        className="bg-white rounded-lg p-6 shadow-md min-h-[200px]"
      >
        <div>Content for {activeTab}</div>
      </AnimatedTabContent>
    </div>
  )
}