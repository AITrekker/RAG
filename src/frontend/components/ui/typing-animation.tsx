import * as React from "react"
import { motion } from "framer-motion"
import { cn } from "../../lib/utils"

interface TypingAnimationProps {
  text: string
  duration?: number
  className?: string
  onComplete?: () => void
  showCursor?: boolean
  startDelay?: number
}

export const TypingAnimation: React.FC<TypingAnimationProps> = ({
  text,
  duration = 2,
  className,
  onComplete,
  showCursor = true,
  startDelay = 0
}) => {
  const [displayedText, setDisplayedText] = React.useState("")
  const [isComplete, setIsComplete] = React.useState(false)

  React.useEffect(() => {
    const timer = setTimeout(() => {
      const chars = text.split("")
      let index = 0
      
      const typeInterval = setInterval(() => {
        if (index < chars.length) {
          setDisplayedText(prev => prev + chars[index])
          index++
        } else {
          clearInterval(typeInterval)
          setIsComplete(true)
          onComplete?.()
        }
      }, (duration * 1000) / chars.length)

      return () => clearInterval(typeInterval)
    }, startDelay * 1000)

    return () => clearTimeout(timer)
  }, [text, duration, onComplete, startDelay])

  return (
    <span className={cn("inline-block", className)}>
      {displayedText}
      {showCursor && (
        <motion.span
          className="inline-block w-0.5 h-5 bg-current ml-1"
          animate={{ opacity: isComplete ? 0 : [1, 0] }}
          transition={{ 
            duration: 0.8, 
            repeat: isComplete ? 0 : Infinity,
            repeatType: "reverse"
          }}
        />
      )}
    </span>
  )
}

interface StreamingTextProps {
  text: string
  speed?: number
  className?: string
  onComplete?: () => void
}

export const StreamingText: React.FC<StreamingTextProps> = ({
  text,
  speed = 50,
  className,
  onComplete
}) => {
  const [currentIndex, setCurrentIndex] = React.useState(0)

  React.useEffect(() => {
    if (currentIndex < text.length) {
      const timer = setTimeout(() => {
        setCurrentIndex(prev => prev + 1)
      }, speed)
      
      return () => clearTimeout(timer)
    } else {
      onComplete?.()
    }
  }, [currentIndex, text.length, speed, onComplete])

  return (
    <motion.div 
      className={className}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {text.slice(0, currentIndex)}
      {currentIndex < text.length && (
        <motion.span
          className="inline-block w-0.5 h-5 bg-blue-500 ml-1"
          animate={{ opacity: [1, 0] }}
          transition={{ duration: 0.8, repeat: Infinity, repeatType: "reverse" }}
        />
      )}
    </motion.div>
  )
}

// Loading dots animation
export const LoadingDots: React.FC<{ className?: string }> = ({ className }) => {
  return (
    <div className={cn("flex space-x-1", className)}>
      {[0, 1, 2].map((index) => (
        <motion.div
          key={index}
          className="w-2 h-2 bg-blue-500 rounded-full"
          animate={{
            scale: [1, 1.2, 1],
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