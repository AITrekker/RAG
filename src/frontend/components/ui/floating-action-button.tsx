import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Plus, MessageSquare, Upload, Settings, X } from "lucide-react"
import { cn } from "../../lib/utils"

interface FloatingAction {
  id: string
  label: string
  icon: React.ReactNode
  onClick: () => void
  color?: string
}

interface FloatingActionButtonProps {
  actions: FloatingAction[]
  className?: string
}

export const FloatingActionButton: React.FC<FloatingActionButtonProps> = ({ 
  actions, 
  className 
}) => {
  const [isOpen, setIsOpen] = React.useState(false)

  const toggleMenu = () => setIsOpen(!isOpen)

  return (
    <div className={cn("fixed bottom-6 right-6 z-50", className)}>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            className="flex flex-col-reverse gap-3 mb-3"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            {actions.map((action, index) => (
              <motion.button
                key={action.id}
                onClick={action.onClick}
                className={cn(
                  "flex items-center gap-3 bg-white text-gray-700 px-4 py-3 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 group",
                  action.color || "hover:bg-blue-50"
                )}
                initial={{ 
                  scale: 0,
                  x: 20,
                  opacity: 0 
                }}
                animate={{ 
                  scale: 1,
                  x: 0,
                  opacity: 1 
                }}
                exit={{ 
                  scale: 0,
                  x: 20,
                  opacity: 0 
                }}
                transition={{ 
                  delay: index * 0.1,
                  type: "spring",
                  stiffness: 400,
                  damping: 10
                }}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <span className="text-sm font-medium whitespace-nowrap">
                  {action.label}
                </span>
                <div className="w-10 h-10 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 flex items-center justify-center text-white shadow-md group-hover:shadow-lg transition-shadow">
                  {action.icon}
                </div>
              </motion.button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main FAB */}
      <motion.button
        onClick={toggleMenu}
        className="w-14 h-14 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-full shadow-xl hover:shadow-2xl flex items-center justify-center"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        animate={{ rotate: isOpen ? 45 : 0 }}
        transition={{ type: "spring", stiffness: 400, damping: 10 }}
      >
        <AnimatePresence mode="wait">
          {isOpen ? (
            <motion.div
              key="close"
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <X size={24} />
            </motion.div>
          ) : (
            <motion.div
              key="plus"
              initial={{ rotate: 90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: -90, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <Plus size={24} />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  )
}

// Example usage component
export const RAGFloatingActions: React.FC = () => {
  const actions: FloatingAction[] = [
    {
      id: "query",
      label: "New Query",
      icon: <MessageSquare size={20} />,
      onClick: () => console.log("New query"),
    },
    {
      id: "upload",
      label: "Upload Document",
      icon: <Upload size={20} />,
      onClick: () => console.log("Upload document"),
    },
    {
      id: "settings",
      label: "Settings",
      icon: <Settings size={20} />,
      onClick: () => console.log("Settings"),
    },
  ]

  return <FloatingActionButton actions={actions} />
}