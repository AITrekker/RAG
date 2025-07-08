import * as React from "react"
import { motion } from "framer-motion"
import { TrendingUp, TrendingDown, BarChart3, Zap, FileText, Clock } from "lucide-react"
import { cn } from "../../lib/utils"

interface StatsCardProps {
  title: string
  value: string | number
  change?: {
    value: number
    type: "increase" | "decrease"
  }
  icon?: React.ReactNode
  color?: "blue" | "green" | "purple" | "orange" | "red"
  trend?: number[]
  onClick?: () => void
  className?: string
}

const colorVariants = {
  blue: "from-blue-500 to-blue-600",
  green: "from-green-500 to-green-600", 
  purple: "from-purple-500 to-purple-600",
  orange: "from-orange-500 to-orange-600",
  red: "from-red-500 to-red-600"
}

export const StatsCard: React.FC<StatsCardProps> = ({
  title,
  value,
  change,
  icon = <BarChart3 size={24} />,
  color = "blue",
  trend,
  onClick,
  className
}) => {
  const [isHovered, setIsHovered] = React.useState(false)

  return (
    <motion.div
      className={cn(
        "relative bg-white rounded-xl shadow-md hover:shadow-xl border border-gray-100 overflow-hidden cursor-pointer group",
        className
      )}
      whileHover={{ y: -2, scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      onClick={onClick}
      transition={{ type: "spring", stiffness: 400, damping: 10 }}
    >
      {/* Gradient background */}
      <div className={cn("absolute inset-0 bg-gradient-to-br opacity-5 group-hover:opacity-10 transition-opacity", colorVariants[color])} />
      
      {/* Content */}
      <div className="relative p-6">
        <div className="flex items-center justify-between mb-4">
          <div className={cn("p-3 rounded-lg bg-gradient-to-br", colorVariants[color])}>
            <motion.div
              className="text-white"
              animate={{ rotate: isHovered ? 360 : 0 }}
              transition={{ duration: 0.6 }}
            >
              {icon}
            </motion.div>
          </div>
          
          {change && (
            <motion.div
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium",
                change.type === "increase" 
                  ? "bg-green-100 text-green-700" 
                  : "bg-red-100 text-red-700"
              )}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              {change.type === "increase" ? (
                <TrendingUp size={12} />
              ) : (
                <TrendingDown size={12} />
              )}
              {Math.abs(change.value)}%
            </motion.div>
          )}
        </div>

        <div className="space-y-2">
          <motion.h3 
            className="text-sm font-medium text-gray-600 uppercase tracking-wide"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            {title}
          </motion.h3>
          
          <motion.div 
            className="text-3xl font-bold text-gray-900"
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 400 }}
          >
            {typeof value === "number" ? value.toLocaleString() : value}
          </motion.div>
        </div>

        {/* Mini trend chart */}
        {trend && (
          <motion.div 
            className="mt-4 h-8 flex items-end gap-1"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            {trend.map((point, index) => (
              <motion.div
                key={index}
                className={cn("bg-gradient-to-t flex-1 rounded-sm", colorVariants[color])}
                style={{ height: `${(point / Math.max(...trend)) * 100}%` }}
                initial={{ height: 0 }}
                animate={{ height: `${(point / Math.max(...trend)) * 100}%` }}
                transition={{ delay: 0.4 + index * 0.05 }}
              />
            ))}
          </motion.div>
        )}
      </div>

      {/* Hover effect border */}
      <motion.div
        className={cn("absolute inset-0 border-2 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity", 
          `border-${color}-500`)}
        initial={{ opacity: 0 }}
        animate={{ opacity: isHovered ? 1 : 0 }}
      />
    </motion.div>
  )
}

// Example dashboard stats
export const RAGDashboardStats: React.FC = () => {
  const stats = [
    {
      title: "Total Queries",
      value: 1247,
      change: { value: 12, type: "increase" as const },
      icon: <Zap size={24} />,
      color: "blue" as const,
      trend: [45, 52, 48, 61, 55, 67, 73, 82, 76, 89, 95, 88]
    },
    {
      title: "Documents Processed",
      value: 342,
      change: { value: 8, type: "increase" as const },
      icon: <FileText size={24} />,
      color: "green" as const,
      trend: [12, 15, 18, 22, 19, 25, 28, 31, 29, 34, 37, 42]
    },
    {
      title: "Avg Response Time",
      value: "1.2s",
      change: { value: 5, type: "decrease" as const },
      icon: <Clock size={24} />,
      color: "purple" as const,
      trend: [2.1, 1.9, 1.7, 1.5, 1.6, 1.4, 1.3, 1.2, 1.1, 1.2, 1.0, 1.2]
    }
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {stats.map((stat, index) => (
        <motion.div
          key={stat.title}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.1 }}
        >
          <StatsCard {...stat} />
        </motion.div>
      ))}
    </div>
  )
}